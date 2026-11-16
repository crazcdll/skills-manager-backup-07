#!/usr/bin/env python3
"""
前端异常日报生成器
用法：
  python3 gen_error_report.py [projectName] [report_time]

参数：
  projectName  Raptor 项目名，默认 rn_hotel_hotelchannel-orderfill-duo
  report_time  报告基准时间（ISO格式），默认当前时间，例：2026-03-13T10:00:00

时间窗口（滚动24h对齐）：
  当前窗口：report_time - 24h  ~  report_time
  对比窗口：report_time - 48h  ~  report_time - 24h
"""

import json, sys, os, subprocess, time, tempfile, html as html_lib, threading
from datetime import datetime, timedelta
try:
    import urllib.request as _urllib
    import urllib.parse as _urlparse
    _HAS_URLLIB = True
except ImportError:
    _HAS_URLLIB = False

# ── 版本 ──────────────────────────────────────────────────────────────────────
# 每次修改脚本时更新此日期，格式 YYYYMMDD
SKILL_VERSION = "20260325"

# ── 配置 ──────────────────────────────────────────────────────────────────────
MCP_ENDPOINT = "http://mcphub-server.sankuai.com/mcphub-b/d0a6625a180b40"

# Raptor Web API（直调，需要 cookie）
RAPTOR_BASE   = "https://raptor.mws.sankuai.com/cat/fe/"
RAPTOR_META   = "https://raptor.mws.sankuai.com/cat/fe/meta/project/listForScene"
RAPTOR_WEB    = "https://raptor.mws.sankuai.com/frontend/error/detail"
# cookie 文件路径（可选，优先级高于环境变量）
COOKIE_FILE   = os.path.expanduser('~/.openclaw/raptor_cookie')

# STATUS 枚举（来自 Raptor 前端 JS 逆向）
STATUS_IGNORED = 4   # 完全忽略
STATUS_MUTED   = 5   # 暂时忽略
IGNORE_STATUSES = {STATUS_IGNORED, STATUS_MUTED}

# 高危关键词：只保留核心支付/下单流程，避免误报
CRITICAL_KEYWORDS = [
    'submit', 'pay', '支付', '下单', 'payment', 'checkout',
    'exitPay', 'prePay', '前置支付',
]
NEW_ERROR_MIN_COUNT   = 1
# 持续异常 / 暴涨异常：动态阈值参数
# 实际阈值 = max(PERSISTENT_ABS_MIN, total * PERSISTENT_RATIO)
PERSISTENT_ABS_MIN    = 10     # 绝对下限（次）
PERSISTENT_RATIO      = 0.005  # 总量的 0.5%
PERSISTENT_TOP_N      = 10     # 最多展示 Top N 条
SURGE_PCT_THRESHOLD   = 100    # 环比暴涨百分比阈值
SURGE_ABS_MIN         = 5      # 暴涨绝对下限（次）
SURGE_RATIO           = 0.001  # 总量的 0.1%
SURGE_TOP_N           = 10     # 最多展示 Top N 条
# ERROR 级别堆栈：拉 top N 条
STACK_TOP_N = 5

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── MCP 调用（单 session 多请求版） ───────────────────────────────────────────

class MCPSession:
    """复用同一 SSE session 发多个请求，减少连接开销"""

    def __init__(self, timeout=120):
        self.timeout = timeout
        self.log_fd, self.log_path = tempfile.mkstemp(suffix='.log', prefix='mcp_')
        os.close(self.log_fd)
        # 用 PIPE 接收 curl 输出，后台线程实时 tee 到文件
        # 避免 curl 写文件时的内部缓冲导致父进程读不到数据
        self.sse_proc = subprocess.Popen(
            ['curl', '-s', '-N', '--max-time', str(timeout),
             MCP_ENDPOINT, '-H', 'Accept: text/event-stream'],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._stop_tee = threading.Event()
        self._tee_thread = threading.Thread(target=self._tee_pipe, daemon=True)
        self._tee_thread.start()
        # 等待 SSE 连接建立并写入 sessionId（最多 10s）
        for _ in range(10):
            time.sleep(1)
            try:
                sid = self._get_session_id()
                if sid:
                    break
            except RuntimeError:
                pass
        self.session_id = self._get_session_id()
        self.ep = "{}?sessionId={}".format(MCP_ENDPOINT, self.session_id)
        self._initialize()
        self._req_id = 2

    def _tee_pipe(self):
        """后台线程：把 curl stdout pipe 实时写到日志文件"""
        with open(self.log_path, 'w') as fh:
            for raw_line in self.sse_proc.stdout:
                line = raw_line.decode('utf-8', errors='replace')
                fh.write(line)
                fh.flush()
                if self._stop_tee.is_set():
                    break

    def _get_session_id(self):
        with open(self.log_path) as f:
            for line in f:
                if 'sessionId=' in line:
                    for part in line.split():
                        if 'sessionId=' in part:
                            return part.split('sessionId=')[-1].strip().rstrip('/')
        raise RuntimeError("Failed to get sessionId")

    def _initialize(self):
        subprocess.run(
            ['curl', '-s', '-X', 'POST', self.ep,
             '-H', 'Content-Type: application/json',
             '-d', json.dumps({
                 "jsonrpc": "2.0", "method": "initialize", "id": 1,
                 "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "catpaw-report", "version": "1.0"}}
             })],
            capture_output=True
        )
        time.sleep(1)

    def call(self, tool_name, arguments, wait=45):
        req_id = self._req_id
        self._req_id += 1
        subprocess.run(
            ['curl', '-s', '-X', 'POST', self.ep,
             '-H', 'Content-Type: application/json',
             '-d', json.dumps({
                 "jsonrpc": "2.0", "method": "tools/call", "id": req_id,
                 "params": {"name": tool_name, "arguments": arguments}
             })],
            capture_output=True
        )
        target = '"id":{}'.format(req_id)
        for _ in range(wait // 3):
            time.sleep(3)
            with open(self.log_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('data:') and target in line:
                        raw = line[5:].strip()
                        resp = json.loads(raw)
                        text = resp['result']['content'][0]['text']
                        return json.loads(text)
        raise RuntimeError("Timeout waiting for tool={} id={}".format(tool_name, req_id))

    def close(self):
        self._stop_tee.set()
        self.sse_proc.terminate()
        try:
            self.sse_proc.stdout.close()
        except Exception:
            pass
        self._tee_thread.join(timeout=3)
        try:
            os.unlink(self.log_path)
        except Exception:
            pass


def mcp_call(tool_name, arguments, timeout=60):
    """单次调用（兼容旧接口）"""
    s = MCPSession(timeout=timeout + 10)
    try:
        return s.call(tool_name, arguments, wait=timeout)
    finally:
        s.close()


# ── Raptor Web API 直调层 ─────────────────────────────────────────────────────

class RaptorWebAPI:
    """
    直接调用 Raptor 后端 API（/cat/fe/log/summaryTable 等），
    获取官方 STATUS（TAG）和 newErrors（官方首现列表）。

    cookie 来源优先级：
      1. 构造时传入的 cookie 字符串
      2. COOKIE_FILE 文件（.raptor_cookie）
      3. 环境变量 RAPTOR_COOKIE
    """

    def __init__(self, cookie=None):
        self.cookie = cookie or self._load_cookie()
        if not self.cookie:
            raise RuntimeError(
                "未找到 Raptor cookie。请将 cookie 写入 {} 或设置环境变量 RAPTOR_COOKIE".format(COOKIE_FILE)
            )
        self._project_id_cache = {}

    @staticmethod
    def _load_cookie():
        # 1. 文件
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE) as f:
                c = f.read().strip()
                if c:
                    return c
        # 2. 环境变量
        return os.environ.get('RAPTOR_COOKIE', '')

    def _get(self, url, params=None, timeout=30):
        if params:
            qs = '&'.join('{}={}'.format(k, _urlparse.quote(str(v))) for k, v in params.items())
            url = url + ('&' if '?' in url else '?') + qs
        req = _urllib.Request(url)
        req.add_header('Cookie', self.cookie)
        req.add_header('Referer', 'https://raptor.mws.sankuai.com/web/error/list')
        req.add_header('X-Requested-With', 'XMLHttpRequest')
        req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        with _urllib.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def get_project_id(self, project_name):
        """通过 projectName 查询 projectId"""
        if project_name in self._project_id_cache:
            return self._project_id_cache[project_name]
        data = self._get(RAPTOR_META, {'name': project_name, 'scene': 'PROJECT_VIEW'})
        if not data.get('success') or not data.get('result'):
            raise RuntimeError("无法查询 projectId for {}: {}".format(project_name, data))
        pid = data['result'][0]['id']
        self._project_id_cache[project_name] = pid
        print("  projectId={} ({})".format(pid, data['result'][0].get('displayName', '')))
        return pid

    def fetch_summary_table(self, project_name, start_ms, end_ms, limit=200, offset=0):
        """
        调用 /cat/fe/log/summaryTable，返回：
          - rows: 异常列表，每条含 STATUS（TAG）、LEVEL、CATEGORY、COUNT、USER_COUNT
          - newErrors: 官方首现异常名称列表
          - total: 总条数
        """
        pid = self.get_project_id(project_name)
        data = self._get(RAPTOR_BASE + 'log/summaryTable', {
            'projectId': pid,
            'start': start_ms,
            'end': end_ms,
            'limit': limit,
            'offset': offset,
        })
        if not data.get('success'):
            raise RuntimeError("summaryTable failed: {}".format(data.get('message')))
        result = data['result']
        rows = result.get('table', {}).get('rows', [])
        new_errors = result.get('newErrors') or []   # 防御 None
        total = result.get('total', 0)
        return rows, new_errors, total

    def fetch_error_stack(self, project_name, error_name, start_ms, end_ms, limit=5):
        """
        拉取某个异常名称的原始日志列表，返回第一条的堆栈内容。
        接口：/cat/fe/log/list（按 keyword 过滤）
        """
        pid = self.get_project_id(project_name)
        try:
            data = self._get(RAPTOR_BASE + 'log/list', {
                'projectId': pid,
                'start': start_ms,
                'end': end_ms,
                'keyword': error_name,
                'limit': limit,
                'offset': 0,
                'logType': 'jsError',
            })
            if not data.get('success'):
                return ''
            rows = data.get('result', {}).get('rows', [])
            if not rows:
                return ''
            # 取第一条，拼接 content 字段（通常是堆栈）
            first = rows[0]
            content = first.get('content') or first.get('stack') or first.get('msg') or ''
            return content
        except Exception as e:
            print("  [warn] fetch_error_stack({}) failed: {}".format(error_name[:40], e))
            return ''

    def fetch_all_errors(self, project_name, start_ms, end_ms,
                         filter_ignored=True, page_size=100):
        """
        分页拉取全量异常，自动过滤 STATUS=4（完全忽略）和 STATUS=5（暂时忽略）。

        newErrors[] 按 offset 分布在各页，与 limit 大小无关。
        终止条件使用 offset >= total（接口未过滤总数），确保走完所有页。
        每页的 newErrors 都收集并合并去重，最终得到完整的官方首现集合。

        返回 (rows, new_errors_set, kept_count)
        """
        all_rows = []
        official_new = set()
        offset = 0
        total = None
        while True:
            rows, page_new_errors, page_total = self.fetch_summary_table(
                project_name, start_ms, end_ms, limit=page_size, offset=offset)
            if total is None:
                total = page_total  # total 是接口未过滤的总数，用于判断是否还有后续页
            official_new.update(page_new_errors)  # 每页都收集，合并去重
            for row in rows:
                status = row.get('STATUS', 0)
                if filter_ignored and status in IGNORE_STATUSES:
                    continue
                all_rows.append(row)
            # 终止条件：只用 offset 判断，不能用 len(rows) < page_size
            # 原因：STATUS 过滤后实际行数可能少于 page_size，但接口仍有后续页
            offset += page_size
            if total is None or offset >= total:
                break
        return all_rows, official_new, len(all_rows)



# ── Cookie 自动刷新 ───────────────────────────────────────────────────────────

def _refresh_cookie_via_browser(timeout=60):
    """
    用 agent-browser 自动从 Raptor 页面抓取最新 cookie。
    返回 cookie 字符串，失败返回 None。
    SSO 登录状态通常已持久化（~/.agent-browser 默认 profile），无需重新扫码。
    """
    try:
        result = subprocess.run(
            ['agent-browser', '--session', 'raptor-cookie-refresh',
             'open', 'https://raptor.mws.sankuai.com/frontend/error/detail'],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            print("  [cookie] agent-browser open 失败: {}".format(result.stderr[:200]))
            return None

        # 等待页面加载
        subprocess.run(
            ['agent-browser', '--session', 'raptor-cookie-refresh',
             'wait', '--load', 'networkidle'],
            capture_output=True, text=True, timeout=30
        )

        # 检查是否被 SSO 拦截
        url_result = subprocess.run(
            ['agent-browser', '--session', 'raptor-cookie-refresh', 'get', 'url'],
            capture_output=True, text=True, timeout=10
        )
        current_url = url_result.stdout.strip()
        if 'ssosv.sankuai.com' in current_url or 'sso.sankuai.com' in current_url:
            print("  [cookie] 检测到 SSO 登录拦截，跳过自动刷新（需手动扫码）")
            return None

        # 抓取 cookie
        eval_result = subprocess.run(
            ['agent-browser', '--session', 'raptor-cookie-refresh',
             'eval', 'document.cookie'],
            capture_output=True, text=True, timeout=10
        )
        cookie = eval_result.stdout.strip().strip('"')
        if not cookie or len(cookie) < 50:
            print("  [cookie] cookie 为空或过短，抓取失败")
            return None

        # 写入持久化文件
        with open(COOKIE_FILE, 'w') as f:
            f.write(cookie)
        print("  [cookie] 自动刷新成功，已写入 {}（{} bytes）".format(
            COOKIE_FILE, len(cookie)))
        return cookie
    except subprocess.TimeoutExpired:
        print("  [cookie] agent-browser 超时")
        return None
    except FileNotFoundError:
        print("  [cookie] agent-browser 未安装，跳过自动刷新")
        return None
    except Exception as ex:
        print("  [cookie] 自动刷新异常: {}".format(ex))
        return None
    finally:
        # 关闭临时会话
        try:
            subprocess.run(
                ['agent-browser', '--session', 'raptor-cookie-refresh', 'close'],
                capture_output=True, timeout=5
            )
        except Exception:
            pass


def _rows_to_list(rows):
    """把 summaryTable rows 转成统一格式 [{name, type, level, count, status}]"""
    result = []
    for row in rows:
        result.append({
            'name':   row.get('main', ''),
            'type':   row.get('CATEGORY', 'jsError'),
            'level':  (row.get('LEVEL') or 'info').upper(),
            'count':  int(row.get('COUNT', 0)),
            'users':  int(row.get('USER_COUNT', 0)),
            'status': int(row.get('STATUS', 0)),
            'date':   row.get('DATE', ''),
        })
    return result


# ── 数据拉取 ──────────────────────────────────────────────────────────────────

FMT = "%Y-%m-%d %H:%M:%S"

def fetch_error_list(session, project, start, end, level="INFO"):
    result = session.call('raptor_get_web_error_list', {
        "mode": "RAPTOR_PROD",
        "projectName": project,
        "startStr": start.strftime(FMT),
        "endStr": end.strftime(FMT),
        "level": level,
    })
    if not result.get('success'):
        raise RuntimeError("raptor_get_web_error_list failed: {}".format(result))
    return result['data']


def fetch_summary(session, project, start, end):
    result = session.call('raptor_web_error_simple_summary', {
        "mode": "RAPTOR_PROD",
        "projectName": project,
        "startStr": start.strftime(FMT),
        "endStr": end.strftime(FMT),
        "level": "INFO",
    })
    if not result.get('success'):
        raise RuntimeError("raptor_web_error_simple_summary failed: {}".format(result))
    return result['data']


def fetch_error_stacks(session, project, start, end, error_list, top_n=STACK_TOP_N):
    """
    对 ERROR 级别 top N 异常，尝试拉一条堆栈详情。
    策略：先拿 detail_list 的 logId，逐条拉 detail，按 secCategory 匹配。
    最多尝试 30 条 logId，避免超时。
    """
    targets = {r['name']: r for r in error_list[:top_n]}
    if not targets:
        return {}

    try:
        detail_list = session.call('raptor_get_web_error_detail_list', {
            "mode": "RAPTOR_PROD",
            "project": project,
            "startStr": start.strftime(FMT),
            "endStr": end.strftime(FMT),
            "logType": "JS_ERROR",
        })
        rows = detail_list['data']['rows'][:30]
    except Exception as e:
        print("  [warn] detail_list failed: {}".format(e))
        return {}

    found = {}
    for row in rows:
        if len(found) >= len(targets):
            break
        log_id = row['id']
        log_time = row['main'][:19].replace('T', ' ')
        try:
            detail = session.call('raptor_get_web_error_detail', {
                "mode": "RAPTOR_PROD",
                "dateStr": log_time,
                "logId": log_id,
            }, wait=30)
            if detail.get('data') and len(detail['data']) > 0:
                item = detail['data'][0]
                sec_cat = item.get('secCategory', '')
                for name in targets:
                    if name not in found and (name in sec_cat or sec_cat in name):
                        content = item.get('content', '')
                        found[name] = {
                            'logId': log_id,
                            'level': item.get('level', ''),
                            'content': content,
                            'count': targets[name].get('count', targets[name].get('count_cur', 0)),
                        }
                        break
        except Exception:
            pass

    return found


# ── 数据处理 ──────────────────────────────────────────────────────────────────

def is_critical(name):
    nl = name.lower()
    return any(kw.lower() in nl for kw in CRITICAL_KEYWORDS)


def get_api_group(name, err_type):
    if err_type == 'ajaxError':
        parts = name.split(':')
        if len(parts) >= 2:
            return parts[0].strip()
    return None


def process(cur_list, prev_list, official_new_errors=None):
    """
    cur_list / prev_list : 统一格式列表 [{name, type, level, count, status, ...}]
    official_new_errors  : Raptor 官方首现集合（set of name），即 summaryTable 返回的
                           newErrors[]，含义是「较上周同期首现」。
                           None 表示获取失败，此时 is_new 全部为 False，不做推断。

    返回合并后的处理结果，每条带 level、is_official_new 字段
    """
    prev_map = {x['name']: x['count'] for x in prev_list}

    results = []
    for item in cur_list:
        name = item['name']
        count_cur = item['count']
        count_prev = prev_map.get(name, 0)
        # 首现判断：仅使用 Raptor 官方 newErrors[]（较上周同期首现）
        # 若官方数据不可用（None），不做任何推断，is_new 一律为 False
        is_new = (name in official_new_errors) if official_new_errors is not None else False
        change_pct = (count_cur - count_prev) / count_prev * 100 if count_prev > 0 else None

        results.append({
            'name': name,
            'type': item['type'],
            'level': item.get('level', 'INFO'),
            'count_cur': count_cur,
            'count_prev': count_prev,
            'is_new': is_new,
            'change_pct': change_pct,
            'is_critical': is_critical(name),
            'api_group': get_api_group(name, item['type']),
        })

    # 接口聚合
    api_groups = {}
    for r in results:
        g = r['api_group']
        if g:
            if g not in api_groups:
                api_groups[g] = {'cur': 0, 'prev': 0}
            api_groups[g]['cur'] += r['count_cur']
            api_groups[g]['prev'] += r['count_prev']

    new_errors = [r for r in results if r['is_new'] and r['count_cur'] >= NEW_ERROR_MIN_COUNT]

    # 动态阈值：基于当前窗口总次数
    total_count = sum(r['count_cur'] for r in results)
    persistent_threshold = max(PERSISTENT_ABS_MIN, total_count * PERSISTENT_RATIO)
    surge_threshold      = max(SURGE_ABS_MIN,      total_count * SURGE_RATIO)

    # 持续异常：两窗口均出现 + 非首现 + 次数超动态阈值，按次数降序取 Top N
    persistent_candidates = sorted(
        [r for r in results
         if not r['is_new']
         and r['count_prev'] > 0
         and r['count_cur'] >= persistent_threshold],
        key=lambda x: x['count_cur'], reverse=True
    )
    critical_persistent = persistent_candidates[:PERSISTENT_TOP_N]

    # 环比暴涨：环比超阈值 + 次数超动态阈值，按环比降序取 Top N
    surge_candidates = sorted(
        [r for r in results
         if r['change_pct'] is not None
         and r['change_pct'] > SURGE_PCT_THRESHOLD
         and r['count_cur'] >= surge_threshold],
        key=lambda x: x['change_pct'], reverse=True
    )
    surge_errors = surge_candidates[:SURGE_TOP_N]
    error_level_list = [r for r in results if r['level'] == 'ERROR']

    # 异常类型统计
    js_count   = sum(1 for r in results if r['type'] == 'jsError')
    ajax_count = sum(1 for r in results if r['type'] == 'ajaxError')
    other_count = len(results) - js_count - ajax_count

    return {
        'all_errors': results,
        'new_errors': new_errors,
        'critical_persistent': critical_persistent,
        'surge_errors': surge_errors,
        'api_groups': sorted(api_groups.items(), key=lambda x: x[1]['cur'], reverse=True),
        'error_level_list': error_level_list,
        'official_new_available': official_new_errors is not None,
        'type_stats': {'js': js_count, 'ajax': ajax_count, 'other': other_count},
        'persistent_threshold': persistent_threshold,
        'surge_threshold': surge_threshold,
    }


# ── AI 堆栈分析 ───────────────────────────────────────────────────────────────

def analyze_stack(name, content, count):
    """
    基于异常名称 + 堆栈内容做简单的业务影响推断。
    不调用外部 AI，用规则 + 关键词判断。
    """
    risk = 'medium'
    impact = ''
    suggestion = ''

    name_lower = name.lower()
    content_lower = (content or '').lower()

    # 风险等级判断
    if any(k in name_lower for k in ['支付', 'pay', 'submit', '下单', 'checkout']):
        risk = 'high'
        impact = '涉及支付/下单核心链路，可能导致用户无法完成交易'
        suggestion = '建议立即排查，确认是否影响支付成功率'
    elif 'errorboundary' in name_lower or '零容忍' in name_lower:
        risk = 'high'
        impact = '组件渲染崩溃，用户看到错误边界兜底页面，体验严重受损'
        suggestion = '查看堆栈定位崩溃组件，检查近期相关代码变更'
    elif 'syntaxerror' in name_lower or 'referenceerror' in name_lower:
        risk = 'high'
        impact = '代码语法/引用错误，可能导致页面功能完全不可用'
        suggestion = '检查近期发布的 bundle，确认是否有编译问题'
    elif 'typeerror' in name_lower:
        risk = 'medium'
        impact = '类型错误，可能导致特定功能异常'
        suggestion = '查看堆栈定位具体调用链，检查数据结构变更'
    elif 'timeout' in name_lower or 'network' in content_lower:
        risk = 'low'
        impact = '网络超时，通常为用户网络问题，非代码 bug'
        suggestion = '关注量级变化，若持续上涨需排查网络链路'
    elif 'undefined' in name_lower:
        risk = 'medium'
        impact = '数据字段缺失，可能导致相关功能展示异常'
        suggestion = '检查数据来源，确认接口返回结构是否有变更'
    else:
        risk = 'low'
        impact = '影响范围待评估'
        suggestion = '结合堆栈和业务场景进一步分析'

    # 从堆栈提取关键帧（取前3行非空行）
    stack_lines = []
    if content:
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('at <unknown>') and len(stack_lines) < 3:
                stack_lines.append(line)

    return {
        'risk': risk,
        'impact': impact,
        'suggestion': suggestion,
        'stack_preview': stack_lines,
    }


# ── HTML 生成 ─────────────────────────────────────────────────────────────────

def fmt_num(n):
    return '{:,}'.format(n)


def fmt_pct(v):
    if v is None:
        return '<span class="tag-new">首现</span>'
    cls = 'up' if v > 0 else 'down'
    arrow = '▲' if v > 0 else '▼'
    return '<span class="chg {}">{}{:.1f}%</span>'.format(cls, arrow, abs(v))


def pct(a, b):
    return (a - b) / b * 100 if b > 0 else None


RISK_COLOR = {'high': '#e74c3c', 'medium': '#f39c12', 'low': '#27ae60'}
RISK_LABEL = {'high': '高风险', 'medium': '中风险', 'low': '低风险'}


def build_stack_section(error_level_list, stacks):
    if not error_level_list:
        return '<p class="empty">✅ 当前窗口无 ERROR 级别 JS 异常</p>'

    cards = []
    for item in error_level_list:
        name = item['name']
        count = item.get('count_cur', item.get('count', 0))
        stack_info = stacks.get(name, {})
        analysis = analyze_stack(name, stack_info.get('content', ''), count)
        risk = analysis['risk']
        color = RISK_COLOR[risk]
        label = RISK_LABEL[risk]

        stack_preview_html = ''
        if analysis['stack_preview']:
            lines = ''.join(
                '<div class="stack-line">{}</div>'.format(html_lib.escape(l))
                for l in analysis['stack_preview']
            )
            stack_preview_html = '<div class="stack-preview">{}</div>'.format(lines)
        elif stack_info.get('content'):
            preview = html_lib.escape(stack_info['content'][:200])
            stack_preview_html = '<div class="stack-preview"><div class="stack-line">{}</div></div>'.format(preview)

        cards.append('''
        <div class="stack-card" style="border-left-color:{color}">
          <div class="stack-header">
            <span class="risk-badge" style="background:{color}">{label}</span>
            <span class="stack-name">{name}</span>
            <span class="stack-count">×{count}</span>
          </div>
          <div class="stack-analysis">
            <div class="analysis-row"><b>影响：</b>{impact}</div>
            <div class="analysis-row"><b>建议：</b>{suggestion}</div>
          </div>
          {stack_preview}
        </div>'''.format(
            color=color, label=label,
            name=html_lib.escape(name),
            count=fmt_num(count),
            impact=html_lib.escape(analysis['impact']),
            suggestion=html_lib.escape(analysis['suggestion']),
            stack_preview=stack_preview_html,
        ))

    return '\n'.join(cards)


def _raptor_link(name, project_id, project_name='', cur_start=None, cur_end=None):
    """构造 Raptor 异常详情页跳转链接
    URL 格式参考：/frontend/error/detail?type=datetimerange
      &start=YYYYMMDDHHmmss&end=YYYYMMDDHHmmss
      &projectId=...&projectName=...&keyword=...
    """
    try:
        import urllib.parse as _up
        # 时间格式：YYYYMMDDHHmmss
        fmt = '%Y%m%d%H%M%S'
        start_str = cur_start.strftime(fmt) if cur_start else ''
        end_str   = cur_end.strftime(fmt)   if cur_end   else ''
        params = (
            'type=datetimerange'
            '&start={start}&end={end}'
            '&projectId={pid}'
            '&webVersion=all'
            '&projectName={pname}'
            '&keyword={kw}'
            '&errorListCurrentPage=1'
            '&errorName={kw}'
            '&errorDetailCurrentPage=1'
            '&errorDetailCurrentPageSize=50'
        ).format(
            start=start_str,
            end=end_str,
            pid=project_id,
            pname=_up.quote(project_name),
            kw=_up.quote(name),
        )
        return '{}?{}'.format(RAPTOR_WEB, params)
    except Exception:
        return '#'


def build_alert_card(r, reason, project_id=None, project_name='', cur_start=None, cur_end=None, is_new=False):
    cp = r['change_pct']
    etype = 'JS' if r['type'] == 'jsError' else 'AJAX'
    type_cls = 'js' if r['type'] == 'jsError' else 'ajax'
    level_badge = ''
    if r.get('level') == 'ERROR':
        level_badge = '<span class="level-badge error">ERROR</span>'
    if project_id:
        name_html = '<a href="{}" target="_blank" class="alert-name alert-link">{}</a>'.format(
            _raptor_link(r['name'], project_id, project_name, cur_start, cur_end), html_lib.escape(r['name']))
    else:
        name_html = '<span class="alert-name">{}</span>'.format(html_lib.escape(r['name']))
    # 首现卡片：官方是跟上周同期比，对比窗口次数和环比对首现无意义，不展示
    if is_new:
        meta_extra = ''
    else:
        meta_extra = '''
        <span class="alert-count">对比窗口 {cy}</span>
        {chg}'''.format(
            cy=fmt_num(r['count_prev']) if r['count_prev'] > 0 else '-',
            chg=fmt_pct(cp),
        )
    return '''
    <div class="alert-card">
      <div class="alert-header">
        <span class="etype {type_cls}">{etype}</span>
        {level_badge}
        {name_html}
      </div>
      <div class="alert-meta">
        <span class="reason">{reason}</span>
        <span class="alert-count">当前窗口 <b>{ct}</b></span>
        {meta_extra}
      </div>
    </div>'''.format(
        type_cls=type_cls, etype=etype,
        level_badge=level_badge,
        name_html=name_html,
        reason=reason,
        ct=fmt_num(r['count_cur']),
        meta_extra=meta_extra,
    )


def build_row(r, idx, max_count, project_id=None, project_name='', cur_start=None, cur_end=None):
    name = r['name']
    etype = r['type']
    ct = r['count_cur']
    cy = r['count_prev']
    is_new = r['is_new']
    cp = r['change_pct']
    is_crit = r['is_critical']
    level = r.get('level', 'INFO')

    type_cls = 'js' if etype == 'jsError' else 'ajax'
    type_label = 'JS' if etype == 'jsError' else 'AJAX'

    tags = ''
    if level == 'ERROR':
        tags += '<span class="tag tag-error">ERROR</span>'
    if is_new:
        tags += '<span class="tag tag-new">首现</span>'
    if is_crit:
        tags += '<span class="tag tag-crit">交易链路</span>'

    bar_w = min(100, int(ct / max(max_count, 1) * 100))

    if project_id:
        name_html = '<a href="{}" target="_blank" class="ename ename-link">{}</a>'.format(
            _raptor_link(name, project_id, project_name, cur_start, cur_end), html_lib.escape(name))
    else:
        name_html = '<span class="ename">{}</span>'.format(html_lib.escape(name))

    return '''
    <tr class="{row_cls}">
      <td class="idx">{idx}</td>
      <td class="name-cell">
        <div class="name-inner">
          <span class="etype {type_cls}">{type_label}</span>
          {name_html}
          {tags}
        </div>
      </td>
      <td class="count">{ct}</td>
      <td class="count prev">{cy}</td>
      <td class="chg-cell">{chg}</td>
      <td class="bar-cell"><div class="bar" style="width:{bar_w}%"></div></td>
    </tr>'''.format(
        row_cls='row-error' if level == 'ERROR' else ('row-crit' if is_crit else ''),
        idx=idx + 1,
        type_cls=type_cls, type_label=type_label,
        name_html=name_html,
        tags=tags,
        ct=fmt_num(ct),
        cy=fmt_num(cy) if cy > 0 else '-',
        chg=fmt_pct(cp),
        bar_w=bar_w,
    )


def generate_html(project, cur_start, cur_end, prev_start, prev_end,
                  cur_summary, prev_summary, processed, stacks, gen_time,
                  project_id=None):

    ts = cur_summary
    ys = prev_summary
    t_errors = ts['errorCounts']['all']
    t_users  = ts['errorUsers']['all']
    y_errors = ys['errorCounts']['all']
    y_users  = ys['errorUsers']['all']

    all_errors = processed['all_errors']
    max_count = all_errors[0]['count_cur'] if all_errors else 1

    rows_html = ''.join(build_row(r, i, max_count, project_id, project, cur_start, cur_end) for i, r in enumerate(all_errors))

    new_errors = processed['new_errors']
    critical   = processed['critical_persistent']
    surge      = processed['surge_errors']
    api_groups = processed['api_groups']
    error_level_list = processed['error_level_list']
    type_stats = processed.get('type_stats', {})

    official_new_available = processed.get('official_new_available', False)
    new_label = '最近一周首现'
    if official_new_available:
        new_section_title = '最近一周首现异常'
    else:
        new_section_title = ('最近一周首现异常'
            '<span style="font-size:12px;color:#e67e22;font-weight:400">'
            ' ⚠ 官方首现数据获取失败，本节暂无数据</span>')
    if official_new_available:
        new_cards = ''.join(
            build_alert_card(r, new_label, project_id, project, cur_start, cur_end, is_new=True) for r in new_errors
        ) or '<p class="empty">✅ 当前窗口无新增首现异常</p>'
    else:
        new_cards = '<p class="empty">⚠ 官方首现数据暂不可用，请前往 Raptor 页面手动查看</p>'

    p_thresh = int(processed.get('persistent_threshold', 0))
    s_thresh = int(processed.get('surge_threshold', 0))

    critical_cards = ''
    for r in critical:
        cp = r['change_pct']
        if cp is not None and cp > 20:
            reason = '持续存在 · 环比上涨 {:.0f}%'.format(cp)
        elif cp is not None and cp < -20:
            reason = '持续存在 · 环比下降 {:.0f}%'.format(abs(cp))
        else:
            reason = '持续存在 · 基本持平'
        critical_cards += build_alert_card(r, reason, project_id, project, cur_start, cur_end)
    if not critical_cards:
        critical_cards = '<p class="empty">✅ 无持续异常</p>'

    surge_cards = ''.join(
        build_alert_card(r, '环比暴涨 +{:.0f}%'.format(r['change_pct']), project_id, project, cur_start, cur_end) for r in surge
    ) or '<p class="empty">✅ 无环比暴涨异常</p>'

    # 异常类型统计卡片
    js_cnt   = type_stats.get('js', 0)
    ajax_cnt = type_stats.get('ajax', 0)
    err_cnt  = len(error_level_list)
    new_cnt  = len(new_errors)

    api_rows = ''.join('''
    <tr>
      <td>{}</td><td>{}</td><td>{}</td><td>{}</td>
    </tr>'''.format(
        html_lib.escape(g), fmt_num(v['cur']), fmt_num(v['prev']),
        fmt_pct(pct(v['cur'], v['prev'])),
    ) for g, v in api_groups)

    stack_section = build_stack_section(error_level_list, stacks)

    window_label = '{} ~ {}'.format(
        cur_start.strftime('%m-%d %H:%M'), cur_end.strftime('%m-%d %H:%M'))
    prev_label = '{} ~ {}'.format(
        prev_start.strftime('%m-%d %H:%M'), prev_end.strftime('%m-%d %H:%M'))

    error_count_badge = len(error_level_list)

    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>异常报告 · {project} · {window}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", sans-serif;
         background: #f5f6fa; color: #1a1a2e; font-size: 14px; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
             color: white; padding: 28px 40px; }}
  .header h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 8px; }}
  .header .meta {{ color: #8892b0; font-size: 13px; line-height: 1.9; }}
  .header .meta b {{ color: #ccd6f6; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px 20px; }}

  /* 概览 */
  .overview {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 28px; }}
  @media (max-width: 900px) {{ .overview {{ grid-template-columns: repeat(2, 1fr); }} }}
  .card {{ background: white; border-radius: 12px; padding: 20px 24px;
           box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
  .card .label {{ color: #8892b0; font-size: 12px; margin-bottom: 8px;
                  text-transform: uppercase; letter-spacing: .5px; }}
  .card .value {{ font-size: 32px; font-weight: 700; color: #1a1a2e; margin-bottom: 6px; }}
  .card .compare {{ font-size: 13px; color: #8892b0; }}
  .card .type-row {{ display: flex; gap: 12px; margin-top: 8px; flex-wrap: wrap; }}
  .card .type-item {{ font-size: 12px; color: #555; }}
  .card .type-item b {{ font-weight: 600; }}

  /* 链接样式 */
  a.alert-link, a.ename-link {{
    color: inherit; text-decoration: none;
  }}
  a.alert-link:hover {{ text-decoration: underline; color: #3498db; }}
  a.ename-link:hover {{ color: #3498db; text-decoration: underline; }}

  /* 变化 */
  .chg {{ font-weight: 600; font-size: 13px; }}
  .chg.up {{ color: #e74c3c; }}
  .chg.down {{ color: #27ae60; }}
  .tag-new {{ background: #fff3cd; color: #856404; padding: 1px 6px;
              border-radius: 4px; font-size: 11px; font-weight: 600; }}

  /* Section */
  .section {{ margin-bottom: 28px; }}
  .section-title {{ font-size: 16px; font-weight: 600; color: #1a1a2e; margin-bottom: 14px;
                    display: flex; align-items: center; gap: 8px; }}
  .section-title .dot {{ width: 4px; height: 18px; border-radius: 2px; background: #e74c3c; }}
  .section-title .dot.blue {{ background: #3498db; }}
  .section-title .dot.green {{ background: #27ae60; }}
  .section-title .dot.orange {{ background: #f39c12; }}
  .section-title .dot.purple {{ background: #9b59b6; }}
  .badge {{ background: #e74c3c; color: white; font-size: 11px; font-weight: 700;
            padding: 1px 7px; border-radius: 10px; }}

  /* 告警卡片 */
  .alert-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 12px; }}
  .alert-card {{ background: white; border-radius: 10px; padding: 14px 16px;
                 box-shadow: 0 2px 6px rgba(0,0,0,.05); border-left: 3px solid #e74c3c; }}
  .alert-header {{ display: flex; align-items: flex-start; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }}
  .alert-name {{ font-size: 13px; font-weight: 500; color: #1a1a2e; line-height: 1.4;
                 word-break: break-all; flex: 1;
                 display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
                 overflow: hidden; }}
  .alert-meta {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .reason {{ font-size: 11px; color: #8892b0; background: #f8f9fa; padding: 2px 8px; border-radius: 4px; }}
  .alert-count {{ font-size: 12px; color: #555; }}
  .alert-count b {{ color: #1a1a2e; }}
  .empty {{ color: #8892b0; font-size: 13px; padding: 12px 0; }}
  .tip {{ cursor: help; color: #aaa; font-size: 11px; }}

  /* 类型/等级标签 */
  .etype {{ display: inline-block; font-size: 10px; font-weight: 700; padding: 2px 6px;
            border-radius: 4px; flex-shrink: 0; }}
  .etype.js {{ background: #fef3c7; color: #92400e; }}
  .etype.ajax {{ background: #dbeafe; color: #1e40af; }}
  .level-badge {{ display: inline-block; font-size: 10px; font-weight: 700; padding: 2px 6px;
                  border-radius: 4px; flex-shrink: 0; }}
  .level-badge.error {{ background: #fee2e2; color: #991b1b; }}
  .tag {{ display: inline-block; font-size: 10px; padding: 1px 5px; border-radius: 3px; margin-left: 4px; }}
  .tag-crit {{ background: #fee2e2; color: #991b1b; }}
  .tag-error {{ background: #fee2e2; color: #991b1b; }}

  /* 接口聚合 */
  .api-table {{ width: 100%; background: white; border-radius: 10px;
                box-shadow: 0 2px 6px rgba(0,0,0,.05); border-collapse: collapse; overflow: hidden; }}
  .api-table th {{ background: #f8f9fa; padding: 10px 16px; text-align: left;
                   font-size: 12px; color: #8892b0; font-weight: 600; border-bottom: 1px solid #eee; }}
  .api-table td {{ padding: 10px 16px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }}
  .api-table tr:last-child td {{ border-bottom: none; }}
  .api-table tr:hover td {{ background: #fafbfc; }}

  /* 堆栈分析 */
  .stack-card {{ background: white; border-radius: 10px; padding: 16px 18px;
                 box-shadow: 0 2px 6px rgba(0,0,0,.05); border-left: 4px solid #e74c3c;
                 margin-bottom: 12px; }}
  .stack-header {{ display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }}
  .risk-badge {{ display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 8px;
                 border-radius: 4px; color: white; flex-shrink: 0; }}
  .stack-name {{ font-size: 13px; font-weight: 600; color: #1a1a2e; flex: 1; word-break: break-all; }}
  .stack-count {{ font-size: 12px; color: #8892b0; flex-shrink: 0; }}
  .stack-analysis {{ margin-bottom: 10px; }}
  .analysis-row {{ font-size: 13px; color: #444; line-height: 1.7; }}
  .analysis-row b {{ color: #1a1a2e; }}
  .stack-preview {{ background: #1a1a2e; border-radius: 6px; padding: 10px 14px; margin-top: 8px; }}
  .stack-line {{ font-family: "SF Mono", "Fira Code", monospace; font-size: 11px;
                 color: #a8b2d8; line-height: 1.6; word-break: break-all; }}

  /* 完整列表 */
  .filter-bar {{ display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }}
  .filter-btn {{ padding: 5px 14px; border: 1px solid #e0e0e0; border-radius: 20px; background: white;
                 cursor: pointer; font-size: 12px; color: #555; transition: all .15s; }}
  .filter-btn:hover, .filter-btn.active {{ background: #1a1a2e; color: white; border-color: #1a1a2e; }}
  .error-table {{ width: 100%; background: white; border-radius: 10px;
                  box-shadow: 0 2px 6px rgba(0,0,0,.05); border-collapse: collapse; overflow: hidden; }}
  .error-table th {{ background: #f8f9fa; padding: 10px 16px; text-align: left;
                     font-size: 12px; color: #8892b0; font-weight: 600; border-bottom: 1px solid #eee; }}
  .error-table td {{ padding: 9px 16px; border-bottom: 1px solid #f5f5f5; vertical-align: middle; }}
  .error-table tr:last-child td {{ border-bottom: none; }}
  .error-table tr:hover td {{ background: #fafbfc; }}
  .error-table .row-error td {{ background: #fff5f5; }}
  .error-table .row-error:hover td {{ background: #ffecec; }}
  .error-table .row-crit td {{ background: #fff8f8; }}
  .idx {{ color: #ccc; font-size: 12px; width: 36px; white-space: nowrap; }}
  .name-cell {{ min-width: 260px; }}
  .name-inner {{ display: flex; align-items: baseline; gap: 4px; flex-wrap: wrap; }}
  .ename {{ font-size: 13px; color: #1a1a2e; overflow-wrap: break-word; word-break: break-word; min-width: 0; }}
  .count {{ text-align: right; font-size: 13px; font-weight: 500; width: 90px; }}
  .count.prev {{ color: #8892b0; font-weight: 400; }}
  .chg-cell {{ text-align: right; width: 90px; }}
  .bar-cell {{ width: 100px; padding-right: 16px; }}
  .bar {{ height: 6px; background: linear-gradient(90deg, #3498db, #2980b9); border-radius: 3px; min-width: 2px; }}
  /* 分页 */
  .pagination {{ display: flex; align-items: center; gap: 6px; margin-top: 14px; flex-wrap: wrap; }}
  .pg-info {{ font-size: 12px; color: #8892b0; margin-right: 6px; }}
  .pg-btn {{ padding: 4px 10px; border: 1px solid #e0e0e0; border-radius: 6px; background: white;
             cursor: pointer; font-size: 12px; color: #555; transition: all .15s; }}
  .pg-btn:hover {{ background: #f0f0f0; }}
  .pg-btn.pg-active {{ background: #1a1a2e; color: white; border-color: #1a1a2e; font-weight: 600; }}
  .footer {{ text-align: center; color: #ccc; font-size: 12px; padding: 20px; margin-top: 10px; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 前端异常报告</h1>
  <div class="meta">
    <div>项目：<b>{project}</b></div>
    <div>当前窗口：<b>{window}</b> &nbsp;|&nbsp; 对比窗口：{prev_window}</div>
    <div>生成时间：{gen_time}</div>
  </div>
</div>

<div class="container">

  <!-- 概览 4 卡片 -->
  <div class="overview">
    <div class="card">
      <div class="label">总异常次数（INFO+）</div>
      <div class="value">{t_errors}</div>
      <div class="compare">对比窗口 {y_errors} &nbsp; {err_chg}</div>
    </div>
    <div class="card">
      <div class="label">影响用户数</div>
      <div class="value">{t_users}</div>
      <div class="compare">对比窗口 {y_users} &nbsp; {user_chg}</div>
    </div>
    <div class="card">
      <div class="label">异常类型分布</div>
      <div class="value">{total_types}</div>
      <div class="type-row">
        <span class="type-item"><b style="color:#92400e">JS</b> {js_cnt}</span>
        <span class="type-item"><b style="color:#1e40af">AJAX</b> {ajax_cnt}</span>
      </div>
    </div>
  </div>

  <!-- 首现 -->
  <div class="section">
    <div class="section-title">
      <div class="dot orange"></div>{new_section_title}
    </div>
    <div class="alert-grid">{new_cards}</div>
  </div>

  <!-- 暴涨 -->
  <div class="section">
    <div class="section-title"><div class="dot"></div>环比暴涨异常 <span style="font-size:12px;color:#8892b0;font-weight:400">&gt;{surge_pct}% 且 &gt;{s_thresh}次 · Top {surge_top_n}</span></div>
    <div class="alert-grid">{surge_cards}</div>
  </div>

  <!-- 持续异常 -->
  <div class="section">
    <div class="section-title"><div class="dot"></div>持续异常 <span style="font-size:12px;color:#8892b0;font-weight:400">两窗口均出现 &gt;{p_thresh}次 · Top {persistent_top_n}</span></div>
    <div class="alert-grid">{critical_cards}</div>
  </div>

  <!-- ERROR 级别堆栈分析 -->
  <div class="section">
    <div class="section-title">
      <div class="dot purple"></div>ERROR 级别 JS 异常分析
      {error_badge}
    </div>
    {stack_section}
  </div>

  <!-- 接口聚合 -->
  <div class="section">
    <div class="section-title"><div class="dot blue"></div>AJAX 接口异常聚合</div>
    <table class="api-table">
      <thead><tr><th>接口名</th><th>当前窗口</th><th>对比窗口</th><th>环比</th></tr></thead>
      <tbody>{api_rows}</tbody>
    </table>
  </div>

  <!-- 完整列表 -->
  <div class="section">
    <div class="section-title"><div class="dot green"></div>完整异常列表（共 {total} 条）</div>
    <div class="filter-bar">
      <button class="filter-btn active" onclick="filterTable('all',this)">全部</button>
      <button class="filter-btn" onclick="filterTable('error',this)">ERROR 级别</button>
      <button class="filter-btn" onclick="filterTable('js',this)">JS Error</button>
      <button class="filter-btn" onclick="filterTable('ajax',this)">AJAX Error</button>
      <button class="filter-btn" onclick="filterTable('crit',this)">交易链路</button>
      <button class="filter-btn" onclick="filterTable('new',this)">首现</button>
    </div>
    <table class="error-table" id="errorTable">
      <thead>
        <tr>
          <th>#</th><th>异常名称</th>
          <th style="text-align:right">当前窗口</th>
          <th style="text-align:right">对比窗口</th>
          <th style="text-align:right">环比</th>
          <th>占比</th>
        </tr>
      </thead>
      <tbody id="errorTbody">{rows_html}</tbody>
    </table>
    <!-- 分页控件 -->
    <div class="pagination" id="pagination"></div>
  </div>

</div>
<div class="footer">由 CatClaw 自动生成 · {gen_time} · hotel-raptor-inspection {skill_version}</div>

<script>
(function() {{
  var PAGE_SIZE = 100;
  var currentFilter = 'all';
  var currentPage = 1;

  function getFilteredRows() {{
    var allRows = Array.from(document.querySelectorAll('#errorTbody tr'));
    if (currentFilter === 'all') return allRows;
    return allRows.filter(function(row) {{
      if (currentFilter === 'error') return row.querySelector('.tag-error');
      if (currentFilter === 'js')    return row.querySelector('.etype.js');
      if (currentFilter === 'ajax')  return row.querySelector('.etype.ajax');
      if (currentFilter === 'crit')  return row.querySelector('.tag-crit');
      if (currentFilter === 'new')   return row.querySelector('.tag-new');
      return true;
    }});
  }}

  function renderPage(page) {{
    currentPage = page;
    var filtered = getFilteredRows();
    var total = filtered.length;
    var totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (currentPage > totalPages) currentPage = totalPages;
    var start = (currentPage - 1) * PAGE_SIZE;
    var end = start + PAGE_SIZE;

    // 先隐藏所有行
    Array.from(document.querySelectorAll('#errorTbody tr')).forEach(function(r) {{
      r.style.display = 'none';
    }});
    // 显示当前页的过滤行
    filtered.slice(start, end).forEach(function(r) {{
      r.style.display = '';
    }});

    // 渲染分页控件
    var pg = document.getElementById('pagination');
    if (totalPages <= 1) {{ pg.innerHTML = ''; return; }}
    var html = '<span class="pg-info">共 ' + total + ' 条，第 ' + currentPage + '/' + totalPages + ' 页</span>';
    if (currentPage > 1) {{
      html += '<button class="pg-btn" onclick="window._goPage(' + (currentPage-1) + ')">‹ 上一页</button>';
    }}
    // 页码按钮（最多显示7个）
    var s = Math.max(1, currentPage - 3);
    var e = Math.min(totalPages, s + 6);
    s = Math.max(1, e - 6);
    for (var i = s; i <= e; i++) {{
      var cls = i === currentPage ? 'pg-btn pg-active' : 'pg-btn';
      html += '<button class="' + cls + '" onclick="window._goPage(' + i + ')">' + i + '</button>';
    }}
    if (currentPage < totalPages) {{
      html += '<button class="pg-btn" onclick="window._goPage(' + (currentPage+1) + ')">下一页 ›</button>';
    }}
    pg.innerHTML = html;
  }}

  window._goPage = function(page) {{
    renderPage(page);
    document.getElementById('errorTable').scrollIntoView({{behavior:'smooth', block:'start'}});
  }};

  window.filterTable = function(type, btn) {{
    document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    currentFilter = type;
    renderPage(1);
  }};

  // 初始渲染
  renderPage(1);
}})();
</script>
</body>
</html>'''.format(
        project=html_lib.escape(project),
        window=window_label, prev_window=prev_label,
        gen_time=gen_time.strftime('%Y-%m-%d %H:%M:%S'),
        t_errors=fmt_num(t_errors), y_errors=fmt_num(y_errors),
        t_users=fmt_num(t_users),   y_users=fmt_num(y_users),
        err_chg=fmt_pct(pct(t_errors, y_errors)),
        user_chg=fmt_pct(pct(t_users, y_users)),
        total_types=fmt_num(len(all_errors)),
        js_cnt=fmt_num(js_cnt), ajax_cnt=fmt_num(ajax_cnt),
        new_section_title=new_section_title,
        new_cards=new_cards,
        critical_cards=critical_cards,
        surge_cards=surge_cards,
        p_thresh=p_thresh,
        persistent_top_n=PERSISTENT_TOP_N,
        surge_pct=SURGE_PCT_THRESHOLD,
        s_thresh=s_thresh,
        surge_top_n=SURGE_TOP_N,
        error_badge='<span class="badge">{}</span>'.format(error_count_badge) if error_count_badge else '',
        stack_section=stack_section,
        api_rows=api_rows,
        total=len(all_errors),
        rows_html=rows_html,
        skill_version=SKILL_VERSION,
    )


# ── 主流程 ────────────────────────────────────────────────────────────────────

def _make_summary_stub(count, users):
    """构造 summary 数据结构（兼容 generate_html）"""
    return {
        'errorCounts': {'all': count},
        'errorUsers':  {'all': users},
    }


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else 'rn_hotel_hotelchannel-orderfill-duo'
    if len(sys.argv) > 2:
        report_time = datetime.fromisoformat(sys.argv[2])
    else:
        report_time = datetime.now().replace(second=0, microsecond=0)

    cur_end    = report_time
    cur_start  = report_time - timedelta(hours=24)
    prev_end   = cur_start
    prev_start = cur_start - timedelta(hours=24)

    cur_ms  = int(cur_start.timestamp() * 1000)
    cur_ems = int(cur_end.timestamp() * 1000)
    prv_ms  = int(prev_start.timestamp() * 1000)
    prv_ems = int(prev_end.timestamp() * 1000)

    print("项目：{}".format(project))
    print("当前窗口：{} ~ {}".format(cur_start, cur_end))
    print("对比窗口：{} ~ {}".format(prev_start, prev_end))
    print()

    # ── 模式 A：Raptor Web API 直调（官方 TAG + 官方首现）────────────────────
    use_web_api = False
    cur_list = prev_list = []
    official_new = None
    project_id = None       # 用于构造跳转链接
    cur_summary = prev_summary = None
    stacks = {}

    try:
        api = RaptorWebAPI()
        # 顺便拿 projectId（用于跳转链接）
        project_id = api.get_project_id(project)

        print("[1/4] Raptor Web API：拉取当前窗口数据（含 TAG 过滤 + 官方首现）...")
        cur_rows, cur_new, _ = api.fetch_all_errors(project, cur_ms, cur_ems)
        cur_list = _rows_to_list(cur_rows)
        # official_new 来自各分页 newErrors[] 合并，含义是「较上周同期首现」
        # 注意：空集合 set() 表示「有数据，0条首现」，与 None（获取失败）不同
        official_new = cur_new  # 始终是 set，可能为空集合
        print("  当前窗口: {} 条（已过滤忽略 TAG），官方首现: {} 条".format(
            len(cur_list), len(official_new)))

        print("[2/4] 拉取对比窗口数据...")
        prev_rows, _, _ = api.fetch_all_errors(project, prv_ms, prv_ems)
        prev_list = _rows_to_list(prev_rows)
        print("  对比窗口: {} 条".format(len(prev_list)))

        print("[3/4] 聚合汇总数据...")
        # 构造 summary（从列表聚合）
        cur_total  = sum(r['count'] for r in cur_list)
        cur_users  = sum(r['users'] for r in cur_list)
        prev_total = sum(r['count'] for r in prev_list)
        prev_users = sum(r['users'] for r in prev_list)
        cur_summary  = _make_summary_stub(cur_total, cur_users)
        prev_summary = _make_summary_stub(prev_total, prev_users)
        use_web_api = True

        # 拉取 ERROR 级别堆栈（Web API 模式）
        error_items_for_stack = sorted(
            [r for r in cur_list if r.get('level') == 'ERROR'],
            key=lambda x: x['count'], reverse=True
        )[:STACK_TOP_N]
        if error_items_for_stack:
            print("[3.5/4] 拉取 ERROR 级别堆栈（top {}）...".format(len(error_items_for_stack)))
            for item in error_items_for_stack:
                name = item['name']
                content = api.fetch_error_stack(project, name, cur_ms, cur_ems)
                if content:
                    stacks[name] = {'content': content, 'count': item['count']}
            print("  获取到堆栈: {} 条".format(len(stacks)))

    except Exception as e:
        err_msg = str(e)
        # cookie 失效时（302/401/未找到）尝试自动刷新后重试一次
        if not use_web_api and ('302' in err_msg or '401' in err_msg or 'cookie' in err_msg.lower() or 'Cookie' in err_msg):
            print("  [warn] Web API 失败（{}），尝试自动刷新 cookie...".format(err_msg[:80]))
            new_cookie = _refresh_cookie_via_browser()
            if new_cookie:
                try:
                    api2 = RaptorWebAPI(cookie=new_cookie)
                    project_id = api2.get_project_id(project)
                    print("[1/4] 重试 Raptor Web API（刷新 cookie 后）...")
                    cur_rows, cur_new, _ = api2.fetch_all_errors(project, cur_ms, cur_ems)
                    cur_list = _rows_to_list(cur_rows)
                    official_new = cur_new
                    print("  当前窗口: {} 条，官方首现: {} 条".format(len(cur_list), len(official_new)))
                    print("[2/4] 拉取对比窗口数据...")
                    prev_rows, _, _ = api2.fetch_all_errors(project, prv_ms, prv_ems)
                    prev_list = _rows_to_list(prev_rows)
                    print("  对比窗口: {} 条".format(len(prev_list)))
                    print("[3/4] 聚合汇总数据...")
                    cur_total  = sum(r['count'] for r in cur_list)
                    cur_users  = sum(r['users'] for r in cur_list)
                    prev_total = sum(r['count'] for r in prev_list)
                    prev_users = sum(r['users'] for r in prev_list)
                    cur_summary  = _make_summary_stub(cur_total, cur_users)
                    prev_summary = _make_summary_stub(prev_total, prev_users)
                    use_web_api = True
                    error_items_for_stack = sorted(
                        [r for r in cur_list if r.get('level') == 'ERROR'],
                        key=lambda x: x['count'], reverse=True
                    )[:STACK_TOP_N]
                    if error_items_for_stack:
                        print("[3.5/4] 拉取 ERROR 级别堆栈（top {}）...".format(len(error_items_for_stack)))
                        for item in error_items_for_stack:
                            name = item['name']
                            content_stack = api2.fetch_error_stack(project, name, cur_ms, cur_ems)
                            if content_stack:
                                stacks[name] = {'content': content_stack, 'count': item['count']}
                        print("  获取到堆栈: {} 条".format(len(stacks)))
                except Exception as e2:
                    print("  [warn] 重试仍失败（{}），降级到 MCP 模式".format(e2))
            else:
                print("  [warn] cookie 刷新失败，降级到 MCP 模式")
        else:
            print("  [warn] Raptor Web API 不可用（{}），降级到 MCP 模式".format(err_msg[:120]))

    # ── 模式 B：MCP 降级 ──────────────────────────────────────────────────────
    if not use_web_api:
        print("[1/5] MCP 模式：拉取当前窗口数据...")
        s1 = MCPSession(timeout=120)
        try:
            cur_info  = fetch_error_list(s1, project, cur_start, cur_end, level="INFO")
            cur_err   = fetch_error_list(s1, project, cur_start, cur_end, level="ERROR")
            cur_summary = fetch_summary(s1, project, cur_start, cur_end)
            print("  INFO: {} 条  ERROR: {} 条".format(len(cur_info), len(cur_err)))
        finally:
            s1.close()

        print("[2/5] 拉取对比窗口数据...")
        s2 = MCPSession(timeout=120)
        try:
            prev_info = fetch_error_list(s2, project, prev_start, prev_end, level="INFO")
            prev_err  = fetch_error_list(s2, project, prev_start, prev_end, level="ERROR")
            prev_summary = fetch_summary(s2, project, prev_start, prev_end)
            print("  INFO: {} 条  ERROR: {} 条".format(len(prev_info), len(prev_err)))
        finally:
            s2.close()

        # 合并 INFO + ERROR，统一格式
        err_names = {x['name'] for x in cur_err}
        cur_list = [{**x, 'level': 'ERROR' if x['name'] in err_names else 'INFO',
                     'users': 0, 'status': 0} for x in cur_info]
        prev_list = [{**x, 'level': 'INFO', 'users': 0, 'status': 0} for x in prev_info]

    # ── 堆栈分析（ERROR 级别，MCP 模式下才需要单独拉）────────────────────────
    error_items = [r for r in cur_list if r.get('level') == 'ERROR']
    if not use_web_api and error_items:
        print("[3/4] 拉取 ERROR 级别堆栈（top {}）...".format(STACK_TOP_N))
        s3 = MCPSession(timeout=120)
        try:
            stacks = fetch_error_stacks(s3, project, cur_start, cur_end,
                                        error_items[:STACK_TOP_N], top_n=STACK_TOP_N)
            print("  获取到堆栈: {} 条".format(len(stacks)))
        finally:
            s3.close()

    print("[4/4] 数据处理 & 生成报告...")
    processed = process(cur_list, prev_list,
                        official_new_errors=official_new)
    new_status = '（官方，{}条）'.format(len(processed['new_errors'])) if processed['official_new_available'] else '（官方数据不可用）'
    print("  首现: {}  高危: {}  暴涨: {}".format(
        new_status,
        len(processed['critical_persistent']),
        len(processed['surge_errors'])))

    gen_time = datetime.now()
    html_content = generate_html(
        project, cur_start, cur_end, prev_start, prev_end,
        cur_summary, prev_summary, processed, stacks, gen_time,
        project_id=project_id,
    )

    fname = 'error_report_{}_{}.html'.format(
        project, report_time.strftime('%Y%m%d_%H%M'))
    out_path = os.path.join(OUTPUT_DIR, fname)
    with open(out_path, 'w') as f:
        f.write(html_content)

    print()
    mode_str = '✓ Raptor Web API（官方 TAG + 官方首现）' if use_web_api else '⚠ MCP 降级模式'
    print("✅ 报告已生成：{}".format(out_path))
    print("   数据模式：{}".format(mode_str))
    return out_path


if __name__ == '__main__':
    main()
