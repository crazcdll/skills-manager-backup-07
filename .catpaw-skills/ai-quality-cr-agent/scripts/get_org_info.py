#!/usr/bin/env python3
"""
get_org_info.py - 查询员工姓名 + 组织架构 + 团队配置（群号/表格ID/文档目录）
用法: python3 get_org_info.py <misId>
输出 JSON: {"authorName": "曾剑涛", "orgId": "103461", "mis": "zengjiantao",
            "orgName": "<团队名>", "chatGroupId": "<群ID>",
            "tableId": "2757941889", "citadelParentId": "2770377864"}
失败时: {"authorName": "<misId>", "orgId": "", "mis": "<misId>", "orgName": "",
        "chatGroupId": "", "tableId": "", "citadelParentId": "", "error": "..."}
"""
import sys
import json
import urllib.request
import urllib.parse

API_URL = "https://spt.sankuai.com/api/aicr/user-info"


def fetch_user_info(mis_id, timeout=8):
    """调用 spt.sankuai.com 接口查询用户信息 + 团队配置"""
    url = API_URL + "?" + urllib.parse.urlencode({"mis": mis_id})
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


FALLBACK = {
    "authorName": "", "orgId": "", "mis": "", "orgName": "",
    "chatGroupId": "", "tableId": "", "citadelParentId": "",
}


def get_org_info(mis_id):
    resp = None
    last_error = ""
    for attempt in range(3):
        resp = fetch_user_info(mis_id)
        if resp and resp.get("success") and resp.get("data"):
            break
        import time; time.sleep(1)
        last_error = f"attempt {attempt+1} failed or empty"

    if not resp or not resp.get("success") or not resp.get("data"):
        fallback = dict(FALLBACK)
        fallback["authorName"] = mis_id
        fallback["mis"] = mis_id
        fallback["error"] = last_error
        return fallback

    data = resp["data"]
    return {
        "authorName": (data.get("name") or "").strip() or mis_id,
        "orgId": str(data.get("orgId") or ""),
        "mis": mis_id,
        "orgName": (data.get("orgName") or "").strip(),
        "chatGroupId": str(data.get("chatGroupId") or ""),
        "tableId": str(data.get("tableId") or ""),
        "citadelParentId": str(data.get("citadelParentId") or ""),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: get_org_info.py <misId>"}))
        sys.exit(1)

    mis = sys.argv[1].strip()
    result = get_org_info(mis)
    print(json.dumps(result, ensure_ascii=False))
