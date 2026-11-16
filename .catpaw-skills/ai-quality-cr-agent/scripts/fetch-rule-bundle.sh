#!/usr/bin/env bash
# fetch-rule-bundle.sh — 基于 repo locator 拉取平台「当前有效规则包」(L1 公司规范 + L2 团队规范)到指定目录
#
# 依赖: mt-code-standards-setup skill(软依赖,未安装退出码 3)
# 原理: 传 --repository 后 Runner 在空目录即可拉取,无需 clone。原地跑:成功后把 team/(L2)
#       原地提出、清掉 Runner 内部痕迹,全程只有一个目录、零跨目录拷贝。
#
# 用法:
#   fetch-rule-bundle.sh --repo <org/repo> [--domain backend|frontend] [--out <dir>] [--timeout <秒>] [--l2-only]
#
# --l2-only: 只交付 L2 团队规范(team/),丢弃 L1 公司规范。
#            注意:Runner 内部仍会拉全量(resolve 一次调用 L1+L2 都返回),丢弃发生在落盘层;
#            l1_bootstrap 模式(未订阅)本来就无 L2 → 输出空 team/,manifest 如实记录。
#
# 输出(稳定接口,后置链路只认这里):
#   {out}/team/<规则集ID>/*.md    L2 团队规范(已订阅时;未订阅为空目录)
#   {out}/company/*.md            L1 公司规范(--l2-only 时不输出)
#   {out}/manifest.json           拉取清单(repo/mode/文件数/时间)
#
# 退出码:
#   0  成功(resolve 拿到 L1+L2,或 l1_bootstrap 仅 L1——未订阅属正常)
#   2  参数错误
#   3  mt-code-standards-setup 未安装(调用方应跳过,不报错)
#   4  Runner 失败/超时(调用方回退仓库内已有规则,不阻塞)
#   5  DOMAIN_CONFIRMATION_REQUIRED(仓库无代码特征且未传 --domain;传 domain 重试即可)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="$SCRIPT_DIR/../../mt-code-standards-setup/scripts/sync-effective-rules-with-sso.mjs"

REPO=""; DOMAIN=""; OUT=""; TIMEOUT=90; L2ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)    REPO="$2";    shift 2;;
    --domain)  DOMAIN="$2";  shift 2;;
    --out)     OUT="$2";     shift 2;;
    --timeout) TIMEOUT="$2"; shift 2;;
    --l2-only) L2ONLY=1;     shift;;
    *) echo "fetch-rule-bundle: 未知参数 $1" >&2; exit 2;;
  esac
done
[ -z "$REPO" ] && { echo "fetch-rule-bundle: 必须传 --repo <org/repo>" >&2; exit 2; }
[ -z "$OUT" ]  && OUT="/tmp/cr_rule_bundle_$(echo "$REPO" | tr '/' '_')"
[ -f "$RUNNER" ] || { echo "SKIP: mt-code-standards-setup 未安装($RUNNER 不存在)" >&2; exit 3; }

# 清理 Runner 内部痕迹(.mdp/日志),失败路径也调用,保证 $OUT 只留稳定接口产物
clean_internal() { rm -rf "$OUT/.mdp" "$OUT/.runner.log"; }

# 原地准备:幂等重跑
rm -rf "$OUT/team" "$OUT/company" "$OUT/manifest.json"
mkdir -p "$OUT"

DOMAIN_ARGS=()
[ -n "$DOMAIN" ] && DOMAIN_ARGS=(--domain "$DOMAIN")

timeout "$TIMEOUT" node "$RUNNER" --repo-root "$OUT" --repository "$REPO" \
  --stage cr --execution-agent sandbox ${DOMAIN_ARGS[@]+"${DOMAIN_ARGS[@]}"} \
  >"$OUT/.runner.log" 2>&1
RC=$?

if grep -q "RULE_BUNDLE_DOMAIN_CONFIRMATION_REQUIRED" "$OUT/.runner.log" 2>/dev/null; then
  clean_internal
  echo "fetch-rule-bundle: 仓库无法自动判定 domain,请显式传 --domain backend|frontend 后重试" >&2
  exit 5
fi
if [ $RC -ne 0 ]; then
  echo "fetch-rule-bundle: Runner 失败(rc=$RC),详见下方日志" >&2
  tail -5 "$OUT/.runner.log" >&2
  clean_internal
  exit 4
fi

# 判定模式(resolve=已登记+订阅; l1_bootstrap=未登记仅L1)
if grep -q "mt-effective-rule-bundle-install/v1" "$OUT/.runner.log"; then
  MODE="resolve"
elif grep -q "mt-l1-bootstrap-install/v1" "$OUT/.runner.log"; then
  MODE="l1_bootstrap"
else
  echo "fetch-rule-bundle: Runner 成功但未识别到收据 schema" >&2
  clean_internal
  exit 4
fi

# 原地收割:team/(L2)必留;company/(L1)仅非 l2-only 时保留;其余 Runner 痕迹全清
if [ -d "$OUT/.mdp/rules/team" ]; then
  mv "$OUT/.mdp/rules/team" "$OUT/team"
else
  mkdir -p "$OUT/team"
fi
if [ "$L2ONLY" -eq 0 ] && [ -d "$OUT/.mdp/rules/company" ]; then
  mv "$OUT/.mdp/rules/company" "$OUT/company"
fi
clean_internal

L1_N=$(ls "$OUT/company" 2>/dev/null | wc -l | tr -d ' ')
L2_N=$(ls "$OUT/team" 2>/dev/null | wc -l | tr -d ' ')

EXTRA_FIELD=""
[ "$L2ONLY" -eq 1 ] && EXTRA_FIELD=",
  \"l2_only\": true"

cat > "$OUT/manifest.json" <<EOF
{
  "repo": "$REPO",
  "mode": "$MODE",
  "l1_files": $L1_N,
  "l2_rule_sets": $L2_N,
  "domain": "${DOMAIN:-auto}",
  "pulled_at": "$(date '+%Y-%m-%dT%H:%M:%S%z')"$EXTRA_FIELD
}
EOF

echo "✅ fetch-rule-bundle: $REPO → $OUT (mode=$MODE, L1=${L1_N}文件, L2=${L2_N}规则集${L2ONLY:+ [l2-only]})"
exit 0
