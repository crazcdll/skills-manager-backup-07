#!/usr/bin/env python3
"""
org-auth-query: 权限查询工具
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time

try:
    import requests
except ImportError:
    print("缺少依赖：pip install requests", file=sys.stderr)
    sys.exit(1)

OFFLINE_COOKIE_CACHE = os.path.expanduser("~/.openclaw/org-auth-offline-cookie.json")
OFFLINE_COOKIE_TTL = 8 * 3600

ONLINE_URL_MIS = "https://org.sankuai.com/org/api/index/resources"
OFFLINE_URL_MIS = "https://org.it.test.sankuai.com/org/api/index/resources"
ONLINE_URL_APP_PRECHECK = "https://org.sankuai.com/org/api/manage/application"
OFFLINE_URL_APP_PRECHECK = "https://org.it.test.sankuai.com/org/api/manage/application"
ONLINE_URL_APP_APPLYINFO = "https://org.sankuai.com/org/api/manage/applyInfo"
OFFLINE_URL_APP_APPLYINFO = "https://org.it.test.sankuai.com/org/api/manage/applyInfo"
ONLINE_URL_EMP_AUTH = "https://org.sankuai.com/org/api/auth/queryEmpAuth"
OFFLINE_URL_EMP_AUTH = "https://org.it.test.sankuai.com/org/api/auth/queryEmpAuth"
ONLINE_URL_ORG_AUTH = "https://org.sankuai.com/org/api/auth/queryOrgAuth"
OFFLINE_URL_ORG_AUTH = "https://org.it.test.sankuai.com/org/api/auth/queryOrgAuth"
ONLINE_URL_BILLS = "https://org.sankuai.com/org/api/apply/bills"
OFFLINE_URL_BILLS = "https://org.it.test.sankuai.com/org/api/apply/bills"
ONLINE_URL_CURRENT_USER = "https://org.sankuai.com/org/api/index/currentUser"
OFFLINE_URL_CURRENT_USER = "https://org.it.test.sankuai.com/org/api/index/currentUser"
ONLINE_URL_EMP_SOURCE = "https://better.sankuai.com/api/v1/org2/emp/get"
OFFLINE_URL_EMP_SOURCE = "https://qabetter.it.test.sankuai.com/api/v1/org2/emp/get"

ORG_CLIENT_ID_ONLINE = "c554e69579"
ORG_CLIENT_ID_OFFLINE = "e5b3c6fa19"

SOURCE_DICT = {
    "KLDL": "快驴代理商", "MTYKF": "美团云客服", "DCFWSC": "到餐服务市场代理商", "ZPAVA": "RPO代理商",
    "WMXYS": "外卖校园商", "DCZH": "到餐直混业务代理商", "PKSH": "品控审核", "SHBZ": "视频标注供应商",
    "MDQQ": "美团圈圈代理商", "JWKF": "境外客服", "WMSJ": "歪马送酒", "MDYL": "美团医疗代理商",
    "MTPDC": "PDC兼职", "XWY": "小物业", "JRCS": "金融贷后", "MDKMM": "客满满代理商",
    "WBHZGS": "外部合作公司", "XTZH": "系统账号", "WBNOS": "外包-非onsite", "SJZH": "审计帐号",
    "WBBIIKE": "外部人员", "TZGS": "投资公司", "JZZH": "兼职账号", "WBYW": "外部运维",
    "MDLS": "零售代理商", "WBNOSHADS": "外包电销", "SQZS": "收钱助手代理商", "MDZLC": "助力车代理商",
    "MDWMA": "外卖代理商", "MDSYA": "收银代理商", "MDKFA": "客服代理商", "MDJWA": "境外代理商",
    "MDJRA": "金融代理商", "MDDZA": "到综代理商", "MDDCA": "到餐代理商", "MDCDB": "充电宝代理商",
    "MDBIKE": "单车代理商", "KLSJ": "快驴司机", "KLCC": "快驴仓储", "MY": "猫眼", "MT": "美团", "TAG": "数字员工",
}

COLUMN_AUTH_LABELS = {
    "BANK": "员工银行卡信息", "EMP_BASE": "员工基本信息", "CONTRACT": "员工合同信息", "CERT": "员工证件信息", "EMP_POS": "员工岗位信息",
    "ORG": "组织信息",
}
FIELD_LABELS = {
    # 通用身份字段
    "job_number":               ("员工工号", "C2"),
    "mis":                      ("员工MIS号", "C2"),
    "emp_id":                   ("员工账号ID", "C2"),
    "source":                   ("业务管理单元", "C2"),
    "tenant_id":                ("租户ID", "C2"),

    # 员工基本信息 (EMP_BASE)
    "name":                     ("员工姓名", "C2"),
    "en_name":                  ("英文名", "C2"),
    "pinyin_name":              ("姓名拼音", "C2"),
    "pinyin_ming":              ("拼音名", "C2"),
    "pinyin_xing":              ("拼音姓", "C2"),
    "legal_name":               ("法定姓名", "C4"),
    "legal_english_name":       ("法定英文名", "C4"),
    "display_name":             ("显示名", "C2"),
    "gender":                   ("性别", "C2"),
    "birthday":                 ("出生日期", "C3"),
    "decode_mobile":            ("明文手机号", "C4"),
    "mobile_encrypt":           ("加密手机号", "C3"),
    "mobile_token":             ("手机号Token", "C2"),
    "mobile":                   ("脱敏手机号", "C2"),
    "mobile_extension":         ("手机号国际化区号", "C2"),
    "personal_email":           ("个人邮箱", "C3"),
    "personal_email_token":     ("个人邮箱Token", "C2"),
    "email":                    ("工作邮箱", "C3"),
    "email_token":              ("公司邮箱Token", "C2"),
    "desk_phone":               ("座机号", "C2"),
    "job_status":               ("在职状态", "C2"),
    "job_status_id":            ("在职状态ID", "C2"),
    "join_date":                ("入职时间", "C3"),
    "left_date":                ("离职时间", "C3"),
    "trans_date":               ("转正日期", "C3"),
    "first_work_date":          ("首次工作时间", "C3"),
    "welfare_begin_date":       ("福利开始时间", "C3"),
    "join_status":              ("入职身份名称", "C3"),
    "join_status_id":           ("入职身份ID", "C3"),
    "recruit":                  ("校招标签", "C2"),
    "level":                    ("职级", "C4"),
    "station":                  ("办公区工位", "C2"),
    "floor":                    ("办公区楼层", "C2"),
    "province_name":            ("办公区省份名称", "C2"),
    "province_id":              ("办公区省份ID", "C2"),
    "site_code_name":           ("办公区名称", "C2"),
    "site_code_id":             ("办公区ID", "C2"),
    "city_name":                ("base地城市名称", "C2"),
    "gb_city_code":             ("base地城市国标编码", "C2"),
    "city_id":                  ("base地城市ID", "C2"),
    "gb_city_code_name":        ("base地国标城市编码名称", "C2"),
    "gb_district_name":         ("base地国标区/县编码名称", "C2"),
    "gb_district_code":         ("base地国标区/县编码", "C2"),
    "gb_province_name":         ("员工base地所在省份名称", "C2"),
    "gb_province_code":         ("员工base地所在省份编码", "C2"),
    "gb_country_name":          ("员工base地所在国家名称", "C2"),
    "gb_country_code":          ("员工base地所在国家编码", "C2"),
    "company_name":             ("公司名称", "C2"),
    "company_id":               ("公司ID", "C2"),
    "company_country_name":     ("公司主体所在国家区域名称", "C2"),
    "company_country_code":     ("公司主体所在国家区域code", "C2"),
    "org_name":                 ("组织名称", "C4"),
    "org_id":                   ("组织ID", "C2"),
    "org_path":                 ("组织ID链", "C2"),
    "bg_name":                  ("组织深度为1的组织名称", "C4"),
    "bg_id":                    ("组织深度为1的组织ID", "C2"),
    "bg_sub1_name":             ("组织深度为2的组织名称", "C4"),
    "bg_sub1_id":               ("组织深度为2的组织ID", "C2"),
    "cost_center_id":           ("成本中心ID", "C2"),
    "hrbp_name":                ("HRBP姓名", "C2"),
    "hrbp_mis":                 ("HRBPMIS号", "C2"),
    "hrbp_job_number":          ("HRBP工号", "C2"),
    "hrbp_emp_id":              ("HRBP账号ID", "C2"),
    "job_family_id":            ("jobFamilyId", "C2"),
    "job_family_name":          ("jobFamilyName", "C2"),
    "jobFamilyId":              ("jobFamilyId", "C2"),
    "jobFamilyName":            ("jobFamilyName", "C2"),
    "job_group_id":             ("jobGroupId", "C2"),
    "job_group_name":           ("jobGroupName", "C2"),
    "job_code_id":              ("jobCodeID", "C2"),
    "job_code_name":            ("jobCodeName", "C2"),
    # 银行卡 (BANK)
    "account_name":             ("银行卡持卡人姓名", "C4"),
    "bank_province":            ("开户行省份", "C4"),
    "bank_city":                ("开户行城市", "C4"),
    "bank_name":                ("开户行银行名称", "C4"),
    "branch_bank_name":         ("开户行支行名称", "C4"),
    "bank_code":                ("开户行银行编码", "C4"),
    "bank_account_no":          ("银行卡号", "C4"),
    "bank_token":               ("银行卡号Token", "C2"),
    "bank_account_type":        ("银行卡类型", "C2"),
    # 合同 (CONTRACT)
    "main_body":                ("合同主体ID", "C2"),
    "main_body_desc":           ("合同主体名称", "C2"),
    "type_desc":                ("合同类型名称", "C4"),
    "type":                     ("合同类型ID", "C4"),
    "sign_type":                ("合同签订类别ID", "C4"),
    "sign_type_desc":           ("合同签订类别名称", "C4"),
    # 证件 (CERT)
    "code_token":               ("证件编号Token", "C2"),
    "code":                     ("证件编号", "C4"),
    "name_cert":                ("证件类型名称", "C4"),  # name 在 CERT 里含义不同，用 table-level 处理
    "category":                 ("证件类型编码", "C4"),
    "category_id":              ("证件类型ID", "C4"),
    # 岗位 (EMP_POS)
    "emp_pos_id":               ("岗位ID", "C2"),
    "report_emp_pos_id":        ("上级主管岗位ID", "C2"),
    "report_emp_name_path":     ("上级主管姓名链", "C2"),
    "report_job_number_path":   ("上级主管工号链", "C2"),
    "report_emp_id_path":       ("上级主管账号ID链", "C2"),
    "report_emp_name":          ("上级主管姓名", "C2"),
    "report_emp_mis":           ("上级主管MIS号", "C2"),
    "report_emp_job_number":    ("上级主管工号", "C2"),
    "report_emp_id":            ("上级主管账号ID", "C2"),
    "dot_line_report_emp_pos_id": ("虚线上级主管岗位ID", "C2"),
    "dot_line_report_emp_id":   ("虚线上级主管账号ID", "C2"),
    "dot_line_report_emp_mis":  ("虚线上级主管MIS号", "C2"),
    "dot_line_report_emp_job_number": ("虚线上级主管工号", "C2"),
    "dot_line_report_emp_name": ("虚线上级主管姓名", "C2"),
    # 组织 (ORG) 特有字段
    "sort":                     ("排序值", "C2"),
    "status":                   ("证件状态", "C2"),
    "mirror_org_id":            ("镜像组织ID", "C2"),
    "mirror_org_name":          ("镜像组织名称", "C4"),
    "current_level":            ("组织层级深度", "C2"),
    "org_name_path":            ("组织名称链", "C4"),
    "parent_name":              ("上级组织名称", "C4"),
    "parent_id":                ("上级组织ID", "C2"),
    "head_mis":                 ("组织首长MIS", "C2"),
    "head_job_number":          ("组织首长工号", "C2"),
    "head_name":                ("组织首长姓名", "C2"),
    "head_emp_id":              ("组织首长账号ID", "C2"),
    "category_name":            ("组织类型名称", "C2"),
    "en_name":                  ("英文名", "C2"),
}


def get_offline_cookie(force: bool = False) -> str:
    if not force:
        try:
            with open(OFFLINE_COOKIE_CACHE) as f:
                d = json.load(f)
            if int(time.time()) - d.get("timestamp", 0) < OFFLINE_COOKIE_TTL:
                return d.get("cookie", "")
        except Exception:
            pass
    script = os.path.join(os.path.dirname(__file__), "get_offline_cookie.py")
    result = subprocess.run(["python3", script] + (["--force"] if force else []), capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def extract_mis_from_token(token: str) -> str | None:
    try:
        parts = token.split("**")
        user_info_b64 = parts[3]
        decoded = base64.urlsafe_b64decode(user_info_b64 + "==").decode("utf-8", errors="replace")
        return decoded.split(",")[1].strip()
    except Exception:
        return None


def validate_mis(input_mis: str, token: str) -> None:
    if not token:
        return
    token_mis = extract_mis_from_token(token)
    if token_mis and input_mis.strip().lower() != token_mis.strip().lower():
        print("抱歉，你不能查其他用户负责的应用信息", file=sys.stderr)
        sys.exit(1)


def _build_headers(token=None, extra=None, env="online", cookie=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    elif token:
        client_id = ORG_CLIENT_ID_OFFLINE if env == "offline" else ORG_CLIENT_ID_ONLINE
        headers["Cookie"] = f"{client_id}_ssoid={token}"
    if extra:
        headers.update(extra)
    return headers


def _post(url, body, headers):
    resp = requests.post(url, json=body, headers=headers, timeout=30)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {"raw": resp.text}


def _browser_fetch(url, body):
    """通过 agent-browser eval 在浏览器登录态下发请求（绕过 HttpOnly cookie）"""
    js = (
        f'fetch({json.dumps(url)},{{'
        f'method:"POST",'
        f'headers:{{"Content-Type":"application/json"}},'
        f'body:JSON.stringify({json.dumps(body)}),'
        f'credentials:"include"'
        f'}}).then(r=>r.text())'
    )
    result = subprocess.run(
        ["agent-browser", "eval", js],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"agent-browser eval failed: {result.stderr.strip()}")
    raw = result.stdout.strip()
    # agent-browser 输出带引号的 JSON 字符串
    if raw.startswith('"') and raw.endswith('"'):
        raw = json.loads(raw)
    return 200, json.loads(raw)


def query_by_mis(mis, env="online", token=None, extra_headers=None, cookie=None, browser=False):
    validate_mis(mis, token)
    url = ONLINE_URL_MIS if env == "online" else OFFLINE_URL_MIS
    if browser:
        return _browser_fetch(url, {"mis": mis})
    return _post(url, {"mis": mis}, _build_headers(token, extra_headers, env, cookie))


def precheck_app(appid, env="online", token=None, extra_headers=None, cookie=None, browser=False):
    url = ONLINE_URL_APP_PRECHECK if env == "online" else OFFLINE_URL_APP_PRECHECK
    if browser:
        return _browser_fetch(url, {"appId": appid})
    return _post(url, {"appId": appid}, _build_headers(token, extra_headers, env, cookie))


def query_app_applyinfo(appid, env="online", token=None, extra_headers=None, cookie=None, browser=False):
    url = ONLINE_URL_APP_APPLYINFO if env == "online" else OFFLINE_URL_APP_APPLYINFO
    if browser:
        return _browser_fetch(url, {"appId": appid})
    return _post(url, {"appId": appid}, _build_headers(token, extra_headers, env, cookie))


def query_emp_auth(appkey, mis, source, tenant_id, env="online", token=None, extra_headers=None, cookie=None, browser=False):
    url = ONLINE_URL_EMP_AUTH if env == "online" else OFFLINE_URL_EMP_AUTH
    body = {"appkey": appkey, "mis": mis, "source": [source], "tenantId": tenant_id}
    if browser:
        return _browser_fetch(url, body)
    return _post(url, body, _build_headers(token, extra_headers, env, cookie))


def query_org_auth(appkey, org_id, source, tenant_id, env="online", token=None, extra_headers=None, cookie=None, browser=False):
    url = ONLINE_URL_ORG_AUTH if env == "online" else OFFLINE_URL_ORG_AUTH
    body = {"appkey": appkey, "orgId": org_id, "source": [source], "tenantId": tenant_id}
    if browser:
        return _browser_fetch(url, body)
    return _post(url, body, _build_headers(token, extra_headers, env, cookie))


def lookup_source_by_mis(mis, tenant_id, env="offline"):
    url = OFFLINE_URL_EMP_SOURCE if env == "offline" else ONLINE_URL_EMP_SOURCE
    payload = {"account": mis, "tenantId": tenant_id, "isOnline": env == "online"}
    try:
        resp = requests.post(url, json=payload, timeout=20)
        data = resp.json()
    except Exception:
        return None
    candidates = []
    if isinstance(data, dict):
        for key in ["data", "result"]:
            val = data.get(key)
            if isinstance(val, dict):
                for sk in ["source", "bu", "businessUnit"]:
                    if val.get(sk):
                        candidates.append(val.get(sk))
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        for sk in ["source", "bu", "businessUnit"]:
                            if item.get(sk):
                                candidates.append(item.get(sk))
        for sk in ["source", "bu", "businessUnit"]:
            if data.get(sk):
                candidates.append(data.get(sk))
    return candidates[0] if candidates else None


def is_blank(v):
    return v in (None, "", [], {})


# 字段在特定表内含义不同的覆盖映射 {table: {field: (label, level)}}
TABLE_FIELD_OVERRIDES = {
    "CERT": {
        "name":   ("证件类型名称", "C4"),
        "code":   ("证件编号", "C4"),
        "status": ("证件状态", "C2"),
    },
    "ORG": {
        "name":       ("组织名称", "C4"),
        "en_name":    ("组织英文名", "C2"),
        "city_name":  ("组织所在城市名称", "C2"),
        "city_id":    ("组织所在城市ID", "C2"),
        "status":     ("组织状态", "C2"),
        "type":       ("组织类型", "C2"),
        "category_id": ("组织类型ID", "C2"),
    },
    "EMP_POS": {
        "org_name": ("组织名称", "C4"),
        "org_id":   ("组织ID", "C2"),
    },
    "EMP_BASE": {
        "name": ("员工姓名", "C2"),
        "status": ("在职状态", "C2"),
    },
    "CONTRACT": {
        "type":      ("合同类型ID", "C4"),
        "type_desc": ("合同类型名称", "C4"),
    },
}


def format_field_inline(code, table=None):
    """返回字段的展示字符串，如果字典中找不到该字段则返回 None（调用方负责过滤）"""
    if table and table in TABLE_FIELD_OVERRIDES:
        override = TABLE_FIELD_OVERRIDES[table].get(code)
        if override:
            name, level = override
            return f"{name}({level})" if level else name
    entry = FIELD_LABELS.get(code)
    if entry is None:
        return None  # 未匹配到，不展示
    name, level = entry
    return f"{name}({level})" if level else name


def format_source_dict():
    lines = ["未能自动识别 source，可参考以下 source 字典："]
    for k, v in SOURCE_DICT.items():
        lines.append(f"- {k}：{v}")
    return "\n".join(lines)


def format_app_applyinfo_result(result, env):
    data = result.get("data") or {}
    app = data.get("applicationan") or data.get("application") or {}
    lines = []
    lines.append(f"**应用基础信息**")
    lines.append(f"- 应用编码：`{app.get('appId', '-')}`")
    if app.get("appName"):
        lines.append(f"- 应用名称：`{app.get('appName')}`")
    octo = app.get("octo") or []
    if octo:
        lines.append(f"- 数据权限应用：{', '.join([x for x in octo if not is_blank(x)])}")
    domain_auth = data.get("domainAuth") or []
    if domain_auth:
        domain_strs = []
        for item in domain_auth:
            if not isinstance(item, dict):
                continue
            space = item.get("space", "")
            domains = item.get("domain") or []
            if domains:
                domain_strs.append(f"{space} → {', '.join(domains)}")
        if domain_strs:
            lines.append(f"- 域权限：{'；'.join(domain_strs)}")

    for title, obj in [("员工信息领域", data.get("empInfo")), ("组织信息领域", data.get("deptInfo"))]:
        if not isinstance(obj, dict):
            continue
        lines.append("")
        lines.append(f"**{title}**")

        tenant = obj.get("tenantId") or []
        source = obj.get("source") or []
        dept = obj.get("deptScope") or []
        column_auth = obj.get("columnAuth") or {}
        jf = obj.get("jobfamilyId") or []
        mjf = obj.get("mobileJobfamilyId") or []

        if tenant:
            tenant_str = "、".join([f"{i.get('name','-')}" for i in tenant if isinstance(i, dict)])
            lines.append(f"- **租户范围**：{tenant_str}")

        if source:
            source_str = "、".join([f"{i.get('businessUnit','-')}({i.get('businessName','-')})" for i in source if isinstance(i, dict)])
            lines.append(f"- **source 范围**：{source_str}")

        if dept:
            dept_str = "；".join([i.get('orgNamePath','') for i in dept if isinstance(i, dict) and i.get('orgNamePath')])
            lines.append(f"- **部门范围**：{dept_str}")

        # columnAuth 可能是 list（新格式）或 dict（旧格式）
        if isinstance(column_auth, list) and column_auth:
            lines.append(f"- **字段权限**：")
            for item in column_auth:
                if not isinstance(item, dict):
                    continue
                table = item.get("table", "")
                fields = item.get("fields") or []
                if not fields:
                    continue
                fields_str = "、".join([x for x in (format_field_inline(f, table) for f in fields) if x is not None])
                lines.append(f"  - {COLUMN_AUTH_LABELS.get(table, table)}：{fields_str}")
        elif isinstance(column_auth, dict) and column_auth:
            lines.append(f"- **字段权限**：")
            for key, value in column_auth.items():
                if not value:
                    continue
                fields = value.get("fields") if isinstance(value, dict) else None
                if fields:
                    fields_str = "、".join([format_field_inline(f) for f in fields])
                    lines.append(f"  - {COLUMN_AUTH_LABELS.get(key, key)}：{fields_str}")

        if jf:
            jf_str = "、".join([f"{i.get('jobfamilyId','-')}({i.get('jobfamilyName','-')})" for i in jf if isinstance(i, dict)])
            lines.append(f"- **职务序列范围**：{jf_str}")

        if mjf:
            mjf_str = "、".join([f"{i.get('jobfamilyId','-')}({i.get('jobfamilyName','-')})" for i in mjf if isinstance(i, dict)])
            lines.append(f"- **手机号职务序列范围**：{mjf_str}")

    if env == "offline":
        lines += ["", "⚠️ 注意：以上为【线下测试环境】数据，请勿与线上数据混淆。"]
    return "\n".join(lines)


def summarize_auth_result(kind, result):
    data = result.get("data") or {}
    has_auth = data.get("hasAuth")
    msg = (data.get("msg") or "").strip()
    lines = []
    if has_auth is True:
        lines.append(f"有权限：{kind}鉴权通过。")
    elif has_auth is False:
        lines.append(f"无权限：{kind}鉴权不通过。")
    else:
        lines.append(f"{kind}鉴权结果未知。")
    if msg:
        lines.append("说明：")
        for part in [x.strip() for x in msg.splitlines() if x.strip()]:
            lines.append(f"- {part}")
    if has_auth is False:
        missing = []
        hint_map = {
            "组织权限范围不足": "组织范围权限",
            "员工查询的列权限": "字段列权限",
            "source": "source 范围权限",
            "tenant": "租户范围权限",
            "部门": "部门范围权限",
            "orgId": "组织范围权限",
        }
        for k, v in hint_map.items():
            if k in msg:
                missing.append(v)
        if missing:
            lines.append(f"缺少权限：{'、'.join(dict.fromkeys(missing))}")
    return "\n".join(lines)


def get_current_user_mis(env="online", token=None, extra_headers=None, cookie=None, browser=False):
    """获取当前登录用户的 mis，用于安全校验"""
    url = ONLINE_URL_CURRENT_USER if env == "online" else OFFLINE_URL_CURRENT_USER
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    if cookie:
        headers["Cookie"] = cookie
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("mis") or data.get("mis") or data.get("loginName")
    except Exception:
        pass
    return None


def query_bills(mis, env="online", token=None, extra_headers=None, cookie=None, browser=False):
    url = ONLINE_URL_BILLS if env == "online" else OFFLINE_URL_BILLS
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    if cookie:
        headers["Cookie"] = cookie
    try:
        resp = requests.post(url, json={"mis": mis}, headers=headers, timeout=15)
        return resp.status_code, resp.json()
    except Exception as e:
        return 0, {"error": str(e)}


def format_bills_result(result):
    data = result.get("data") or []
    if not data:
        return "暂无申请单据记录。\n\n> 如需查看单据详情，请跳转：https://org.sankuai.com/index"
    header = "| 应用ID | 应用名称 | 工单号 | 工单类型 | 状态 | 发起人 |"
    sep    = "|--------|----------|--------|----------|------|--------|"
    rows = []
    for item in data:
        row = "| {} | {} | {} | {} | {} | {} |".format(
            item.get("appId", "-"),
            item.get("appName", "-"),
            item.get("bpmCode", "-"),
            item.get("type", "-"),
            item.get("status", "-"),
            item.get("applicant", "-"),
        )
        rows.append(row)
    table = "\n".join([header, sep] + rows)
    return f"{table}\n\n> 如需查看单据详情，请跳转：https://org.sankuai.com/index"


def main():
    parser = argparse.ArgumentParser(description="org 权限查询工具")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ["mis", "app", "empauth", "orgauth", "bills"]:
        p = sub.add_parser(name)
        p.add_argument("--env", choices=["online", "offline"], default="online")
        p.add_argument("--token")
        p.add_argument("--cookie")
        p.add_argument("--browser", action="store_true", help="通过 agent-browser 在浏览器登录态下发请求（无需 token/cookie）")
        p.add_argument("--header", nargs="*", metavar="KEY=VALUE")
    sub.choices["mis"].add_argument("mis")
    sub.choices["app"].add_argument("client_id")
    sub.choices["empauth"].add_argument("--appkey", required=True)
    sub.choices["empauth"].add_argument("--mis", required=True)
    sub.choices["empauth"].add_argument("--source")
    sub.choices["empauth"].add_argument("--tenantId", required=True, type=int)
    sub.choices["orgauth"].add_argument("--appkey", required=True)
    sub.choices["orgauth"].add_argument("--orgId", required=True, type=int)
    sub.choices["orgauth"].add_argument("--source", required=True)
    sub.choices["orgauth"].add_argument("--tenantId", required=True, type=int)
    sub.choices["bills"].add_argument("mis")

    args = parser.parse_args()
    extra_headers = {}
    for kv in getattr(args, "header", None) or []:
        if "=" in kv:
            k, v = kv.split("=", 1)
            extra_headers[k.strip()] = v.strip()

    cookie = getattr(args, "cookie", None)
    use_browser = getattr(args, "browser", False)
    if args.env == "offline" and not cookie and not args.token and not use_browser:
        cookie = get_offline_cookie()

    def ensure_cookie(status):
        nonlocal cookie
        if args.env == "offline" and status == 401 and not use_browser:
            cookie = get_offline_cookie(force=True)
            return True
        return False

    if args.command == "mis":
        status, result = query_by_mis(args.mis, args.env, args.token, extra_headers, cookie, use_browser)
        if ensure_cookie(status):
            status, result = query_by_mis(args.mis, args.env, args.token, extra_headers, cookie, use_browser)
        if status not in (200, 201):
            print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command in ("app", "empauth", "orgauth"):
        appid = args.client_id if args.command == "app" else args.appkey
        pre_status, pre_result = precheck_app(appid, args.env, args.token, extra_headers, cookie, use_browser)
        if ensure_cookie(pre_status):
            pre_status, pre_result = precheck_app(appid, args.env, args.token, extra_headers, cookie, use_browser)
        if pre_status not in (200, 201):
            print(json.dumps(pre_result, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(1)
        if pre_result.get("status") == 0:
            print(f"当前用户mis号无权限查询appid={appid}的应用信息")
            return

    if args.command == "app":
        status, result = query_app_applyinfo(args.client_id, args.env, args.token, extra_headers, cookie, use_browser)
        if ensure_cookie(status):
            status, result = query_app_applyinfo(args.client_id, args.env, args.token, extra_headers, cookie, use_browser)
        if status not in (200, 201):
            print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(1)
        print(format_app_applyinfo_result(result, args.env))
        return

    if args.command == "empauth":
        source = args.source
        if not source:
            source = lookup_source_by_mis(args.mis, args.tenantId, args.env)
            if not source:
                print(format_source_dict())
                return
            print(f"已自动识别 source：{source}")
        status, result = query_emp_auth(args.appkey, args.mis, source, args.tenantId, args.env, args.token, extra_headers, cookie, use_browser)
        if ensure_cookie(status):
            status, result = query_emp_auth(args.appkey, args.mis, source, args.tenantId, args.env, args.token, extra_headers, cookie, use_browser)
        if status not in (200, 201):
            print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(1)
        print(summarize_auth_result("员工", result))
        return

    if args.command == "orgauth":
        status, result = query_org_auth(args.appkey, args.orgId, args.source, args.tenantId, args.env, args.token, extra_headers, cookie, use_browser)
        if ensure_cookie(status):
            status, result = query_org_auth(args.appkey, args.orgId, args.source, args.tenantId, args.env, args.token, extra_headers, cookie, use_browser)
        if status not in (200, 201):
            print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(1)
        print(summarize_auth_result("组织", result))

    if args.command == "bills":
        # ⚠️ 安全校验：只允许查询当前登录用户自己的申请单据
        current_mis = get_current_user_mis(args.env, args.token, extra_headers, cookie, use_browser)
        if current_mis and current_mis != args.mis:
            print(f"❌ 安全校验失败：只允许查询您自己的申请单据，无法查询他人数据。")
            print(f"   当前登录用户：{current_mis}，请求查询：{args.mis}")
            sys.exit(1)
        if not current_mis:
            print("⚠️ 无法获取当前登录用户信息，请确认 token/cookie 是否有效。", file=sys.stderr)
            sys.exit(1)
        status, result = query_bills(args.mis, args.env, args.token, extra_headers, cookie, use_browser)
        if ensure_cookie(status):
            status, result = query_bills(args.mis, args.env, args.token, extra_headers, cookie, use_browser)
        if status not in (200, 201):
            print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(1)
        print(format_bills_result(result))


if __name__ == "__main__":
    main()
