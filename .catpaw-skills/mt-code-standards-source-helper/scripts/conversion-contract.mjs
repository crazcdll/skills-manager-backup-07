import { LIMITS, PackageContractError, canonical, manifestDigest, parseStrictJson, safeRelativePath, sha256, validateContent } from './package-contract.mjs';

export const CONVERSION_SCHEMA = 'source-helper-conversion/v1';
const fail = (code, path, message) => { throw new PackageContractError(code, path, message); };
const ensure = (condition, code, path, message) => { if (!condition) fail(code, path, message); };

export function validateConversionManifest(value) {
  canonical(value);
  ensure(value && typeof value === 'object' && !Array.isArray(value), 'CONVERSION_MANIFEST_INVALID', '/manifest', '转换包清单必须是 JSON 对象。');
  ensure(value.schema_version === CONVERSION_SCHEMA, 'CONVERSION_SCHEMA_INVALID', '/manifest/schema_version', '转换包版本不受支持。');
  ensure(value.operation === 'normalize_source', 'CONVERSION_SCHEMA_INVALID', '/manifest/operation', '转换包只能表示原材料规范化结果。');
  ensure(value.render_contract === 'rule-markdown/v2', 'CONVERSION_SCHEMA_INVALID', '/manifest/render_contract', '渲染合同不受支持。');
  ensure(!['standard_domain', 'scope_level', 'rule_set'].some((field) => Object.hasOwn(value, field)), 'CONVERSION_PLATFORM_FIELD', '/manifest', '转换包不能携带平台规则集元信息。');
  ensure(value.source && ['git', 'km'].includes(value.source.type) && Array.isArray(value.source.files) && value.source.files.length > 0, 'CONVERSION_SOURCE_INVALID', '/manifest/source', '转换包必须包含 Git 或学城来源文件。');
  ensure(value.converter?.name === 'mt-code-standards-source-helper' && typeof value.converter.version === 'string', 'CONVERSION_SCHEMA_INVALID', '/manifest/converter', '转换器信息无效。');
  ensure(value.counts && Number.isSafeInteger(value.counts.sources) && Number.isSafeInteger(value.counts.documents) && Number.isSafeInteger(value.counts.rules) && value.counts.sources === value.source.files.length, 'CONVERSION_SCHEMA_INVALID', '/manifest/counts', '转换包计数不完整。');
  ensure(Array.isArray(value.files) && value.files.length >= 2 && value.files.length <= LIMITS.entries, 'CONVERSION_SCHEMA_INVALID', '/manifest/files', '转换包文件清单无效。');
  ensure(typeof value.content_digest === 'string', 'CONVERSION_SCHEMA_INVALID', '/manifest/content_digest', '转换包缺少内容校验值。');
  return value;
}

export async function validateConversion(files, { requireConfirmation = true } = {}) {
  ensure(files instanceof Map, 'CONVERSION_FILES_INVALID', '', '转换包需要完整的文件集合。');
  ensure(files.has('manifest.json') && files.has('content.json') && files.has('AGENTS.md'), 'CONVERSION_FILE_MISSING', '', '转换包缺少 manifest、content 或 AGENTS 索引。');
  if (requireConfirmation) ensure(files.has('confirmation.json'), 'CONVERSION_CONFIRMATION_REQUIRED', '/confirmation', '尚未确认当前转换预览。');
  for (const [path, bytes] of files) {
    safeRelativePath(path, path);
    ensure(bytes instanceof Uint8Array && bytes.length <= LIMITS.expandedBytes, 'CONVERSION_FILE_INVALID', path, '转换包文件无效或超出大小限制。');
  }
  const manifest = validateConversionManifest(parseStrictJson(files.get('manifest.json'), '/manifest.json', LIMITS.manifestBytes));
  const content = validateContent(parseStrictJson(files.get('content.json'), '/content.json', LIMITS.contentBytes));
  ensure(manifest.counts.documents === content.documents.length && manifest.counts.rules === content.rules.length, 'CONVERSION_COUNT_MISMATCH', '/manifest/counts', '转换包计数与规范正文不一致。');
  ensure(await manifestDigest(manifest) === manifest.content_digest, 'CONVERSION_HASH_MISMATCH', '/manifest/content_digest', '转换包内容校验值不匹配。');
  const listed = new Map();
  for (const entry of manifest.files) {
    ensure(entry && typeof entry.path === 'string' && Number.isSafeInteger(entry.byte_size) && typeof entry.sha256 === 'string', 'CONVERSION_FILES_INVALID', '/manifest/files', '转换包文件清单条目无效。');
    ensure(!listed.has(entry.path) && entry.path !== 'manifest.json' && entry.path !== 'confirmation.json', 'CONVERSION_FILES_INVALID', '/manifest/files', '转换包文件清单重复或包含自身文件。');
    listed.set(entry.path, entry);
    const bytes = files.get(entry.path);
    ensure(bytes && bytes.length === entry.byte_size && await sha256(bytes) === entry.sha256, 'CONVERSION_HASH_MISMATCH', `/manifest/files/${entry.path}`, '转换包文件校验值不匹配。');
  }
  for (const sourceFile of manifest.source.files || []) {
    const entry = listed.get(sourceFile.package_path);
    ensure(entry && entry.byte_size === sourceFile.byte_size && entry.sha256 === sourceFile.sha256, 'CONVERSION_SOURCE_MISMATCH', `/manifest/source/files/${sourceFile.package_path}`, '来源文件清单与转换包文件不一致。');
  }
  ensure(listed.has('content.json') && listed.has('AGENTS.md'), 'CONVERSION_FILES_INVALID', '/manifest/files', '转换包必须包含规范正文和 AGENTS 索引。');
  ensure([...files.keys()].every((path) => path === 'manifest.json' || path === 'confirmation.json' || listed.has(path)), 'CONVERSION_FILES_INVALID', '/manifest/files', '转换包包含未声明文件。');
  if (files.has('confirmation.json')) {
    const confirmation = parseStrictJson(files.get('confirmation.json'), '/confirmation.json', LIMITS.confirmationBytes);
    ensure(confirmation.content_digest === manifest.content_digest && confirmation.decision === 'confirmed', 'CONVERSION_CONFIRMATION_INVALID', '/confirmation', '确认记录不属于当前转换内容。');
  }
  return { manifest, content };
}
