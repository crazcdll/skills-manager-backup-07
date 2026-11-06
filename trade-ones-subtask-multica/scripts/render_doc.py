#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 state.json 渲染成《Wxx 需求任务创建》整篇文档的 CitadelXML。

流程里每次写学城都是「整篇重渲染 + updateDocumentByXml」，所以这个脚本是唯一的
文档排版出口，保证各阶段小节顺序、标题层级（H2）和表格结构稳定。

用法：
  python3 render_doc.py --state /tmp/osm-state.json --out /tmp/osm-newdoc.xml
  # 用户手填「涉及页面」后：先把线上文档当前 XML 里的涉及页面合并回 state，再重渲染
  oa-skills citadel getDocumentXml --contentId <newDocId> --mis "$MIS" --output /tmp/osm-cur.xml
  python3 render_doc.py --state /tmp/osm-state.json --merge-pages-from /tmp/osm-cur.xml \
      --out /tmp/osm-newdoc.xml
"""

import argparse
import json
import re
import sys
import uuid
import xml.etree.ElementTree as ET

ONES_REQ_RE = re.compile(r"/workItem/requirement/detail/(\d+)")
H2_ONCE = "Ones 子任务创建结果"
H2_MULTICA_IN = "Multica 新任务创建输入"
H2_MULTICA_OUT = "Multica 新任务创建结果"


def esc(text):
    return (str(text if text is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def nid():
    return str(uuid.uuid4())


def cell(text, mention=None, link=None):
    """单个单元格；link = (文字, href)。"""
    if mention:
        uid = mention.get("uid") or mention.get("mis") or ""
        if not uid:
            return cell("@" + (mention.get("name") or ""))
        inner = '<km-mention name="%s" uid="%s" empId="%s" />' % (
            esc(mention.get("name")), esc(uid), esc(mention.get("empId")))
    elif link:
        label, href = link
        inner = '<a href="%s" autoUpdate="true">%s</a>' % (esc(href), esc(label or href))
    else:
        inner = esc(text)
    return '<td nodeId="%s">%s</td>' % (nid(), inner)


def head(text):
    return '<th nodeId="%s">%s</th>' % (nid(), esc(text))


def table(rows):
    body = "".join('<tr nodeId="%s">%s</tr>' % (nid(), "".join(r)) for r in rows)
    return ('<table borderWidth="1" responsive="true" nodeId="%s">%s</table>'
            % (nid(), body))


def para(text="", link=None):
    if link:
        label, href = link
        return '<p nodeId="%s">%s<a href="%s" autoUpdate="true">%s</a></p>' % (
            nid(), esc(text), esc(href), esc(label))
    return '<p nodeId="%s">%s</p>' % (nid(), esc(text))


def h2(text):
    return '<h2 nodeId="%s">%s</h2>' % (nid(), esc(text))


def num(value):
    """31.0 -> 31，7.5 -> 7.5。"""
    try:
        return "%g" % float(value)
    except (TypeError, ValueError):
        return str(value)


def summary_para(state):
    c = (state.get("stats") or {}).get("counts") or {}
    pd = (state.get("stats") or {}).get("pd") or {}
    # 承接率：手填值（stats.rate）优先，重渲染时不能盖掉人的输入；
    # 没手填就用排期表自动算的 rateAuto（境内+境外 本周需求池 / 排期表需求数）。
    rate = (state.get("stats") or {}).get("rate") \
        or (state.get("stats") or {}).get("rateAuto") or "{人工填写}"
    parent = state.get("parentUrl", "")
    if pd:
        formula = "境内 %spd + 境外 %spd + 民宿 %spd = %spd" % (
            num(pd.get("境内", 0)), num(pd.get("境外", 0)),
            num(pd.get("民宿", 0)), num(pd.get("total", 0)))
        if pd.get("borrow"):
            formula += "（借调%spd）" % num(pd["borrow"])
    else:
        formula = ""
    p1 = ('<p nodeId="%s">本周新增需求%s个，已评审待排期 %s个，跟进中%s个，已排期%s个。'
          '需求承接率: %s。详细排期情况见<a href="%s" autoUpdate="true">%s</a></p>'
          % (nid(), c.get("new", 0), c.get("pendingSchedule", 0), c.get("following", 0),
             c.get("scheduled", 0), esc(rate), esc(parent), esc(parent)))
    return p1 + "\n" + para(formula)


def ones_detail_table(results):
    rows = [[head("开发人员"), head("任务标题"), head("工作量"), head("日期"),
             head("状态"), head("标签"), head("任务ID")]]
    for r in results:
        person = cell("", mention={"name": r["person"], "uid": r["uid"],
                                   "empId": r.get("empId", "")})
        task_url = "https://ones.sankuai.com/ones/product/%s/workItem/devTask/detail/%s" % (
            r.get("projectId", ""), r.get("newId", ""))
        rows.append([
            person,
            cell(r.get("taskTitle", "")),
            cell("%s天" % num(r.get("duration", ""))),
            cell(r.get("dateRange", "")),
            cell(r.get("status", "")),
            cell(r.get("labelNames", "")),
            cell("", link=(str(r.get("newId")), task_url)) if r.get("newId") else cell("—"),
        ])
    return table(rows)


def ones_person_table(results):
    order, agg = [], {}
    for r in results:
        if r["uid"] not in agg:
            agg[r["uid"]] = {"name": r["person"], "uid": r["uid"], "empId": r.get("empId", ""),
                             "count": 0, "days": 0, "new": 0, "exist": 0, "pending": 0}
            order.append(r["uid"])
        a = agg[r["uid"]]
        a["count"] += 1
        a["days"] += r.get("duration", 0) or 0
        if r.get("status") == "新创建":
            a["new"] += 1
        elif r.get("status") == "已存在":
            a["exist"] += 1
        else:
            a["pending"] += 1
    rows = [[head("开发人员"), head("任务数"), head("总人天"),
             head("新创建"), head("已存在"), head("待确认")]]
    for uid in order:
        a = agg[uid]
        rows.append([
            cell("", mention=a),
            cell(str(a["count"])),
            cell("%s天" % num(round(a["days"], 2))),
            cell(str(a["new"])),
            cell(str(a["exist"])),
            cell(str(a["pending"])),
        ])
    total = len(results)
    new_cnt = sum(1 for r in results if r.get("status") == "新创建")
    exist_cnt = sum(1 for r in results if r.get("status") == "已存在")
    pending_cnt = total - new_cnt - exist_cnt
    days = round(sum(r.get("duration", 0) or 0 for r in results), 2)
    extra = "，待确认 %s 个" % pending_cnt if pending_cnt else ""
    text = "人力投入汇总：总任务 %s 个（新创建 %s 个，已存在 %s 个%s），总人力 %s 人天，参与 %s 人" % (
        total, new_cnt, exist_cnt, extra, num(days), len(order))
    return para(text), table(rows)


def multica_input_table(items):
    rows = [[head("开发人员"), head("任务标题"), head("需求 ones"),
             head("需求 PRD"), head("涉及页面")]]
    for it in items:
        owners = it.get("owners") or []
        person = cell("", mention=owners[0]) if owners else cell(", ".join(
            o.get("name", "") for o in owners) or it.get("person", ""))
        rows.append([
            person,
            cell(it.get("taskTitle", "")),
            cell("", link=(str(it.get("reqId", "")), it.get("reqUrl", ""))) if it.get("reqUrl")
            else cell(""),
            cell("", link=("PRD", it["prdUrl"])) if it.get("prdUrl") else cell(""),
            cell(it.get("pages", "")),
        ])
    return table(rows)


def multica_result_table(results):
    header = ["序号", "开发人员", "需求名称", "需求 ONES", "PRD", "涉及页面",
              "项目", "Multica Issue", "状态", "备注"]
    rows = [[head(h) for h in header]]
    for r in results:
        rows.append([
            cell(str(r.get("seq", ""))),
            cell(r.get("person", "")),
            cell(r.get("reqName", "")),
            cell("", link=(str(r.get("reqId", "")), r.get("reqUrl", ""))) if r.get("reqUrl")
            else cell(""),
            cell("", link=("PRD", r["prdUrl"])) if r.get("prdUrl") else cell(""),
            cell(r.get("pages", "")),
            cell(r.get("project", "")),
            cell("", link=(r.get("issue", ""), r.get("issueUrl", ""))) if r.get("issue") else cell(""),
            cell(r.get("status", "")),
            cell(r.get("note", "")),
        ])
    return table(rows)


def read_rate_from_doc(xml):
    """从线上文档里取用户已手填的「需求承接率: xx%」。"""
    m = re.search(r"需求承接率[:：]\s*([^。<\"&]+)", xml)
    if not m:
        return ""
    rate = m.group(1).strip()
    return "" if "{" in rate else rate


def warn_rate_mismatch(st):
    """手填值与排期表自动计算值不一致时提醒，不静默改人的数字。"""
    hand, auto = st.get("rate"), st.get("rateAuto")
    if not hand or not auto:
        return
    if hand.replace("%", "").strip() != auto.replace("%", "").strip():
        d = st.get("rateDetail") or {}
        sys.stderr.write("[rate] 文档手填 %s ≠ 排期表自动计算 %s（分子 %s / 分母 %s，仅境内+境外）\n"
                         % (hand, auto, d.get("num"), d.get("den")))


def read_pages_from_doc(xml, items):
    """从用户手填后的文档里取「Multica 新任务创建输入」表的涉及页面列。"""
    root = ET.fromstring(xml)
    for table_el in root.iter("table"):
        texts = [re.sub(r"\s+", "", "".join(t.text or "" for t in tr.iter()))
                 for tr in table_el.findall("tr")]
        if not texts or "涉及页面" not in texts[0]:
            continue
        data_rows = table_el.findall("tr")[1:]
        for idx, tr in enumerate(data_rows):
            cells = tr.findall("th") + tr.findall("td")
            if len(cells) < 5:
                continue
            page = "".join(cells[4].itertext()).strip()
            req_id = None
            for el in cells[2].iter():
                m = ONES_REQ_RE.search(el.get("href") or "")
                if m:
                    req_id = int(m.group(1))
                    break
            target = None
            if req_id:
                target = next((it for it in items if it.get("reqId") == req_id), None)
            if target is None and idx < len(items):
                target = items[idx]
            if target is not None and page:
                target["pages"] = page
    return items


def render(state):
    parts = ['<km-doc>', '<km-title nodeId="%s">%s 需求任务创建</km-title>'
             % (nid(), esc(state.get("week", "")))]

    table_xml = state.get("_tableXml")
    if table_xml:
        parts.append(table_xml)
    else:
        parts.append(para("（排期表复制失败，请手工把父文档「三、人员分布一览表」粘贴到此）"))

    results = (state.get("ones") or {}).get("results") or []
    if results:
        parts += [para(), h2(H2_ONCE), ones_detail_table(results), para(), summary_para(state),
                  para()]
        person_para, person_table = ones_person_table(results)
        parts += [person_para, person_table]

    items = (state.get("multica") or {}).get("input") or []
    if items:
        parts += [para(), h2(H2_MULTICA_IN), multica_input_table(items)]

    m_results = (state.get("multica") or {}).get("results") or []
    if m_results:
        parts += [para(), h2(H2_MULTICA_OUT), multica_result_table(m_results)]

    parts.append("</km-doc>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--merge-pages-from")
    ap.add_argument("--keep-rate-from")
    ap.add_argument("--use-rate-auto", action="store_true",
                    help="丢弃手填的承接率，改用排期表自动计算值")
    args = ap.parse_args()

    state = json.load(open(args.state, encoding="utf-8"))
    state["_tableXml"] = open(state["tableXmlPath"], encoding="utf-8").read()

    if args.keep_rate_from:
        rate = read_rate_from_doc(open(args.keep_rate_from, encoding="utf-8").read())
        if rate:
            state.setdefault("stats", {})["rate"] = rate
            json.dump({k: v for k, v in state.items() if not k.startswith("_")},
                      open(args.state, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    if args.use_rate_auto:
        state.get("stats", {}).pop("rate", None)
        json.dump({k: v for k, v in state.items() if not k.startswith("_")},
                  open(args.state, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    warn_rate_mismatch(state.get("stats") or {})

    if args.merge_pages_from:
        items = (state.get("multica") or {}).get("input") or []
        if items:
            read_pages_from_doc(open(args.merge_pages_from, encoding="utf-8").read(), items)
            json.dump({k: v for k, v in state.items() if not k.startswith("_")},
                      open(args.state, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    open(args.out, "w", encoding="utf-8").write(render(state))
    print(args.out)


if __name__ == "__main__":
    main()
