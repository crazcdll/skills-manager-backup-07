import { canonicalHash } from './package-contract.mjs';
const escape = (value) => displayText(value).replace(/[&<>"']/gu, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
export function displayText(value) {
  return String(value ?? '').replace(/https?:\/\/[^\s<>"')]+/gu, (raw) => {
    try { const url = new URL(raw); let redacted = false; for (const key of [...url.searchParams.keys()]) if (/token|signature|credential|secret|access.?key|authorization/iu.test(key)) { url.searchParams.delete(key); redacted = true; } return redacted ? `${url.toString()} [敏感查询参数已隐藏]` : raw; } catch { return raw; }
  });
}
const inline = (value) => escape(displayText(value)).replace(/`([^`]+)`/gu, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/gu, '<strong>$1</strong>').replace(/~~([^~]+)~~/gu, '<del>$1</del>');
function diagnosticMessage(validation) {
  const rule = validation.path?.match(/^\/content\/rules\/(\d+)(?:\/(.*))?$/u);
  if (rule && rule[2] === 'execution_level') return `第 ${Number(rule[1]) + 1} 条规则尚未选择“强制”或“推荐”，请先确认执行级别。`;
  if (rule && rule[2]?.startsWith('omissions')) return `请确认第 ${Number(rule[1]) + 1} 条规则是否省略示例，并说明原因。`;
  if (rule && rule[2] === 'title') return `请补充第 ${Number(rule[1]) + 1} 条规则的名称。`;
  return validation.message;
}
const colorCode = (value, language) => {
  const raw = displayText(value); if (!/^(?:js|jsx|javascript|ts|tsx|typescript|java|json)$/iu.test(language)) return escape(raw);
  const expression = /(?:\/\/[^\n]*|\/\*[\s\S]*?\*\/)|(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|\b(?:class|extends|const|let|var|function|return|new|if|else|throw|try|catch|public|private|static|void|import|export|from|async|await|true|false|null|undefined)\b|\b\d+(?:\.\d+)?\b/gu;
  let html = '', cursor = 0;
  for (const match of raw.matchAll(expression)) { html += escape(raw.slice(cursor, match.index)); const type = match[0].startsWith('//') || match[0].startsWith('/*') ? 'comment' : /^["'`]/u.test(match[0]) ? 'string' : /^\d/u.test(match[0]) ? 'number' : 'keyword'; html += `<span class="${type}">${escape(match[0])}</span>`; cursor = match.index + match[0].length; }
  return html + escape(raw.slice(cursor));
};
export function renderMarkdown(text, depth = 0) {
  if (depth > 16) return `<p>${inline(text)}</p>`;
  const lines = String(text ?? '').split(/\r\n|\r|\n/u); let html = '', code = [], marker = null, language = 'text', table = false, list = false, quote = [];
  const closeList = () => { if (list) html += '</ul>'; list = false; };
  const closeTable = () => { if (table) html += '</tbody></table></div>'; table = false; };
  const closeQuote = () => { if (quote.length) html += `<blockquote>${renderMarkdown(quote.join('\n'), depth + 1)}</blockquote>`; quote = []; };
  for (const line of lines) {
    if (!marker) {
      const quoted = line.match(/^\s{0,3}> ?(.*)$/u);
      if (quoted) { closeList(); closeTable(); quote.push(quoted[1]); continue; }
      closeQuote();
    }
    const fence = line.match(/^\s{0,3}(`{3,}|~{3,})(.*)$/u);
    if (marker) { if (fence && fence[1][0] === marker[0] && fence[1].length >= marker.length) { html += `<pre><code>${colorCode(code.join('\n'), language)}</code></pre>`; marker = null; code = []; } else code.push(line); continue; }
    if (fence) { closeList(); closeTable(); marker = fence[1]; language = fence[2].trim(); continue; }
    if (/^\s*\|.+\|\s*$/u.test(line)) {
      closeList(); const cells = line.trim().replace(/^\||\|$/gu, '').split(/(?<!\\)\|/u).map((cell) => cell.trim());
      if (cells.every((cell) => /^:?-+:?$/u.test(cell))) continue;
      if (!table) { html += '<div class="table-wrap"><table><tbody>'; table = true; }
      html += '<tr>' + cells.map((cell) => `<td>${inline(cell)}</td>`).join('') + '</tr>'; continue;
    }
    closeTable();
    const item = line.match(/^\s*(?:[-*+] |\d+[.)] )(.*)$/u);
    if (item) { if (!list) { html += '<ul>'; list = true; } html += `<li>${inline(item[1])}</li>`; continue; }
    closeList();
    const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+)$/u);
    if (heading) { const level = Math.min(6, heading[1].length + 2); html += `<h${level}>${inline(heading[2])}</h${level}>`; }
    else if (line.trim()) html += `<p>${inline(line)}</p>`;
  }
  closeList(); closeTable(); closeQuote(); if (marker) html += `<pre><code>${colorCode(code.join('\n'), language)}</code></pre>`;
  return html;
}
export function generateAgentsIndex(content, source, indexEntries = []) {
  const sourceById = new Map(source.files.map((file) => [file.source_ref, file]));
  const bindings = [], referenceByDoc = new Map(), indexed = new Set(), rows = new Set();
  const cell = (value) => String(value ?? '').replace(/\|/gu, '\\|').replace(/[\r\n]/gu, ' ').trim();
  const add = (reference, scene) => rows.add(`| \`${cell(reference)}\` | ${cell(scene)} |`);
  for (const document of content.documents) {
    const file = sourceById.get(document.source_ref); if (!file) continue;
    const reference = source.type === 'km' ? source.locator.url : file.source_path;
    bindings.push({ reference, document_ref: document.document_ref });
    referenceByDoc.set(document.document_ref, reference);
  }
  for (const entry of indexEntries) {
    const reference = referenceByDoc.get(entry.document_ref); if (!reference) continue;
    add(reference, entry.scene);
    indexed.add(entry.document_ref);
  }
  for (const document of content.documents) {
    const reference = referenceByDoc.get(document.document_ref);
    if (reference && !indexed.has(document.document_ref)) add(reference, document.description);
  }
  return { markdown: ['# 规则集索引', '', '| 规则文件 | 触发条件 |', '| --- | --- |', ...rows, ''].join('\n'), bindings };
}
const originBadge = (item) => {
  const origin = item.provenance?.origin;
  if (origin === 'source_extract') return '';
  const label = ({ agent_generated: 'AI 补充', user_modified: '用户修改' })[origin] || '来源待确认';
  return `<span class="origin">${label}</span>`;
};
const fieldRow = (key, value, badge = '') => `<div class="field"><dt>${escape(key)}:</dt><dd>${badge}${Array.isArray(value) ? `[${value.map(escape).join(', ')}]` : inline(value)}</dd></div>`;
function bodyBlocks(items, fields = []) {
  const out = [];
  const flushFields = () => {
    if (fields.length) out.push(`<dl class="fields">${fields.join('')}</dl>`);
    fields = [];
  };
  for (let i = 0; i < items.length;) {
    const item = items[i++];
    if (item.type !== 'example') {
      const lines = String(item.text || '').split(/\r\n|\r|\n/u), prose = [];
      const flush = () => {
        const text = prose.join('\n').trim();
        if (text) {
          flushFields();
          out.push(`<div class="block">${originBadge(item)}${renderMarkdown(text)}</div>`);
        }
        prose.length = 0;
      };
      for (const line of lines) {
        const field = /^(source|trigger):[ \t]+([^\r\n]+)$/u.exec(line);
        if (field) { flush(); fields.push(fieldRow(field[1], field[2], originBadge(item))); }
        else prose.push(line);
      }
      flush();
      continue;
    }
    flushFields();
    const group = [item];
    while (items[i]?.type === 'example' && items[i].role === item.role) group.push(items[i++]);
    const title = ({ good: '推荐写法', bad: '错误写法', neutral: '示例' })[item.role] || '示例';
    out.push(`<section class="example" data-role="${escape(item.role)}"><header>${title}</header>${group.map((part) => `<div class="code-part"><div class="language">${escape(part.language)}${originBadge(part)}</div>${part.caption ? `<p>${inline(part.caption)}</p>` : ''}<pre><code>${colorCode(part.code, part.language)}</code></pre></div>`).join('')}</section>`);
  }
  flushFields();
  return out.join('');
}
// Only combine an old draft's standalone source ID with its title if the frozen Git heading confirms both.
function sourceHeading(first, title, file, payload) {
  if (first?.type !== 'markdown' || first.provenance?.origin !== 'source_extract' || !/^[A-Z][A-Z0-9_-]*-\d+$/u.test(first.text)) return null;
  const spans = first.provenance.source_spans || [], span = spans[0], bytes = payload?.get(file?.package_path);
  if (!bytes || spans.length !== 1 || span.source_ref !== file.source_ref) return null;
  const raw = Buffer.from(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const begin = span.byte_start ? raw.lastIndexOf(10, span.byte_start - 1) + 1 : 0, next = raw.indexOf(10, span.byte_end);
  const line = raw.toString('utf8', begin, next < 0 ? raw.length : next).trim();
  if (!/^#{1,6}[ \t]+/u.test(line) || line.replace(/^#{1,6}[ \t]+/u, '') !== `${first.text} ${title}`) return null;
  // Some Markdown sources call the execution level "severity". Only show that spelling when attested.
  const header = next < 0 ? '' : raw.toString('utf8', next + 1, next + 8192).trimStart().split(/\r?\n[ \t]*\r?\n/u)[0];
  const level = header.match(/^severity:[ \t]*\[(强制|推荐|建议)\][ \t]*\r?$/mu)?.[1];
  return { id: first.text, level };
}
function ruleArticle(rule, heading, number) {
  const metadata = rule.metadata || {}, body = rule.body || [];
  const start = heading ? 1 : 0, desc = body[start];
  const groupedDescription = desc?.type === 'markdown' && typeof metadata.description === 'string' && (desc.text === metadata.description || desc.text === `description: ${metadata.description}`);
  const levelKey = ['mandatory', 'recommended'].includes(rule.execution_level) ? rule.execution_level : 'pending';
  const level = { mandatory: '强制', recommended: '推荐', pending: '待确认' }[levelKey];
  const originalLevel = heading?.level && (heading.level === level || (heading.level === '建议' && level === '推荐')) ? heading.level : null;
  const otherStacks = (rule.tech_stacks || []).filter(x => ![...(metadata.language || []), ...(metadata.framework || [])].some(y => y.toLowerCase() === x.toLowerCase()));
  const rows = [
    ['ruleType', metadata.ruleType],
    ['description', metadata.description, groupedDescription ? originBadge(desc) : ''],
    ...(originalLevel ? [['severity', [originalLevel]]] : []),
    ['language', metadata.language], ['framework', metadata.framework], ['stage', rule.stages],
    ['tech_stacks', otherStacks.length ? otherStacks : undefined], ['applicability_tags', rule.applicability_tags?.length ? rule.applicability_tags : undefined],
    ['level', metadata.level], ['ruleVersion', metadata.ruleVersion],
    [originalLevel ? '风险等级' : 'severity', metadata.severity?.length ? metadata.severity : undefined],
  ].filter(([, value]) => value !== undefined && value !== null && value !== '');
  return `<article class="rule" data-rule="${escape(rule.rule_ref)}" id="${escape(rule.rule_ref)}"><div class="rule-top"><span>${heading ? '编号 ' : ''}${escape(number)}</span><strong class="execution-level" data-level="${levelKey}">${level}</strong></div><h3>${escape(rule.title)}</h3>${bodyBlocks(body.slice(start + (groupedDescription ? 1 : 0)), rows.map(([key,value,badge]) => fieldRow(key, value, badge)))}<div class="omissions">${(rule.omissions || []).map((item) => `<p>${item.role === 'good' ? '正例' : '反例'}省略：${escape(item.reason)}</p>`).join('')}</div></article>`;
}
// Embedded as static code in the offline preview. Source values come only from escaped DOM text.
function bindPreviewNavigation() {
  const byId = (id) => document.getElementById(id);
  const search = byId('rule-search');
  const articles = [...document.querySelectorAll('article.rule')];
  const documents = [...document.querySelectorAll('section.document')];
  const entries = new Map(articles.map((article) => {
    const desc = [...article.querySelectorAll('dt')].find((dt) => dt.textContent === 'description:');
    const id = article.querySelector('.rule-top span').textContent;
    const title = article.querySelector('h3').textContent;
    return [article.dataset.rule, [id, title, desc?.nextElementSibling?.textContent, article.dataset.rule].join(' ').toLowerCase()];
  }));
  const buttons = [...document.querySelectorAll('[data-go]')];
  function markCurrent(article) {
    for (const button of buttons) {
      if (article && button.dataset.go === article.dataset.rule) button.setAttribute('aria-current', 'location');
      else button.removeAttribute('aria-current');
    }
  }
  function filter() {
    byId('clear-search').hidden = search.value.length === 0;
    const terms = search.value.toLowerCase().trim().split(/\s+/u).filter(Boolean);
    const matched = articles.filter(a => terms.every(term => entries.get(a.dataset.rule).includes(term)));
    const refs = new Set(matched.map(a => a.dataset.rule));
    for (const a of articles) a.hidden = !refs.has(a.dataset.rule);
    for (const button of buttons) button.hidden = !refs.has(button.dataset.go);
    for (const doc of documents) doc.hidden = terms.length > 0 && !doc.querySelector('article.rule:not([hidden])');
    byId('search-count').textContent = terms.length ? '匹配 ' + matched.length + ' / ' + articles.length + ' 条' : '全部 ' + articles.length + ' 条';
    byId('no-matches').hidden = !terms.length || matched.length > 0;
    markCurrent(matched[0]);
  }
  function go(ref) {
    const article = byId(ref);
    if (!article?.matches('article.rule:not([hidden])')) return;
    markCurrent(article);
    article.scrollIntoView({ block: 'start' });
  }
  search.addEventListener('input', filter);
  byId('clear-search').onclick = () => { search.value = ''; filter(); search.focus(); };
  for (const button of buttons) button.onclick = () => go(button.dataset.go);
  filter();
  go(location.hash.slice(1));
  window.addEventListener('hashchange', () => go(location.hash.slice(1)));
}
export async function renderPreview({ manifest, content, agentsIndex, questions = [], validation = null, requestedRef = null, refOrigin = null, payload }) {
  const rules = new Map((content.rules || []).map((rule) => [rule.rule_ref, rule]));
  const sourceFiles = new Map((manifest.source?.files || []).map((f) => [f.source_ref, f]));
  const directoryButtons = [];
  const articles = (content.documents || []).map((doc) => `<section class="document"><h2>${escape(doc.title)}</h2><p class="muted">${escape(doc.description)}</p>${(doc.content || []).map((item) => {
    if (item.type !== 'rule') return bodyBlocks([item]);
    const rule = rules.get(item.rule_ref); if (!rule) return '<p class="error">规则引用不存在</p>';
    const heading = sourceHeading(rule.body?.[0], rule.title, sourceFiles.get(doc.source_ref), payload);
    const number = heading?.id ?? `待编号 ${String(directoryButtons.length + 1).padStart(2, '0')}`;
    directoryButtons.push(`<button data-go="${escape(rule.rule_ref)}"><span class="directory-id">${escape(number)}</span> ${escape(rule.title || rule.rule_ref)}</button>`);
    return ruleArticle(rule, heading, number);
  }).join('')}</section>`).join('');
  const questionHtml = questions.length ? `<section class="notice"><h2>待你确认</h2><ol>${questions.map((question) => `<li>${escape(question.message || question.explanation || question.question_ref)}</li>`).join('')}</ol></section>` : '';
  const errorHtml = validation ? `<section class="notice"><h2>还不能生成最终包</h2><p>${escape(diagnosticMessage(validation))}</p><details><summary>诊断详情</summary><p class="muted">${escape(validation.code)} · ${escape(validation.path)}</p></details></section>` : '';
  const exclusions = (content.coverage || []).filter((unit) => unit.disposition === 'excluded');
  const sourceLabel = manifest.source?.type === 'git' ? manifest.source.revision.commit : `学城历史步骤 ${manifest.source?.revision.step_version}`;
  const platformFields = manifest.rule_set ? `规则集名称：${escape(manifest.rule_set.name)}<br>维护人意向：${escape(manifest.rule_set.owner_mis)} · ${escape(manifest.scope_level || "L2")} / ${escape({frontend:"前端",backend:"后端"}[manifest.standard_domain] || manifest.standard_domain || "待确认")}<br>适用范围：${escape(manifest.rule_set.applicability_scope)}` : "规则集名称、展示名称、Owner、治理域和适用范围：待平台填写";
  const displayName = manifest.rule_set?.display_name || "规范原材料转换预览";
  const displayDescription = manifest.rule_set?.description || "以下内容是本地对 Git/学城原材料的规范化结果，平台导入时再填写规则集元信息。";
  const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'"><title>${escape(displayName)} · 规范预览</title><style>
:root{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;color:#172b3a;background:#f4f7f8}*{box-sizing:border-box}body{margin:0}.shell{max-width:1536px;margin:0 auto;padding:34px 28px}.hero{padding:30px;background:#073c35;color:white;border-radius:16px}.hero h1{font-size:28px;margin:10px 0}.hero p{color:#cde6df;line-height:1.8}.badge{font-size:12px;color:#b9e8d9}.summary{display:flex;gap:12px;margin:22px 0}.summary span{background:white;border:1px solid #dde7e3;border-radius:10px;padding:14px}.layout{display:grid;grid-template-columns:clamp(300px,23vw,350px) minmax(0,1fr);gap:24px}nav{position:sticky;top:20px;align-self:start;background:white;border-radius:12px;padding:16px}.directory button{display:block;width:100%;border:0;background:#f1f6f4;text-align:left;margin:8px 0;padding:10px;color:#075f4d;cursor:pointer}.rule{background:white;border:1px solid #dce6e2;border-radius:13px;padding:22px;margin:18px 0}.rule-top{display:flex;justify-content:space-between;color:#087761;font:12px monospace}h2{font-size:21px}h3{font-size:19px;margin:14px 0}p,li{line-height:1.85;font-size:14px;overflow-wrap:anywhere}.muted{color:#667e86;font-size:12px}.origin{display:inline-block;background:#edf3f6;color:#657a84;border-radius:4px;padding:3px 6px;font-size:11px;margin:8px 0}.example{background:#102337;color:#dbe7f1;border-radius:10px;overflow:hidden;margin:12px 0}.example header{display:flex;justify-content:space-between;background:#dff0e8;color:#095e47;padding:10px 14px;font-size:13px}.example p{padding:0 14px}pre{padding:16px;background:#102337;color:#dbe7f1;border-radius:8px;overflow:auto;white-space:pre-wrap;word-break:break-word;line-height:1.7;font-size:12px}p code,li code{background:#edf3f4;padding:2px 4px;border-radius:3px}.keyword{color:#c69ef5}.string{color:#b7d995}.comment{color:#8299a7}.number{color:#e5bb7d}.notice{background:#fff8e5;border:1px solid #efdaa4;border-radius:12px;padding:18px;margin:16px 0}.notice h2{font-size:16px}.error{color:#a53333}.omissions{color:#7d744d;font-size:12px}table{border-collapse:collapse;width:100%;font-size:13px}td{border:1px solid #dbe3e7;padding:10px;vertical-align:top}.table-wrap{overflow:auto}details{background:white;border-radius:10px;padding:18px;margin:14px 0}summary{cursor:pointer;color:#096e58}footer{font-size:12px;color:#6b7e85;margin-top:28px}.hash{font-family:monospace;overflow-wrap:anywhere;font-size:11px}@media(max-width:760px){.layout{display:block}nav{position:static}.summary{flex-wrap:wrap}}[hidden]{display:none!important}
.fields{margin:8px 0 12px}.field{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:.5em;margin:3px 0;font-size:14px;line-height:1.6}.field dt{font:12px/1.9 ui-monospace,monospace;color:#516570}.field dd{margin:0;overflow-wrap:anywhere}.field .origin,.language .origin{margin:0 6px}.language{color:#a7c9d6;padding:8px 14px 0;font:12px/1.5 ui-monospace,monospace}.code-part pre{margin:0;border-radius:0;padding-top:4px}.code-part+.code-part{border-top:1px solid #405464}.example[data-role="bad"] header{background:#f8e8e6;color:#84392c}.origin-note{color:#526770}.origin{font-weight:600}
nav label{display:block;margin-top:12px;font-size:13px;color:#516570}
.directory-id{display:inline-block;color:#425d66;font:600 12px/1.5 ui-monospace,monospace;margin-inline-end:.25em;max-width:100%;vertical-align:baseline}
.rule{scroll-margin-top:16px}.rule-top{align-items:center;gap:12px}
.execution-level{flex:none;border:1px solid #cbd5e1;border-radius:6px;padding:3px 8px;background:#f1f5f9;color:#475569;font:600 12px/1.5 system-ui,sans-serif}
.execution-level[data-level="mandatory"]{color:#991b1b;background:#fef2f2;border-color:#fecaca}
.execution-level[data-level="recommended"]{color:#854d0e;background:#fffbeb;border-color:#edcd80}
.code-part pre{white-space:pre;word-break:normal}
.directory button[aria-current="location"]{background:#dcece6;box-shadow:inset 3px 0 #087761;font-weight:600}
@media(max-width:760px){.shell{padding:16px}.rule{padding:16px}}
.search-field{display:flex;align-items:center;margin-top:6px;border:1px solid #abcabd;border-radius:5px;background:white}
.search-field:focus-within{border-color:#236957}
.search-field input{flex:1;min-width:0;border:0;outline:0;border-radius:5px;background:transparent;padding:8px;font:inherit;font-size:14px}
.search-field button{width:28px;height:28px;margin-right:3px;border:0;border-radius:4px;background:transparent;color:#516570;font:20px/1 system-ui;cursor:pointer}
.search-field button:hover,.search-field button:focus-visible{background:#dff0e8;color:#073c35}
.directory{max-height:50vh;overflow:auto;padding:2px}.directory button{overflow-wrap:anywhere}.directory button:hover{background:#dff0e8}.directory button:focus-visible{outline:2px solid #087761;outline-offset:2px}
</style></head><body><div class="shell"><header class="hero"><span class="badge">编码规范原材料整理助手 · 本地草稿</span><h1>${escape(displayName)}</h1><p>${escape(displayDescription)}<br>${platformFields}</p><p class="hash">${requestedRef ? `${refOrigin === 'remote_default' ? '仓库默认分支' : '输入分支'}：${escape(requestedRef)}<br>` : ""}来源版本：${escape(sourceLabel)}<br>转换内容版本：${escape(manifest.content_digest)}</p></header><details><summary>来源文件 · ${(manifest.source?.files || []).length} 份</summary>${(manifest.source?.files || []).map((file) => `<p>${escape([manifest.source.locator?.root_path,file.source_path].filter(Boolean).join("/"))} · ${file.byte_size} 字节</p>`).join("")}</details><div class="summary"><span>${(content.documents || []).length} 份文档</span><span>${rules.size} 条规则</span><span>${questions.length} 个待确认项</span><span>${exclusions.length} 个排除单元</span></div><details><summary>规则集索引 AGENTS.md</summary>${renderMarkdown(agentsIndex)}</details><details><summary>排除项与处理决定${exclusions.length ? ` · ${exclusions.length} 项排除` : ""}</summary>${exclusions.map((unit) => `<p>${escape(unit.unit_ref)}：${escape(unit.reason)}</p>`).join('') || '<p>没有排除项。</p>'}${(content.resolutions || []).map((r) => `<p>${escape(r.decision)}：${escape(r.explanation)}</p>`).join('')}</details>${questionHtml}${errorHtml}<p class="origin-note">未单独标注的正文和代码为原文摘取；补充或修改会在对应位置注明。</p><div class="layout"><nav aria-label="规则目录"><b>规则目录</b><label for="rule-search">筛选规则</label><div class="search-field"><input type="text" role="searchbox" id="rule-search" placeholder="编号、标题或描述"><button type="button" id="clear-search" aria-label="清空筛选" title="清空筛选" hidden>×</button></div><p id="search-count" role="status" class="muted"></p><div class="directory">${directoryButtons.join('')}</div><p class="muted">通过对话修改内容。预览不会执行上传或发布。</p></nav><main><p id="no-matches" hidden>没有匹配的规则。</p>${articles}</main></div><footer>这是本地预览，尚未在平台生效。规则编号由平台分配。外部图片和链接内容未自动加载；含凭据的 URL 查询参数仅在展示中隐藏，来源快照保持原样。</footer></div><script>
(${bindPreviewNavigation.toString()})();
</script></body></html>`;
  return { html, preview_digest: await canonicalHash({ content_digest: manifest.content_digest, requested_ref: requestedRef, ...(refOrigin ? {refOrigin} : {}), questions, validation, html }) };
}
