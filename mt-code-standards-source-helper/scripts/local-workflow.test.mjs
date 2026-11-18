import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, mkdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { canonical, utf8, sha256, validatePackage, validateRuleSetIntent, PackageContractError, LIMITS } from './package-contract.mjs';
import { minimalPackage } from './fixtures/minimal-package.mjs';
import { encodeStoreZip, decodeStoreZip } from './store-zip.mjs';
import { buildSourceUnits, parseHistoryTree, renderHistoryNode, verifyReaderEvidence } from './source-units.mjs';
import { parseSourceUrl, readKmSource } from './source-reader.mjs';
import { readGitRawSource } from './code-source.mjs';
import { materializeDraft } from './draft-workflow.mjs';
import { renderPreview, displayText } from './preview.mjs';
import { validateConversion } from './conversion-contract.mjs';
const fixtureUrl = 'https://dev.sankuai.com/code/repo-detail/~fixture/rules/file/detail?path=docs%2Frules.md&branch=refs%2Fheads%2Ffeature-rules';
const commit = 'a'.repeat(40);
async function readyDraft(source, files) {
  const units = await buildSourceUnits(source, files);
  return { schema_version: 'source-helper-draft/v1', content: {
    documents: [{ document_ref: 'document_one', source_ref: source.files[0].source_ref, title: '异常处理', description: '捕获和包装异常时查阅', category_key: 'engineering', subcategory_key: 'general', rule_type: 'Model Request', content: [{ type: 'rule', rule_ref: 'rule_one' }] }],
    rules: [{ rule_ref: 'rule_one', document_ref: 'document_one', title: '保留异常链', execution_level: 'mandatory', category_key: 'engineering', subcategory_key: 'general', rule_type: 'Model Request', tech_stacks: ['java'], stages: ['coding','cr'], applicability_tags: [], body: [{ type: 'markdown', text: units.map((unit) => unit.text).join(''), provenance: { origin: 'source_extract', unit_refs: units.map((unit) => unit.unit_ref), reason: '' } }], omissions: [{ role: 'good', reason: '合成夹具不包含示例' }, { role: 'bad', reason: '合成夹具不包含示例' }] }],
    coverage: units.map((unit) => ({ unit_ref: unit.unit_ref, disposition: 'included', targets: ['rule_one'], reason: '' })),
    resolutions: [{ question_ref: 'omission_confirmed', kind: 'omission', decision: '同意保留示例为空', explanation: '仅合成自动测试，不代表真实用户确认', affected_refs: ['rule_one'] }],
  }, index_entries: [{ group: '异常处理', name: '异常链', scene: '捕获和包装异常时', document_ref: 'document_one' }], open_questions: [] };
}

test('source URL preserves user branch and root, rejects overrides/default branch', () => {
  const plan = parseSourceUrl(fixtureUrl); assert.equal(plan.requested_ref, 'refs/heads/feature-rules'); assert.equal(plan.selected_path, 'docs/rules.md'); assert.equal(plan.root_path, 'docs'); assert.equal(plan.project, '~fixture');
  assert.equal(parseSourceUrl('git@git.sankuai.com:~fixture/rules.git', { branch: 'feature-rules', path: 'docs/rules.md' }).requested_ref, plan.requested_ref);
  assert.throws(() => parseSourceUrl(fixtureUrl, { branch: 'main' }), /不一致/);
  assert.throws(() => parseSourceUrl(fixtureUrl.replace(/&branch=.*/u,'')), /分支/);
  assert.throws(() => parseSourceUrl(fixtureUrl.replace('docs%2Frules.md','..%2Fsecret')), PackageContractError);
});

test('Code raw reader verifies current actor and selected branch without archive substitution', async () => {
  const calls=[];const fetchImpl=async(url,options)=>{calls.push([String(url),options]);if(String(url).includes('/whoami?'))return new Response(JSON.stringify({code:200,data:{subject:'fixture.user'}}));if(String(url).includes('/commits?'))return new Response(JSON.stringify({values:[{id:commit}]}));if(String(url).includes('/raw/docs/rules.md?'))return new Response('正文\n');throw Error('unexpected endpoint');};
  const result=await readGitRawSource(parseSourceUrl(fixtureUrl),{actor_mis:'fixture.user'},{fetchImpl,tokenProvider:()=> 'synthetic-ticket'});
  assert.equal(result.source.files[0].source_path,'rules.md');assert.equal(result.source.locator.root_path,'docs');assert.equal(result.receipt.raw_snapshot_verified,true);assert.ok(calls[1][0].includes('until=refs%2Fheads%2Ffeature-rules'));assert.ok(calls[2][0].includes('at='+commit));
  await assert.rejects(readGitRawSource(parseSourceUrl(fixtureUrl),{actor_mis:'someone.else'},{fetchImpl,tokenProvider:()=> 'synthetic-ticket'}),/身份/);
});

test('KM reader verifies metadata and exact step, hashes raw history string', async () => {
  const body = '{ "type":"doc", "content":[{"type":"paragraph","content":[{"type":"text","text":"要求"}]}]}';
  const runCommand = (_cmd,args) => JSON.stringify(args[1] === 'getDocumentMetaInfo' ? {contentId:'123',type:3} : args[1] === 'getDocumentVersions' ? {versions:[{stepVersion:7,version:99}]} : {contentId:'123',stepVersion:7,body});
  const result = await readKmSource(parseSourceUrl('https://km.sankuai.com/collabpage/123'), {actor_mis:'fixture'}, {runCommand});
  assert.equal(result.source.revision.step_version,7); assert.equal(result.source.files[0].sha256,await sha256(utf8(body)));
  await assert.rejects(readKmSource(parseSourceUrl('https://km.sankuai.com/collabpage/123'), {actor_mis:'fixture',step_version:8}, {runCommand}), /版本/);
});

test('fixed units cover all bytes without splitting a fenced code block', async () => {
  const content = '# A\n\n```js\n\n# inside\n```\n\n## B\n要求\n'; const bytes = utf8(content); const source = { type:'git',files:[{source_ref:'source_a',package_path:'sources/a.md'}] };
  const units=await buildSourceUnits(source,new Map([['sources/a.md',bytes]])); assert.equal(units.map((u)=>u.text).join(''),content);
  assert.ok(units.some((unit)=>unit.text.includes('# inside')&&unit.text.includes('```js')&&unit.text.includes('```\n')));
  assert.equal(units[0].byte_start,0); assert.equal(units.at(-1).byte_end,bytes.length);
});

test('history JSON mapper retains raw ranges and marks unsupported components', async () => {
  const bytes=utf8('{"type":"doc","content":[{"type":"heading","attrs":{"level":2},"content":[{"type":"text","text":"标题"}]},{"type":"image","attrs":{"src":"https://example.invalid/a"}}]}');
  const tree=parseHistoryTree(bytes); assert.equal(tree.value.type,'doc');
  const units=await buildSourceUnits({type:'km',files:[{source_ref:'source_a',package_path:'sources/a.json'}]},new Map([['sources/a.json',bytes]]));
  assert.equal(units.length,2);assert.equal(units[0].text,'## 标题\n\n');assert.deepEqual(units[1].unsupported,['image']);assert.equal(units[0].byte_end,units[1].byte_start);
  assert.throws(()=>parseHistoryTree(utf8('{"a":1,"a":2}')),/重复/);
  assert.equal(renderHistoryNode({type:'codeBlock',attrs:{language:'jsx'},content:[{type:'text',text:'const x = 1;'}]}).text,'```jsx\nconst x = 1;\n```\n\n');
});

test('materialized draft has one canonical body, generated evidence and topic index', async () => {
  const packageFiles=await minimalPackage();const manifest=JSON.parse(new TextDecoder().decode(packageFiles.get('manifest.json')));const source=manifest.source;const files=new Map(source.files.map((file)=>[file.package_path,packageFiles.get(file.package_path)]));
  const draft=await readyDraft(source,files);const material=await materializeDraft({request:{standard_domain:'backend',rule_set:manifest.rule_set},source,files,draft});
  assert.equal(material.validation,null);assert.ok(material.agentsIndex.includes('## 异常处理'));assert.equal(material.content.rules[0].body[0].provenance.origin,'source_extract');
  const preview=await renderPreview(material);assert.ok(preview.html.includes('待编号 01'));assert.ok(preview.html.includes("connect-src 'none'"));
  await verifyReaderEvidence(await validateConversion(material.payload,{requireConfirmation:false}),material.payload);
  const manifestWithPlatformFields = JSON.parse(new TextDecoder().decode(material.payload.get('manifest.json')));
  manifestWithPlatformFields.rule_set = { name: 'should-not-be-here' };
  const forgedConversion = new Map(material.payload); forgedConversion.set('manifest.json', utf8(canonical(manifestWithPlatformFields)));
  await assert.rejects(validateConversion(forgedConversion, { requireConfirmation: false }), (error) => error.code === 'CONVERSION_PLATFORM_FIELD');
  material.content.coverage[0].unit_ref='forged_unit';
  await assert.rejects(verifyReaderEvidence({manifest,content:material.content},material.payload),/单元/);
});

test('HTML escapes source markup, hides credential URL query, and never loads remote images', async () => {
  const result=displayText('https://img.example/a?token=secret&size=1');assert.ok(!result.includes('secret'));
  const html=(await renderPreview({manifest:{rule_set:{display_name:'<script>alert(1)</script>',description:'',applicability_scope:''},source:{type:'git',revision:{commit}},content_digest:'x'},content:{documents:[],rules:[],coverage:[],resolutions:[]},agentsIndex:'# Index',questions:[{message:'<img src=x onerror=alert(1)>'}]})).html;
  assert.ok(!html.includes('<script>alert(1)</script>'));assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<img src=x'));assert.ok(html.includes("img-src 'none'"));
});

test('STORE ZIP roundtrip rejects corruption, unsupported flags, paths and hidden data', async () => {
  const files=await minimalPackage();const zip=encodeStoreZip(files);assert.equal((await validatePackage(decodeStoreZip(zip))).manifest.content_digest,JSON.parse(new TextDecoder().decode(files.get('manifest.json'))).content_digest);
  const corrupt=zip.slice();corrupt[45]^=1;assert.throws(()=>decodeStoreZip(corrupt),PackageContractError);
  const hidden=new Uint8Array(zip.length+1);hidden.set(zip);assert.throws(()=>decodeStoreZip(hidden),PackageContractError);
  assert.throws(()=>encodeStoreZip(new Map([['../x',utf8('x')]])),PackageContractError);
  const oversized=new Uint8Array(LIMITS.zipBytes+1);assert.throws(()=>decodeStoreZip(oversized),PackageContractError);
});

test('platform naming limits reject unsupported intent without renaming', async () => {
  const manifest=JSON.parse(new TextDecoder().decode((await minimalPackage()).get('manifest.json')));
  for(const name of ['Team-Rules','ab','con','my_rules','a'.repeat(81)]) assert.throws(()=>validateRuleSetIntent({...manifest.rule_set,name}),PackageContractError);
});

test('CLI synthetic full flow cannot package before explicit current preview confirmation', async () => {
  const root=await mkdtemp(join(tmpdir(),'source-helper-cli-test-'));
  await writeFile(join(root,'source.md'),'# 异常处理\n捕获异常时保留原始异常链。\n');
  const request={schema_version:'source-helper-request/v2',source_url:fixtureUrl,selection_type:'file',actor_mis:'fixture.user'};await writeFile(join(root,'request.json'),canonical(request));
  const cli=join(root,'synthetic-driver.mjs'),work=join(root,'work');
  const helperUrl=new URL('./source-helper.mjs',import.meta.url).href,readerUrl=new URL('./source-reader.mjs',import.meta.url).href;
  const driver="import{main}from "+JSON.stringify(helperUrl)+";import{readSource}from "+JSON.stringify(readerUrl)+";import{readFile}from'node:fs/promises';const fetchImpl=async(url)=>{if(String(url).includes('/whoami?'))return new Response(JSON.stringify({code:200,data:{subject:'fixture.user'}}));if(String(url).includes('/commits?'))return new Response(JSON.stringify({values:[{id:"+JSON.stringify(commit)+"}]}));if(String(url).includes('/raw/'))return new Response(await readFile("+JSON.stringify(join(root,'source.md'))+"));throw Error('unexpected');};main(process.argv.slice(2),{readSourceImpl:(request)=>readSource(request,{fetchImpl,tokenProvider:()=> 'synthetic-ticket'})}).catch(e=>{console.log(JSON.stringify({code:e.code,message:e.message}));process.exitCode=1});";
  await writeFile(cli,driver);
  const run=(...args)=>{const p=spawnSync(process.execPath,[cli,...args],{encoding:'utf8'});return{status:p.status,result:JSON.parse(p.stdout.trim())};};
  try{
    assert.equal(run('prepare','--request',join(root,'request.json'),'--workspace',work).status,0);
    assert.equal(run('prepare','--request',join(root,'request.json'),'--workspace',work,'--resume').status,0);
    await writeFile(join(root,'changed-request.json'),canonical({...request,source_url:fixtureUrl.replace('feature-rules','main')}));
    assert.equal(run('prepare','--request',join(root,'changed-request.json'),'--workspace',work,'--resume').result.code,'RESUME_REQUEST_CHANGED');
    const source=JSON.parse(await readFile(join(work,'source.json'),'utf8'));const files=new Map();for(const file of source.files)files.set(file.package_path,new Uint8Array(await readFile(join(work,file.package_path))));
    const draft=await readyDraft(source,files);await writeFile(join(work,'draft.json'),canonical(draft));
    const preview=run('preview','--workspace',work);assert.equal(preview.status,0);assert.equal(preview.result.status,'preview_ready');
    assert.equal(run('package','--workspace',work,'--output',join(root,'before.zip')).result.code,'CONFIRMATION_REQUIRED');
    assert.equal(run('confirm','--workspace',work,'--preview-digest','wrong','--user-confirmed').result.code,'CONFIRMATION_REQUIRED');
    assert.equal(run('confirm','--workspace',work,'--preview-digest',preview.result.preview_digest,'--user-confirmed').status,0);
    assert.equal(run('package','--workspace',work,'--output',join(root,'final.zip')).status,0);
    const validated=run('validate','--package',join(root,'final.zip'));assert.equal(validated.status,0);assert.equal(validated.result.source_verified,false);assert.equal(validated.result.publishable,false);
    draft.open_questions=[{question_ref:'recheck',message:'新的判断需确认'}];await writeFile(join(work,'draft.json'),canonical(draft));
    assert.equal(run('package','--workspace',work,'--output',join(root,'stale.zip')).result.code,'DRAFT_NOT_READY');
  }finally{await rm(root,{recursive:true,force:true});}
});

test('real Git attributes prove archive is not a raw source; raw provider retains ignored files and literal substitutions', async () => {
  const root=await mkdtemp(join(tmpdir(),'source-helper-attributes-'));
  const git=(...args)=>{const result=spawnSync('git',['-C',root,...args],{encoding:null});if(result.status!==0)throw Error('local Git fixture command failed');return result.stdout;};
  try{
    git('init','-q');git('checkout','-b','feature-rules');await mkdir(join(root,'docs'));
    await writeFile(join(root,'.gitattributes'),'docs/subst.md export-subst\ndocs/ignored.md export-ignore\n');
    const raw='原始 $Format:%H$ 内容\n';await writeFile(join(root,'docs/subst.md'),raw);await writeFile(join(root,'docs/ignored.md'),'不能遗漏的正文\n');
    git('add','--','.gitattributes','docs/subst.md','docs/ignored.md');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','synthetic attributes');
    const revision=git('rev-parse','HEAD').toString().trim();const archive=git('archive','--format=tar',revision);
    const listing=spawnSync('tar',['-tf','-'],{input:archive,encoding:'utf8'});assert.equal(listing.status,0);assert.ok(!listing.stdout.includes('docs/ignored.md'));
    const archived=spawnSync('tar',['-xOf','-','docs/subst.md'],{input:archive,encoding:'utf8'});assert.equal(archived.status,0);assert.notEqual(archived.stdout,raw);
    const fetchImpl=async(url)=>{
      const u=new URL(url);if(u.pathname.endsWith('/whoami'))return new Response(JSON.stringify({code:200,data:{subject:'fixture.user'}}));
      if(u.pathname.endsWith('/commits'))return new Response(JSON.stringify({values:[{id:revision}]}));
      if(u.pathname.endsWith('/files'))return new Response(JSON.stringify({values:git('ls-tree','-r','--name-only',revision).toString().trim().split('\n'),isLastPage:true}));
      const path=decodeURIComponent(u.pathname.split('/raw/')[1]);assert.equal(u.searchParams.get('at'),revision);return new Response(git('show',`${revision}:${path}`));
    };
    const plan=parseSourceUrl(fixtureUrl.replace('docs%2Frules.md','docs'),{selection_type:'directory'});
    const result=await readGitRawSource(plan,{actor_mis:'fixture.user'},{fetchImpl,tokenProvider:()=> 'synthetic-ticket'});
    assert.deepEqual(result.source.files.map(file=>file.source_path),['ignored.md','subst.md']);
    const substituted=result.source.files.find(file=>file.source_path==='subst.md');assert.equal(new TextDecoder().decode(result.files.get(substituted.package_path)),raw);
  }finally{await rm(root,{recursive:true,force:true});}
});

test('strike semantics stay visible in rich text mapping and preview', async () => {
  const rendered=renderHistoryNode({type:'paragraph',content:[{type:'text',text:'已废弃要求',marks:[{type:'strike'}]}]});assert.equal(rendered.text,'~~已废弃要求~~\n\n');assert.deepEqual(rendered.unsupported,[]);
});

test('history renderer uses own data only; parser isolates raw objects from inherited fields', () => {
  const inherited=Object.create({type:'text',text:'inherited-only'});
  assert.equal(renderHistoryNode(inherited).text,'');assert.ok(renderHistoryNode(inherited).unsupported.length);
  const parsed=parseHistoryTree(utf8('{"type":"paragraph","content":[]}'));
  assert.equal(Object.getPrototypeOf(parsed.value),null);assert.equal(renderHistoryNode(parsed.value).text,'\n\n');
  assert.equal(renderHistoryNode({type:'heading',attrs:Object.create({level:6}),content:[{type:'text',text:'标题'}]}).unsupported.includes('invalid_attrs'),true);
  let getterRan=false;const node={type:'text'};Object.defineProperty(node,'text',{get(){getterRan=true;return'secret';}});
  assert.equal(renderHistoryNode(node).unsupported.includes('invalid_text'),true);assert.equal(getterRan,false);
  assert.equal(renderHistoryNode({type:'text',text:'正常',marks:[Object.create({type:'strike'})]}).text,'正常');
  for(const input of ['{"__proto__":{}}','{"constructor":{}}','{"prototype":{}}'])assert.throws(()=>parseHistoryTree(utf8(input)),/不允许/);
});

test('blockquote stays quoted and ambiguous inline code is explicitly unsupported', async () => {
  const {renderMarkdown}=await import('./preview.mjs');
  const node={type:'blockquote',content:[{type:'paragraph',content:[{type:'text',text:'被引用的旧要求'}]}]};
  const rendered=renderHistoryNode(node);assert.equal(rendered.text,'> 被引用的旧要求\n\n');assert.deepEqual(rendered.unsupported,[]);assert.ok(renderMarkdown(rendered.text).includes('<blockquote>'));
  const code=renderHistoryNode({type:'text',text:'a`b',marks:[{type:'code'}]});assert.equal(code.text,'a`b');assert.ok(code.unsupported.includes('inline_code_delimiter'));
  const basic=renderHistoryNode({type:'text',text:'value',marks:[{type:'code'}]});assert.equal(basic.text,'`value`');assert.deepEqual(basic.unsupported,[]);
});

test('Code adapter distinguishes expired authentication from explicit repository ACL denial',async()=>{
 const scenarios=[
  {status:401,body:{message:'expired'},code:'SOURCE_AUTH_REQUIRED',login:true},
  {status:403,body:{message:'denied'},code:'SOURCE_PERMISSION_DENIED',login:false},
  {status:401,body:{errors:[{message:'Permission denied, need permission:REPO_GUEST'}]},code:'SOURCE_PERMISSION_DENIED',login:false},
 ];
 for(const scenario of scenarios){
  let calls=0;const fetchImpl=async(url)=>{calls++;return String(url).includes('/whoami?')?new Response(JSON.stringify({code:200,data:{subject:'fixture.user'}})):new Response(JSON.stringify(scenario.body),{status:scenario.status});};
  await assert.rejects(readGitRawSource(parseSourceUrl(fixtureUrl),{actor_mis:'fixture.user'},{fetchImpl,tokenProvider:()=> 'synthetic-ticket'}),(error)=>{assert.equal(error.code,scenario.code);assert.equal(error.message.includes('code-cli auth login'),scenario.login);if(!scenario.login)assert.match(error.message,/授权|权限/);return true;});
  assert.equal(calls,2,'failed upstream request must not trigger login retries or another transport');
 }
});

test('real CLI consumer retains safe-house recovery guidance without exposing secrets or unsafe diagnostics',async()=>{
 const {chmod}=await import('node:fs/promises');const root=await mkdtemp(join(tmpdir(),'source-helper-safe-house-'));const bin=join(root,'bin');await mkdir(bin);
 const request={schema_version:'source-helper-request/v1',source_url:'https://km.sankuai.com/collabpage/123',actor_mis:'fixture.user',standard_domain:'backend',rule_set:{name:'safe-house-fixture',display_name:'测试',description:'合成失败测试',owner_mis:'fixture.owner',applicability_scope:'合成测试'}};
 await writeFile(join(root,'request.json'),canonical(request));
 const cases=[
  {stderr:'Error: 高密文档，请携带安全屋Token后重试。\n',exact:'高密文档，请携带安全屋Token后重试。'},
  {stderr:'Error: 请携带安全屋Token后重试；token=do-not-print-secret; https://private.invalid/a /Users/private/secret\n    at internal (file.js:1:2)\nSELECT secret FROM users\n'},
  {stderr:JSON.stringify({error:{message:'请携带安全屋Token后重试；Authorization: Bearer hidden-ticket'}})+'\n'},
  {stderr:'Error: 安全屋读取失败 SELECT secret FROM users\n'},
 ];
 try{for(const [index,fixture]of cases.entries()){
  const command=join(bin,'oa-skills');await writeFile(command,`#!${process.execPath}\nprocess.stderr.write(${JSON.stringify(fixture.stderr)});process.exit(1);\n`);await chmod(command,0o700);
  const result=spawnSync(process.execPath,[new URL('./source-helper.mjs',import.meta.url).pathname,'prepare','--request',join(root,'request.json'),'--workspace',join(root,`work-${index}`)],{encoding:'utf8',env:{...process.env,PATH:`${bin}:${process.env.PATH}`}});
  assert.notEqual(result.status,0);const error=JSON.parse(result.stdout.trim());assert.equal(error.code,'SOURCE_SECURE_ENVIRONMENT_REQUIRED');assert.match(error.message,/安全屋Token.*重试/u);if(fixture.exact)assert.equal(error.message,fixture.exact);
  const rendered=result.stdout+result.stderr;for(const denied of ['do-not-print-secret','hidden-ticket','SELECT','file.js','private.invalid','/Users/private'])assert.ok(!rendered.includes(denied));
 }}finally{await rm(root,{recursive:true,force:true});}
});
