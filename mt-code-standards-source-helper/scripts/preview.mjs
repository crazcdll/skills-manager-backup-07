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
export function generateAgentsIndex(content, source) {
  const sourceById = new Map(source.files.map((file) => [file.source_ref, file]));
  const rows = []; const bindings = [];
  const cell = (value) => String(value || '').replace(/\|/gu, '\\|').replace(/[\r\n]/gu, ' ');
  for (const document of content.documents || []) {
    const file = sourceById.get(document.source_ref); if (!file) continue;
    const reference = source.type === 'km' ? source.locator.url : file.source_path;
    const rules = (content.rules || []).filter((rule) => rule.document_ref === document.document_ref);
    const scenes = [...new Set(rules.flatMap((rule) => rule.stages || []))].map((stage) => ({ design: '设计方案', coding: '编写代码', cr: '代码评审' })[stage] || stage).join('、');
    rows.push(`| ${cell(document.title)} | ${cell(document.description || scenes)} | \`${cell(reference)}\` |`);
    bindings.push({ reference, document_ref: document.document_ref });
  }
  return { markdown: '# 规则集索引\n\n| 名称 | 触发场景 | 路径 |\n| --- | --- | --- |\n' + rows.join('\n') + '\n', bindings };
}
export async function renderPreview({ manifest, content, agentsIndex, questions = [], validation = null, requestedRef = null }) {
  const rules = new Map((content.rules || []).map((rule) => [rule.rule_ref, rule]));
  const renderedRules = [];
  const originLabel = { source_extract: '原文摘取', agent_generated: 'AI 补充', user_modified: '用户修改' };
  const block = (item) => `<div class="block"><span class="origin">${escape(originLabel[item.provenance?.origin] || '来源待确认')}</span>${item.type === 'example' ? `<section class="example"><header>${escape({ good: '推荐写法', bad: '错误写法', neutral: '示例' }[item.role])}<small>${escape(item.language)}</small></header>${item.caption ? `<p>${inline(item.caption)}</p>` : ''}<pre><code>${colorCode(item.code, item.language)}</code></pre></section>` : renderMarkdown(item.text)}</div>`;
  let ordinal = 0;
  const articles = (content.documents || []).map((doc) => `<section class="document"><h2>${escape(doc.title)}</h2><p class="muted">${escape(doc.description)}</p>${(doc.content || []).map((item) => {
    if (item.type !== 'rule') return block(item);
    const rule = rules.get(item.rule_ref); if (!rule) return '<p class="error">规则引用不存在</p>';
    renderedRules.push(rule);
    const stackNames = { general: '通用', javascript: 'JavaScript', typescript: 'TypeScript', html: 'HTML', css: 'CSS', vue: 'Vue', react: 'React', mrn: 'MRN', java: 'Java', spring: 'Spring' };
    const stageNames = { design: '方案设计', coding: '编写代码', cr: '代码评审' };
    ordinal += 1; return `<article class="rule" data-rule="${escape(rule.rule_ref)}"><div class="rule-top"><span>待编号 ${String(ordinal).padStart(2, '0')}</span><b>${escape({ mandatory: '强制', recommended: '推荐' }[rule.execution_level] || '执行级别待确认')}</b></div><h3>${escape(rule.title)}</h3><p class="muted">${escape((rule.tech_stacks || []).map((value) => stackNames[value] || value).join(' / '))} · ${escape((rule.stages || []).map((value) => stageNames[value] || value).join(' / '))}</p>${(rule.body || []).map(block).join('')}<div class="omissions">${(rule.omissions || []).map((item) => `<p>${item.role === 'good' ? '正例' : '反例'}省略：${escape(item.reason)}</p>`).join('')}</div></article>`;
  }).join('')}</section>`).join('');
  const questionHtml = questions.length ? `<section class="notice"><h2>待你确认</h2><ol>${questions.map((question) => `<li>${escape(question.message || question.explanation || question.question_ref)}</li>`).join('')}</ol></section>` : '';
  const errorHtml = validation ? `<section class="notice"><h2>还不能生成最终包</h2><p>${escape(diagnosticMessage(validation))}</p><details><summary>诊断详情</summary><p class="muted">${escape(validation.code)} · ${escape(validation.path)}</p></details></section>` : '';
  const exclusions = (content.coverage || []).filter((unit) => unit.disposition === 'excluded');
  const sourceLabel = manifest.source?.type === 'git' ? manifest.source.revision.commit : `学城历史步骤 ${manifest.source?.revision.step_version}`;
  const platformFields = manifest.rule_set ? `规则集名称：${escape(manifest.rule_set.name)}<br>维护人意向：${escape(manifest.rule_set.owner_mis)} · ${escape(manifest.scope_level || "L2")} / ${escape({frontend:"前端",backend:"后端"}[manifest.standard_domain] || manifest.standard_domain || "待确认")}<br>适用范围：${escape(manifest.rule_set.applicability_scope)}` : "规则集名称、展示名称、Owner、治理域和适用范围：待平台填写";
  const displayName = manifest.rule_set?.display_name || "规范原材料转换预览";
  const displayDescription = manifest.rule_set?.description || "以下内容是本地对 Git/学城原材料的规范化结果，平台导入时再填写规则集元信息。";
  const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'"><title>${escape(displayName)} · 规范预览</title><style>
:root{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;color:#172b3a;background:#f4f7f8}*{box-sizing:border-box}body{margin:0}.shell{max-width:1180px;margin:0 auto;padding:34px 28px}.hero{padding:30px;background:#073c35;color:white;border-radius:16px}.hero h1{font-size:28px;margin:10px 0}.hero p{color:#cde6df;line-height:1.8}.badge{font-size:12px;color:#b9e8d9}.summary{display:flex;gap:12px;margin:22px 0}.summary span{background:white;border:1px solid #dde7e3;border-radius:10px;padding:14px}.layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:24px}nav{position:sticky;top:20px;align-self:start;background:white;border-radius:12px;padding:16px}nav button{display:block;width:100%;border:0;background:#f1f6f4;text-align:left;margin:8px 0;padding:10px;color:#075f4d;cursor:pointer}.rule{background:white;border:1px solid #dce6e2;border-radius:13px;padding:22px;margin:18px 0}.rule-top{display:flex;justify-content:space-between;color:#087761;font:12px monospace}.rule-top b{background:#e8f4ef;padding:4px 8px;border-radius:6px}h2{font-size:21px}h3{font-size:19px;margin:14px 0}p,li{line-height:1.85;font-size:14px;overflow-wrap:anywhere}.muted{color:#667e86;font-size:12px}.origin{display:inline-block;background:#edf3f6;color:#657a84;border-radius:4px;padding:3px 6px;font-size:11px;margin:8px 0}.example{background:#102337;color:#dbe7f1;border-radius:10px;overflow:hidden;margin:12px 0}.example header{display:flex;justify-content:space-between;background:#dff0e8;color:#095e47;padding:10px 14px;font-size:13px}.example p{padding:0 14px}pre{padding:16px;background:#102337;color:#dbe7f1;border-radius:8px;overflow:auto;white-space:pre-wrap;word-break:break-word;line-height:1.7;font-size:12px}p code,li code{background:#edf3f4;padding:2px 4px;border-radius:3px}.keyword{color:#c69ef5}.string{color:#b7d995}.comment{color:#8299a7}.number{color:#e5bb7d}.notice{background:#fff8e5;border:1px solid #efdaa4;border-radius:12px;padding:18px;margin:16px 0}.notice h2{font-size:16px}.error{color:#a53333}.omissions{color:#7d744d;font-size:12px}table{border-collapse:collapse;width:100%;font-size:13px}td{border:1px solid #dbe3e7;padding:10px;vertical-align:top}.table-wrap{overflow:auto}.pager{display:flex;gap:14px;align-items:center;margin:24px 0}.pager button{padding:9px 15px;border:1px solid #abcabd;border-radius:6px;background:white;cursor:pointer}.pager button:disabled{opacity:.4}details{background:white;border-radius:10px;padding:18px;margin:14px 0}summary{cursor:pointer;color:#096e58}footer{font-size:12px;color:#6b7e85;margin-top:28px}.hash{font-family:monospace;overflow-wrap:anywhere;font-size:11px}@media(max-width:760px){.layout{display:block}nav{position:static}.summary{flex-wrap:wrap}}[hidden]{display:none!important}
</style></head><body><div class="shell"><header class="hero"><span class="badge">编码规范原材料整理助手 · 本地草稿</span><h1>${escape(displayName)}</h1><p>${escape(displayDescription)}<br>${platformFields}</p><p class="hash">${requestedRef ? `输入分支：${escape(requestedRef)}<br>` : ""}来源版本：${escape(sourceLabel)}<br>转换内容版本：${escape(manifest.content_digest)}</p></header><details><summary>来源文件 · ${(manifest.source?.files || []).length} 份</summary>${(manifest.source?.files || []).map((file) => `<p>${escape([manifest.source.locator?.root_path,file.source_path].filter(Boolean).join("/"))} · ${file.byte_size} 字节</p>`).join("")}</details><div class="summary"><span>${(content.documents || []).length} 份文档</span><span>${rules.size} 条规则</span><span>${questions.length} 个待确认项</span><span>${exclusions.length} 个排除单元</span></div>${questionHtml}${errorHtml}<div class="layout"><nav><b>规则目录</b>${renderedRules.map((rule) => `<button data-go="${escape(rule.rule_ref)}">${escape(rule.title || rule.rule_ref)}</button>`).join('')}<p class="muted">通过对话修改内容。预览不会执行上传或发布。</p></nav><main>${articles}<div class="pager"><button id="prev">上一页</button><span id="page"></span><button id="next">下一页</button></div><details><summary>规则集索引 AGENTS.md</summary>${renderMarkdown(agentsIndex)}</details><details><summary>排除项与处理决定</summary>${exclusions.map((unit) => `<p>${escape(unit.unit_ref)}：${escape(unit.reason)}</p>`).join('') || '<p>没有排除项。</p>'}${(content.resolutions || []).map((r) => `<p>${escape(r.decision)}：${escape(r.explanation)}</p>`).join('')}</details></main></div><footer>这是本地预览，尚未在平台生效。规则编号由平台分配。外部图片和链接内容未自动加载；含凭据的 URL 查询参数仅在展示中隐藏，来源快照保持原样。</footer></div><script>
const articles=[...document.querySelectorAll('.rule')];let page=0;const size=10;function show(){articles.forEach((a,i)=>a.hidden=Math.floor(i/size)!==page);document.querySelector('#page').textContent='第 '+(articles.length?page+1:0)+' / '+Math.ceil(articles.length/size)+' 页 · 共 '+articles.length+' 条';document.querySelector('#prev').disabled=page===0;document.querySelector('#next').disabled=(page+1)*size>=articles.length;}document.querySelector('#prev').onclick=()=>{page--;show()};document.querySelector('#next').onclick=()=>{page++;show()};document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>{const i=articles.findIndex(a=>a.dataset.rule===b.dataset.go);if(i<0)return;page=Math.floor(i/size);show();articles[i].scrollIntoView({behavior:'smooth',block:'start'})});show();
</script></body></html>`;
  return { html, preview_digest: await canonicalHash({ content_digest: manifest.content_digest, requested_ref: requestedRef, questions, validation }) };
}
