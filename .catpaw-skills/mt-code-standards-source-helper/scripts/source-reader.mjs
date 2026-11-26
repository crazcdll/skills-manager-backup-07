import { spawnSync } from 'node:child_process';
import { posix } from 'node:path';
import { LIMITS, PackageContractError, safeRelativePath, utf8, sha256 } from './package-contract.mjs';
import { buildSourceUnits, parseHistoryTree } from './source-units.mjs';
import { readGitRawSource, validGitBranchRef } from './code-source.mjs';
import { extractPublicErrorMessage } from './upstream-error-message.mjs';
const fail = (code, path, message) => { throw new PackageContractError(code, path, message); };
const MIS = /^[a-z][a-z0-9._-]{0,63}$/u;
export function parseSourceUrl(value, { selection_type, branch = null, path: selectedPath = null } = {}, { frozen = false } = {}) {
  const input = typeof value === 'string' && /^git@git\.sankuai\.com:/u.test(value) ? value.replace(/^git@git\.sankuai\.com:/u, 'ssh://git@git.sankuai.com/') : value;
  let url; try { url = new URL(input); } catch { fail('SOURCE_URL_INVALID', '/source_url', '请提供有效的 Git 或学城地址。'); }
  const ssh = url.protocol === 'ssh:' && url.hostname === 'git.sankuai.com' && url.username === 'git';
  if ((!ssh && (url.protocol !== 'https:' || url.username)) || url.port || url.password) fail('SOURCE_URL_INVALID', '/source_url', '来源必须使用支持的 HTTPS 或本人 Git SSH 地址。');
  if (url.hostname === 'km.sankuai.com') {
    const id = url.pathname.match(/^\/(?:collabpage|page|md)\/([1-9][0-9]*)(?:\.md)?\/?$/u)?.[1];
    if (!id) fail('SOURCE_URL_INVALID', '/source_url', '无法识别学城文档 ID。');
    return { type: 'km', content_id: id, canonical_url: `https://km.sankuai.com/${url.pathname.startsWith('/md/') ? 'md' : 'collabpage'}/${id}` };
  }
  if (selection_type !== undefined && !['file', 'directory'].includes(selection_type)) fail('SOURCE_SCOPE_INVALID', '/selection_type', '来源范围必须明确为文件或目录。');
  let project, repository, selected, linkType;
  if (url.hostname === 'dev.sankuai.com') {
    const match = url.pathname.match(/^\/code\/repo-detail\/([^/]+)\/([^/]+)\/file\/(detail|list)\/?$/u);
    if (!match) fail('SOURCE_URL_INVALID', '/source_url', '请提供代码平台的文件或目录地址。');
    [, project, repository] = match; selected = url.searchParams.get('path'); linkType = match[3] === 'detail' ? 'file' : 'directory';
  } else if (['git.sankuai.com', 'code.sankuai.com'].includes(url.hostname)) {
    const match = url.pathname.match(/^\/(?:projects\/([^/]+)\/repos\/([^/]+)(?:\/browse)?|([^/]+)\/([^/]+))\/?$/u);
    if (!match) fail('SOURCE_URL_INVALID', '/source_url', '无法识别 Git 仓库位置。');
    project = match[1] || match[3]; repository = (match[2] || match[4]).replace(/\.git$/u, ''); selected = url.searchParams.get('path');
  } else fail('SOURCE_URL_INVALID', '/source_url', '仅支持当前代码平台和学城来源。');
  project = decodeURIComponent(project); repository = decodeURIComponent(repository);
  if (!/^~?[A-Za-z0-9][A-Za-z0-9._-]*$/u.test(project) || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/u.test(repository)) fail('SOURCE_URL_INVALID', '/source_url', '仓库命名空间或名称无效。');
  const queryBranch = url.searchParams.get('branch'); const fullRef = (value) => value.startsWith('refs/') ? value : `refs/heads/${value}`;
  if (branch && queryBranch && fullRef(branch) !== fullRef(queryBranch)) fail('SOURCE_SCOPE_MISMATCH', '/source_url/branch', '显式分支与来源链接中的分支不一致。');
  branch ||= queryBranch;
  const narrower = selected && selectedPath && selected !== selectedPath && linkType === 'directory' && selectedPath.startsWith(selected + '/');
  if (selectedPath && selected && selectedPath !== selected && !narrower) fail('SOURCE_SCOPE_MISMATCH', '/source_url/path', '显式路径与来源链接中的路径不一致。');
  if (!frozen && !narrower && selection_type && linkType && selection_type !== linkType) fail('SOURCE_SCOPE_MISMATCH', '/selection_type', '链接类型与指定范围不一致；若只取目录内一个文件，请提供该文件路径。');
  selection_type ??= narrower ? 'file' : linkType || 'file';
  selected = selectedPath || selected;
  if (!selected) fail('SOURCE_SCOPE_REQUIRED', '/source_url', '请明确本次读取的文件或目录路径。');
  safeRelativePath(selected, '/source_url/path');
  const ref = branch ? fullRef(branch) : null;
  if (ref && !validGitBranchRef(ref)) fail('SOURCE_BRANCH_INVALID', '/source_url/branch', '分支名称不符合要求。');
  return { type: 'git', project, repository, selected_path: selected, selection_type, requested_ref: ref,
    ref_origin: ref ? 'explicit' : 'remote_default', canonical_url: `https://git.sankuai.com/${encodeURIComponent(project).replace('%7E', '~')}/${repository}`,
    ssh_url: `ssh://git@git.sankuai.com/${project}/${repository}.git`,
    root_path: selection_type === 'directory' ? selected : posix.dirname(selected) === '.' ? '' : posix.dirname(selected) };
}
function run(command, args, { binary = false, timeout = 180000, maxBuffer = 2 * 1024 * 1024, env = process.env } = {}) {
  const result = spawnSync(command, args, { encoding: binary ? null : 'utf8', timeout, maxBuffer, env, shell: false });
  if (result.error?.code === 'ENOENT') fail('SOURCE_TOOL_MISSING', '/runtime', `缺少官方工具 ${command}，请先按 Skill 指引安装并登录。`);
  if (result.error?.code === 'ETIMEDOUT') fail('SOURCE_TIMEOUT', '/source', '来源读取超时；请检查网络后重新尝试，不会改用其他版本。');
  if (result.status !== 0) {
    const stderr = String(result.stderr || '');
    if (stderr.includes('安全屋')) {
      const upstream = extractPublicErrorMessage({ stderr, status: result.status }, { prefer: (message) => message.includes('安全屋') });
      fail('SOURCE_SECURE_ENVIRONMENT_REQUIRED', '/source', upstream?.includes('安全屋') ? upstream : '学城要求安全屋Token，请通过获授权的安全屋方式携带安全屋Token后重试。');
    }
    if (/permission denied|authentication|未认证|未登录|认证失败|授权失败|凭据|token expired/iu.test(stderr)) fail('SOURCE_AUTH_REQUIRED', '/source', '来源认证失败，请使用本人账号完成官方工具登录后继续。');
    fail('SOURCE_READ_FAILED', '/source', '无法读取指定来源，请检查本人权限、网络和来源地址；未尝试其他账号或分支。');
  }
  return result.stdout;
}
export async function readKmSource(plan, request, { runCommand = run } = {}) {
  if (request.actor_mis && !MIS.test(request.actor_mis)) fail('SOURCE_ACTOR_INVALID', '/actor_mis', '当前登录身份标识格式无效。');
  const common = ['--contentId', plan.content_id, ...(request.actor_mis ? ['--mis', request.actor_mis] : []), '--env', 'product', '--no-version-check', '--raw'];
  const deadline = Date.now() + 180000;
  const invoke = (method, extra = []) => {
    const remaining = deadline - Date.now();
    if (remaining <= 0) fail('SOURCE_TIMEOUT', '/source', '本次学城读取超过时间预算，请确认官方登录和网络后重试。');
    const raw = runCommand('oa-skills', ['citadel', method, ...common, ...extra], { timeout: Math.min(15000, remaining), maxBuffer: 2 * 1024 * 1024 });
    try { return JSON.parse(String(raw)); } catch { fail('SOURCE_RESPONSE_INVALID', '/source', '官方工具未返回可校验的 JSON，请检查工具版本和登录状态。'); }
  };
  const metadata = invoke('getDocumentMetaInfo');
  if (![3, 7].includes(metadata.type) || String(metadata.contentId) !== plan.content_id || metadata.deleted) fail('SOURCE_TYPE_UNSUPPORTED', '/source', '该学城类型或状态无法读取固定历史版本；不会回退当前正文。');
  let step = request.step_version;
  if (step === undefined) {
    const versions = invoke('getDocumentVersions');
    if (!Array.isArray(versions.versions) || !versions.versions.length) fail('SOURCE_REVISION_INVALID', '/source/revision', '没有可读取的固定历史版本。');
    step = Math.max(...versions.versions.map((version) => Number.isSafeInteger(version.stepVersion) && version.stepVersion > 0 ? version.stepVersion : 0));
  }
  if (!Number.isSafeInteger(step) || step < 1) fail('SOURCE_REVISION_INVALID', '/source/revision', '请使用有效的 stepVersion，不能使用展示版本号。');
  const history = invoke('getDocumentVersionContent', ['--stepVersion', String(step)]);
  if (String(history.contentId) !== plan.content_id || history.stepVersion !== step || typeof history.body !== 'string' || !history.body.trim()) fail('SOURCE_REVISION_MISMATCH', '/source/revision', '历史响应与请求文档或版本不一致。');
  const bytes = utf8(history.body); if (bytes.length > LIMITS.sourceFileBytes) fail('SOURCE_FILE_LIMIT', '/source', '学城历史原件超过 128 KiB 上限。');
  parseHistoryTree(bytes);
  const sourceRef = `source_km_${plan.content_id}`, packagePath = `sources/${sourceRef}.json`;
  const source = { type: 'km', reader_contract: 'fixed-source/v1', locator: { content_id: plan.content_id, url: plan.canonical_url, document_type: metadata.type }, revision: { step_version: step }, files: [{ source_ref: sourceRef, source_path: `km/${plan.content_id}.json`, package_path: packagePath, representation: 'citadel-history-json', sha256: await sha256(bytes), byte_size: bytes.length }] };
  return { source, files: new Map([[packagePath, bytes]]), originalIndex: null, warnings: metadata.type === 7 ? ['原生 MD 历史读取路径需核对本次真实输出；未验证内容不会允许封包。'] : [], receipt: { transport: 'official-citadel-history', content_id: plan.content_id, step_version: step, document_type: metadata.type } };
}
export async function readSource(request, options) {
  const plan = parseSourceUrl(request.source_url, request);
  const result = plan.type === 'git' ? await readGitRawSource(plan, request, options) : await readKmSource(plan, request, options);
  const total = result.source.files.reduce((sum, file) => sum + file.byte_size, 0);
  if (result.source.files.length > LIMITS.sourceFiles || total > LIMITS.sourceTotalBytes) fail('SOURCE_FILE_LIMIT', '/source', '来源数量或总字节数超过本版上限。');
  return { ...result, units: await buildSourceUnits(result.source, result.files) };
}
