// Portable contract: no filesystem, process, network, or Node-specific imports.
// The platform must separately establish source authenticity and user authority.
export const PACKAGE_SCHEMA = 'rule-local-package/v1';
export const CONTENT_SCHEMA = 'rule-local-content/v1';
export const CONFIRMATION_SCHEMA = 'rule-local-confirmation/v1';
export const CONTENT_CONTRACT = 'rule-canonical-content/v1';
export const RENDER_CONTRACT = 'rule-markdown/v2';
export const LIMITS = Object.freeze({
  sourceFileBytes: 128 * 1024, sourceTotalBytes: 256 * 1024,
  sourceFiles: 50, rules: 200, contentBytes: 512 * 1024,
  indexBytes: 64 * 1024, manifestBytes: 64 * 1024,
  confirmationBytes: 16 * 1024, expandedBytes: 1024 * 1024,
  zipBytes: 2 * 1024 * 1024, entries: 54, jsonDepth: 32,
});
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });
const HASH_PATTERN = '^sha256:[0-9a-f]{64}$';
const REF_PATTERN = '^[a-z][a-z0-9_-]{0,63}$';
const FORBIDDEN_KEYS = new Set(['__proto__', 'prototype', 'constructor']);

export class PackageContractError extends Error {
  constructor(code, path, message) {
    super(message);
    this.name = 'PackageContractError';
    this.code = code;
    this.path = path;
  }
}
const fail = (code, path, message) => { throw new PackageContractError(code, path, message); };
const pointer = (path, key) => `${path}/${String(key).replace(/~/g, '~0').replace(/\//g, '~1')}`;
export const utf8 = (value) => encoder.encode(value);
export function decodeUtf8(bytes, path = '') {
  if (!(bytes instanceof Uint8Array)) fail('PACKAGE_BYTES_INVALID', path, '文件内容必须是原始字节。');
  try { return decoder.decode(bytes); } catch { return fail('PACKAGE_UTF8_INVALID', path, '文件不是有效的 UTF-8 编码。'); }
}
function validString(value, path) {
  if (value.includes('\0')) fail('PACKAGE_TEXT_INVALID', path, '内容包含无法保存的 NUL 字符。');
  for (let i = 0; i < value.length; i += 1) {
    const n = value.charCodeAt(i);
    if (n >= 0xd800 && n <= 0xdbff) {
      const next = value.charCodeAt(++i);
      if (!(next >= 0xdc00 && next <= 0xdfff)) fail('PACKAGE_TEXT_INVALID', path, '内容包含不完整的 Unicode 字符。');
    } else if (n >= 0xdc00 && n <= 0xdfff) fail('PACKAGE_TEXT_INVALID', path, '内容包含不完整的 Unicode 字符。');
  }
}
function assertJson(value, path = '', depth = 0) {
  if (depth > LIMITS.jsonDepth) fail('PACKAGE_JSON_DEPTH', path, 'JSON 嵌套层级超过上限。');
  if (value === null || typeof value === 'boolean') return;
  if (typeof value === 'string') return validString(value, path);
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) fail('PACKAGE_NUMBER_INVALID', path, 'JSON 数值必须是安全整数，不能使用负零。');
    return;
  }
  if (Array.isArray(value)) {
    if (Reflect.ownKeys(value).length !== value.length + 1) fail('PACKAGE_JSON_INVALID', path, 'JSON 数组不能有空洞或额外属性。');
    for (let i = 0; i < value.length; i += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(i));
      if (!descriptor || !descriptor.enumerable || !Object.hasOwn(descriptor, 'value')) fail('PACKAGE_JSON_INVALID', pointer(path, i), 'JSON 数组必须是连续数据。');
      assertJson(descriptor.value, pointer(path, i), depth + 1);
    }
    return;
  }
  if (typeof value !== 'object' || Object.getPrototypeOf(value) !== Object.prototype || Object.getOwnPropertySymbols(value).length) {
    fail('PACKAGE_JSON_INVALID', path, '只接受普通 JSON 对象。');
  }
  for (const key of Object.getOwnPropertyNames(value)) {
    validString(key, path);
    if (FORBIDDEN_KEYS.has(key)) fail('PACKAGE_JSON_INVALID', pointer(path, key), 'JSON 包含不允许的属性名。');
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor || !descriptor.enumerable || !Object.hasOwn(descriptor, 'value')) fail('PACKAGE_JSON_INVALID', pointer(path, key), 'JSON 属性必须是可枚举数据。');
    assertJson(descriptor.value, pointer(path, key), depth + 1);
  }
}

// UTF-16 key order is the ECMAScript default sort. Arrays retain input order.
// Strings retain their exact Unicode sequence and line endings; no NFC/trim.
export function canonical(value) {
  assertJson(value);
  const render = (item) => {
    if (item === null || typeof item !== 'object') return JSON.stringify(item);
    if (Array.isArray(item)) return `[${item.map(render).join(',')}]`;
    return `{${Object.keys(item).sort().map((key) => `${JSON.stringify(key)}:${render(item[key])}`).join(',')}}`;
  };
  return render(value);
}
export async function sha256(bytes) {
  if (!(bytes instanceof Uint8Array)) fail('PACKAGE_BYTES_INVALID', '', 'Hash 输入必须是原始字节。');
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return `sha256:${Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')}`;
}
export const canonicalHash = (value) => sha256(utf8(canonical(value)));

// JSON.parse alone accepts duplicate keys and loses the overwritten value.
export function parseStrictJson(bytes, path = '', maxBytes = LIMITS.contentBytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length > maxBytes) fail('PACKAGE_FILE_LIMIT', path, 'JSON 文件超过大小上限。');
  const input = decodeUtf8(bytes, path);
  let at = 0;
  const invalid = () => fail('PACKAGE_JSON_INVALID', path, '文件不是严格有效的 JSON。');
  const space = () => { while (/[\x20\t\r\n]/.test(input[at] || '\u0001')) at += 1; };
  const string = () => {
    const begin = at++;
    let escaped = false;
    while (at < input.length) {
      const ch = input[at++];
      if (!escaped && ch === '"') {
        let result;
        try { result = JSON.parse(input.slice(begin, at)); } catch { return invalid(); }
        validString(result, path);
        return result;
      }
      if (!escaped && ch === '\\') escaped = true;
      else escaped = false;
    }
    return invalid();
  };
  const value = (depth) => {
    if (depth > LIMITS.jsonDepth) fail('PACKAGE_JSON_DEPTH', path, 'JSON 嵌套层级超过上限。');
    space();
    const ch = input[at];
    if (ch === '"') return string();
    if (ch === '{') {
      at += 1; space(); const object = {}; const keys = new Set();
      if (input[at] === '}') { at += 1; return object; }
      while (at < input.length) {
        space(); if (input[at] !== '"') return invalid();
        const key = string();
        if (keys.has(key)) fail('PACKAGE_JSON_DUPLICATE_KEY', pointer(path, key), 'JSON 属性重复。');
        if (FORBIDDEN_KEYS.has(key)) fail('PACKAGE_JSON_INVALID', pointer(path, key), 'JSON 包含不允许的属性名。');
        keys.add(key); space(); if (input[at++] !== ':') return invalid();
        object[key] = value(depth + 1); space();
        const sep = input[at++]; if (sep === '}') return object; if (sep !== ',') return invalid();
      }
      return invalid();
    }
    if (ch === '[') {
      at += 1; space(); const array = [];
      if (input[at] === ']') { at += 1; return array; }
      while (at < input.length) {
        array.push(value(depth + 1)); space();
        const sep = input[at++]; if (sep === ']') return array; if (sep !== ',') return invalid();
      }
      return invalid();
    }
    for (const [word, literal] of [['true', true], ['false', false], ['null', null]]) {
      if (input.startsWith(word, at)) { at += word.length; return literal; }
    }
    const match = input.slice(at).match(/^-?(?:0|[1-9][0-9]*)/);
    if (!match) return invalid();
    at += match[0].length;
    const result = Number(match[0]);
    if (/[.eE]/.test(input[at] || '\u0001') || !Number.isSafeInteger(result) || Object.is(result, -0)) {
      fail('PACKAGE_NUMBER_INVALID', path, 'JSON 数值必须是安全整数，不能使用浮点数、指数或负零。');
    }
    return result;
  };
  const result = value(0); space(); if (at !== input.length) invalid();
  assertJson(result, path);
  return result;
}

const object = (properties) => ({ type: 'object', additionalProperties: false, required: Object.keys(properties), properties });
const string = (maxLength, minLength = 1, pattern) => ({ type: 'string', minLength, maxLength, ...(pattern ? { pattern } : {}) });
const array = (items, maxItems, minItems = 0, uniqueItems = false) => ({ type: 'array', minItems, maxItems, items, ...(uniqueItems ? { uniqueItems: true } : {}) });
const enumeration = (...values) => ({ enum: values });
const literal = (value) => ({ const: value });
const ref = (name) => ({ $ref: `#/$defs/${name}` });
const integer = (maximum, minimum = 0) => ({ type: 'integer', minimum, maximum });

const key = string(64, 1, REF_PATTERN);
const hash = string(71, 71, HASH_PATTERN);
const slug = string(64, 1, '^[a-z][a-z0-9_-]*$');
const textBlock = object({ type: literal('markdown'), text: string(65536), provenance: ref('provenance') });
const exampleBlock = object({
  type: literal('example'), role: enumeration('good', 'bad', 'neutral'),
  language: string(40, 1, '^[a-zA-Z0-9_+.#-]+$'), code: string(65536),
  caption: string(1000, 0), provenance: ref('provenance'),
});
const sourceCommon = {
  reader_contract: literal('fixed-source/v1'),
  files: array(ref('sourceFile'), LIMITS.sourceFiles, 1),
};

// The YAML header is part of the single-rule contract.  Platform-owned fields
// (ruleSetId and owner) are deliberately added only when the platform renders
// a confirmed L2 rule set; they are not accepted as local conversion input.
const singleRuleMetadata = object({
  ruleType: literal('Model Request'),
  description: string(2000),
  level: literal('L2'),
  ruleTitle: string(200),
  ruleVersion: string(40, 1, '^[0-9]+\\.[0-9]+\\.[0-9]+$'),
  category: array(string(64), 20, 1, true),
  severity: array(enumeration('P0', 'P1', 'P2', 'P3'), 4, 0, true),
  status: array(enumeration('open', 'closed'), 2, 1, true),
  language: array(string(64), 20, 0, true),
  framework: array(string(64), 20, 0, true),
});
export const PACKAGE_JSON_SCHEMA = {
  $schema: 'https://json-schema.org/draft/2020-12/schema',
  $id: 'urn:mt-code-standards:rule-local-package:v1',
  title: '本地规范标准包 V1 的解析后结构',
  ...object({ manifest: ref('manifest'), content: ref('content'), confirmation: ref('confirmation') }),
  $defs: {
    sourceFile: object({
      source_ref: key, source_path: string(240), package_path: string(240),
      representation: enumeration('git-raw-utf8', 'citadel-history-json'),
      sha256: hash, byte_size: integer(LIMITS.sourceFileBytes, 1),
    }),
    source: { oneOf: [
      object({ type: literal('git'), ...sourceCommon,
        locator: object({ repository_url: string(1000), root_path: string(240, 0) }),
        revision: object({ commit: string(40, 40, '^[0-9a-f]{40}$') }),
      }),
      object({ type: literal('km'), ...sourceCommon,
        locator: object({ content_id: string(30, 1, '^[1-9][0-9]*$'), url: string(1000), document_type: enumeration(3, 7) }),
        revision: object({ step_version: integer(Number.MAX_SAFE_INTEGER, 1) }),
      }),
    ] },
    manifest: object({
      schema_version: literal(PACKAGE_SCHEMA), operation: literal('create_l2'),
      standard_domain: enumeration('frontend', 'backend'), scope_level: literal('L2'),
      rule_set: object({ name: string(80, 3, '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'), display_name: string(120), description: string(2000), owner_mis: string(64, 1, '^[a-z][a-z0-9._-]*$'), applicability_scope: string(2000) }),
      source: ref('source'), render_contract: literal(RENDER_CONTRACT),
      converter: object({ name: literal('mt-code-standards-source-helper'), version: string(40, 1, '^[0-9]+\\.[0-9]+\\.[0-9]+$') }),
      counts: object({ sources: integer(50, 1), documents: integer(50, 1), rules: integer(200, 1), excluded_units: integer(4096) }),
      files: array(object({ path: string(240), byte_size: integer(LIMITS.contentBytes, 1), sha256: hash }), 52, 3),
      content_digest: hash,
    }),
    span: object({ source_ref: key, byte_start: integer(LIMITS.sourceFileBytes), byte_end: integer(LIMITS.sourceFileBytes, 1), sha256: hash }),
    provenance: object({ origin: enumeration('source_extract', 'agent_generated', 'user_modified'), source_spans: array(ref('span'), 200), reason: string(2000, 0) }),
    document: object({
      document_ref: key, source_ref: key, title: string(200), description: string(2000), category_key: slug, subcategory_key: slug,
      rule_type: literal('Model Request'),
      content: array({ oneOf: [textBlock, object({ type: literal('rule'), rule_ref: key })] }, 4096, 1),
    }),
    rule: (() => {
      const schema = object({
      rule_ref: key, document_ref: key, title: string(200), execution_level: enumeration('mandatory', 'recommended'),
      category_key: slug, subcategory_key: slug, rule_type: literal('Model Request'),
      tech_stacks: array(enumeration('general', 'javascript', 'typescript', 'html', 'css', 'vue', 'react', 'mrn', 'java', 'spring'), 10, 1, true),
      stages: array(enumeration('design', 'coding', 'cr'), 3, 1, true),
      applicability_tags: array(string(200), 20, 0, true),
      body: array({ oneOf: [textBlock, exampleBlock] }, 4096, 1),
      omissions: array(object({ role: enumeration('good', 'bad'), reason: string(2000) }), 2),
      });
      schema.properties.metadata = singleRuleMetadata;
      return schema;
    })(),
    content: object({
      schema_version: literal(CONTENT_SCHEMA), content_contract: literal(CONTENT_CONTRACT),
      documents: array(ref('document'), 50, 1), rules: array(ref('rule'), 200, 1),
      coverage: array(object({
        source_ref: key, unit_ref: key, byte_start: integer(LIMITS.sourceFileBytes), byte_end: integer(LIMITS.sourceFileBytes, 1),
        disposition: enumeration('included', 'support', 'excluded'), targets: array(key, 250, 0, true), reason: string(2000, 0),
      }), 4096, 1),
      resolutions: array(object({ question_ref: key, kind: enumeration('conflict', 'omission', 'exclusion', 'scope', 'other'), decision: string(2000), explanation: string(2000), affected_refs: array(key, 250, 1, true) }), 1000),
      agents_index: object({ schema_version: literal('rule-set-agents-index/v1'), path: literal('AGENTS.md'), bindings: array(object({ reference: string(1000), document_ref: key }), 1000, 1) }),
    }),
    confirmation: object({
      schema_version: literal(CONFIRMATION_SCHEMA), content_digest: hash, decision: literal('confirmed'),
      confirmed_at: string(30, 20, '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\\.[0-9]{3})?Z$'),
      confirmed_scope: object({ content: literal(true), agents_index: literal(true), exclusions: literal(true), generated_changes: literal(true) }),
    }),
  },
};

// Evaluates the fixed vocabulary used by PACKAGE_JSON_SCHEMA; callers cannot
// provide a different schema. Cross-field invariants are checked below.
function schemaErrors(value, schema, path) {
  if (schema.$ref) return schemaErrors(value, PACKAGE_JSON_SCHEMA.$defs[schema.$ref.slice('#/$defs/'.length)], path);
  if (schema.oneOf || schema.anyOf) {
    const branches = schema.oneOf || schema.anyOf;
    const results = Array.from(branches, (branch) => schemaErrors(value, branch, path));
    const valid = results.filter((errors) => errors.length === 0).length;
    if (schema.oneOf ? valid === 1 : valid > 0) return [];
    return results.sort((a, b) => a.length - b.length)[0].length ? results.sort((a, b) => a.length - b.length)[0] : [{ path, message: '字段不符合唯一允许的结构。' }];
  }
  const errors = [];
  const add = (message, target = path) => errors.push({ path: target, message });
  if (Object.hasOwn(schema, 'const') && value !== schema.const) add('字段值不在支持的合同内。');
  if (schema.enum && !schema.enum.includes(value)) add('字段值不在允许范围内。');
  if (!schema.type) return errors;
  const types = { object: value !== null && !Array.isArray(value) && typeof value === 'object', array: Array.isArray(value), string: typeof value === 'string', integer: Number.isSafeInteger(value), null: value === null };
  if (!types[schema.type]) { add(`字段类型必须为 ${schema.type}。`); return errors; }
  if (schema.type === 'object') {
    for (const key of schema.required || []) if (!Object.hasOwn(value, key)) add('缺少必填字段。', pointer(path, key));
    for (const key of Object.keys(value)) {
      if (!Object.hasOwn(schema.properties, key)) add('包含未定义字段。', pointer(path, key));
      else errors.push(...schemaErrors(value[key], schema.properties[key], pointer(path, key)));
    }
  } else if (schema.type === 'array') {
    if (value.length < schema.minItems || value.length > schema.maxItems) { add('数组项数超出允许范围。'); return errors; }
    if (schema.uniqueItems && new Set(value.map(canonical)).size !== value.length) add('数组项重复。');
    value.forEach((item, i) => errors.push(...schemaErrors(item, schema.items, pointer(path, i))));
  } else if (schema.type === 'string') {
    const length = Array.from(value).length;
    if (length < schema.minLength || length > schema.maxLength || (schema.minLength > 0 && !value.trim())) add('文本为空或超过长度上限。');
    if (schema.pattern && !new RegExp(schema.pattern, 'u').test(value)) add('文本格式不符合要求。');
  } else if (schema.type === 'integer' && (value < schema.minimum || value > schema.maximum)) add('整数超出允许范围。');
  return errors;
}
function validateAgainstSchema(value, schema, path) {
  assertJson(value);
  const errors = schemaErrors(value, schema, path);
  if (errors.length) fail('PACKAGE_SCHEMA_INVALID', errors[0].path, errors[0].message);
  return value;
}
export const validateManifest = (value) => validateAgainstSchema(value, PACKAGE_JSON_SCHEMA.$defs.manifest, '/manifest');
export const validateContent = (value) => validateAgainstSchema(value, PACKAGE_JSON_SCHEMA.$defs.content, '/content');
export const validateConfirmation = (value) => validateAgainstSchema(value, PACKAGE_JSON_SCHEMA.$defs.confirmation, '/confirmation');
export function validateRuleSetIntent(value) {
  assertJson(value);
  const errors = schemaErrors(value, PACKAGE_JSON_SCHEMA.$defs.manifest.properties.rule_set, '/rule_set');
  if (errors.length) fail('PACKAGE_SCHEMA_INVALID', errors[0].path, errors[0].message);
  if (/^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$/u.test(value.name)) fail('PACKAGE_NAME_INVALID', '/rule_set/name', '规则集名称不能使用系统保留名称。');
  return value;
}
export async function manifestDigest(manifest) {
  const { content_digest: _digest, ...input } = manifest;
  return canonicalHash(input);
}

export function safeRelativePath(value, path = '') {
  if (typeof value !== 'string' || !value || value.length > 240 || value.startsWith('/') || /[\\:\x00-\x1f\x7f]/u.test(value)
    || value.split('/').some((part) => !part || part === '.' || part === '..' || part.endsWith('.') || part.endsWith(' '))) {
    fail('PACKAGE_PATH_INVALID', path, '文件路径必须是受控的相对路径。');
  }
  return value;
}
const ensure = (condition, code, path, message) => { if (!condition) fail(code, path, message); };
const uniqueBy = (values, key, path) => {
  const map = new Map();
  values.forEach((item, i) => {
    ensure(!map.has(item[key]), 'PACKAGE_REFERENCE_INVALID', pointer(path, i), '标识或路径重复。');
    map.set(item[key], item);
  });
  return map;
};
export function agentsRows(markdown) {
  const rows = []; const lines = markdown.split(/\r?\n/u); let inTable = false; let fence = null;
  const cells = (line) => line.trim().replace(/^\|/u, '').replace(/\|$/u, '').split(/(?<!\\)\|/u).map((x) => x.trim());
  for (let i = 0; i < lines.length; i += 1) {
    const marker = lines[i].trim().match(/^(`{3,}|~{3,})/u)?.[1];
    if (marker) { if (!fence) fence = marker[0]; else if (fence === marker[0]) fence = null; inTable = false; continue; }
    if (fence) continue;
    const row = cells(lines[i]);
    const header = row.join('|');
    if ((header === '名称|触发场景|路径' || header === '分类|规则文件|Rule UID 范围|触发场景') && cells(lines[i + 1] || '').length === row.length && cells(lines[i + 1] || '').every((c) => /^:?-{3,}:?$/u.test(c))) { inTable = row.length === 4 ? 'file' : 'topic'; i += 1; continue; }
    const expected = inTable === 'file' ? 4 : 3;
    if (!inTable || !lines[i].includes('|') || row.length !== expected) { inTable = false; continue; }
    const reference = (inTable === 'file' ? row[1] : row[2]).replace(/^`+|`+$/gu, '').replace(/^\[[^\]]*\]\(([^)]+)\)$/u, '$1');
    ensure(row.every(Boolean) && reference, 'PACKAGE_INDEX_INVALID', `/AGENTS.md/${i + 1}`, '索引行需要名称、触发场景和真实引用。');
    rows.push({ name: row[0], scene: inTable === 'file' ? row[3] : row[1], reference, line: i + 1 });
  }
  ensure(rows.length > 0, 'PACKAGE_INDEX_INVALID', '/AGENTS.md', '缺少有效的规则集索引表格。');
  return rows;
}
const kmIdentity = (value) => {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.hostname !== 'km.sankuai.com' || url.port || url.username || url.password || url.search || url.hash) return null;
    return url.pathname.match(/^\/(?:collabpage|page|md)\/([1-9][0-9]*)(?:\.md)?\/?$/u)?.[1] || null;
  } catch { return null; }
};
export function indexReferenceKey(value, sourceType) {
  if (sourceType === 'km') return kmIdentity(value) ? `km:${kmIdentity(value)}` : null;
  return value.startsWith('./') ? value.slice(2) : value;
}

export async function validatePackage(files, { requireConfirmation = true } = {}) {
  ensure(files instanceof Map, 'PACKAGE_FILES_INVALID', '', '标准包需要完整的文件集合。');
  ensure(files.size >= (requireConfirmation ? 5 : 4) && files.size <= LIMITS.entries, 'PACKAGE_FILE_LIMIT', '', '标准包文件数量超出上限。');
  let total = 0;
  for (const [path, bytes] of files) {
    safeRelativePath(path, path);
    ensure(bytes instanceof Uint8Array, 'PACKAGE_BYTES_INVALID', path, '文件必须保留原始字节。');
    total += bytes.length;
    ensure(total <= LIMITS.expandedBytes, 'PACKAGE_FILE_LIMIT', '', '标准包展开大小超过上限。');
  }
  for (const path of ['manifest.json', 'content.json', 'AGENTS.md', ...(requireConfirmation ? ['confirmation.json'] : [])]) {
    ensure(files.has(path), 'PACKAGE_FILE_MISSING', path, '标准包缺少必需文件。');
  }
  const manifest = validateManifest(parseStrictJson(files.get('manifest.json'), '/manifest.json', LIMITS.manifestBytes));
  const content = validateContent(parseStrictJson(files.get('content.json'), '/content.json', LIMITS.contentBytes));
  const confirmation = files.has('confirmation.json') ? validateConfirmation(parseStrictJson(files.get('confirmation.json'), '/confirmation.json', LIMITS.confirmationBytes)) : null;
  if (confirmation) {
    const time = new Date(confirmation.confirmed_at);
    ensure(!Number.isNaN(time.getTime()) && time.toISOString().replace('.000Z', 'Z') === confirmation.confirmed_at.replace('.000Z', 'Z'), 'PACKAGE_CONFIRMATION_INVALID', '/confirmation/confirmed_at', '确认时间不是有效的 UTC 时间。');
  }
  ensure(!/[\\/\x00-\x1f]/u.test(manifest.rule_set.name) && manifest.rule_set.name === manifest.rule_set.name.trim() && !['.', '..'].includes(manifest.rule_set.name), 'PACKAGE_NAME_INVALID', '/manifest/rule_set/name', '规则集名称不能包含路径分隔符或首尾空白。');
  ensure(!/^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$/u.test(manifest.rule_set.name), 'PACKAGE_NAME_INVALID', '/manifest/rule_set/name', '规则集名称不能使用系统保留名称。');

  const listed = uniqueBy(manifest.files, 'path', '/manifest/files');
  ensure(canonical([...listed.keys()]) === canonical([...listed.keys()].sort()), 'PACKAGE_FILES_INVALID', '/manifest/files', '载荷清单必须按路径的 UTF-16 顺序排序。');
  ensure(!listed.has('manifest.json') && !listed.has('confirmation.json'), 'PACKAGE_FILES_INVALID', '/manifest/files', '载荷清单不能包含 manifest 或 confirmation。');
  const expected = new Set(['manifest.json', ...(confirmation ? ['confirmation.json'] : []), ...listed.keys()]);
  ensure(expected.size === files.size && [...files.keys()].every((path) => expected.has(path)), 'PACKAGE_FILES_INVALID', '/manifest/files', '文件集合与载荷清单不一致。');
  for (const [i, entry] of manifest.files.entries()) {
    safeRelativePath(entry.path, `/manifest/files/${i}/path`);
    const bytes = files.get(entry.path);
    ensure(bytes && bytes.length === entry.byte_size && await sha256(bytes) === entry.sha256, 'PACKAGE_HASH_MISMATCH', `/manifest/files/${i}`, '文件长度或校验值不匹配。');
  }
  ensure(listed.has('content.json') && listed.has('AGENTS.md'), 'PACKAGE_FILES_INVALID', '/manifest/files', '载荷清单必须包含规范内容和索引。');
  ensure(await manifestDigest(manifest) === manifest.content_digest, 'PACKAGE_HASH_MISMATCH', '/manifest/content_digest', '规范内容校验值不匹配。');
  if (confirmation) ensure(confirmation.content_digest === manifest.content_digest, 'PACKAGE_CONFIRMATION_INVALID', '/confirmation/content_digest', '确认记录不属于当前内容，请重新预览并确认。');

  const source = manifest.source;
  const sources = uniqueBy(source.files, 'source_ref', '/manifest/source/files');
  uniqueBy(source.files, 'source_path', '/manifest/source/files');
  uniqueBy(source.files, 'package_path', '/manifest/source/files');
  const sourceBytes = new Map(); let sourceTotal = 0;
  if (source.type === 'git') {
    let url;
    try { url = new URL(source.locator.repository_url); } catch { fail('PACKAGE_SOURCE_INVALID', '/manifest/source/locator/repository_url', 'Git 来源地址无效。'); }
    ensure(url.protocol === 'https:' && ['git.sankuai.com', 'code.sankuai.com'].includes(url.hostname) && !url.port && !url.username && !url.password && !url.search && !url.hash, 'PACKAGE_SOURCE_INVALID', '/manifest/source/locator/repository_url', 'Git 来源必须是受支持的代码平台 HTTPS 地址。');
    ensure(url.pathname.split('/').filter(Boolean).length >= 2, 'PACKAGE_SOURCE_INVALID', '/manifest/source/locator/repository_url', 'Git 地址缺少仓库定位。');
    if (source.locator.root_path) safeRelativePath(source.locator.root_path, '/manifest/source/locator/root_path');
  } else {
    ensure(kmIdentity(source.locator.url) === source.locator.content_id && source.files.length === 1, 'PACKAGE_SOURCE_INVALID', '/manifest/source/locator', '学城来源须为一个固定文档，地址与身份必须一致。');
  }
  for (const [i, entry] of source.files.entries()) {
    const path = `/manifest/source/files/${i}`;
    safeRelativePath(entry.source_path, `${path}/source_path`);
    safeRelativePath(entry.package_path, `${path}/package_path`);
    ensure(/^sources\/[a-z][a-z0-9_-]{0,63}\.(?:md|json|txt)$/u.test(entry.package_path), 'PACKAGE_PATH_INVALID', `${path}/package_path`, '快照必须使用 sources 目录中的受控文件名。');
    const expectedRepresentation = source.type === 'git' ? 'git-raw-utf8' : 'citadel-history-json';
    ensure(entry.representation === expectedRepresentation, 'PACKAGE_SOURCE_INVALID', `${path}/representation`, '来源快照表示与来源类型不匹配。');
    const declaration = listed.get(entry.package_path);
    ensure(declaration && declaration.sha256 === entry.sha256 && declaration.byte_size === entry.byte_size, 'PACKAGE_SOURCE_INVALID', path, '来源快照与载荷清单不一致。');
    const bytes = files.get(entry.package_path);
    const text = decodeUtf8(bytes, entry.package_path); validString(text, entry.package_path);
    ensure(text.trim().length > 0, 'PACKAGE_SOURCE_INVALID', path, '来源快照不能为空白。');
    sourceTotal += bytes.length;
    ensure(sourceTotal <= LIMITS.sourceTotalBytes, 'PACKAGE_FILE_LIMIT', '/manifest/source/files', '来源总大小超过上限。');
    sourceBytes.set(entry.source_ref, bytes);
  }
  ensure(listed.size === sources.size + 2 && [...listed.keys()].every((path) => path === 'content.json' || path === 'AGENTS.md' || source.files.some((entry) => entry.package_path === path)), 'PACKAGE_FILES_INVALID', '/manifest/files', '载荷清单包含未使用的文件。');

  const documents = uniqueBy(content.documents, 'document_ref', '/content/documents');
  const rules = uniqueBy(content.rules, 'rule_ref', '/content/rules');
  const units = uniqueBy(content.coverage, 'unit_ref', '/content/coverage');
  uniqueBy(content.resolutions, 'question_ref', '/content/resolutions');
  const allRefs = [...sources.keys(), ...documents.keys(), ...rules.keys(), ...units.keys()];
  ensure(new Set(allRefs).size === allRefs.length, 'PACKAGE_REFERENCE_INVALID', '/content', '来源、文档、规则与覆盖单元的临时标识必须全局唯一。');
  const docSources = new Map(); const usedRules = new Set();
  for (const [i, doc] of content.documents.entries()) {
    const path = `/content/documents/${i}`;
    ensure(sources.has(doc.source_ref) && !docSources.has(doc.source_ref), 'PACKAGE_REFERENCE_INVALID', `${path}/source_ref`, '物理文档必须唯一对应本次一个来源文件。');
    docSources.set(doc.source_ref, doc.document_ref);
    let count = 0;
    for (const [j, block] of doc.content.entries()) if (block.type === 'rule') {
      const rule = rules.get(block.rule_ref);
      ensure(rule && rule.document_ref === doc.document_ref && !usedRules.has(block.rule_ref), 'PACKAGE_REFERENCE_INVALID', `${path}/content/${j}`, '规则引用缺失、重复或不属于此文档。');
      usedRules.add(block.rule_ref); count += 1;
    }
    ensure(count > 0, 'PACKAGE_REFERENCE_INVALID', `${path}/content`, '纳入的物理文档至少需要一条规则。');
  }
  ensure(usedRules.size === rules.size, 'PACKAGE_REFERENCE_INVALID', '/content/rules', '存在没有进入正文的规则。');
  const allowedStacks = manifest.standard_domain === 'frontend'
    ? new Set(['general', 'javascript', 'typescript', 'html', 'css', 'vue', 'react', 'mrn'])
    : new Set(['general', 'java', 'spring']);
  for (const [i, rule] of content.rules.entries()) {
    const path = `/content/rules/${i}`;
    ensure(rule.tech_stacks.every((stack) => allowedStacks.has(stack)), 'PACKAGE_DOMAIN_INVALID', `${path}/tech_stacks`, '技术栈与规则集治理域不一致。');
    ensure(rule.body.some((block) => block.type === 'markdown'), 'PACKAGE_CONTENT_INVALID', `${path}/body`, '规则需要明确的要求正文，不能只有示例。');
    const omissions = uniqueBy(rule.omissions, 'role', `${path}/omissions`);
    for (const role of ['good', 'bad']) {
      const examples = rule.body.some((block) => block.type === 'example' && block.role === role);
      ensure(examples !== omissions.has(role), 'PACKAGE_OMISSION_INVALID', `${path}/omissions`, '缺失示例需要明确省略原因，已有示例不能同时标为省略。');
      if (!examples) ensure(content.resolutions.some((r) => r.kind === 'omission' && r.affected_refs.includes(rule.rule_ref)), 'PACKAGE_OMISSION_INVALID', `${path}/omissions`, '省略示例需要对应的用户决定记录。');
    }
  }
  const targetSource = (target) => documents.get(target)?.source_ref || (rules.has(target) ? documents.get(rules.get(target).document_ref)?.source_ref : undefined);
  const referencedRules = new Set();
  for (const [sourceRef, bytes] of sourceBytes) {
    const ranges = content.coverage.filter((unit) => unit.source_ref === sourceRef).sort((a, b) => a.byte_start - b.byte_start);
    let cursor = 0;
    for (const unit of ranges) {
      const path = `/content/coverage/${content.coverage.indexOf(unit)}`;
      ensure(unit.byte_start === cursor && unit.byte_end > unit.byte_start && unit.byte_end <= bytes.length, 'PACKAGE_COVERAGE_INVALID', path, '来源覆盖存在缺口、重叠或越界。');
      decodeUtf8(bytes.subarray(unit.byte_start, unit.byte_end), path);
      cursor = unit.byte_end;
      ensure(unit.targets.every((target) => targetSource(target) === sourceRef), 'PACKAGE_REFERENCE_INVALID', `${path}/targets`, '覆盖目标不属于此来源文件。');
      if (unit.disposition === 'excluded') {
        ensure(!unit.targets.length && unit.reason.trim() && content.resolutions.some((r) => r.kind === 'exclusion' && r.affected_refs.includes(unit.unit_ref)), 'PACKAGE_COVERAGE_INVALID', path, '排除内容必须无目标且有原因和用户决定。');
      } else {
        ensure(unit.targets.length > 0, 'PACKAGE_COVERAGE_INVALID', path, '纳入或支持内容需要明确关联目标。');
        if (unit.disposition === 'support') ensure(unit.reason.trim(), 'PACKAGE_COVERAGE_INVALID', `${path}/reason`, '支持材料需要说明用途。');
        unit.targets.forEach((target) => { if (rules.has(target)) referencedRules.add(target); });
      }
    }
    ensure(cursor === bytes.length, 'PACKAGE_COVERAGE_INVALID', '/content/coverage', '来源没有完整的覆盖记录。');
  }
  ensure(content.coverage.every((unit) => sources.has(unit.source_ref)) && referencedRules.size === rules.size, 'PACKAGE_COVERAGE_INVALID', '/content/coverage', '规则缺少来源覆盖，或覆盖记录引用了不存在的来源。');
  for (const [i, resolution] of content.resolutions.entries()) ensure(resolution.affected_refs.every((target) => allRefs.includes(target)), 'PACKAGE_REFERENCE_INVALID', `/content/resolutions/${i}/affected_refs`, '用户决定关联了不存在的内容。');

  let sourceExtractionPending = false;
  const verifyProvenance = async (block, path) => {
    const provenance = block.provenance;
    if (provenance.origin === 'source_extract') ensure(provenance.source_spans.length > 0, 'PACKAGE_PROVENANCE_INVALID', path, '原文摘取必须具有来源证据。');
    else ensure(provenance.reason.trim().length > 0, 'PACKAGE_PROVENANCE_INVALID', path, '生成或修改内容必须说明原因。');
    const texts = [];
    for (const [i, span] of provenance.source_spans.entries()) {
      const bytes = sourceBytes.get(span.source_ref);
      ensure(bytes && span.byte_start < span.byte_end && span.byte_end <= bytes.length, 'PACKAGE_PROVENANCE_INVALID', `${path}/source_spans/${i}`, '来源证据范围无效。');
      const excerpt = bytes.subarray(span.byte_start, span.byte_end);
      ensure(await sha256(excerpt) === span.sha256, 'PACKAGE_HASH_MISMATCH', `${path}/source_spans/${i}/sha256`, '来源证据校验值不匹配。');
      texts.push(decodeUtf8(excerpt, `${path}/source_spans/${i}`));
    }
    if (provenance.origin === 'source_extract') {
      if (source.type === 'git') {
        ensure(texts.join('') === (block.type === 'example' ? block.code : block.text), 'PACKAGE_PROVENANCE_INVALID', path, '标记为原文摘取的内容与来源字节不一致。');
      } else sourceExtractionPending = true;
    }
  };
  for (const [i, doc] of content.documents.entries()) for (const [j, block] of doc.content.entries()) if (block.type === 'markdown') await verifyProvenance(block, `/content/documents/${i}/content/${j}/provenance`);
  for (const [i, rule] of content.rules.entries()) for (const [j, block] of rule.body.entries()) await verifyProvenance(block, `/content/rules/${i}/body/${j}/provenance`);

  const indexBytes = files.get('AGENTS.md');
  ensure(indexBytes.length <= LIMITS.indexBytes, 'PACKAGE_FILE_LIMIT', '/AGENTS.md', '索引超过本版本大小上限。');
  const index = decodeUtf8(indexBytes, '/AGENTS.md'); validString(index, '/AGENTS.md');
  const rows = agentsRows(index);
  const bindings = new Map();
  const indexedDocuments = new Set();
  for (const [i, binding] of content.agents_index.bindings.entries()) {
    const doc = documents.get(binding.document_ref);
    const sourceFile = doc && sources.get(doc.source_ref);
    const reference = indexReferenceKey(binding.reference, source.type);
    const expectedReference = source.type === 'km' ? `km:${source.locator.content_id}` : sourceFile?.source_path;
    ensure(doc && reference && reference === expectedReference && !bindings.has(reference), 'PACKAGE_INDEX_INVALID', `/content/agents_index/bindings/${i}`, '索引引用不能唯一映射到真实文档。');
    bindings.set(reference, binding.document_ref); indexedDocuments.add(binding.document_ref);
  }
  const usedBindings = new Set();
  for (const row of rows) {
    const reference = indexReferenceKey(row.reference, source.type);
    ensure(bindings.has(reference), 'PACKAGE_INDEX_INVALID', `/AGENTS.md/${row.line}`, '索引引用未匹配本次规范文档。');
    usedBindings.add(reference);
  }
  ensure(usedBindings.size === bindings.size && indexedDocuments.size === documents.size, 'PACKAGE_INDEX_INVALID', '/content/agents_index/bindings', '索引必须覆盖全部纳入文档，且不能包含未使用的绑定。');
  const counts = { sources: sources.size, documents: documents.size, rules: rules.size, excluded_units: content.coverage.filter((u) => u.disposition === 'excluded').length };
  ensure(canonical(counts) === canonical(manifest.counts), 'PACKAGE_COUNTS_INVALID', '/manifest/counts', '声明计数与实际规范内容不一致。');
  return { manifest, content, confirmation, agentsIndex: index, counts,
    integrityVerified: true, confirmationBound: Boolean(confirmation), sourceVerified: false, sourceExtractionPending,
    readerCoverageVerified: false, publishable: false,
  };
}
