import { PACKAGE_SCHEMA, CONTENT_SCHEMA, CONFIRMATION_SCHEMA, CONTENT_CONTRACT, RENDER_CONTRACT, canonical, sha256, utf8, manifestDigest } from '../package-contract.mjs';

// Synthetic fixture, not an authenticated source or a real user confirmation.
export async function minimalPackage() {
  const sourceText = '# 异常处理\n捕获异常时保留原始异常链。\n';
  const bytes = utf8(sourceText);
  const sourceHash = await sha256(bytes);
  const extracted = { origin: 'source_extract', source_spans: [{ source_ref: 'source_one', byte_start: 0, byte_end: bytes.length, sha256: sourceHash }], reason: '' };
  const index = '# 规则集索引\n\n| 名称 | 触发场景 | 路径 |\n| --- | --- | --- |\n| 异常处理 | 捕获或包装异常 | rules/errors.md |\n';
  const content = {
    schema_version: CONTENT_SCHEMA, content_contract: CONTENT_CONTRACT,
    documents: [{ document_ref: 'document_one', source_ref: 'source_one', title: '异常处理', description: '异常处理的检查要求', category_key: 'engineering', subcategory_key: 'general', rule_type: 'Model Request', content: [{ type: 'rule', rule_ref: 'rule_one' }] }],
    rules: [{ rule_ref: 'rule_one', document_ref: 'document_one', title: '保留异常链', execution_level: 'mandatory', category_key: 'engineering', subcategory_key: 'general', rule_type: 'Model Request', tech_stacks: ['java'], stages: ['coding', 'cr'], applicability_tags: [], body: [{ type: 'markdown', text: sourceText, provenance: extracted }], omissions: [{ role: 'good', reason: '本夹具仅验证规则正文。' }, { role: 'bad', reason: '本夹具仅验证规则正文。' }] }],
    coverage: [{ source_ref: 'source_one', unit_ref: 'unit_one', byte_start: 0, byte_end: bytes.length, disposition: 'included', targets: ['rule_one'], reason: '' }],
    resolutions: [{ question_ref: 'question_one', kind: 'omission', decision: '保留正反例为空', explanation: '合成夹具，不代表真实用户确认。', affected_refs: ['rule_one'] }],
    agents_index: { schema_version: 'rule-set-agents-index/v1', path: 'AGENTS.md', bindings: [{ reference: 'rules/errors.md', document_ref: 'document_one' }] },
  };
  const files = new Map([
    ['content.json', utf8(canonical(content))], ['AGENTS.md', utf8(index)], ['sources/source_one.md', bytes],
  ]);
  const manifest = {
    schema_version: PACKAGE_SCHEMA, operation: 'create_l2', standard_domain: 'backend', scope_level: 'L2',
    rule_set: { name: 'fixture-errors', display_name: '异常处理测试规范', description: '合成测试材料', owner_mis: 'fixture.owner', applicability_scope: '合成测试仓库' },
    source: { type: 'git', reader_contract: 'fixed-source/v1', locator: { repository_url: 'https://git.sankuai.com/fixture/rules', root_path: '' }, revision: { commit: '1'.repeat(40) }, files: [{ source_ref: 'source_one', source_path: 'rules/errors.md', package_path: 'sources/source_one.md', representation: 'git-raw-utf8', sha256: sourceHash, byte_size: bytes.length }] },
    render_contract: RENDER_CONTRACT, converter: { name: 'mt-code-standards-source-helper', version: '0.1.0' },
    counts: { sources: 1, documents: 1, rules: 1, excluded_units: 0 }, files: [], content_digest: `sha256:${'0'.repeat(64)}`,
  };
  for (const path of [...files.keys()].sort()) manifest.files.push({ path, byte_size: files.get(path).length, sha256: await sha256(files.get(path)) });
  manifest.content_digest = await manifestDigest(manifest);
  const confirmation = { schema_version: CONFIRMATION_SCHEMA, content_digest: manifest.content_digest, decision: 'confirmed', confirmed_at: '2026-11-12T00:00:00Z', confirmed_scope: { content: true, agents_index: true, exclusions: true, generated_changes: true } };
  files.set('manifest.json', utf8(canonical(manifest)));
  files.set('confirmation.json', utf8(canonical(confirmation)));
  return files;
}

// Rehash a mutated fixture so negative tests reach relational checks rather than
// failing at the outer integrity layer. Never use this helper in production.
export async function resealFixture(files) {
  const manifest = JSON.parse(new TextDecoder().decode(files.get('manifest.json')));
  manifest.files = [];
  for (const path of [...files.keys()].filter((p) => !['manifest.json', 'confirmation.json'].includes(p)).sort()) manifest.files.push({ path, byte_size: files.get(path).length, sha256: await sha256(files.get(path)) });
  manifest.content_digest = await manifestDigest(manifest);
  const confirmation = JSON.parse(new TextDecoder().decode(files.get('confirmation.json')));
  confirmation.content_digest = manifest.content_digest;
  files.set('manifest.json', utf8(canonical(manifest))); files.set('confirmation.json', utf8(canonical(confirmation)));
  return files;
}
