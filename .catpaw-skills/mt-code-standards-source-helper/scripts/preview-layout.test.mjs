import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderPreview } from './preview.mjs';

const source = 'source_one', file = { source_ref: source, package_path: 'sources/one.md', source_path: 'rules.md' };
const md = (text, origin = 'source_extract') => ({ type: 'markdown', text, provenance: { origin } });
const ex = (role, language, code, origin = 'source_extract') => ({ type: 'example', role, language, code, caption: '', provenance: { origin } });
function sample(body) {
  return {
    manifest: { content_digest: 'digest', source: { type: 'git', revision: { commit: 'a'.repeat(40) }, files: [file] } },
    content: { documents: [{ title: '安全', source_ref: source, content: [{ type: 'rule', rule_ref: 'rule_one' }] }], rules: [{
      rule_ref: 'rule_one', title: '检查输入', execution_level: 'recommended', metadata: { description: '检查传入的字段', level: 'L2', language: ['TypeScript'], framework: [], severity: [] },
      tech_stacks: ['typescript'], stages: ['coding', 'cr'], body
    }] }, agentsIndex: '',
  };
}
test('contiguous examples share a role heading, keep languages and provenance, and never cross prose', async () => {
  const data = sample([ex('good','yaml','example-1'),ex('good','md','example-2','user_modified'),md('转折说明','agent_generated'),ex('good','ts','example-3'),ex('bad','text','example-4'),ex('bad','sh','example-5')]);
  const before = structuredClone(data.content), {html} = await renderPreview(data);
  const groups = [...html.matchAll(/<section class="example" data-role="([^"]+)">([\s\S]*?)<\/section>/gu)];
  assert.deepEqual(groups.map(g=>[g[1],(g[2].match(/<pre><code>/gu)||[]).length]), [['good',2],['good',1],['bad',2]]);
  assert.match(groups[0][2],/yaml[\s\S]*?example-1[\s\S]*?md<span class="origin">用户修改<\/span>[\s\S]*?example-2/u);
  const plain = html.replace(/<[^>]+>/gu, '');
  assert.ok(plain.indexOf('转折说明') > plain.indexOf('example-2') && plain.indexOf('转折说明') < plain.indexOf('example-3'));
  assert.match(html, /AI 补充<\/span><p>转折说明/u);
  assert.equal((html.match(/原文摘取/gu)||[]).length,1);
  assert.deepEqual(data.content,before);
});
test('field rows retain values; only a verified frozen rule heading absorbs the old ID block', async () => {
  const first = md('CODE-001'), data=sample([first, md('检查传入的字段'), md('source: 原文文档')]);
  const raw=Buffer.from('## CODE-001 检查输入\n\ndescription: 检查传入的字段\nseverity: [建议]\nframework: []\n');
  first.provenance.source_spans=[{source_ref:source,byte_start:3,byte_end:11}];
  data.payload=new Map([[file.package_path,raw]]);
  const {html}=await renderPreview(data);
  assert.match(html,/<span>编号 CODE-001<\/span>[\s\S]*<h3>检查输入<\/h3>/u);
  assert.equal((html.match(/检查传入的字段/gu)||[]).length,1);
  for(const [key,value] of [['description','检查传入的字段'],['language','[TypeScript]'],['framework','[]'],['stage','[coding, cr]'],['source','原文文档'],['severity','[建议]']]) {
    assert.ok(html.includes('<dt>'+key+':</dt><dd>'+value+'</dd>'),key);
  }
  assert.doesNotMatch(html, /<dt>(?:category|status):<\/dt>/u);
  const groups = [...html.matchAll(/<dl class="fields">([\s\S]*?)<\/dl>/gu)];
  assert.equal(groups.length, 1);
  assert.match(groups[0][1], /<dt>level:<\/dt>[\s\S]*<dt>source:<\/dt>/u);
  data.content.rules[0].title='新标题';
  assert.match((await renderPreview(data)).html, /<div class="block"><p>CODE-001<\/p>/u);
});

test('source and trigger lines become fields even when the source block also contains checks', async () => {
  const { html } = await renderPreview(sample([md('trigger: 修改提交逻辑\n\nchecks:\n\n- 保留失败分支\n\nsource: 原文规则')])) ;
  assert.match(html, /<dt>trigger:<\/dt><dd>修改提交逻辑<\/dd>/u);
  assert.match(html, /<dt>source:<\/dt><dd>原文规则<\/dd>/u);
  assert.match(html, /<p>checks:<\/p>/u);
  assert.match(html, /<dt>trigger:[\s\S]*?<\/dl>[\s\S]*?<p>checks:<\/p>[\s\S]*?<dl class="fields">[\s\S]*?<dt>source:/u);
});
