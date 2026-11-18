import { PackageContractError, decodeUtf8, utf8, sha256, canonicalHash } from './package-contract.mjs';
const fail = (path, message) => { throw new PackageContractError('PACKAGE_READER_INVALID', path, message); };
const byteOffsets = (text) => {
  const offsets = new Array(text.length + 1); let byte = 0;
  for (let i = 0; i < text.length;) { const point = String.fromCodePoint(text.codePointAt(i)); offsets[i] = byte; byte += utf8(point).length; i += point.length; }
  offsets[text.length] = byte; return offsets;
};

// Keeps raw JSON value ranges, not reserialized values. Rich text evidence can
// point to a complete node or text token with its exact source byte boundaries.
export function parseHistoryTree(bytes) {
  const text = decodeUtf8(bytes, '/source'); const offsets = byteOffsets(text); let at = 0, count = 0;
  const space = () => { while (/[ \t\r\n]/u.test(text[at] || '\u0001')) at += 1; };
  const parse = (depth = 0) => {
    if (depth > 64 || ++count > 20000) fail('/source', '学城历史结构过深或节点过多。');
    space(); const begin = at; let value; const children = new Map();
    if (text[at] === '{' || text[at] === '[') {
      const array = text[at++] === '['; value = array ? [] : Object.create(null); space(); const close = array ? ']' : '}';
      if (text[at] !== close) while (at < text.length) {
        let key;
        if (array) key = value.length;
        else { const token = parse(depth + 1); if (typeof token.value !== 'string') fail('/source', '学城原件含无效对象键。'); key = token.value; if (children.has(key) || ['__proto__', 'constructor', 'prototype'].includes(key)) fail('/source', '学城原件含重复或不允许的对象键。'); space(); if (text[at++] !== ':') fail('/source', '学城历史 JSON 无效。'); }
        const child = parse(depth + 1); children.set(key, child); value[key] = child.value; space();
        if (text[at] === close) break; if (text[at++] !== ',') fail('/source', '学城历史 JSON 无效。');
      }
      if (text[at++] !== close) fail('/source', '学城历史 JSON 不完整。');
    } else if (text[at] === '"') {
      at += 1; let escaped = false, closed = false;
      while (at < text.length) { const ch = text[at++]; if (!escaped && ch === '"') { closed = true; break; } escaped = !escaped && ch === '\\'; }
      if (!closed) fail('/source', '学城历史 JSON 字符串不完整。');
      try { value = JSON.parse(text.slice(begin, at)); } catch { fail('/source', '学城历史 JSON 字符串无效。'); }
    } else {
      const token = text.slice(at).match(/^(?:null|true|false|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/u)?.[0];
      if (!token) fail('/source', '学城历史 JSON 值无效。'); at += token.length;
      value = JSON.parse(token); if (typeof value === 'number' && !Number.isFinite(value)) fail('/source', '学城历史 JSON 数值无效。');
    }
    return { value, children, byte_start: offsets[begin], byte_end: offsets[at] };
  };
  const tree = parse(); space(); if (at !== text.length) fail('/source', '学城历史 JSON 含尾随内容。');
  return tree;
}

const fence = (code) => '`'.repeat(Math.max(3, ...[...code.matchAll(/`+/gu)].map((m) => m[0].length + 1)));
const record = (value) => value !== null && typeof value === 'object' && !Array.isArray(value) && [Object.prototype, null].includes(Object.getPrototypeOf(value));
const ownData = (value, key) => {
  if (!record(value)) return undefined;
  const descriptor = Object.getOwnPropertyDescriptor(value, key);
  return descriptor && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined;
};
export function renderHistoryNode(node) {
  if (typeof node === 'string') return { text: node, unsupported: [] };
  if (!record(node)) return { text: '', unsupported: ['unknown_value'] };
  const kind = ownData(node, 'type'); const unsupported = [];
  const rawContent = ownData(node, 'content');
  if (Object.hasOwn(node, 'content') && !Array.isArray(rawContent)) unsupported.push('invalid_content');
  const nodes = Array.isArray(rawContent) ? rawContent : [];
  const children = nodes.map((item) => { const r = renderHistoryNode(item); unsupported.push(...r.unsupported); return r.text; });
  const body = children.join(''); const rawAttrs = ownData(node, 'attrs');
  if (Object.hasOwn(node, 'attrs') && !record(rawAttrs)) unsupported.push('invalid_attrs');
  const attrs = record(rawAttrs) ? rawAttrs : Object.create(null);
  let text;
  if (kind === 'text') {
    const rawText = ownData(node, 'text'); text = typeof rawText === 'string' ? rawText : '';
    if (typeof rawText !== 'string') unsupported.push('invalid_text');
    const marks = ownData(node, 'marks');
    if (Object.hasOwn(node, 'marks') && !Array.isArray(marks)) unsupported.push('invalid_marks');
    for (const mark of Array.isArray(marks) ? marks : []) {
      if (!record(mark) || typeof ownData(mark, 'type') !== 'string') { unsupported.push('invalid_mark'); continue; }
      const type = ownData(mark, 'type'); const markAttrs = ownData(mark, 'attrs');
      if (Object.hasOwn(mark, 'attrs') && !record(markAttrs)) { unsupported.push('invalid_mark_attrs'); continue; }
      if (['bold', 'strong'].includes(type)) text = '**' + text + '**';
      else if (['italic', 'em'].includes(type)) text = '*' + text + '*';
      else if (type === 'code') {
        // Complex inline delimiters need an explicit source decision rather than
        // silently changing the boundaries of the marked code.
        if (/[\x60\r\n]/u.test(text) || !text.trim() || text !== text.trim()) unsupported.push('inline_code_delimiter');
        else text = String.fromCharCode(96) + text + String.fromCharCode(96);
      } else if (type === 'link') {
        const href = ownData(markAttrs, 'href');
        if (typeof href !== 'string') unsupported.push('invalid_link');
        else text = '[' + text + '](' + href + ')';
      } else if (type === 'strike') text = '~~' + text + '~~';
      else if (!['textStyle', 'highlight', 'underline'].includes(type)) unsupported.push('mark:' + type);
    }
  } else if (['doc', 'fragment', 'tableRow', 'table_row', 'listItem', 'list_item'].includes(kind)) text = body;
  else if (['paragraph', 'paragraphBlock', 'title'].includes(kind)) text = body + '\n\n';
  else if (['blockquote', 'blockQuote'].includes(kind)) text = body.replace(/\n+$/u, '').split('\n').map((line) => '> ' + line).join('\n') + '\n\n';
  else if (kind === 'heading') text = '#'.repeat(Math.min(6, Math.max(1, Number(ownData(attrs, 'level')) || 2))) + ' ' + body + '\n\n';
  else if (['hardBreak', 'hard_break'].includes(kind)) text = '\n';
  else if (['horizontalRule', 'horizontal_rule'].includes(kind)) text = '\n---\n';
  else if (['codeBlock', 'code_block'].includes(kind)) {
    const code = nodes.map((item) => typeof ownData(item, 'text') === 'string' ? ownData(item, 'text') : renderHistoryNode(item).text).join('');
    const language = String(ownData(attrs, 'language') || 'text').replace(/[^a-zA-Z0-9_+.#-]/gu, '') || 'text'; const ticks = fence(code); text = ticks + language + '\n' + code + '\n' + ticks + '\n\n';
  } else if (['bulletList', 'bullet_list', 'orderedList', 'ordered_list'].includes(kind)) text = children.map((child, i) => (kind.startsWith('ordered') ? (i + (Number(ownData(attrs, 'start')) || 1)) + '.' : '-') + ' ' + child.trimEnd().replace(/\n/gu, '\n  ') + '\n').join('') + '\n';
  else if (['tableCell', 'table_cell', 'tableHeader', 'table_header'].includes(kind)) {
    text = body.trim().replace(/\|/gu, '\\|').replace(/\n/gu, '<br>');
    if ((ownData(attrs, 'colspan') || 1) !== 1 || (ownData(attrs, 'rowspan') || 1) !== 1) unsupported.push('merged_table_cell');
  } else if (kind === 'table') {
    const rows = nodes.map((row) => {
      const cells = ownData(row, 'content');
      if (!Array.isArray(cells)) { unsupported.push('invalid_table_row'); return []; }
      return cells.map((cell) => renderHistoryNode(cell).text);
    });
    const width = Math.max(0, ...rows.map((row) => row.length));
    text = rows.map((row, i) => '| ' + [...row, ...Array(Math.max(0, width - row.length)).fill('')].join(' | ') + ' |\n' + (i === 0 ? '| ' + Array(width).fill('---').join(' | ') + ' |\n' : '')).join('') + '\n';
  } else { text = body; unsupported.push(typeof kind === 'string' ? kind : 'unknown_node'); }
  return { text, unsupported: [...new Set(unsupported)] };
}

export async function buildSourceUnits(source, sourceFiles) {
  const all = [];
  for (const entry of source.files) {
    const bytes = sourceFiles.get(entry.package_path); if (!(bytes instanceof Uint8Array)) fail('/source/files', '缺少来源快照。');
    const text = decodeUtf8(bytes, '/source'); let records;
    if (source.type === 'git') {
      const lines = text.match(/[^\n]*\n|[^\n]+$/gu) || []; const starts = [0]; let offset = 0, inFence = null;
      for (let i = 0; i < lines.length; i += 1) {
        const line = lines[i]; const marker = line.trimStart().match(/^(`{3,}|~{3,})/u)?.[1];
        if (!inFence && i > 0 && /^\s{0,3}#{1,6}\s/u.test(line) && starts.at(-1) !== offset) starts.push(offset);
        if (marker) { if (!inFence) inFence = { char: marker[0], length: marker.length }; else if (marker[0] === inFence.char && marker.length >= inFence.length) inFence = null; }
        offset += utf8(line).length;
        if (!inFence && !line.trim() && offset < bytes.length && starts.at(-1) !== offset) starts.push(offset);
      }
      records = starts.map((start, i) => ({ start, end: starts[i + 1] ?? bytes.length, evidenceStart: start, evidenceEnd: starts[i + 1] ?? bytes.length, text: decodeUtf8(bytes.subarray(start, starts[i + 1] ?? bytes.length)), unsupported: [] }));
    } else {
      const tree = parseHistoryTree(bytes); const nodes = tree.children.get('content');
      if (tree.value?.type !== 'doc' || !Array.isArray(nodes?.value) || !nodes.value.length) fail('/source', '学城历史正文缺少可识别的文档节点。');
      const top = [...nodes.children.values()];
      records = top.map((node, i) => ({ start: i ? node.byte_start : 0, end: top[i + 1]?.byte_start ?? bytes.length, evidenceStart: node.byte_start, evidenceEnd: node.byte_end, ...renderHistoryNode(node.value) }));
    }
    for (const record of records) {
      if (record.start === record.end) continue;
      if (all.length >= 4096) fail('/source', '固定来源单元超过 4096 个，请明确缩小本次读取范围。');
      const unitHash = await canonicalHash({ source_ref: entry.source_ref, start: record.start, end: record.end, sha256: await sha256(bytes.subarray(record.start, record.end)) });
      all.push({ source_ref: entry.source_ref, unit_ref: `unit_${unitHash.slice(7, 31)}`, byte_start: record.start, byte_end: record.end, text: record.text, unsupported: record.unsupported,
        evidence_span: { source_ref: entry.source_ref, byte_start: record.evidenceStart, byte_end: record.evidenceEnd, sha256: await sha256(bytes.subarray(record.evidenceStart, record.evidenceEnd)) } });
    }
  }
  return all;
}

export async function verifyReaderEvidence(validated, files) {
  const units = await buildSourceUnits(validated.manifest.source, files);
  const byId = new Map(units.map((unit) => [unit.unit_ref, unit]));
  if (units.length !== validated.content.coverage.length) fail('/content/coverage', '覆盖单元与固定读取器结果不一致。');
  for (const coverage of validated.content.coverage) {
    const unit = byId.get(coverage.unit_ref);
    if (!unit || unit.source_ref !== coverage.source_ref || unit.byte_start !== coverage.byte_start || unit.byte_end !== coverage.byte_end) fail('/content/coverage', '覆盖记录不能改变固定读取器的单元边界。');
    if (unit.unsupported.length && coverage.disposition !== 'excluded') fail('/content/coverage', '存在尚不支持的学城组件，请补充为支持的文字材料或明确排除。');
  }
  if (validated.manifest.source.type === 'km') {
    const spanTexts = new Map();
    for (const entry of validated.manifest.source.files) {
      const tree = parseHistoryTree(files.get(entry.package_path));
      const visit = (node) => {
        const rendered = typeof node.value === 'string' ? { text: node.value, unsupported: [] } : node.value?.type ? renderHistoryNode(node.value) : null;
        if (rendered && !rendered.unsupported.length) spanTexts.set(`${entry.source_ref}:${node.byte_start}:${node.byte_end}`, rendered.text);
        for (const child of node.children.values()) visit(child);
      }; visit(tree);
    }
    const blocks = [...validated.content.documents.flatMap((doc) => doc.content.filter((block) => block.type === 'markdown')), ...validated.content.rules.flatMap((rule) => rule.body)];
    for (const block of blocks) if (block.provenance.origin === 'source_extract') {
      const texts = block.provenance.source_spans.map((span) => spanTexts.get(`${span.source_ref}:${span.byte_start}:${span.byte_end}`));
      if (texts.some((text) => text === undefined) || texts.join('') !== (block.type === 'example' ? block.code : block.text)) fail('/content/provenance', '学城摘取内容与固定历史 JSON 映射不一致。');
    }
  }
  return { ...validated, readerCoverageVerified: true, sourceExtractionPending: false, sourceVerified: false, publishable: false };
}
