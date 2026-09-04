#!/usr/bin/env python3
"""
同步完成后发送大象消息，提醒相关研发同学补充 AI-Coding 数据。

发送路径：catdesk daxiang send（通过内置浏览器以用户身份发送，非机器人）。

消息格式（单条消息）：
  第一行：学城文档链接（--link-title 渲染为带标题的链接卡片）
  第二行：提醒文案，末尾用大象原生 @mention 语法 @ 本周研发同学

大象原生 @mention 语法：
  [@姓名|mtdaxiang://www.meituan.com/profile?uid=<数字uid>&isAt=true]

关键安全约束：
  1. 发送前必须成功解析所有研发同学的 MIS -> 大象数字 UID；
  2. UID 查询失败会重试，重试后仍失败则整个消息不发送；
  3. 禁止降级为纯文本 @姓名，避免产生“看起来提醒了、实际上没有 @ 到人”的消息；
  4. --dry-run 仅展示最终消息和预检结果，绝不发送到群。

用法：
  python3 send_notification.py \
    --requirement-md /tmp/requirement.md \
    --doc-title "2026-09-03-AICoding需求开发统计" \
    --doc-url "https://km.sankuai.com/collabpage/2784206118" \
    --group-id 69695119485
"""

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass


DEFAULT_GROUP_ID = "69695119485"
DEFAULT_RETRIES = 3
MENTION_TEMPLATE = "[@{name}|mtdaxiang://www.meituan.com/profile?uid={uid}&isAt=true]"
REMINDER_TEXT = "更新下 ai coding 情况，AI成熟度分析、开发状态 一定要写，"


@dataclass(frozen=True)
class Assignee:
    """需求列表中解析出的研发同学。"""

    name: str
    mis: str


@dataclass(frozen=True)
class ResolvedMention:
    """已完成 MIS->数字 UID 预检、可安全发送的大象 @mention。"""

    name: str
    mis: str
    uid: str

    def render(self) -> str:
        """生成大象可渲染为蓝色、可点击的原生 @mention 文本。"""
        return MENTION_TEMPLATE.format(name=self.name, uid=self.uid)


def parse_assignees(md_path: str) -> list[Assignee]:
    """
    从 requirement.md 提取唯一的研发同学列表。

    extract_requirements.py 的研发同学列格式如下：
      [mention]{name="王宇" uid="wangyu193" empId="2099700255"}

    返回值按首次出现顺序去重。这里的 uid 是 MIS，不是大象发消息所需的数字 UID，
    因此仍必须经过 resolve_uid_with_retry() 预检。
    """
    with open(md_path, "r", encoding="utf-8") as file:
        content = file.read()

    assignees = []
    seen_mis = set()
    pattern = r'\[mention\]\{name="([^"]+)"\s+uid="([^"]+)"\s+empId="([^"]+)"\}'
    for name, mis, _ in re.findall(pattern, content):
        if not mis or mis in seen_mis:
            continue
        seen_mis.add(mis)
        assignees.append(Assignee(name=name, mis=mis))

    return assignees


def search_uid_once(mis: str) -> tuple[str | None, str | None]:
    """
    执行一次 catdesk 用户搜索。

    仅接受 type=user、MIS 完全匹配且 id 全为数字的结果。返回 (uid, error)：
    uid 非空代表成功；error 非空代表可诊断失败原因。
    """
    try:
        result = subprocess.run(
            ["catdesk", "daxiang", "search", "--keyword", mis],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return None, "catdesk daxiang search 超时"
    except OSError as error:
        return None, f"无法执行 catdesk daxiang search: {error}"

    if result.returncode != 0:
        stderr = result.stderr.strip().replace("\n", " ")
        return None, f"搜索命令退出码为 {result.returncode}: {stderr[:300]}"

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        stdout = result.stdout.strip().replace("\n", " ")
        return None, f"搜索结果不是有效 JSON: {stdout[:300]}"

    if not payload.get("success"):
        return None, f"搜索接口返回失败: {payload.get('message', payload)}"

    for item in payload.get("data", {}).get("results", []):
        uid = str(item.get("id", ""))
        if item.get("type") == "user" and item.get("mis") == mis and uid.isdigit():
            return uid, None

    return None, f"未找到 MIS={mis} 的数字 UID"


def resolve_uid_with_retry(assignee: Assignee, retries: int) -> ResolvedMention:
    """
    为单个研发同学解析数字 UID，并在瞬时搜索失败时重试。

    未解析成功会抛出 RuntimeError，调用方必须中止整条消息发送。这样不会再出现
    “第一条消息中的 @ 只是纯文本，第二条补发才是真实 @mention”的问题。
    """
    errors = []
    for attempt in range(1, retries + 1):
        uid, error = search_uid_once(assignee.mis)
        if uid:
            return ResolvedMention(name=assignee.name, mis=assignee.mis, uid=uid)
        errors.append(f"第 {attempt} 次: {error}")
        if attempt < retries:
            # 仅在失败重试之间短暂停顿，规避 CatDesk 查询的短暂不稳定。
            time.sleep(1)

    raise RuntimeError(
        f"无法解析 {assignee.name}（{assignee.mis}）的大象数字 UID；"
        + "；".join(errors)
    )


def preflight_mentions(assignees: list[Assignee], retries: int) -> list[ResolvedMention]:
    """
    预检所有人员的 MIS->UID 映射。

    此函数是发送的硬闸门：任一人员解析失败便抛错，调用者不可发送降级消息。
    """
    if not assignees:
        raise RuntimeError("需求列表中没有可 @ 的研发同学")

    resolved = []
    failures = []
    for assignee in assignees:
        try:
            resolved.append(resolve_uid_with_retry(assignee, retries))
        except RuntimeError as error:
            failures.append(str(error))

    if failures:
        raise RuntimeError("@mention 预检未通过：\n- " + "\n- ".join(failures))

    return resolved


def build_message(doc_url: str, mentions: list[ResolvedMention]) -> str:
    """构造最终单条消息，并做发送前的格式断言。"""
    if not doc_url.startswith("https://km.sankuai.com/collabpage/"):
        raise ValueError(f"AI-Coding 文档 URL 非法: {doc_url}")
    if not mentions:
        raise ValueError("没有可发送的大象 @mention")

    mention_text = " ".join(mention.render() for mention in mentions)
    message = f"{doc_url}\n\n{REMINDER_TEXT}{mention_text}"

    # 只接受原生 @mention 语法，防止未来改动时悄悄回退为纯文本 @。
    for mention in mentions:
        expected = mention.render()
        if expected not in message:
            raise ValueError(f"消息格式预检失败，缺少原生 @mention: {mention.mis}")

    return message


def send_message(group_id: str, doc_title: str, message: str) -> None:
    """通过 CatDesk 发送已完成预检的大象消息。"""
    command = [
        "catdesk",
        "daxiang",
        "send",
        "--group-id",
        group_id,
        "--message",
        message,
        "--link-title",
        doc_title,
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("大象消息发送超时") from error
    except OSError as error:
        raise RuntimeError(f"无法执行 catdesk daxiang send: {error}") from error

    if result.returncode != 0:
        raise RuntimeError(f"大象消息发送失败: {result.stderr.strip()[:500]}")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"大象消息发送响应不是有效 JSON: {result.stdout.strip()[:500]}") from error

    if not payload.get("success") or not payload.get("data", {}).get("success"):
        raise RuntimeError(f"大象消息发送失败: {payload}")


def send_notification(
    doc_title: str,
    doc_url: str,
    group_id: str,
    assignees: list[Assignee],
    retries: int,
    dry_run: bool,
) -> bool:
    """
    预检全部 @mention 后发送单条通知。

    执行顺序固定为：解析人员 -> 解析全部 UID -> 校验消息格式 -> 发送。
    因此只要函数返回成功，发送到群内的消息一定使用可点击蓝色 @mention；
    如果任一前置步骤失败，函数返回 False 且完全不调用发送命令。
    """
    try:
        mentions = preflight_mentions(assignees, retries)
        message = build_message(doc_url, mentions)
    except (RuntimeError, ValueError) as error:
        print(f"[ERROR] 通知预检失败，未发送任何群消息: {error}", file=sys.stderr)
        return False

    print(f"[INFO] 通知预检通过：群 {group_id}，@ {len(mentions)} 人")
    for mention in mentions:
        print(f"       - @{mention.name} ({mention.mis}) -> uid {mention.uid}")
    print("[INFO] 最终消息：")
    print(message)

    if dry_run:
        print("[INFO] dry-run 模式：已完成格式预检，未发送群消息")
        return True

    try:
        send_message(group_id, doc_title, message)
    except RuntimeError as error:
        print(f"[ERROR] 大象消息发送失败: {error}", file=sys.stderr)
        return False

    print("[INFO] 大象消息发送成功")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="发送 AI-Coding 同步完成通知（大象群消息）"
    )
    parser.add_argument(
        "--requirement-md",
        required=True,
        help="需求列表 markdown 文件路径（由 extract_requirements.py 生成）",
    )
    parser.add_argument(
        "--doc-title",
        required=True,
        help="AI-Coding 文档标题（用于链接卡片的显示标题）",
    )
    parser.add_argument(
        "--doc-url",
        required=True,
        help="AI-Coding 文档 URL（学城 collabpage 链接）",
    )
    parser.add_argument(
        "--group-id",
        default=DEFAULT_GROUP_ID,
        help=f"大象群 ID（默认: {DEFAULT_GROUP_ID} 酒店民宿平台交易方向）",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"每位人员 MIS->UID 查询重试次数（默认: {DEFAULT_RETRIES}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅输出全部预检结果和最终消息，不发送到群",
    )
    args = parser.parse_args()

    if args.retries < 1:
        parser.error("--retries 必须大于等于 1")

    assignees = parse_assignees(args.requirement_md)
    success = send_notification(
        doc_title=args.doc_title,
        doc_url=args.doc_url,
        group_id=args.group_id,
        assignees=assignees,
        retries=args.retries,
        dry_run=args.dry_run,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
