/* ═══════════════════════════════════════════════════════════════
   AI UI 测试控制台 · 前端逻辑（无框架、零构建）

   风格对齐 baguette Device Farm：header（机队统计）/ rail（过滤）/
   wall（设备，3:4 面板）/ logs（日志，可拖拽宽度）。

   模型：
     · 单条全局事件流（SSE），每条带 task(会话)/run/device 归属；
     · 会话 = workspace(task)，从 ws-init 起即存在，是日志归属的唯一稳定单元；
     · 日志作用域只有「会话」一维（会话↔设备 1:1）；点 wall 面板 = 选中该设备 → 锁定其会话日志；
     · wall 面板 keep-DOM：只对新增设备插面板，已存在只改 class/文本 → 画面不重拉、不闪。
   ═══════════════════════════════════════════════════════════════ */
'use strict';

const INJECTED = window.__CONSOLE_TOKEN__;
const TOKEN = ((INJECTED && INJECTED !== '__CONSOLE_TOKEN__')
  ? INJECTED
  : (new URLSearchParams(location.search).get('token') || '')).trim();
const $ = (id) => document.getElementById(id);

const MAX_EVENTS = 6000;    // 内存事件上限
const RENDER_LIMIT = 700;   // 一次渲染的行数上限
const STREAM_KEEP = 900;    // DOM 行数上限

const STATUS_LABEL = { active: 'LIVE', idle: 'IDLE', stale: 'STALE' };
const STATUS_ORDER = ['active', 'idle', 'stale'];
const PLATFORM_LABEL = { android: 'Android', harmony: 'Harmony', ios: 'iOS' };
const ACCESS_LABEL = { sandbox: '云模拟器', cloud_device: '云真机', local: '本地真机' };
const LOG_MODES = [
  { key: 'all', label: '测试日志' },
  { key: 'error', label: '问题' },
  { key: 'stage', label: '阶段' },
  { key: 'step', label: '步骤' },
  { key: 'event', label: '事件' },
  { key: 'raw', label: '输出' },
];

const state = {
  events: [],
  devices: [],
  runs: [],
  sessions: [],
  sessionsSet: new Set(),
  overview: {},
  // 设备过滤（facet）：集合 = 「勾选保留」的取值；发现新取值即默认纳入（seed）
  facets: { status: new Set(), platform: new Set(), access: new Set() },
  mode: 'all',          // 日志类型（see LOG_MODES）
  session: null,        // 日志作用域（task）；null = 全部会话
  sessionDevice: {},    // task -> serial（事件设备归属兜底）
  src: {},              // 每设备画面来源：'scrcpy' | 'mjpeg'
  paused: false,
  autoScroll: true,
  visible: 0,           // 当前筛选下可见事件数（增量维护）
  scoped: false,        // 是否已确定日志作用域（手动 / 自动都算）
  autoScoped: false,    // 当前作用域是否为"自动默认选中"
};

/* ── 基础工具 ─────────────────────────────────────────── */
const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const api = (path) => {
  const sep = path.includes('?') ? '&' : '?';
  return fetch(`${path}${sep}token=${encodeURIComponent(TOKEN)}`).then((r) => r.json());
};
const fmtTime = (ts) => {
  const m = String(ts || '').match(/T(\d{2}:\d{2}:\d{2})/);
  return m ? m[1] : '--:--:--';
};
const evTask = (ev) => ev.task || '';
const evDevice = (ev) => ev.device || state.sessionDevice[evTask(ev)] || '';
const shortDev = (s) => (!s ? '' : (/^[\d.]+:/.test(s) ? s : s.slice(0, 8)));
const devHue = (s) => { let h = 0; for (let i = 0; i < (s || '').length; i++) h = ((h * 31) + s.charCodeAt(i)) % 360; return h; };

/* ── 画面（MJPEG / scrcpy）───────────────────────────── */
const canStream = (d) => !!d.session_id;
const SECURE_CTX = typeof window !== 'undefined' && !!window.isSecureContext;
const srcFor = (d) => state.src[d.serial]
  || ((d.scrcpy_url && d.scrcpy_udid && SECURE_CTX) ? 'scrcpy' : 'mjpeg');
function scrcpySrc(d) {
  const base = `/device/${encodeURIComponent(d.serial)}/scrcpy/`;
  const host = (d.scrcpy_url || '').replace(/^https?:\/\//, 'wss://').replace(/\/+$/, '');
  const udid = d.scrcpy_udid || d.adb_address || d.serial;
  const ws = `${host}/?action=proxy-adb&remote=${encodeURIComponent('tcp:8886')}&udid=${encodeURIComponent(udid)}`;
  return `${base}#!action=stream&udid=${encodeURIComponent(udid)}&player=mse&ws=${encodeURIComponent(ws)}`;
}
const srcToggleBtn = (d) => (SECURE_CTX && d.scrcpy_url && d.scrcpy_udid && canStream(d))
  ? `<button class="qa" data-src="${esc(d.serial)}" title="切换画面来源（当前：${srcFor(d) === 'scrcpy' ? 'scrcpy' : '截图'}）">${srcFor(d) === 'scrcpy' ? '⧉' : '◉'}</button>`
  : '';
const reloadBtn = (d) => canStream(d)
  ? `<button class="qa" data-reload="${esc(d.serial)}" title="重连画面流">↻</button>` : '';
function mediaHtml(d) {
  if (srcFor(d) === 'scrcpy' && d.scrcpy_url) {
    return `<iframe src="${esc(scrcpySrc(d))}" allow="autoplay"></iframe>`;
  }
  if (!canStream(d)) {
    return `<div class="fallback">无可用画面流<br>${esc(d.device_type || '')}</div>`;
  }
  const src = `/device/${encodeURIComponent(d.serial)}/mjpeg?token=${encodeURIComponent(TOKEN)}`;
  return `<img alt="${esc(d.serial)}" data-base="${esc(src)}" src="${esc(src)}" onerror="imgError(this)" />`;
}
function imgError(el) {
  if (!el || !el.dataset) return;
  clearTimeout(el._t);
  el._t = setTimeout(() => {
    const base = (el.dataset.base || el.src || '').split('&_r=')[0];
    if (base) el.src = `${base}&_r=${Date.now()}`;
  }, 2500);
}
/** 切换某设备画面来源（scrcpy 内嵌 / 截图流），就地替换画面与按钮。 */
function toggleSrc(serial) {
  const d = state.devices.find((x) => x.serial === serial);
  if (!d) return;
  state.src[serial] = srcFor(d) === 'scrcpy' ? 'mjpeg' : 'scrcpy';
  const screen = document.querySelector(`.tile[data-serial="${CSS.escape(serial)}"] .screen`);
  if (screen) { screen.innerHTML = mediaHtml(d); screen.dataset.media = mediaSig(d); }
  const now = srcFor(d);
  document.querySelectorAll(`.tile[data-serial="${CSS.escape(serial)}"] [data-src]`).forEach((b) => {
    b.textContent = now === 'scrcpy' ? '⧉' : '◉';
    b.title = `切换画面来源（当前：${now === 'scrcpy' ? 'scrcpy' : '截图'}）`;
  });
}
/** 重连画面流（重挂 MJPEG / iframe）。 */
function reloadFeed(serial) {
  const d = state.devices.find((x) => x.serial === serial);
  if (!d) return;
  const screen = document.querySelector(`.tile[data-serial="${CSS.escape(serial)}"] .screen`);
  if (screen) { screen.innerHTML = mediaHtml(d); screen.dataset.media = mediaSig(d); }
}
const mediaSig = (d) => `${srcFor(d)}|${d.session_id || ''}`;

/* ═══ HEADER ═══ */
function renderHeader() {
  $('app-header').innerHTML = `
    <div class="brand">
      <div class="mark"><em>Autotest</em></div>
      <div class="sub">AI UI 测试控制台</div>
    </div>
    <div class="telemetry">
      <div class="stat live"><div class="label">Devices</div>
        <div class="value"><span data-stat="devices">0</span><span class="unit" data-stat="devices-total">/ 0 online</span></div></div>
      <div class="stat cyan"><div class="label">Sessions</div>
        <div class="value"><span data-stat="sessions">0</span><span class="unit">active</span></div></div>
      <div class="stat warn"><div class="label">Events</div>
        <div class="value"><span data-stat="events">0</span><span class="unit">live</span></div></div>
    </div>
    <div class="head-right">
      <span class="url-chip" id="origin" title="点击复制控制台地址（仅本机可访问）"></span>
      <button class="btn" id="pause" title="暂停/继续（快捷键 P）">暂停</button>
      <div class="clock off" id="conn"><span class="led"></span><time data-stat="clock">--:--:--</time></div>
    </div>`;
  const oc = $('origin');
  const addr = `${location.origin}/`;
  oc.textContent = addr;
  oc.addEventListener('click', () => {
    if (!(navigator.clipboard && navigator.clipboard.writeText)) return;
    navigator.clipboard.writeText(addr).then(() => {
      oc.textContent = '已复制 ✓';
      setTimeout(() => { oc.textContent = addr; }, 1200);
    }).catch(() => {});
  });
  $('pause').addEventListener('click', togglePause);
}
function setConn(on) {
  const el = $('conn');
  const off = !on;
  // 值未变则不写：SSE 每条消息都会调用，避免反复改 class 触发无谓重绘
  if (el.classList.contains('off') !== off) el.classList.toggle('off', off);
}
/** 活跃事件数 = 属于「当前会话集合」的事件数（会话结束即归零，与日志面板口径一致）。 */
function activeEventCount() {
  let n = 0;
  for (const e of state.events) if (state.sessionsSet.has(evTask(e))) n++;
  return n;
}
function updateHeaderStats() {
  const o = state.overview;
  document.querySelectorAll('[data-stat="devices"]').forEach((el) => { el.textContent = o.devices_active ?? 0; });
  document.querySelectorAll('[data-stat="devices-total"]').forEach((el) => { el.textContent = `/ ${o.devices_total ?? 0} online`; });
  document.querySelectorAll('[data-stat="sessions"]').forEach((el) => { el.textContent = o.sessions_active ?? 0; });
  document.querySelectorAll('[data-stat="events"]').forEach((el) => { el.textContent = activeEventCount(); });
}
function startClock() {
  const tick = () => {
    const t = new Date(); const p = (n) => String(n).padStart(2, '0');
    document.querySelectorAll('[data-stat="clock"]').forEach((el) => { el.textContent = `${p(t.getHours())}:${p(t.getMinutes())}:${p(t.getSeconds())}`; });
  };
  tick(); setInterval(tick, 1000);
}

/* ═══ RAIL（过滤）═══ */
let railSig = '';
function facetRows(facet, counts, order) {
  return order.map((v) => {
    const label = facet === 'status' ? (STATUS_LABEL[v] || v)
      : facet === 'platform' ? (PLATFORM_LABEL[v] || v)
      : (ACCESS_LABEL[v] || v);
    const on = state.facets[facet].has(v);
    return `<label class="facet">
        <input type="checkbox" data-facet="${facet}" data-value="${esc(v)}" ${on ? 'checked' : ''}>
        <span class="name">${esc(label)}</span>
        <span class="count">${counts[v] || 0}</span>
      </label>`;
  }).join('');
}
function sessionRows() {
  const total = state.sessions.length;
  const head = `<button class="pill-btn ${state.session ? '' : 'active'}" data-session="">
      <span>全部会话</span><span class="tag">${total}</span></button>`;
  const rows = state.sessions.map((s) => {
    const label = s.task + (s.run ? ` · ${s.run}` : '');
    return `<button class="pill-btn ${state.session === s.task ? 'active' : ''}" data-session="${esc(s.task)}"
        title="${esc([s.task, s.run, s.flow_name, s.device_serial].filter(Boolean).join(' · '))}">
        <span>${esc(label)}</span><span class="tag">${esc(s.status || '')}</span></button>`;
  }).join('');
  return head + rows;
}
function modeRows() {
  return LOG_MODES.map((m) => `
    <button class="pill-btn ${state.mode === m.key ? 'active' : ''}" data-mode="${m.key}">
      <span>${esc(m.label)}</span></button>`).join('');
}
function renderRail() {
  const counts = { status: {}, platform: {}, access: {} };
  state.devices.forEach((d) => {
    counts.status[d.status] = (counts.status[d.status] || 0) + 1;
    counts.platform[d.platform] = (counts.platform[d.platform] || 0) + 1;
    counts.access[d.device_type] = (counts.access[d.device_type] || 0) + 1;
  });
  const sig = JSON.stringify({
    s: [...state.facets.status].sort(), p: [...state.facets.platform].sort(),
    a: [...state.facets.access].sort(), c: counts,
    sess: state.sessions.map((x) => x.task + ':' + x.status).join(','), cur: state.session, mode: state.mode,
  });
  if (sig === railSig) return;
  railSig = sig;
  $('app-rail').innerHTML = `
    <section><h3>Status</h3>${facetRows('status', counts.status, STATUS_ORDER)}</section>
    <section><h3>Platform</h3>${facetRows('platform', counts.platform, [...state.facets.platform].sort())}</section>
    <section><h3>Access</h3>${facetRows('access', counts.access, [...state.facets.access].sort())}</section>
    <section><h3>Session</h3>${sessionRows()}</section>
    <section><h3>Log</h3>${modeRows()}</section>`;
}
function bindRail() {
  const rail = $('app-rail');
  rail.addEventListener('change', (e) => {
    const inp = e.target.closest('input[data-facet]');
    if (!inp) return;
    const set = state.facets[inp.dataset.facet];
    if (inp.checked) set.add(inp.dataset.value); else set.delete(inp.dataset.value);
    renderStage();
  });
  rail.addEventListener('click', (e) => {
    const s = e.target.closest('[data-session]');
    if (s) { setSession(s.dataset.session || null); return; }
    const m = e.target.closest('[data-mode]');
    if (m) { state.mode = m.dataset.mode; railSig = ''; renderRail(); renderStream(); }
  });
}

/* ═══ STAGE / WALL ═══ */
function visibleDevices() {
  return state.devices.filter((d) =>
    state.facets.status.has(d.status) &&
    state.facets.platform.has(d.platform) &&
    state.facets.access.has(d.device_type));
}
function tileName(d) { return d.flow_name || d.run || '空闲设备'; }
function tileHtml(d) {
  const st = d.status || 'idle';
  const selected = (state.session && d.task && d.task === state.session) ? ' selected' : '';
  const ext = d.scrcpy_url
    ? `<a class="qa" href="${esc(d.scrcpy_url)}" target="_blank" rel="noopener" title="新窗口打开 scrcpy">↗</a>` : '';
  return `<div class="tile${selected}" data-serial="${esc(d.serial)}" data-state="${esc(st)}" title="${esc(d.serial)}">
      <span class="reg tl"></span><span class="reg tr"></span><span class="reg bl"></span><span class="reg br"></span>
      <div class="tile-head">
        <div>
          <h3 class="tile-name">${esc(tileName(d))}</h3>
          <div class="tile-udid">${esc(shortDev(d.serial))} · ${esc(d.device_type || '')}</div>
        </div>
        <span class="tile-status" data-state="${esc(st)}"><span class="led"></span>${esc(STATUS_LABEL[st] || st)}</span>
      </div>
      <div class="tile-quick">${srcToggleBtn(d)}${reloadBtn(d)}${ext}</div>
      <div class="screen" data-serial="${esc(d.serial)}" data-media="${esc(mediaSig(d))}">${mediaHtml(d)}</div>
      <div class="tile-readout">
        <div class="col"><div class="k">Stage</div><div class="v ${st === 'active' ? 'lime' : 'dim'}">${esc(d.current_stage || '—')}</div></div>
        <div class="col"><div class="k">Session</div><div class="v">${esc(d.task || '—')}</div></div>
        <div class="col"><div class="k">Feed</div><div class="v">${esc(srcFor(d) === 'scrcpy' ? 'scrcpy' : '截图')}</div></div>
      </div>
    </div>`;
}
function updateTile(el, d) {
  const st = d.status || 'idle';
  el.dataset.state = st;
  el.classList.toggle('selected', !!(state.session && d.task && d.task === state.session));
  const name = el.querySelector('.tile-name'); if (name) name.textContent = tileName(d);
  const udid = el.querySelector('.tile-udid'); if (udid) udid.textContent = `${shortDev(d.serial)} · ${d.device_type || ''}`;
  const status = el.querySelector('.tile-status');
  if (status) { status.dataset.state = st; status.innerHTML = `<span class="led"></span>${esc(STATUS_LABEL[st] || st)}`; }
  const stageV = el.querySelector('.tile-readout .col:nth-child(1) .v');
  if (stageV) { stageV.textContent = d.current_stage || '—'; stageV.className = `v ${st === 'active' ? 'lime' : 'dim'}`; }
  const sessV = el.querySelector('.tile-readout .col:nth-child(2) .v'); if (sessV) sessV.textContent = d.task || '—';
  const feedV = el.querySelector('.tile-readout .col:nth-child(3) .v'); if (feedV) feedV.textContent = srcFor(d) === 'scrcpy' ? 'scrcpy' : '截图';
  const screen = el.querySelector('.screen');
  if (screen && screen.dataset.media !== mediaSig(d)) { screen.innerHTML = mediaHtml(d); screen.dataset.media = mediaSig(d); }
}
function renderStage() {
  const stage = $('app-stage');
  let head = stage.querySelector('.stage-head');
  let grid = stage.querySelector('.grid');
  if (!head || !grid) {
    stage.innerHTML = `<div class="stage-head"><span class="num">0</span><span class="of">/ 0</span><span class="lab">Devices</span></div><div class="grid"></div>`;
    head = stage.querySelector('.stage-head'); grid = stage.querySelector('.grid');
  }
  const list = visibleDevices();
  head.querySelector('.num').textContent = list.length;
  head.querySelector('.of').textContent = `/ ${state.devices.length}`;
  const want = new Set(list.map((d) => d.serial));
  [...grid.children].forEach((c) => { if (!c.dataset.serial || !want.has(c.dataset.serial)) c.remove(); });
  if (!list.length) {
    if (!grid.querySelector('.grid-empty')) {
      grid.innerHTML = '<div class="grid-empty">暂无设备。设备创建后将自动出现在这里。</div>';
    }
    return;
  }
  const ph = grid.querySelector('.grid-empty'); if (ph) ph.remove();
  list.forEach((d) => {
    const cur = grid.querySelector(`.tile[data-serial="${CSS.escape(d.serial)}"]`);
    if (cur) { updateTile(cur, d); return; }
    grid.insertAdjacentHTML('beforeend', tileHtml(d));
  });
}
function bindStage() {
  $('app-stage').addEventListener('click', (e) => {
    const tg = e.target.closest('[data-src]');
    if (tg) { e.stopPropagation(); toggleSrc(tg.dataset.src); return; }
    const rl = e.target.closest('[data-reload]');
    if (rl) { e.stopPropagation(); reloadFeed(rl.dataset.reload); return; }
    if (e.target.closest('a')) return;   // 新窗口链接不触选中
    const tile = e.target.closest('.tile');
    if (!tile) return;
    const d = state.devices.find((x) => x.serial === tile.dataset.serial);
    setSession(d && d.task ? d.task : null);
  });
}

/* ═══ 日志 ═══ */
function passes(ev) {
  if (!state.sessionsSet.has(evTask(ev))) return false;
  if (state.session && evTask(ev) !== state.session) return false;
  if (state.mode === 'all') return ev.kind !== 'raw';
  if (state.mode === 'error') return ['error', 'fatal', 'warn'].includes(ev.level);
  return ev.kind === state.mode;
}
function recountVisible() {
  let n = 0;
  for (const e of state.events) if (passes(e)) n++;
  state.visible = n;
  return n;
}
function rawRowHtml(ev, badge, dev, tag) {
  const text = ev.text || '';
  const lines = text.split('\n').length;
  const multi = lines > 2;
  const cmd = (ev.details && ev.details.cmd) || '';
  const cmdChip = cmd ? `<span class="raw-cmd" title="${esc(cmd)}">${esc(cmd)}</span>` : '';
  const more = multi ? `<button class="raw-more" data-lines="${lines}">展开 ${lines} 行 ▾</button>` : '';
  return `<div class="row ${esc(ev.level || 'info')} raw${multi ? ' has-more' : ''}">
      <div class="time">${fmtTime(ev.ts)}</div>
      <div class="msg raw-msg">
        <div class="raw-head"><span class="badge raw">输出</span>${dev}${tag}${cmdChip}</div>
        <pre class="raw-pre">${esc(text)}</pre>${more}
      </div></div>`;
}
function rowHtml(ev) {
  const badge = (ev.kind === 'event' && ev.event === 'command.executed') ? 'command' : ev.kind;
  const dev = !state.session && evDevice(ev)
    ? `<span class="dev-tag" style="--dh:${devHue(evDevice(ev))}">${esc(shortDev(evDevice(ev)))}</span>` : '';
  const tag = !state.session && evTask(ev) ? `<span class="run-tag">${esc(evTask(ev))}</span>` : '';
  if (ev.kind === 'raw') return rawRowHtml(ev, badge, dev, tag);
  return `<div class="row ${esc(ev.level || 'info')}">
      <div class="time">${fmtTime(ev.ts)}</div>
      <div class="msg">
        <span class="badge ${esc(badge)}">${esc(badge)}</span>
        <span class="txt">${dev}${tag}${esc(ev.text)}</span>
      </div></div>`;
}
const pending = [];
let flushScheduled = false;
function appendRowBatch(list) {
  if (state.paused) return;
  const html = [];
  for (const ev of list) if (passes(ev)) html.push(rowHtml(ev));
  if (!html.length) return;
  const stream = $('stream');
  if (stream.querySelector('.empty')) stream.replaceChildren();
  stream.insertAdjacentHTML('beforeend', html.join(''));
  while (stream.childElementCount > STREAM_KEEP) stream.removeChild(stream.firstChild);
  if (state.autoScroll) stream.scrollTop = stream.scrollHeight;
}
function flushPending() {
  flushScheduled = false;
  const batch = pending.splice(0, pending.length);
  $('m-events').textContent = state.visible;
  appendRowBatch(batch);
}
function scheduleFlush() {
  if (flushScheduled) return;
  flushScheduled = true;
  if (typeof requestAnimationFrame === 'function') requestAnimationFrame(flushPending);
  else setTimeout(flushPending, 60);
}
function renderStream() {
  const stream = $('stream');
  const list = state.events.filter(passes).slice(-RENDER_LIMIT);
  recountVisible();
  if (!list.length) {
    $('m-events').textContent = 0;
    const active = [];
    if (state.session) active.push(`会话 ${state.session}`);
    if (state.mode !== 'all') active.push(`类型「${state.mode}」`);
    let why = '';
    if (state.events.length && !state.sessionsSet.size) why = '当前没有进行中的会话（测试已结束）';
    else if (state.events.length && state.events.some((e) => !state.sessionsSet.has(evTask(e)))) why = '已结束 / 已清理的会话已隐藏';
    else if (state.events.some((e) => e.kind === 'raw')) why = '有引擎原始输出，左侧「日志 → 输出」查看';
    stream.innerHTML = `<div class="empty" style="color:var(--dim);padding:36px 12px;text-align:center">${
      active.length ? `当前筛选（${esc(active.join(' · '))}）没有匹配的日志` : '暂无日志事件'
    }${why ? `<br><span style="color:var(--muted)">（${why}）</span>` : ''}</div>`;
    return;
  }
  stream.innerHTML = list.map(rowHtml).join('');
  stream.scrollTop = stream.scrollHeight;
  $('m-events').textContent = state.visible;
}
let lastSeq = 0;
function addEvent(ev) {
  if (ev && ev._seq && ev._seq <= lastSeq) return;
  if (ev && ev._seq) lastSeq = ev._seq;
  state.events.push(ev);
  if (passes(ev)) state.visible += 1;
  if (state.events.length > MAX_EVENTS * 1.25) {
    const removed = state.events.splice(0, state.events.length - MAX_EVENTS);
    for (const e of removed) if (passes(e)) state.visible -= 1;
  }
  pending.push(ev);
  scheduleFlush();
}
let progressSig = '';
function renderProgress() {
  const el = $('progress');
  const run = (state.session && state.runs.find((r) => r.task === state.session))
    || state.runs.find((r) => r.status === 'running')
    || state.runs[0];
  if (!run || !(run.stages || []).length) {
    if (progressSig !== '') { progressSig = ''; el.classList.remove('show'); el.innerHTML = ''; }
    return;
  }
  const sig = `${run.task}|${run.run}|` + run.stages.map((s) => `${s.id}:${s.status}`).join(',');
  if (sig === progressSig) return;
  progressSig = sig;
  el.classList.add('show');
  el.innerHTML = run.stages.map((s) =>
    `<span class="stage-node ${esc(s.status)}" title="${esc(s.desc)}">${esc(s.id)}</span>`).join('');
}

/* ── 选择 / 作用域 ─────────────────────────────────────── */
function setSession(task) {
  state.session = task || null;
  state.scoped = true;
  state.autoScoped = false;
  railSig = '';
  renderRail();
  renderStage();
  renderProgress();
  renderStream();
}
function togglePause() {
  state.paused = !state.paused;
  const b = $('pause');
  b.textContent = state.paused ? '继续' : '暂停';
  b.classList.toggle('active', state.paused);
  if (!state.paused) renderStream();
}

/* ── 数据刷新 ─────────────────────────────────────────── */
async function refreshOverview() {
  try {
    state.overview = await api('/api/overview');
    updateHeaderStats();
  } catch (_) {}
}
function seedFacets() {
  state.devices.forEach((d) => {
    if (d.status) state.facets.status.add(d.status);
    if (d.platform) state.facets.platform.add(d.platform);
    if (d.device_type) state.facets.access.add(d.device_type);
  });
}
let sesSig = '';
async function refreshState() {
  try {
    const [dv, rn, ss] = await Promise.all([api('/api/devices'), api('/api/runs'), api('/api/sessions')]);
    state.devices = dv.devices || [];
    state.runs = rn.runs || [];
    state.sessions = ss.sessions || [];
    seedFacets();
    state.sessionDevice = {};
    state.devices.forEach((d) => { if (d.task) state.sessionDevice[d.task] = d.serial; });
    state.sessions.forEach((s) => { if (s.task && s.device_serial && !state.sessionDevice[s.task]) state.sessionDevice[s.task] = s.device_serial; });
    state.sessionsSet = new Set(state.sessions.map((s) => s.task));

    let scopeChanged = false;
    const newSesSig = [...state.sessionsSet].sort().join(',');
    if (newSesSig !== sesSig) { sesSig = newSesSig; scopeChanged = true; railSig = ''; }
    if (state.autoScoped && state.session && !state.sessionsSet.has(state.session)) {
      state.session = null; state.autoScoped = false; scopeChanged = true;
    }
    if (!state.scoped && !state.session) {
      const s = state.sessions.find((x) => x.status === 'running') || state.sessions[0];
      if (s) { state.session = s.task; state.scoped = true; state.autoScoped = true; scopeChanged = true; }
    }
    if (scopeChanged) railSig = '';
    renderRail();
    renderStage();
    renderProgress();
    if (scopeChanged) renderStream();
    updateHeaderStats();
  } catch (_) {}
}

/* ── 拖拽调整日志宽度（持久化）───────────────────────── */
function initResizer() {
  const KEY = 'catpaw.console.logsWidth';
  const DEF = 440, MIN = 320, MAX = 760, RAIL = 260, RZ = 8, MIN_STAGE = 360;
  const main = document.querySelector('.app > main');
  const handle = $('app-resizer');
  if (!main || !handle) return;
  let width = DEF;
  const maxWidth = () => Math.max(MIN, Math.min(MAX, main.clientWidth - RAIL - RZ - MIN_STAGE));
  const store = () => { try { localStorage.setItem(KEY, String(width)); } catch (_) {} };
  const set = (req, persist) => {
    width = Math.round(Math.max(MIN, Math.min(maxWidth(), req)));
    main.style.setProperty('--logs-width', width + 'px');
    handle.setAttribute('aria-valuenow', String(width));
    if (persist !== false) store();
  };
  try { const v = Number(localStorage.getItem(KEY)); if (Number.isFinite(v) && v > 0) width = v; } catch (_) {}
  set(width, false);
  let drag = null;
  handle.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    drag = { x: e.clientX, width };
    handle.setPointerCapture(e.pointerId);
    document.body.classList.add('resizing');
    e.preventDefault();
  });
  handle.addEventListener('pointermove', (e) => { if (drag) set(drag.width + drag.x - e.clientX, false); });
  const finish = (e) => {
    if (!drag) return; drag = null;
    document.body.classList.remove('resizing');
    if (handle.hasPointerCapture(e.pointerId)) handle.releasePointerCapture(e.pointerId);
    store();
  };
  handle.addEventListener('pointerup', finish);
  handle.addEventListener('pointercancel', finish);
  handle.addEventListener('dblclick', () => set(DEF));
  handle.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') set(width + 20);
    else if (e.key === 'ArrowRight') set(width - 20);
    else if (e.key === 'Home') set(MIN);
    else if (e.key === 'End') set(maxWidth());
    else return;
    e.preventDefault();
  });
  window.addEventListener('resize', () => set(width, false));
}

/* ── 交互绑定 ─────────────────────────────────────────── */
function bindUI() {
  bindRail();
  bindStage();

  const stream = $('stream');
  stream.addEventListener('click', (e) => {
    const b = e.target.closest('.raw-more');
    if (!b) return;
    const row = b.closest('.row');
    const open = row.classList.toggle('expanded');
    b.textContent = open ? '收起 ▴' : `展开 ${b.dataset.lines} 行 ▾`;
  });
  stream.addEventListener('scroll', () => {
    const nearBottom = stream.scrollHeight - stream.scrollTop - stream.clientHeight < 60;
    state.autoScroll = nearBottom;
    $('jump').classList.toggle('show', !nearBottom && state.events.length > 0);
  });
  $('jump').addEventListener('click', () => {
    state.autoScroll = true;
    $('jump').classList.remove('show');
    stream.scrollTop = stream.scrollHeight;
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.session) setSession(null);
    else if (e.key === 'p' && !/input|textarea/i.test(e.target.tagName)) togglePause();
  });
}

/* ── SSE ──────────────────────────────────────────────── */
function connectSSE(since) {
  const es = new EventSource(`/events?token=${encodeURIComponent(TOKEN)}&since=${since || 0}`);
  es.onopen = () => setConn(true);
  es.onerror = () => setConn(false);
  es.onmessage = (e) => { setConn(true); try { addEvent(JSON.parse(e.data)); } catch (_) {} };
}

/* ── 启动 ─────────────────────────────────────────────── */
async function boot() {
  renderHeader();
  bindUI();
  startClock();
  initResizer();

  await refreshOverview();
  await refreshState();

  let since = 0;
  try {
    const snap = await api('/api/events');
    (snap.events || []).forEach((ev) => state.events.push(ev));
    if (state.events.length > MAX_EVENTS) state.events = state.events.slice(-MAX_EVENTS);
    since = snap.seq || 0;
    lastSeq = since;
    $('m-events').textContent = recountVisible();
  } catch (_) {}

  renderRail();
  renderStage();
  renderProgress();
  renderStream();

  connectSSE(since);
  setInterval(refreshState, 4000);
  setInterval(refreshOverview, 8000);
}

boot();
