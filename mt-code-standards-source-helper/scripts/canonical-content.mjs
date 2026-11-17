import { CONTENT_CONTRACT, RENDER_CONTRACT, LIMITS, PackageContractError, validateContent, canonical, safeRelativePath, agentsRows } from './package-contract.mjs';
const HASH = /^sha256:[0-9a-f]{64}$/u;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const REF = /^[a-z][a-z0-9_-]{0,63}$/u;
const MIS = /^[a-z][a-z0-9._-]{0,63}$/u;
const matches = (pattern, value) => typeof value === 'string' && pattern.test(value);
export const CANONICAL_FIELDS = Object.freeze(['content_contract', 'render_contract', 'canonical_content_descriptor']);
export const CANONICAL_PROJECTION_NOTICE = '完整正文保存在结构化规范中，请使用支持该合同的规范查看器。';
const fail = (path, message) => { throw new PackageContractError('CANONICAL_CONTENT_INVALID', path, message); };
const exact = (value, keys, path) => {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).sort().join(',') !== [...keys].sort().join(',')) fail(path, '结构化规范字段不完整或包含未定义字段。');
  return value;
};
const ensure = (condition, path, message) => { if (!condition) fail(path, message); };
const oneLine = (value, path) => ensure(typeof value === 'string' && value.trim() && !/[\r\n]/u.test(value), path, '标题必须是非空单行文本，请在本地调整并重新确认。');
const boundedRows = (value, max, path) => ensure(Array.isArray(value) && value.length > 0 && value.length <= max, path, '绑定数量超出本版范围。');
const unique = (rows, field, path) => { const result = new Map(); for (const row of rows) { ensure(!result.has(row[field]), path, '绑定标识重复。'); result.set(row[field], row); } return result; };
export function canonicalContractFields(value) {
  const present = CANONICAL_FIELDS.filter((field) => Object.hasOwn(value || {}, field));
  if (!present.length) return {};
  ensure(present.length === CANONICAL_FIELDS.length && value.content_contract === CONTENT_CONTRACT && value.render_contract === RENDER_CONTRACT, '/content_contract', '结构化正文合同必须成组出现且版本受支持。');
  validateCanonicalDescriptor(value.canonical_content_descriptor);
  return Object.fromEntries(CANONICAL_FIELDS.map((field) => [field, value[field]]));
}
export function validateCanonicalDescriptor(value) {
  canonical(value);
  exact(value, ['artifact_ref', 'package_content_digest', 'owner_mis', 'rule_set_context', 'source_bindings', 'document_bindings', 'rule_bindings'], '/canonical_content_descriptor');
  exact(value.artifact_ref, ['artifact_id', 'kind', 'media_type', 'byte_size', 'sha256'], '/canonical_content_descriptor/artifact_ref');
  const artifact = value.artifact_ref;
  ensure(matches(UUID, artifact.artifact_id) && artifact.kind === 'candidate_manifest' && artifact.media_type === 'application/json' && matches(HASH, artifact.sha256) && Number.isSafeInteger(artifact.byte_size) && artifact.byte_size > 0 && artifact.byte_size <= LIMITS.contentBytes, '/canonical_content_descriptor/artifact_ref', '结构化正文必须引用独立、受限且带 Hash 的 JSON Artifact。');
  ensure(matches(HASH, value.package_content_digest) && matches(MIS, value.owner_mis), '/canonical_content_descriptor', '内容确认 Hash 或维护人无效。');
  exact(value.rule_set_context, ['description', 'applicability_scope'], '/canonical_content_descriptor/rule_set_context');
  for (const field of ['description', 'applicability_scope']) {
    ensure(typeof value.rule_set_context[field] === 'string' && value.rule_set_context[field].trim() && Array.from(value.rule_set_context[field]).length <= 2000, `/canonical_content_descriptor/rule_set_context/${field}`, '规则集说明和适用范围必须保持用户确认的非空文本。');
    assertNoEmbeddedRuleHeadings(value.rule_set_context[field], `/canonical_content_descriptor/rule_set_context/${field}`);
  }
  boundedRows(value.source_bindings, LIMITS.sourceFiles, '/source_bindings');
  boundedRows(value.document_bindings, LIMITS.sourceFiles, '/document_bindings');
  boundedRows(value.rule_bindings, LIMITS.rules, '/rule_bindings');
  for (const row of value.source_bindings) {
    exact(row, ['source_ref', 'relative_path', 'content_hash', 'byte_size'], '/source_bindings');
    ensure(matches(REF, row.source_ref) && matches(HASH, row.content_hash) && Number.isSafeInteger(row.byte_size) && row.byte_size > 0 && row.byte_size <= LIMITS.sourceFileBytes, '/source_bindings', '来源绑定无效。');
    safeRelativePath(row.relative_path, '/source_bindings/relative_path');
  }
  ensure(value.source_bindings.reduce((total, row) => total + row.byte_size, 0) <= LIMITS.sourceTotalBytes, '/source_bindings', '来源绑定的总字节数超过 V1 上限。');
  for (const row of value.document_bindings) {
    exact(row, ['document_ref', 'document_id', 'source_path'], '/document_bindings');
    ensure(matches(REF, row.document_ref) && matches(UUID, row.document_id), '/document_bindings', '文档绑定无效。'); safeRelativePath(row.source_path, '/document_bindings/source_path');
  }
  for (const row of value.rule_bindings) {
    exact(row, ['rule_ref', 'rule_uid', 'local_rule_id', 'document_id'], '/rule_bindings');
    const number = typeof row.local_rule_id === 'string' ? row.local_rule_id.match(/^[A-Z][A-Z0-9_]{1,31}-([0-9]{3,9})$/u)?.[1] : null;
    ensure(matches(REF, row.rule_ref) && matches(UUID, row.document_id) && number && Number(number) > 0 && String(Number(number)).padStart(3, '0') === number && typeof row.rule_uid === 'string' && row.rule_uid.endsWith(`:${row.local_rule_id}`), '/rule_bindings', '规则绑定无效。');
  }
  for (const field of ['source_ref', 'relative_path']) unique(value.source_bindings, field, '/source_bindings');
  for (const field of ['document_ref', 'document_id', 'source_path']) unique(value.document_bindings, field, '/document_bindings');
  for (const field of ['rule_ref', 'rule_uid', 'local_rule_id']) unique(value.rule_bindings, field, '/rule_bindings');
  return value;
}
const ASCII_ENTITIES = Object.freeze({
  Tab:'\t', NewLine:'\n', excl:'!', quot:'"', QUOT:'"', num:'#', dollar:'$', percnt:'%', amp:'&', AMP:'&', apos:"'", lpar:'(', rpar:')', ast:'*', plus:'+', comma:',', period:'.', sol:'/', colon:':', semi:';', lt:'<', LT:'<', equals:'=', gt:'>', GT:'>', quest:'?', commat:'@', lsqb:'[', lbrack:'[', bsol:'\\', rsqb:']', rbrack:']', Hat:'^', lowbar:'_', grave:'`', DiacriticalGrave:'`', lcub:'{', lbrace:'{', verbar:'|', vert:'|', VerticalLine:'|', rcub:'}', rbrace:'}', nbsp:'\u00a0', NonBreakingSpace:'\u00a0',
});
const ruleHeading = /^[A-Z][A-Z0-9_]{1,31}-[0-9]{3,9}(?=\b|\s|$)/u;
function headingText(value, path) {
  // A conservative heading-only interpretation, not a full Markdown parser.
  // Unsupported entities/HTML cannot be used to conceal an identifier.
  let codepoints = 0;
  for (const _character of value) {
    if (++codepoints > 2048) fail(path, '标题超过本版 2048 个 Unicode 字符的上限，请在本地明确整理并重新确认。');
  }
  ensure(!/<\/?[a-zA-Z!][^>]*>/u.test(value), path, '标题中的原始 HTML 不属于本版支持子集，请在本地明确整理并重新确认。');
  let unknown = false;
  let text = value.replace(/&(?:#(?:x([0-9a-f]{1,8})|([0-9]{1,10}))|([a-z][a-z0-9]{0,31}));/giu, (raw, hex, decimal, named) => {
    if (hex || decimal) { const value = Number.parseInt(hex || decimal, hex ? 16 : 10); return value > 0 && value <= 0x10ffff && !(value >= 0xd800 && value <= 0xdfff) ? String.fromCodePoint(value) : '\ufffd'; }
    if (Object.hasOwn(ASCII_ENTITIES, named)) return ASCII_ENTITIES[named];
    unknown = true; return raw;
  });
  ensure(!unknown, path, '标题包含本版本无法可靠判定的 HTML 实体，请改用明确文字并重新确认。');
  text = text.replace(/\\([!"#$%&'()*+,\-./:;<=>?@[\]\\^_`{|}~])/gu, '$1');
  // Link destinations do not contribute to a heading's visible identifier.
  text = text.replace(/!?\[([^\]]*)\]\([^)]*\)/gu, '$1').replace(/!?\[([^\]]*)\]\[[^\]]*\]/gu, '$1');
  return text.replace(/[*_~`[\]]/gu, '').trim();
}
function rejectRuleHeading(value, path) {
  ensure(!ruleHeading.test(headingText(value, path)), path, '标题可能被识别为额外的 Rule ID 定义，请在本地明确调整并重新确认；普通文字引用与代码示例不受影响。');
}
function lineIndent(line) {
  let columns = 0, index = 0;
  while (index < line.length && /[ \t]/u.test(line[index])) { columns += line[index] === '\t' ? 4 - (columns % 4) : 1; index += 1; }
  return { columns, text: line.slice(index) };
}
function containerLine(line) {
  let text = line, quoteDepth = 0, list = false, iterations = 0;
  while (iterations++ < 32) {
    const indented = lineIndent(text);
    if (indented.columns > 3) break;
    const quote = indented.text.match(/^> ?(.*)$/u);
    if (quote) { quoteDepth += 1; text = quote[1]; continue; }
    const item = indented.text.match(/^(?:[-+*]|[0-9]{1,9}[.)])[ \t]+(.*)$/u);
    if (item) { list = true; text = item[1]; continue; }
    break;
  }
  ensure(iterations <= 32, '/markdown', 'Markdown 容器嵌套超过本版限制，请在本地明确整理。');
  return { text, quoteDepth, list, container: quoteDepth > 0 || list };
}
export function assertNoEmbeddedRuleHeadings(markdown, path) {
  // Supported subset: ATX/setext, CR/LF/CRLF, top-level legal fenced code,
  // simple indented code outside containers, and ordinary quote/list prose.
  // Ambiguous container code and raw HTML blocks fail closed rather than being
  // mistaken for code that could hide a real heading. No content is rewritten.
  const lines = markdown.split(/\r\n|\r|\n/u);
  const hasContainers = lines.some((line) => containerLine(line).container);
  let fence = null, paragraph = [], indentedCode = false, previousQuoteDepth = 0;
  for (const raw of lines) {
    const indentation = lineIndent(raw);
    if (fence) {
      const closing = indentation.columns <= 3 ? indentation.text.match(/^(`{3,}|~{3,})[ \t]*$/u) : null;
      if (closing && closing[1][0] === fence.char && closing[1].length >= fence.length) fence = null;
      continue;
    }
    if (!raw.trim()) { paragraph = []; previousQuoteDepth = 0; continue; }
    const container = containerLine(raw);
    if (container.list || container.quoteDepth !== previousQuoteDepth) paragraph = [];
    previousQuoteDepth = container.quoteDepth;
    let logical = lineIndent(container.text);
    if (indentedCode && !hasContainers && indentation.columns >= 4) continue;
    indentedCode = false;
    if (indentation.columns >= 4 && !hasContainers && !paragraph.length) { indentedCode = true; continue; }
    if (hasContainers && indentation.columns >= 4 && /^(?:#{1,6}(?:[ \t]|$)|[-=]+[ \t]*$|`{3,}|~{3,})/u.test(logical.text)) {
      fail(path, '列表或引用中的缩进标题/代码边界存在歧义，请使用明确的顶层结构并重新确认。');
    }
    const marker = logical.columns <= 3 ? logical.text.match(/^(`{3,}|~{3,})(.*)$/u) : null;
    if (marker) {
      const legal = marker[1][0] !== '`' || !marker[2].includes('`');
      if (container.container || (hasContainers && indentation.columns > 0)) fail(path, '本版不支持容器内部的代码围栏，请在本地明确整理为独立代码块并重新确认。');
      if (legal && indentation.columns <= 3) { fence = { char: marker[1][0], length: marker[1].length }; paragraph = []; continue; }
      // Invalid backtick info is normal prose in CommonMark, not a safe fence.
    }
    if (logical.columns <= 3 && /^<(?:[A-Za-z/!?]|!--)/u.test(logical.text)) fail(path, '原始 HTML 块不属于本版支持子集，请在本地明确整理并重新确认。');
    const heading = logical.columns <= 3 ? logical.text.match(/^#{1,6}(?:[ \t]+(.*)|[ \t]*)$/u) : null;
    if (heading) { rejectRuleHeading((heading[1] || '').replace(/[ \t]+#+[ \t]*$/u, ''), path); paragraph = []; continue; }
    const setext = logical.columns <= 3 && /^(?:=+|-+)[ \t]*$/u.test(logical.text);
    if (setext && paragraph.length) { rejectRuleHeading(paragraph.join('\n'), path); paragraph = []; continue; }
    if (setext || /^(?:\*[ \t]*){3,}$|^(?:_[ \t]*){3,}$/u.test(logical.text)) { paragraph = []; continue; }
    // A container marker or paragraph continuation remains visible prose. Only
    // a later setext underline can turn the accumulated paragraph into a title.
    paragraph.push(logical.text);
  }
  ensure(fence === null, path, '正文代码围栏未闭合，可能吞并后续规则，请在本地修正并重新确认。');
}
const exampleMarkdown = (block) => {
  const ticks = '`'.repeat(Math.max(3, ...[...block.code.matchAll(/`+/gu)].map((match) => match[0].length + 1)));
  return `${ticks}${block.language}\n${block.code}${block.code.endsWith('\n') ? '' : '\n'}${ticks}`;
};
export function projectCanonicalRule(rule) {
  const requirement = rule.body.filter((block) => block.type === 'markdown').map((block) => block.text).join('\n\n');
  const example = (role) => { const blocks = rule.body.filter((block) => block.type === 'example' && block.role === role); if (blocks.length !== 1) return ''; const value = exampleMarkdown(blocks[0]); return value.length <= 20000 ? value : ''; };
  return { requirement: requirement.length <= 20000 ? requirement : CANONICAL_PROJECTION_NOTICE, good_case: example('good'), bad_case: example('bad') };
}
export function validateCanonicalDraftContent(content) {
  validateContent(content);
  for (const document of content.documents) {
    oneLine(document.title, `/documents/${document.document_ref}/title`);
    rejectRuleHeading(document.title, `/documents/${document.document_ref}/title`);
    for (const block of document.content) if (block.type === 'markdown') assertNoEmbeddedRuleHeadings(block.text, `/documents/${document.document_ref}/content`);
  }
  for (const rule of content.rules) {
    oneLine(rule.title, `/rules/${rule.rule_ref}/title`);
    rejectRuleHeading(rule.title, `/rules/${rule.rule_ref}/title`);
    for (const block of rule.body) {
      if (block.type === 'markdown') assertNoEmbeddedRuleHeadings(block.text, `/rules/${rule.rule_ref}/body`);
      else if (block.caption) assertNoEmbeddedRuleHeadings(block.caption, `/rules/${rule.rule_ref}/caption`);
    }
  }
  return content;
}
export function validateCanonicalBindings(content, descriptor, { candidate = null, ruleSet = candidate?.rule_set } = {}) {
  validateCanonicalDraftContent(content); validateCanonicalDescriptor(descriptor);
  ensure(ruleSet && typeof ruleSet.rule_set_id === 'string' && ruleSet.scope_level === 'L2', '/rule_set', '缺少平台冻结的 L2 规则集身份。');
  const documents = unique(content.documents, 'document_ref', '/documents'); const rules = unique(content.rules, 'rule_ref', '/rules');
  const sources = unique(descriptor.source_bindings, 'source_ref', '/source_bindings');
  const documentBindings = unique(descriptor.document_bindings, 'document_ref', '/document_bindings'); const ruleBindings = unique(descriptor.rule_bindings, 'rule_ref', '/rule_bindings');
  ensure(documents.size === documentBindings.size && rules.size === ruleBindings.size, '/canonical_content_descriptor', '正文与正式绑定不是完整的一一对应关系。');
  const usedSources = new Set(), usedRules = new Set(); const root = `coding-standards/rule-sets/${ruleSet.rule_set_id}/rules/`;
  for (const document of content.documents) {
    oneLine(document.title, `/documents/${document.document_ref}/title`);
    const binding = documentBindings.get(document.document_ref);
    ensure(binding && sources.has(document.source_ref) && !usedSources.has(document.source_ref) && binding.source_path.startsWith(root) && binding.source_path.endsWith('.md'), '/document_bindings', '正式文档或来源绑定不匹配。'); usedSources.add(document.source_ref);
    let ruleCount = 0;
    for (const block of document.content) {
      if (block.type === 'markdown') assertNoEmbeddedRuleHeadings(block.text, `/documents/${document.document_ref}/content`);
      else { const rule = rules.get(block.rule_ref), ruleBinding = ruleBindings.get(block.rule_ref);
        ensure(rule && rule.document_ref === document.document_ref && ruleBinding && ruleBinding.document_id === binding.document_id && !usedRules.has(block.rule_ref), '/rule_bindings', '规则正文顺序与所属文档绑定无效。'); usedRules.add(block.rule_ref); ruleCount += 1; }
    }
    ensure(ruleCount > 0, '/documents', '正式文档不能没有规则。');
  }
  ensure(usedRules.size === rules.size, '/rules', '结构化正文包含未放入文档的规则。');
  for (const rule of content.rules) {
    oneLine(rule.title, `/rules/${rule.rule_ref}/title`);
    const binding = ruleBindings.get(rule.rule_ref);
    ensure(binding && binding.rule_uid === `${ruleSet.rule_set_id}:${binding.local_rule_id}`, '/rule_bindings', '规则身份不属于当前规则集。');
    ensure(rule.body.some((block) => block.type === 'markdown'), `/rules/${rule.rule_ref}/body`, '规则必须有明确要求。');
    for (const block of rule.body) {
      if (block.type === 'markdown') assertNoEmbeddedRuleHeadings(block.text, `/rules/${rule.rule_ref}/body`);
      else if (block.caption) assertNoEmbeddedRuleHeadings(block.caption, `/rules/${rule.rule_ref}/caption`);
    }
    const omissions = unique(rule.omissions, 'role', `/rules/${rule.rule_ref}/omissions`);
    for (const role of ['good','bad']) {
      const present = rule.body.some((block) => block.type === 'example' && block.role === role);
      ensure(present !== omissions.has(role), `/rules/${rule.rule_ref}/omissions`, '示例和省略确认必须按真实正文逐侧一致。');
      if (!present) ensure(content.resolutions.some((resolution) => resolution.kind === 'omission' && resolution.affected_refs.includes(rule.rule_ref)), `/rules/${rule.rule_ref}/omissions`, '真实缺失示例没有对应确认决定。');
    }
  }
  const coverageUnits = unique(content.coverage, 'unit_ref', '/coverage');
  const allRefs = [...sources.keys(), ...documents.keys(), ...rules.keys(), ...coverageUnits.keys()];
  ensure(new Set(allRefs).size === allRefs.length, '/coverage', '来源、文档、规则与覆盖单元的临时标识不能冲突。');
  const coveredRules = new Set();
  const sourceForTarget = (target) => documents.get(target)?.source_ref || (rules.has(target) ? documents.get(rules.get(target).document_ref)?.source_ref : undefined);
  for (const unit of content.coverage) {
    ensure(sources.has(unit.source_ref), '/coverage', '来源覆盖引用未绑定的原件。');
    ensure(unit.targets.every((target) => sourceForTarget(target) === unit.source_ref), '/coverage', '覆盖目标必须属于同一来源。');
    if (unit.disposition === 'excluded') {
      ensure(unit.targets.length === 0 && unit.reason.trim() && content.resolutions.some((row) => row.kind === 'exclusion' && row.affected_refs.includes(unit.unit_ref)), '/coverage', '排除的来源单元必须有明确原因及确认记录，且不能继续关联规则。');
    } else {
      ensure(unit.targets.length > 0 && (unit.disposition !== 'support' || unit.reason.trim()), '/coverage', '纳入的来源单元必须关联目标，支持材料需要说明用途。');
      unit.targets.forEach((target) => { if (rules.has(target)) coveredRules.add(target); });
    }
  }
  for (const [sourceRef, binding] of sources) {
    const ranges = content.coverage.filter((unit) => unit.source_ref === sourceRef).sort((a, b) => a.byte_start - b.byte_start);
    let cursor = 0;
    for (const unit of ranges) {
      ensure(unit.byte_start === cursor && unit.byte_end > unit.byte_start && unit.byte_end <= binding.byte_size, '/coverage', '来源覆盖存在缺口、重叠或越界。');
      cursor = unit.byte_end;
    }
    ensure(cursor === binding.byte_size, '/coverage', '每个来源绑定都必须具有完整覆盖记录，包括明确排除的来源。');
  }
  ensure(coveredRules.size === rules.size, '/coverage', '存在未被来源覆盖关联的规范。');
  for (const resolution of content.resolutions) ensure(resolution.affected_refs.every((ref) => allRefs.includes(ref)), '/resolutions', '用户决定不能引用不存在的来源或规范。');
  const blocks = [...content.documents.flatMap((doc)=>doc.content.filter((block)=>block.type==='markdown')), ...content.rules.flatMap((rule)=>rule.body)];
  for (const block of blocks) for (const span of block.provenance.source_spans) ensure(sources.has(span.source_ref) && span.byte_start < span.byte_end && span.byte_end <= sources.get(span.source_ref).byte_size, '/provenance', '来源证据范围不属于已绑定原件。');
  if (candidate) {
    ensure(candidate.base_release_id === null && !candidate.previous_rule_uids?.length && !candidate.explicit_removals?.length && !candidate.obsolete_rule_paths?.length && !candidate.update_mode && !candidate.update_contract && !candidate.migration, '/candidate', 'V1 结构化正文仅支持新建 L2。');
    const snapshot = unique(candidate.source_snapshot.files, 'relative_path', '/source_snapshot');
    ensure(snapshot.size === sources.size, '/source_bindings', '来源快照与绑定数量不一致。');
    for (const binding of sources.values()) { const file = snapshot.get(binding.relative_path); ensure(file && file.content_hash === binding.content_hash && file.byte_size === binding.byte_size, '/source_bindings', '来源绑定与冻结快照不一致。'); }
    const formalDocuments = unique(candidate.documents, 'document_id', '/candidate/documents'); const formalRules = unique(candidate.rules, 'rule_uid', '/candidate/rules');
    ensure(formalDocuments.size === documents.size && formalRules.size === rules.size, '/candidate', '正式候选与结构化正文数量不一致。');
    for (const binding of documentBindings.values()) { const doc = formalDocuments.get(binding.document_id); ensure(doc && doc.relative_path === binding.source_path, '/document_bindings', '正式文件路径与冻结分配不一致。'); }
    ensure(typeof candidate.agents_index?.content === 'string' && Array.isArray(candidate.agents_index_bindings), '/candidate/agents_index', '结构化候选必须保留索引原件和正式路径绑定。');
    const indexBindings = unique(candidate.agents_index_bindings, 'reference', '/candidate/agents_index_bindings');
    const localIndexBindings = unique(content.agents_index.bindings, 'reference', '/content/agents_index/bindings');
    const indexReferences = new Set(agentsRows(candidate.agents_index.content).map((row) => row.reference));
    ensure(indexBindings.size === localIndexBindings.size && indexReferences.size === localIndexBindings.size && new Set([...localIndexBindings.values()].map((row) => row.document_ref)).size === documents.size, '/candidate/agents_index_bindings', '索引原件、临时文档与正式路径必须完整对应。');
    for (const [reference, binding] of localIndexBindings) {
      const allocated = documentBindings.get(binding.document_ref), actual = indexBindings.get(reference);
      ensure(indexReferences.has(reference) && allocated && actual && actual.document_id === allocated.document_id && actual.source_path === allocated.source_path, '/candidate/agents_index_bindings', '正式索引引用与已确认的临时文档不一致。');
    }
    for (const rule of rules.values()) {
      const binding = ruleBindings.get(rule.rule_ref), formal = formalRules.get(binding.rule_uid); const document = documentBindings.get(rule.document_ref);
      ensure(formal && formal.document_id === binding.document_id && formal.local_rule_id === binding.local_rule_id && formal.source_path === document.source_path, '/rule_bindings', '正式规则与冻结身份不一致。');
      const projection = projectCanonicalRule(rule);
      for (const field of ['title','rule_type','tech_stacks','stages','applicability_tags']) ensure(canonical(formal[field]) === canonical(rule[field]), `/candidate/rules/${binding.rule_uid}/${field}`, '候选元信息与用户确认的规范不一致。');
      for (const field of ['requirement','good_case','bad_case']) ensure(formal[field] === projection[field], `/candidate/rules/${binding.rule_uid}/${field}`, '兼容投影与结构化正文不一致。');
      ensure(!Object.hasOwn(formal,'provenance') && !Object.hasOwn(formal,'field_origins'), '/candidate/rules', '结构化候选不能伪装成旧原文保真合同。');
      const sourcePath = sources.get(documents.get(rule.document_ref).source_ref).relative_path;
      const mappings = candidate.mappings.filter((mapping) => mapping.rule_uid === formal.rule_uid && mapping.mapping_role === 'primary');
      ensure(mappings.length > 0 && mappings.every((mapping) => mapping.relative_path === sourcePath), '/candidate/mappings', '正式规则的主来源映射与结构化文档不一致。');
      const decisions = candidate.decisions.filter((decision) => decision.rule_uid === binding.rule_uid && decision.decision === 'new');
      ensure(decisions.length === 1, '/candidate/decisions', '每条新规则需要明确绑定的审核决定。');
      for (const role of ['good', 'bad']) {
        const omitted = rule.omissions.some((item) => item.role === role);
        ensure((decisions[0][`${role}_case_omission_confirmed`] === true) === omitted, '/candidate/decisions', '示例省略确认必须来自真实正文，不能因为兼容投影为空而伪造。');
      }
    }
  }
  return { documents, rules, sources, documentBindings, ruleBindings };
}
export function renderCanonicalDocuments(content, descriptor, { ruleSet, selectedRuleUids = null } = {}) {
  const bound = validateCanonicalBindings(content, descriptor, { ruleSet });
  const allUids = new Set(descriptor.rule_bindings.map((row) => row.rule_uid));
  const selected = selectedRuleUids === null ? allUids : new Set(selectedRuleUids);
  ensure(selectedRuleUids === null || Array.isArray(selectedRuleUids) && selected.size === selectedRuleUids.length && [...selected].every((uid) => allUids.has(uid)), '/selected_rule_uids', '阶段筛选包含重复或未知规则身份。');
  const files = new Map();
  for (const document of content.documents) {
    const included = document.content.some((block) => block.type === 'rule' && selected.has(bound.ruleBindings.get(block.rule_ref).rule_uid));
    if (!included) continue;
    const body = [];
    for (const block of document.content) {
      if (block.type === 'markdown') { body.push(block.text); continue; }
      const rule = bound.rules.get(block.rule_ref), binding = bound.ruleBindings.get(block.rule_ref);
      if (!selected.has(binding.rule_uid)) continue;
      body.push(`### ${binding.local_rule_id} [${rule.execution_level === 'mandatory' ? '强制' : '推荐'}] ${rule.title}`);
      for (const item of rule.body) body.push(item.type === 'markdown' ? item.text : `${item.caption ? `${item.caption}\n\n` : ''}${exampleMarkdown(item)}`);
    }
    const yamlScalar = (value) => JSON.stringify(value).replace(/[\u007f-\u009f\u2028\u2029]/gu, (character) => `\\u${character.charCodeAt(0).toString(16).padStart(4, '0')}`);
    const frontmatter = ['---', `ruleType: ${yamlScalar(document.rule_type)}`, `description: ${yamlScalar(document.description)}`, 'level: L2', `ruleSetId: ${yamlScalar(ruleSet.rule_set_id)}`, `owner: ${yamlScalar(descriptor.owner_mis)}`, '---'].join('\n');
    const quote = (text) => text.split(/\r\n|\r|\n/u).map((line) => `> ${line}`).join('\n');
    const context = `**规则集说明**\n\n${quote(descriptor.rule_set_context.description)}\n\n**适用范围**\n\n${quote(descriptor.rule_set_context.applicability_scope)}`;
    files.set(bound.documentBindings.get(document.document_ref).source_path, `${frontmatter}\n\n# ${document.title}\n\n${context}\n\n${body.join('\n\n')}\n`);
  }
  return files;
}
