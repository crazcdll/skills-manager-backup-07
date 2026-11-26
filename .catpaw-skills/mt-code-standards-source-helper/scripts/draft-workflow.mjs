import { CONTENT_SCHEMA, CONTENT_CONTRACT, RENDER_CONTRACT, canonical, manifestDigest, PackageContractError, utf8, decodeUtf8, sha256, validateRuleMetadata } from './package-contract.mjs';
import { CONVERSION_SCHEMA, validateConversion } from './conversion-contract.mjs';
import { buildSourceUnits, parseHistoryTree, renderHistoryNode, verifyReaderEvidence } from './source-units.mjs';
import { generateAgentsIndex } from './preview.mjs';
import { validateCanonicalDraftContent } from './canonical-content.mjs';
const fail = (path, message) => { throw new PackageContractError('DRAFT_INVALID', path, message); };
const keys = (object, allowed, path) => { if (!object || typeof object !== 'object' || Array.isArray(object) || Object.keys(object).some((key) => !allowed.includes(key))) fail(path, '草稿含不支持的字段或结构。'); };
const languageNames = Object.freeze({ general: 'General', javascript: 'JavaScript', typescript: 'TypeScript', html: 'HTML', css: 'CSS', java: 'Java', spring: 'Java' });
const frameworkNames = Object.freeze({ vue: 'Vue', react: 'React', mrn: 'MRN' });
function defaultRuleMetadata(rule, document) {
  return {
    ruleType: 'Model Request',
    description: document.description || rule.title,
    level: 'L2',
    ruleTitle: rule.title,
    ruleVersion: '0.0.1',
    severity: [],
    language: [...new Set((rule.tech_stacks || []).map((value) => languageNames[value] || value))],
    framework: [...new Set((rule.tech_stacks || []).filter((value) => frameworkNames[value]).map((value) => frameworkNames[value]))],
  };
}
export function emptyDraft(source, units) {
  return { schema_version: 'source-helper-draft/v1', content: { documents: [], rules: [], coverage: units.map((unit) => ({ unit_ref: unit.unit_ref, disposition: 'excluded', targets: [], reason: '尚未整理，不能作为最终排除决定。' })), resolutions: [] }, index_entries: [], open_questions: [{ question_ref: 'prepare_content', message: '请先根据固定单元整理规范、索引与处理决定，再生成最终包。' }] };
}
async function sourceSpans(text, unitRefs, units, source, files) {
  if (!Array.isArray(unitRefs) || !unitRefs.length || new Set(unitRefs).size !== unitRefs.length) fail('/provenance/unit_refs', '原文摘取需要明确且不重复的固定单元。');
  const selected = unitRefs.map((ref) => units.get(ref)); if (selected.some((unit) => !unit)) fail('/provenance/unit_refs', '引用了不存在的固定来源单元。');
  if (selected.map((unit) => unit.text).join('') === text) return selected.map((unit) => unit.evidence_span);
  const sourceRefs = new Set(selected.map((unit) => unit.source_ref));
  if (sourceRefs.size !== 1) fail('/provenance', '跨文件摘取必须保持各单元原文顺序。');
  const sourceRef = [...sourceRefs][0]; const entry = source.files.find((file) => file.source_ref === sourceRef); const bytes = files.get(entry.package_path);
  if (source.type === 'git') {
    const ordered = [...selected].sort((a, b) => a.byte_start - b.byte_start);
    if (ordered.some((unit, i) => i && ordered[i - 1].byte_end !== unit.byte_start)) fail('/provenance', '局部摘取只能引用连续来源单元。');
    const begin = ordered[0].byte_start, end = ordered.at(-1).byte_end; const raw = decodeUtf8(bytes.subarray(begin, end));
    const at = raw.indexOf(text); if (at < 0 || raw.indexOf(text, at + 1) >= 0) fail('/provenance', '摘取内容未唯一匹配来源，请缩小单元范围或明确标记修改。');
    const byteStart = begin + utf8(raw.slice(0, at)).length, byteEnd = byteStart + utf8(text).length;
    return [{ source_ref: sourceRef, byte_start: byteStart, byte_end: byteEnd, sha256: await sha256(bytes.subarray(byteStart, byteEnd)) }];
  }
  const matches = []; const visit = (node) => {
    if (selected.some((unit) => node.byte_start >= unit.byte_start && node.byte_end <= unit.byte_end)) {
      const r = typeof node.value === 'string' ? { text: node.value, unsupported: [] } : node.value?.type ? renderHistoryNode(node.value) : null;
      if (r && !r.unsupported.length && r.text === text) matches.push(node);
    }
    for (const child of node.children.values()) visit(child);
  }; visit(parseHistoryTree(bytes));
  // Nested single-text nodes can render identically; choose the narrowest exact
  // node when all candidates describe the same nested source location.
  matches.sort((a, b) => (a.byte_end - a.byte_start) - (b.byte_end - b.byte_start));
  const match = matches[0];
  if (!match || matches.some((node) => node.byte_end <= match.byte_start || node.byte_start >= match.byte_end)) fail('/provenance', '学城摘取内容未唯一匹配固定结构，请缩小单元范围。');
  return [{ source_ref: sourceRef, byte_start: match.byte_start, byte_end: match.byte_end, sha256: await sha256(bytes.subarray(match.byte_start, match.byte_end)) }];
}
export async function materializeDraft({ request, source, files, draft }) {
  keys(draft, ['schema_version', 'content', 'index_entries', 'open_questions'], '/draft');
  if (draft.schema_version !== 'source-helper-draft/v1') fail('/draft/schema_version', '不支持此草稿版本。');
  keys(draft.content, ['documents', 'rules', 'coverage', 'resolutions'], '/draft/content');
  const content = structuredClone(draft.content);
  if (!Array.isArray(content.documents) || !Array.isArray(content.rules) || !Array.isArray(content.coverage) || !Array.isArray(content.resolutions) || !Array.isArray(draft.open_questions) || !Array.isArray(draft.index_entries)) fail('/draft', '草稿需要完整的数组字段。');
  for (const question of draft.open_questions) { keys(question, ['question_ref', 'message'], '/open_questions'); if (typeof question.question_ref !== 'string' || typeof question.message !== 'string' || !question.message.trim()) fail('/open_questions', '待确认项必须包含标识和说明。'); }
  const unitsList = await buildSourceUnits(source, files), units = new Map(unitsList.map((unit) => [unit.unit_ref, unit]));
  const convertBlock = async (block) => {
    keys(block.provenance, ['origin', 'unit_refs', 'reason'], '/provenance');
    const refs = block.provenance.unit_refs; if (!Array.isArray(refs) || refs.some((ref) => !units.has(ref))) fail('/provenance/unit_refs', '来源单元引用无效。');
    const spans = block.provenance.origin === 'source_extract'
      ? await sourceSpans(block.type === 'example' ? block.code : block.text, refs, units, source, files)
      : refs.map((ref) => units.get(ref).evidence_span);
    return { ...block, provenance: { origin: block.provenance.origin, source_spans: spans, reason: block.provenance.reason || '' } };
  };
  const byDocument = new Map(content.documents.map((document) => [document.document_ref, document]));
  for (const document of content.documents) document.content = await Promise.all((document.content || []).map((block) => block.type === 'rule' ? block : convertBlock(block)));
  for (const rule of content.rules) {
    const document = byDocument.get(rule.document_ref);
    if (!document) fail(`/content/rules/${rule.rule_ref}/document_ref`, '规则引用了不存在的规范文档。');
    if (rule.metadata === undefined) rule.metadata = defaultRuleMetadata(rule, document);
    else {
      const path = `/content/rules/${rule.rule_ref}/metadata`;
      keys(rule.metadata, ['ruleType', 'description', 'level', 'ruleTitle', 'ruleVersion', 'severity', 'language', 'framework', 'category', 'status'], path);
      if (Object.hasOwn(rule.metadata, 'category') || Object.hasOwn(rule.metadata, 'status')) {
        validateRuleMetadata(rule.metadata, path);
        delete rule.metadata.category;
        delete rule.metadata.status;
      }
    }
    rule.body = await Promise.all((rule.body || []).map(convertBlock));
  }
  content.coverage = content.coverage.map((item) => { keys(item, ['unit_ref', 'disposition', 'targets', 'reason'], '/coverage'); const unit = units.get(item.unit_ref); if (!unit) fail('/coverage/unit_ref', '覆盖记录不属于固定读取器结果。'); return { source_ref: unit.source_ref, unit_ref: unit.unit_ref, byte_start: unit.byte_start, byte_end: unit.byte_end, disposition: item.disposition, targets: item.targets, reason: item.reason || '' }; });
  content.schema_version = CONTENT_SCHEMA; content.content_contract = CONTENT_CONTRACT;
  const byDoc = byDocument;
  for (const row of draft.index_entries) {
    keys(row, ['group', 'name', 'scene', 'document_ref'], '/index_entries');
    if (typeof row.scene !== 'string' || !row.scene.trim()) fail('/index_entries', '请补充读取此文件的触发条件。');
    if (!byDoc.has(row.document_ref)) fail('/index_entries', '索引引用了不存在的文档。');
  }
  const generated = generateAgentsIndex(content, source, draft.index_entries);
  content.agents_index = { schema_version: 'rule-set-agents-index/v1', path: 'AGENTS.md', bindings: generated.bindings };
  const payload = new Map(files); payload.set('content.json', utf8(canonical(content))); payload.set('AGENTS.md', utf8(generated.markdown));
  const manifest = { schema_version: CONVERSION_SCHEMA, operation: 'normalize_source', source, render_contract: RENDER_CONTRACT, converter: { name: 'mt-code-standards-source-helper', version: '0.2.0' }, counts: { sources: source.files.length, documents: content.documents.length, rules: content.rules.length, excluded_units: content.coverage.filter((unit) => unit.disposition === 'excluded').length }, files: [], content_digest: '' };
  for (const path of [...payload.keys()].sort()) manifest.files.push({ path, byte_size: payload.get(path).length, sha256: await sha256(payload.get(path)) });
  manifest.content_digest = await manifestDigest(manifest); payload.set('manifest.json', utf8(canonical(manifest)));
  let validation = null;
  try { validateCanonicalDraftContent(content); await verifyReaderEvidence(await validateConversion(payload, { requireConfirmation: false }), payload); } catch (error) { if (!(error instanceof PackageContractError)) throw error; validation = { code: error.code, path: error.path, message: error.message }; }
  let requestedRef = null;
  if (source.type === 'git') {
    requestedRef = request.branch || null;
    if (!requestedRef && request.source_url) { try { requestedRef = new URL(request.source_url).searchParams.get('branch'); } catch { /* SSH input uses the explicit branch field. */ } }
    if (requestedRef && !requestedRef.startsWith('refs/')) requestedRef = `refs/heads/${requestedRef}`;
  }
  return { manifest, content, payload, agentsIndex: generated.markdown, questions: draft.open_questions, validation, units: unitsList, requestedRef };
}
