import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { LIMITS, PackageContractError, decodeUtf8, utf8, sha256, safeRelativePath } from './package-contract.mjs';
const AUDIENCE = 'f32a546874';
const fail = (code, path, message) => { throw new PackageContractError(code, path, message); };

// Only the official Code CLI's own cache is considered. Do not call load/loadAll:
// those SDK methods also search unrelated products' caches.
export function loadOfficialCodeSession() {
  const ownRequire = createRequire(import.meta.url); let entry;
  try { entry = ownRequire.resolve('@ee/code-cli'); } catch {
    const root = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', timeout: 10000, maxBuffer: 8192 });
    if (root.status !== 0 || !root.stdout.trim()) fail('SOURCE_TOOL_MISSING', '/runtime', '需要安装官方 @ee/code-cli 并运行 code-cli auth login。');
    try { entry = createRequire(join(root.stdout.trim(), 'package.json')).resolve('@ee/code-cli'); } catch { fail('SOURCE_TOOL_MISSING', '/runtime', '需要安装官方 @ee/code-cli 并运行 code-cli auth login。'); }
  }
  try {
    const { TokenStorage } = ownRequire(join(dirname(entry), 'sso/storage.js'));
    const storage = new TokenStorage(AUDIENCE);
    if (typeof storage.loadFromMcode !== 'function') fail('SOURCE_TOOL_UNSUPPORTED', '/runtime', '当前官方 Code CLI 没有受支持的本人会话读取接口，请更新官方工具。');
    const session = storage.loadFromMcode();
    if (typeof session?.access_token !== 'string' || !session.access_token.trim()) fail('SOURCE_AUTH_REQUIRED', '/source', '请先用本人账号运行 code-cli auth login，再继续读取。');
    return session.access_token;
  } catch (error) {
    if (error instanceof PackageContractError) throw error;
    fail('SOURCE_AUTH_REQUIRED', '/source', '无法读取本人 Code CLI 会话，请运行 code-cli auth login；不会使用其他产品凭据。');
  }
}
async function boundedBody(response, maxBytes, path) {
  const length = response.headers.get('content-length'); if (length && Number(length) > maxBytes) fail('SOURCE_FILE_LIMIT', path, '上游响应超过本次读取预算。');
  if (!response.body) fail('SOURCE_RESPONSE_INVALID', path, '来源响应缺少正文。');
  const reader = response.body.getReader(); const parts = []; let total = 0;
  try { for (;;) { const {value,done}=await reader.read(); if(done)break; total+=value.length; if(total>maxBytes)fail('SOURCE_FILE_LIMIT',path,'上游响应超过本次读取预算。'); parts.push(value); } } finally { await reader.cancel().catch(()=>{}); reader.releaseLock(); }
  const result=new Uint8Array(total);let at=0;for(const part of parts){result.set(part,at);at+=part.length;}return result;
}
export async function readGitRawSource(plan, request, { fetchImpl = fetch, tokenProvider = loadOfficialCodeSession } = {}) {
  if (!/^[a-z][a-z0-9._-]{0,63}$/u.test(request.actor_mis || '')) fail('SOURCE_ACTOR_REQUIRED','/actor_mis','Git 读取前请提供当前本人登录用户的 MIS，不能以规则 Owner 代替。');
  const token = await tokenProvider(); const deadline=Date.now()+180000;
  const get=async(url,headers,maxBytes,path)=>{
    const remaining=deadline-Date.now();if(remaining<=0)fail('SOURCE_TIMEOUT',path,'本次来源读取超时，请重新尝试。');
    let response;try{response=await fetchImpl(url,{method:'GET',headers,redirect:'error',signal:AbortSignal.timeout(Math.min(15000,remaining))});}catch{fail('SOURCE_NETWORK_FAILED',path,'来源网络请求失败，请检查内网连接；未改用其他账号或版本。');}
    let repositoryDenied = false;
    if (response.status === 401) {
      try {
        const body = JSON.parse(decodeUtf8(await boundedBody(response, 64 * 1024, path)));
        repositoryDenied = Array.isArray(body?.errors) && body.errors.some((error) => error?.message === 'Permission denied, need permission:REPO_GUEST');
      } catch { /* Keep the original 401 classification when no explicit ACL fact is available. */ }
    }
    if(response.status===403||repositoryDenied)fail('SOURCE_PERMISSION_DENIED',path,'当前本人账号或应用缺少访问授权，请联系对应系统管理员或仓库维护人授予权限后再试。');
    if(response.status===401)fail('SOURCE_AUTH_REQUIRED',path,'本人 Code 登录已失效或缺少有效认证，请运行 code-cli auth login 后再试。');
    if(response.status!==200)fail('SOURCE_READ_FAILED',path,`来源读取失败（HTTP ${response.status}），请检查指定分支、路径和本人权限。`);
    return boundedBody(response,maxBytes,path);
  };
  let identity;try{identity=JSON.parse(decodeUtf8(await get(`https://ssosv.sankuai.com/websso/whoami?client_id=${AUDIENCE}`,{Authorization:`Bearer ${token}`,'x-ai-official-origin':'code-cli'},8192,'/source/identity')));}catch(error){if(error instanceof PackageContractError)throw error;fail('SOURCE_IDENTITY_INVALID','/source/identity','官方身份响应无法识别。');}
  if(String(identity?.code)!=='200'||identity?.data?.subject!==request.actor_mis)fail('SOURCE_IDENTITY_MISMATCH','/source/identity','本人 Code 会话已失效或身份不匹配，请重新登录；不会使用其他来源凭据。');
  const prefix=`https://dev.sankuai.com/rest/api/2.0/projects/${encodeURIComponent(plan.project)}/repos/${encodeURIComponent(plan.repository)}`;
  const api=async(path,query,max=256*1024)=>{const url=new URL(`${prefix}/${path}`);for(const[k,v]of Object.entries(query))url.searchParams.set(k,String(v));return get(url.toString(),{Cookie:`${AUDIENCE}_ssoid=${token}`},max,'/source');};
  const json=async(path,query)=>{try{return JSON.parse(decodeUtf8(await api(path,query)));}catch(error){if(error instanceof PackageContractError)throw error;fail('SOURCE_RESPONSE_INVALID','/source','代码平台返回了无法识别的数据。');}};
  const commits=await json('commits',{until:plan.requested_ref,limit:1});const commit=commits?.values?.[0]?.id;
  if(!Array.isArray(commits?.values)||commits.values.length!==1||!/^[0-9a-f]{40}$/u.test(commit||''))fail('SOURCE_REVISION_INVALID','/source/revision','指定分支未解析为唯一完整提交。');
  let paths=[plan.selected_path];
  if(plan.selection_type==='directory'){
    paths=[];let start=0,read=0;const cursors=new Set();const names=new Set();
    for(let page=0;;page++){
      if(page>=50||cursors.has(start))fail('SOURCE_DIRECTORY_LIMIT','/source','仓库目录枚举超出预算，请缩小来源或选择具体文件。');cursors.add(start);
      const result=await json('files',{at:commit,limit:100,start});
      if(!Array.isArray(result?.values)||typeof result.isLastPage!=='boolean')fail('SOURCE_RESPONSE_INVALID','/source','目录分页缺少完整性信息。');
      for(const path of result.values){safeRelativePath(path,'/source/path');if(names.has(path))fail('SOURCE_RESPONSE_INVALID','/source','目录分页包含重复文件。');names.add(path);if(++read>5000)fail('SOURCE_DIRECTORY_LIMIT','/source','仓库文件元信息超过预算，请选择具体文件。');if(path.startsWith(`${plan.selected_path}/`))paths.push(path);}
      if(paths.length>LIMITS.sourceFiles+2)fail('SOURCE_FILE_LIMIT','/source','指定目录文件过多，请缩小读取范围。');
      if(result.isLastPage)break;if(!Number.isSafeInteger(result.nextPageStart)||result.nextPageStart<=start)fail('SOURCE_RESPONSE_INVALID','/source','目录分页游标无效。');start=result.nextPageStart;
    }
  }
  if(!paths.length)fail('SOURCE_EMPTY','/source','指定范围没有文件。');
  const source={type:'git',reader_contract:'fixed-source/v1',locator:{repository_url:plan.canonical_url,root_path:plan.root_path},revision:{commit},files:[]};
  const files=new Map();let originalIndex=null,total=0;const warnings=[];
  for(const path of paths.sort()){
    const relative=plan.root_path?path.slice(plan.root_path.length+1):path;
    const bytes=await api(`raw/${path.split('/').map(encodeURIComponent).join('/')}`,{at:commit},LIMITS.sourceFileBytes);decodeUtf8(bytes,'/source');
    if(/^(?:AGENTS|agents)\.md$/u.test(relative)){if(bytes.length>LIMITS.indexBytes)fail('SOURCE_FILE_LIMIT','/source','来源索引超过本版预算。');if(relative==='AGENTS.md'||originalIndex===null)originalIndex=bytes;else warnings.push('同时存在大小写索引，使用 AGENTS.md 作为参考。');continue;}
    total+=bytes.length;if(total>LIMITS.sourceTotalBytes||source.files.length>=LIMITS.sourceFiles)fail('SOURCE_FILE_LIMIT','/source','来源正文数量或字节数超过上限。');
    const ref=`source_${(await sha256(utf8(relative))).slice(7,23)}`,packagePath=`sources/${ref}.md`;
    source.files.push({source_ref:ref,source_path:relative,package_path:packagePath,representation:'git-raw-utf8',sha256:await sha256(bytes),byte_size:bytes.length});files.set(packagePath,bytes);
  }
  if(!source.files.length)fail('SOURCE_EMPTY','/source','索引不作为规范正文，指定范围没有规则材料。');
  return{source,files,originalIndex,warnings,receipt:{transport:'official-code-raw',requested_ref:plan.requested_ref,commit,actor_mis:request.actor_mis,identity_verified:true,raw_snapshot_verified:true}};
}
