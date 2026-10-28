import { createHash } from 'node:crypto';

export const AGENTS_INDEX_CONTRACT = 'rule-set-agents-index/v1';
export const AGENTS_INDEX_MAX_BYTES = 5 * 1024 * 1024;
export const AGENTS_INDEX_MAX_JSON_BYTES = 32 * 1024 * 1024;
const hash = (value) => createHash('sha256').update(value).digest('hex');
const canonical = (value) => value === null || typeof value !== 'object' ? JSON.stringify(value)
  : Array.isArray(value) ? `[${value.map(canonical).join(',')}]`
    : `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const safeId = (value) => typeof value === 'string' && /^[a-z][a-z0-9-]{2,99}$/.test(value)
  && !/^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$/i.test(value);
const warning = (code, message, extra = {}) => ({ code, message, ...extra });
const invalid = (message) => { const error = new Error(message); error.code = 'RULE_BUNDLE_AGENTS_INDEX_INVALID'; throw error; };

// Index content is source material. Only transport integrity and binding identity are mandatory;
// Markdown quality is reported by renderAgentsIndexes and never blocks the rule download.
export function validateAgentsIndexes(body, releaseRefs, fail = (_, message) => invalid(message)) {
  const declared = body.snapshot?.agents_indexes_hash;
  if (declared == null && body.agents_indexes == null) return false;
  const reject = (message) => fail('RULE_BUNDLE_AGENTS_INDEX_INVALID', message);
  if (!Array.isArray(body.agents_indexes) || !/^[a-f0-9]{64}$/.test(declared || '')
    || hash(canonical(body.agents_indexes)) !== declared) reject('AGENTS.md 索引集合哈希校验失败');
  const seen = new Set();
  for (const entry of body.agents_indexes) {
    if (!object(entry) || !safeId(entry.rule_set_id) || typeof entry.release_id !== 'string'
      || seen.has(entry.rule_set_id)
      || !releaseRefs.some((ref) => ref.rule_set_id === entry.rule_set_id && ref.release_id === entry.release_id)) {
      reject('AGENTS.md 索引规则集或 release 身份非法');
    }
    seen.add(entry.rule_set_id);
    const index = entry.index;
    if (!object(index) || index.schema_version !== AGENTS_INDEX_CONTRACT
      || !['git', 'upload'].includes(index.origin) || typeof index.source_path !== 'string'
      || !(index.content === null || typeof index.content === 'string')
      || (index.content === null ? index.content_hash !== null : index.content_hash !== `sha256:${hash(index.content)}`)
      || (typeof index.content === 'string' && Buffer.byteLength(index.content, 'utf8') > AGENTS_INDEX_MAX_BYTES)
      || Buffer.byteLength(JSON.stringify(index), 'utf8') > AGENTS_INDEX_MAX_JSON_BYTES
      || !Array.isArray(index.warnings) || !index.warnings.every((item) => object(item)
        && typeof item.code === 'string' && typeof item.message === 'string')
      || !Array.isArray(entry.bindings)) reject('AGENTS.md 原文或内容哈希非法');
    for (const binding of entry.bindings) {
      if (!object(binding) || typeof binding.reference !== 'string'
        || typeof binding.document_id !== 'string' || typeof binding.source_path !== 'string'
        || !(binding.bundle_relative_path === null || typeof binding.bundle_relative_path === 'string')) {
        reject('AGENTS.md 引用映射非法');
      }
    }
  }
  return true;
}

// Split cells without changing their original ranges, escaped pipes or line endings.
function cells(line) {
  const separators = [];
  let escaped = false;
  let ticks = 0;
  for (let offset = 0; offset < line.length; offset++) {
    const char = line[offset];
    if (char === '\\' && !escaped) { escaped = true; continue; }
    if (char === '`' && !escaped) ticks = ticks ? 0 : 1;
    if (char === '|' && !escaped && !ticks) separators.push(offset);
    escaped = false;
  }
  if (!separators.length) return [];
  const bounds = [-1, ...separators, line.length];
  const result = bounds.slice(0, -1).map((start, index) => ({
    start: start + 1, end: bounds[index + 1], value: line.slice(start + 1, bounds[index + 1]).trim(),
  }));
  if (!result[0].value) result.shift();
  if (!result.at(-1)?.value) result.pop();
  return result;
}
const unquote = (value) => value.replace(/^`([^`]+)`$/, '$1').replace(/^\[[^\]]*\]\(([^)]+)\)$/, '$1');

// Placement is explicit: legacy separate indexes, legacy flat team roots,
// or the current scope/domain/name team roots. The wire resolver version alone
// cannot distinguish historical manifests that share a schema number.
export function agentsIndexDestinations(entries, releaseRefs, { indexPlacement = 'flat-team' } = {}) {
  if (!['separate', 'flat-team', 'named-team'].includes(indexPlacement)) invalid('AGENTS.md 索引安装布局非法');
  if (!entries?.length) return new Map();
  const refs = Array.isArray(releaseRefs) ? releaseRefs : [];
  const directories = new Map();
  const byIdentity = new Map();
  for (const ref of refs.filter(item => indexPlacement !== 'separate' && item.scope_level === 'L2')) {
    let directory;
    if (indexPlacement === 'named-team') {
      const name = ref.local_rule_set_name;
      if (!['frontend', 'backend'].includes(ref.standard_domain) || typeof name !== 'string'
        || !name || name !== name.trim() || name !== name.normalize('NFC') || name.startsWith('.')
        || /[\\/<>:"|?*\p{Cc}\p{Cf}\uD800-\uDFFF]/u.test(name) || /[. ]$/u.test(name)
        || /^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:[.]|$)/iu.test(name)
        || Buffer.byteLength(name, 'utf8') > 200) invalid('AGENTS.md 索引所属规则集名称或领域非法');
      directory = `${ref.standard_domain === 'frontend' ? 'fe' : 'java'}/${name}`;
    } else {
      directory = ref.rule_set_name || ref.rule_set_id;
      if (!safeId(directory) || (ref.rule_set_name && (directory.length > 80 || !/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(directory)))) {
        invalid('AGENTS.md 索引所属规则集目录非法');
      }
    }
    const key = directory.normalize('NFC').toUpperCase().toLowerCase().normalize('NFC');
    if (directories.has(key)) invalid('AGENTS.md 索引所属规则集目录不唯一');
    directories.set(key, ref);
    byIdentity.set(`${ref.rule_set_id}\0${ref.release_id}`, directory);
  }
  return new Map((entries || []).map(entry => {
    const matches = refs.filter(ref => ref.rule_set_id === entry.rule_set_id && ref.release_id === entry.release_id);
    if (!safeId(entry.rule_set_id) || matches.length !== 1 || !['L1', 'L2'].includes(matches[0].scope_level)) {
      invalid('AGENTS.md 索引没有唯一已发布规则集归属');
    }
    const ref = matches[0];
    return [entry.rule_set_id, indexPlacement !== 'separate' && ref.scope_level === 'L2'
      ? `team/${byIdentity.get(`${ref.rule_set_id}\0${ref.release_id}`)}/AGENTS.md`
      : `agents-index/${entry.rule_set_id}/AGENTS.md`];
  }));
}

export function renderAgentsIndexes(entries, localFiles, releaseRefs, { indexPlacement = 'flat-team' } = {}) {
  const destinations = agentsIndexDestinations(entries, releaseRefs, { indexPlacement });
  const files = [];
  const warnings = [];
  let warningCount = 0;
  const truncateDiagnostic = (value, limit) => {
    const characters = Array.from(value);
    const suffix = '…（已省略）';
    return characters.length <= limit ? value
      : characters.slice(0, limit - Array.from(suffix).length).join('') + suffix;
  };
  const addWarning = (item) => {
    warningCount += 1;
    if (warnings.length < 50) warnings.push({
      ...item,
      message: truncateDiagnostic(item.message, 256),
      ...(typeof item.path === 'string' ? { path: truncateDiagnostic(item.path, 240) } : {}),
    });
  };
  const localBySource = new Map(localFiles.map((file) => [file.source_relative_path, file.local_relative_path]));
  for (const entry of entries || []) {
    const { index } = entry;
    for (const item of index.warnings) addWarning({ ...item, rule_set_id: entry.rule_set_id });
    const warn = (code, message, extra) => addWarning({ ...warning(code, message, extra), rule_set_id: entry.rule_set_id });
    if (index.content === null) { warn('agents_index_unreadable', 'AGENTS.md 无法读取'); continue; }
    if (!index.content.trim()) warn('agents_index_empty', 'AGENTS.md 内容为空');
    const lines = index.content.split(/(?<=\n)/);
    let table = false;
    let recognized = false;
    let fence = '';
    const output = lines.map((raw, position) => {
      const line = raw.replace(/[\r\n]+$/, '');
      const fenceMatch = line.match(/^\s*(`{3,}|~{3,})/);
      if (fenceMatch) {
        if (!fence) fence = fenceMatch[1][0]; else if (fenceMatch[1][0] === fence) fence = '';
        table = false;
        return raw;
      }
      if (fence) return raw;
      const columns = cells(line);
      if (columns.length === 3 && columns.map((column) => column.value).join('|') === '名称|触发场景|路径') {
        const separator = cells((lines[position + 1] || '').replace(/[\r\n]+$/, ''));
        table = separator.length === 3 && separator.every((column) => /^:?-{3,}:?$/.test(column.value));
        recognized ||= table;
        return raw;
      }
      if (!table) return raw;
      if (columns.length !== 3) { table = false; return raw; }
      if (columns.every((column) => /^:?-{3,}:?$/.test(column.value))) return raw;
      const column = columns[2];
      const reference = unquote(column.value);
      const candidates = entry.bindings.filter((binding) => binding.reference === reference);
      const targets = new Set(candidates.map((binding) => localBySource.get(binding.bundle_relative_path)).filter(Boolean));
      if (!candidates.length || candidates.some((binding) => !localBySource.has(binding.bundle_relative_path)) || targets.size !== 1) {
        warn('agents_index_unmatched_reference', `引用无法唯一匹配本次下载文件：${reference}`, { path: reference, line: position + 1 });
        return raw;
      }
      const target = `.mdp/rules/${[...targets][0]}`;
      const replacement = column.value.startsWith('`') ? `\`${target}\``
        : /^\[[^\]]*\]\([^)]+\)$/.test(column.value) ? column.value.replace(/\([^)]+\)$/, `(${target})`) : target;
      const cell = raw.slice(column.start, column.end);
      return raw.slice(0, column.start) + cell.replace(column.value, () => replacement) + raw.slice(column.end);
    }).join('');
    if (!recognized) warn('agents_index_table_missing', '未识别到「名称 / 触发场景 / 路径」表格');
    files.push({ local_relative_path: destinations.get(entry.rule_set_id), content: output,
      sha256: hash(output), byte_size: Buffer.byteLength(output, 'utf8') });
  }
  if (warningCount > 50) warnings.push(warning('agents_index_diagnostics_omitted',
    `另有 ${warningCount - 50} 条索引诊断已省略，请结合原文件检查。`));
  return { files, warnings };
}

export function agentsManifestFields(bundle, localFiles, { indexPlacement = 'flat-team' } = {}) {
  if (!bundle.snapshot.agents_indexes_hash) return {};
  const rendered = renderAgentsIndexes(bundle.agents_indexes, localFiles, bundle.snapshot.release_refs, { indexPlacement });
  return {
    agents_index_contract: AGENTS_INDEX_CONTRACT,
    agents_indexes_hash: bundle.snapshot.agents_indexes_hash,
    agents_indexes: bundle.agents_indexes,
    managed_agents_indexes: rendered.files.map((file) => file.local_relative_path),
    managed_agents_index_hashes: Object.fromEntries(rendered.files.map((file) => [file.local_relative_path, file.sha256])),
    managed_agents_index_sizes: Object.fromEntries(rendered.files.map((file) => [file.local_relative_path, file.byte_size])),
    agents_index_warnings: [...rendered.warnings, ...bundle.snapshot.release_refs
      .filter((ref) => !bundle.agents_indexes.some((entry) => entry.rule_set_id === ref.rule_set_id))
      .map((ref) => ({ code: "agents_index_missing", message: "该规则集未提供 AGENTS.md", rule_set_id: ref.rule_set_id }))],
  };
}

export function validateAgentsManifest(manifest, { indexPlacement = 'separate' } = {}) {
  if (manifest.agents_index_contract !== AGENTS_INDEX_CONTRACT) return false;
  validateAgentsIndexes({ snapshot: manifest, agents_indexes: manifest.agents_indexes }, manifest.release_refs);
  const localFiles = manifest.managed_files.map((name) => ({
    local_relative_path: name, source_relative_path: manifest.managed_file_sources[name],
  }));
  const expected = agentsManifestFields({ snapshot: manifest, agents_indexes: manifest.agents_indexes }, localFiles, { indexPlacement });
  return ['managed_agents_indexes', 'managed_agents_index_hashes', 'managed_agents_index_sizes', 'agents_index_warnings']
    .every((key) => canonical(expected[key]) === canonical(manifest[key]));
}
