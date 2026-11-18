#!/usr/bin/env node
import { readFile, writeFile, mkdir, lstat, realpath, rename, rm } from 'node:fs/promises';
import { resolve, dirname, join, relative, isAbsolute } from 'node:path';
import { randomUUID } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { CONFIRMATION_SCHEMA, LIMITS, PackageContractError, canonical, canonicalHash, utf8, sha256, parseStrictJson, safeRelativePath, validateRuleSetIntent } from './package-contract.mjs';
import { parseSourceUrl, readSource } from './source-reader.mjs';
import { emptyDraft, materializeDraft } from './draft-workflow.mjs';
import { renderPreview, displayText } from './preview.mjs';
import { verifyReaderEvidence } from './source-units.mjs';
import { encodeStoreZip, decodeStoreZip } from './store-zip.mjs';
import { validateCanonicalDraftContent } from './canonical-content.mjs';
import { validateConversion } from './conversion-contract.mjs';
const fail = (code, path, message) => { throw new PackageContractError(code, path, message); };
async function readBounded(path, max) {
  const stat = await lstat(path);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > max) fail('LOCAL_FILE_INVALID', '', '本地文件类型或大小不符合要求。');
  const bytes = new Uint8Array(await readFile(path)); if (bytes.length !== stat.size || bytes.length > max) fail('LOCAL_FILE_INVALID', '', '本地文件读取期间发生变化。'); return bytes;
}
async function safeFile(root, name) {
  safeRelativePath(name, '/workspace'); const path = resolve(root, name); const rel = relative(root, path);
  if (rel.startsWith('..') || isAbsolute(rel)) fail('LOCAL_PATH_INVALID', '/workspace', '路径超出本次工作目录。');
  let current = root;
  for (const part of rel.split('/')) { current = join(current, part); try { if ((await lstat(current)).isSymbolicLink()) fail('LOCAL_PATH_INVALID', '/workspace', '工作目录内部不允许符号链接。'); } catch (error) { if (error.code !== 'ENOENT') throw error; } }
  return path;
}
async function atomic(root, name, bytes) {
  const target = await safeFile(root, name); await mkdir(dirname(target), { recursive: true }); const temp = `${target}.${randomUUID()}.tmp`;
  await writeFile(temp, bytes, { flag: 'wx', mode: 0o600 }); await rename(temp, target);
}
async function readJson(root, name, max = LIMITS.contentBytes) { return parseStrictJson(await readBounded(await safeFile(root, name), max), `/${name}`, max); }
async function locked(root, task) {
  const lock = join(root, '.source-helper-lock');
  try { await mkdir(lock); } catch (error) { if (error.code === 'EEXIST') fail('WORKSPACE_BUSY', '/workspace', '本次工作目录正被其他操作使用；请确认前次操作结束后再继续。'); throw error; }
  try { return await task(); } finally { await rm(lock, { recursive: true }); }
}
const output = (value) => process.stdout.write(JSON.stringify(value) + '\n');
function requestShape(request) {
  const legacy = request?.schema_version === 'source-helper-request/v1';
  const fields = ['schema_version', 'source_url', 'selection_type', 'path', 'branch', 'step_version', 'actor_mis', ...(legacy ? ['standard_domain', 'rule_set'] : [])];
  if (!request || !['source-helper-request/v1', 'source-helper-request/v2'].includes(request.schema_version) || Object.keys(request).some((field) => !fields.includes(field))) fail('REQUEST_INVALID', '/request', '请求只需要来源地址及来源读取范围；规则集名称、展示名称、Owner、治理域和适用范围由平台填写。');
  if (legacy && (request.standard_domain !== undefined || request.rule_set !== undefined)) {
    if (!['frontend', 'backend'].includes(request.standard_domain)) fail('REQUEST_INVALID', '/standard_domain', '旧版请求的治理域无效；新请求不需要填写治理域。');
    validateRuleSetIntent(request.rule_set);
  }
  parseSourceUrl(request.source_url, request);
  return request;
}
const requestScope = (request) => Object.fromEntries(['source_url', 'selection_type', 'path', 'branch', 'step_version', 'actor_mis'].map((key) => [key, request[key] ?? null]));
async function loadMaterial(root, draftName = 'draft.json') {
  const state = await readJson(root, 'state.json', LIMITS.manifestBytes); const request = requestShape(await readJson(root, 'request.json', LIMITS.manifestBytes)); const source = await readJson(root, 'source.json', LIMITS.manifestBytes);
  if (state.source_request_digest !== await canonicalHash(requestScope(request))) fail('SOURCE_REQUEST_CHANGED', '/request', '来源地址、分支、路径或读取身份已变化，请读取到新的工作目录，不会混入旧快照。');
  const files = new Map(); for (const file of source.files) { const bytes = await readBounded(await safeFile(root, file.package_path), LIMITS.sourceFileBytes); if (await sha256(bytes) !== file.sha256 || bytes.length !== file.byte_size) fail('SOURCE_SNAPSHOT_CHANGED', '/source', '本地来源快照已变化，请重新读取到新的工作目录并确认。'); files.set(file.package_path, bytes); }
  if (await canonicalHash(source) !== state.source_digest) fail('SOURCE_SNAPSHOT_CHANGED', '/source', '来源身份或版本记录已变化，请重新读取。');
  const draft = await readJson(root, draftName);
  const material = await materializeDraft({ request, source, files, draft });
  const receipt = await readJson(root, 'source-receipt.json', LIMITS.manifestBytes);
  if (source.type === 'git' && (receipt.transport !== 'official-code-raw' || receipt.identity_verified !== true || receipt.raw_snapshot_verified !== true || receipt.commit !== source.revision.commit)) {
    material.validation = { code: 'SOURCE_REPRESENTATION_UNVERIFIED', path: '/source', message: '尚未通过本人 Code 会话核验固定提交的 raw 原件。SSH 归档可能受仓库属性影响；请完成官方登录后重新读取，当前仅供草稿预览。' };
  }
  return { state, requestDigest: await canonicalHash(request), ...material };
}
function args(argv) {
  const [command, ...rest] = argv; const options = {};
  for (let i = 0; i < rest.length; i += 1) {
    const key = rest[i]; if (!/^--[a-z-]+$/u.test(key) || Object.hasOwn(options, key)) fail('ARGUMENT_INVALID', '/arguments', '命令参数无效或重复。');
    if (['--user-confirmed', '--resume', '--help'].includes(key)) options[key] = true;
    else { if (!rest[i + 1] || rest[i + 1].startsWith('--')) fail('ARGUMENT_INVALID', '/arguments', '命令参数缺少值。'); options[key] = rest[++i]; }
  }
  const allowed = { plan: ['--source', '--selection-type', '--path', '--branch'], prepare: ['--request', '--workspace', '--resume'], preview: ['--workspace', '--draft'], confirm: ['--workspace', '--preview-digest', '--user-confirmed'], package: ['--workspace', '--output'], validate: ['--package'], status: ['--workspace'], help: [] };
  if (!Object.hasOwn(allowed, command) || Object.keys(options).some((key) => !allowed[command].includes(key))) fail('ARGUMENT_INVALID', '/arguments', '不支持此命令或参数，请运行 help。');
  return { command, options };
}
export async function main(argv = process.argv.slice(2), { readSourceImpl = readSource } = {}) {
  if (Number(process.versions.node.split('.')[0]) < 24) fail('RUNTIME_VERSION_UNSUPPORTED', '/runtime', '请使用 Node.js 24 或更新版本执行。');
  const { command, options } = args(argv.length ? argv : ['help']);
  const requireOption = (name) => { if (!options[name]) fail('ARGUMENT_REQUIRED', '/arguments', `缺少参数 ${name}。`); return options[name]; };
  if (command === 'help') return output({ commands: ['plan --source <URL> [--selection-type file|directory] [--branch <branch>]', 'prepare --request <request.json> --workspace <new-directory> [--resume]', 'preview --workspace <directory> [--draft <draft.json>]', 'confirm --workspace <directory> --preview-digest <sha256> --user-confirmed', 'package --workspace <directory> --output <new.zip>', 'validate --package <zip>', 'status --workspace <directory>'], note: '确认参数只能在用户明确确认当前预览后使用。工具不会调用模型、上传或发布。' });
  if (command === 'plan') return output({ status: 'scope_ready', plan: parseSourceUrl(requireOption('--source'), { selection_type: options['--selection-type'] || 'file', path: options['--path'] || null, branch: options['--branch'] || null }), next: '向用户说明并确认读取范围，再 prepare。' });
  if (command === 'validate') {
    const files = decodeStoreZip(await readBounded(resolve(requireOption('--package')), LIMITS.zipBytes)); const result = await verifyReaderEvidence(await validateConversion(files), files);
    validateCanonicalDraftContent(result.content);
    return output({ status: 'conversion_valid', content_digest: result.manifest.content_digest, counts: result.manifest.counts, source_verified: false, reader_coverage_verified: true, publishable: false, note: '转换包尚需平台填写规则集元信息、核验来源、分配正式编号并进入 Owner 审核。' });
  }
  let root = resolve(requireOption('--workspace'));
  if (command === 'prepare') {
    try {
      await lstat(root);
      if (!options['--resume']) fail('WORKSPACE_EXISTS', '/workspace', '目录已存在；使用 status/preview 继续，或选择新的目录，不会覆盖旧材料。');
      root = await realpath(root); const state = await readJson(root, 'state.json', LIMITS.manifestBytes);
      const frozenRequest = requestShape(await readJson(root, 'request.json', LIMITS.manifestBytes));
      const requested = options['--request'] ? requestShape(parseStrictJson(await readBounded(resolve(options['--request']), LIMITS.manifestBytes), '/request', LIMITS.manifestBytes)) : frozenRequest;
      if (await canonicalHash(requested) !== state.request_digest || await canonicalHash(frozenRequest) !== state.request_digest || await canonicalHash(requestScope(requested)) !== state.source_request_digest) fail('RESUME_REQUEST_CHANGED', '/request', '恢复请求或本地 request.json 已变化。来源变化请使用新目录；仅修改规范意向时请重新生成预览。');
      return output({ status: state.status, workspace: root, next: '继续已冻结来源；需要读取新版本时请使用新的工作目录。' });
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    const requestPath = resolve(requireOption('--request')); const request = requestShape(parseStrictJson(await readBounded(requestPath, LIMITS.manifestBytes), '/request', LIMITS.manifestBytes));
    const loaded = await readSourceImpl(request);
    await mkdir(root, { recursive: false }); root = await realpath(root);
    return locked(root, async () => {
      await atomic(root, 'request.json', utf8(canonical(request))); await atomic(root, 'source.json', utf8(canonical(loaded.source)));
      for (const [path, bytes] of loaded.files) await atomic(root, path, bytes);
      await atomic(root, 'source-receipt.json', utf8(canonical(loaded.receipt)));
      if (loaded.originalIndex) await atomic(root, 'original-AGENTS.md', loaded.originalIndex);
      await atomic(root, 'semantic-input.json', utf8(canonical({ schema_version: 'source-helper-input/v1', source: loaded.source, units: loaded.units, warnings: loaded.warnings })));
      await atomic(root, 'draft.json', utf8(canonical(emptyDraft(loaded.source, loaded.units))));
      await atomic(root, 'state.json', utf8(canonical({ schema_version: 'source-helper-workspace/v1', status: 'sources_ready', source_digest: await canonicalHash(loaded.source), request_digest: await canonicalHash(request), source_request_digest: await canonicalHash(requestScope(request)), content_digest: null, preview_digest: null })));
      return output({ status: 'sources_ready', workspace: root, files: loaded.source.files.length, units: loaded.units.length, warnings: loaded.warnings, next: '阅读 semantic-input.json，整理 draft.json，再生成预览；尚未确认。' });
    });
  }
  root = await realpath(root);
  return locked(root, async () => {
    if (command === 'status') { const state = await readJson(root, 'state.json', LIMITS.manifestBytes); return output({ ...state, workspace: root, note: '状态仅记录最近一次操作；确认/封包会重新计算并验证当前内容。' }); }
    if (command === 'preview' && options['--draft']) {
      const bytes = await readBounded(resolve(options['--draft']), LIMITS.contentBytes); parseStrictJson(bytes, '/draft'); await atomic(root, 'draft.json', bytes);
    }
    const material = await loadMaterial(root); const preview = await renderPreview(material);
    if (command === 'preview') {
      await atomic(root, 'preview.html', utf8(preview.html)); await atomic(root, 'AGENTS.md', utf8(material.agentsIndex));
      await atomic(root, 'preview-manifest.json', utf8(canonical(material.manifest)));
      await atomic(root, 'validation-report.json', utf8(canonical({ content_digest: material.manifest.content_digest, questions: material.questions, validation: material.validation, source_verified: false })));
      await atomic(root, 'state.json', utf8(canonical({ ...material.state, request_digest: material.requestDigest, status: material.questions.length || material.validation ? 'needs_input' : 'preview_ready', content_digest: material.manifest.content_digest, preview_digest: preview.preview_digest })));
      return output({ status: material.questions.length || material.validation ? 'needs_input' : 'preview_ready', preview: join(root, 'preview.html'), preview_digest: preview.preview_digest, content_digest: material.manifest.content_digest, rules: material.content.rules.length, open_questions: material.questions.length, validation: material.validation, next: '让用户查看当前预览；未明确确认前不运行 confirm。' });
    }
    if (material.questions.length || material.validation) fail('DRAFT_NOT_READY', '/draft', '草稿仍有未解决问题或格式错误，请处理并重新生成预览。');
    if (material.state.content_digest !== material.manifest.content_digest || material.state.preview_digest !== preview.preview_digest) fail('PREVIEW_STALE', '/preview', '当前内容与已展示的预览不一致，请重新生成预览并让用户确认。');
    if (command === 'confirm') {
      if (!options['--user-confirmed'] || requireOption('--preview-digest') !== preview.preview_digest) fail('CONFIRMATION_REQUIRED', '/confirmation', '需要用户明确确认当前预览及其版本，不能沿用其他预览确认。');
      const confirmation = { schema_version: CONFIRMATION_SCHEMA, content_digest: material.manifest.content_digest, decision: 'confirmed', confirmed_at: new Date().toISOString(), confirmed_scope: { content: true, agents_index: true, exclusions: true, generated_changes: true } };
      material.payload.set('confirmation.json', utf8(canonical(confirmation)));
      await verifyReaderEvidence(await validateConversion(material.payload), material.payload);
      await atomic(root, 'confirmation.json', utf8(canonical(confirmation))); await atomic(root, 'state.json', utf8(canonical({ ...material.state, status: 'confirmed' })));
      return output({ status: 'confirmed', content_digest: material.manifest.content_digest, next: '可以生成原材料转换包；这不等于平台审核或发布。' });
    }
    if (command === 'package') {
      let confirmation; try { confirmation = await readJson(root, 'confirmation.json', LIMITS.confirmationBytes); } catch (error) { if (error.code === 'ENOENT') fail('CONFIRMATION_REQUIRED', '/confirmation', '尚未确认当前预览，不能生成最终包。'); throw error; }
      material.payload.set('confirmation.json', utf8(canonical(confirmation)));
      await verifyReaderEvidence(await validateConversion(material.payload), material.payload);
      const zipped = encodeStoreZip(material.payload); const decoded = decodeStoreZip(zipped); await verifyReaderEvidence(await validateConversion(decoded), decoded);
      const target = resolve(requireOption('--output')); await writeFile(target, zipped, { flag: 'wx', mode: 0o600 });
      await atomic(root, 'state.json', utf8(canonical({ ...material.state, status: 'packaged' })));
      return output({ status: 'packaged', output: target, package_sha256: await sha256(zipped), content_digest: material.manifest.content_digest, source_verified: false, publishable: false, next: '这是原材料转换包；请在平台填写规则集元信息后导入，工具未上传、审核或发布。' });
    }
  });
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main().catch((error) => { const known = error instanceof PackageContractError; output({ status: 'failed', code: known ? error.code : 'LOCAL_OPERATION_FAILED', path: known ? displayText(error.path).slice(0,240) : '', message: known ? displayText(error.message) : '本地操作失败，请检查目录权限、文件是否存在和运行环境；未输出来源正文或认证日志。' }); process.exitCode = 1; });
}
