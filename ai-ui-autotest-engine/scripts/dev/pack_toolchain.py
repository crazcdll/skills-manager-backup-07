#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新下载并打包 `references/toolchain/` 的内置 adb 离线包 + 清单。

开发期工具，运行期只消费已随包分发的 zip（不会联网）。

用法：
  python3 -B scripts/dev/pack_toolchain.py                    # 按清单现有版本重下
  python3 -B scripts/dev/pack_toolchain.py --version 37.0.1

产出：
  references/toolchain/platform-tools-<plat>-<ver>.zip
  references/toolchain/manifest.json（version / members / 各平台 bundle+size）
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEST = os.path.join(SKILL_DIR, "references", "toolchain")
MANIFEST = os.path.join(DEST, "manifest.json")
BASE = "https://dl.google.com/android/repository/platform-tools_r{ver}-{plat}.zip"
# 解压白名单（相对压缩包内 platform-tools/ 的路径；以 / 结尾表示目录）
MEMBERS = ["adb", "lib64/", "NOTICE.txt"]


def fetch(url, dest):
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        return
    except Exception as e:  # noqa: BLE001 —— 回退到 curl（企业代理下更稳）
        sys.stderr.write(f"[pack] urllib 失败（{e}），改用 curl\n")
    if subprocess.run(["curl", "-fsSL", "-o", dest, url]).returncode != 0:
        raise SystemExit(f"[pack] 下载失败: {url}")


def main():
    ap = argparse.ArgumentParser(description="重新打包内置 adb 离线包")
    ap.add_argument("--version", default=None, help="platform-tools 版本，默认沿用清单")
    args = ap.parse_args()

    version = args.version
    if not version:
        if not os.path.isfile(MANIFEST):
            raise SystemExit("[pack] 清单不存在，请显式传 --version")
        with open(MANIFEST, encoding="utf-8") as f:
            version = json.load(f).get("version")
    if not version:
        raise SystemExit("[pack] 无法确定版本，请显式传 --version")

    os.makedirs(DEST, exist_ok=True)
    platforms = {}
    for plat in ("darwin", "linux"):
        name = f"platform-tools-{plat}-{version}.zip"
        path = os.path.join(DEST, name)
        print(f"[pack] 下载 {plat} {version} …")
        fetch(BASE.format(ver=version, plat=plat), path)
        platforms[plat] = {"bundle": name, "size": os.path.getsize(path)}
        print(f"[pack] {name}  {platforms[plat]['size']}B")

    manifest = {"version": version, "members": MEMBERS, "platforms": platforms}
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[pack] 清单已更新: {MANIFEST}")


if __name__ == "__main__":
    main()
