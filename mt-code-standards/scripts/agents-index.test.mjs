import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { AGENTS_INDEX_CONTRACT, AGENTS_INDEX_MAX_BYTES, AGENTS_INDEX_MAX_JSON_BYTES, renderAgentsIndexes, validateAgentsIndexes } from './agents-index.mjs';
import { sha256Hex, canonicalJson } from './resolve-effective-rules.mjs';

const table = (reference) => `**数据库规范**\r\n\r\n| 名称 | 触发场景 | 路径 |\r\n|---|---|---|\r\n| DB | SQL \\| 建表 | \`${reference}\` |\r\n`;
const entry = (content = table('rules/db.md'), bindings = [{ reference: 'rules/db.md', document_id: 'db', source_path: 'rules/db.md', bundle_relative_path: 'l1/rules/db.md' }]) => ({
  rule_set_id: 'frontend-l1', release_id: 'release-1',
  index: { schema_version: AGENTS_INDEX_CONTRACT, origin: 'git', source_path: 'AGENTS.md', content, content_hash: content === null ? null : `sha256:${sha256Hex(content)}`, warnings: [] },
  bindings,
});
const refs = [{ rule_set_id: 'frontend-l1', release_id: 'release-1', scope_level: 'L1' }];
const local = [{ source_relative_path: 'l1/rules/db.md', local_relative_path: 'company/db--actual.md' }];

test('rewrites only table path cells using actual flattened names and preserves CRLF and prose', () => {
  const raw = 'rules/db.md 原文\r\n' + table('rules/db.md') + '\r\n```markdown\r\n' + table('rules/db.md') + '```\r\n';
  const rendered = renderAgentsIndexes([entry(raw)], local, refs);
  assert.equal(rendered.files[0].content, raw.replace('`rules/db.md`', '`.mdp/rules/company/db--actual.md`'));
  assert.equal(rendered.warnings.length, 0);
});

test('unmatched, stage-filtered and conflicting references preserve source text and warn', () => {
  for (const bindings of [[], [{ reference: 'rules/db.md', document_id: 'db', source_path: 'db.md', bundle_relative_path: null }], [
    { reference: 'rules/db.md', document_id: 'db', source_path: 'db.md', bundle_relative_path: 'l1/rules/db.md' },
    { reference: 'rules/db.md', document_id: 'other', source_path: 'other.md', bundle_relative_path: 'l1/other.md' },
  ]]) {
    const raw = table('rules/db.md');
    const rendered = renderAgentsIndexes([entry(raw, bindings)], [...local, { source_relative_path: 'l1/other.md', local_relative_path: 'company/other.md' }], refs);
    assert.equal(rendered.files[0].content, raw);
    assert.equal(rendered.warnings[0].code, 'agents_index_unmatched_reference');
    assert.equal(rendered.warnings[0].line, 5);
  }
});

test('missing, empty and malformed index content do not block rule installation', () => {
  for (const content of [null, '', 'arbitrary markdown\r\n']) {
    const rendered = renderAgentsIndexes([entry(content)], local, refs);
    assert.ok(rendered.warnings.length);
    assert.equal(rendered.files.length, content === null ? 0 : 1);
    if (content !== null) assert.equal(rendered.files[0].content, content);
  }
});

test('large diagnostic lists and paths stay bounded without truncating index content', () => {
  const longReference = '未匹配'.repeat(500) + '.md';
  const raw = table(longReference) + Array.from({ length: 1000 }, (_, i) =>
    `| DB | 查询 | \`missing-${i}.md\` |\r\n`).join('');
  const rendered = renderAgentsIndexes([entry(raw, [])], local, refs);
  assert.equal(rendered.files[0].content, raw);
  assert.equal(rendered.warnings.length, 51);
  assert.equal(rendered.warnings.at(-1).code, 'agents_index_diagnostics_omitted');
  assert.match(rendered.warnings.at(-1).message, /951/);
  assert.equal(Array.from(rendered.warnings[0].message).length, 256);
  assert.equal(Array.from(rendered.warnings[0].path).length, 240);
  assert.equal(rendered.warnings[0].line, 5);
  assert.ok(Buffer.byteLength(JSON.stringify(rendered.warnings), 'utf8') < 32 * 1024);
});

test('transport hash, original content hash, release and safe directory identity remain mandatory', () => {
  const good = () => { const entries = [entry()]; return { snapshot: { agents_indexes_hash: sha256Hex(canonicalJson(entries)) }, agents_indexes: entries }; };
  const refs = [{ rule_set_id: 'frontend-l1', release_id: 'release-1' }];
  assert.equal(validateAgentsIndexes(good(), refs), true);
  assert.equal(validateAgentsIndexes({ snapshot: {} }, refs), false);
  for (const mutate of [
    (body) => { body.snapshot.agents_indexes_hash = '0'.repeat(64); },
    (body) => { body.agents_indexes[0].index.content_hash = sha256Hex('wrong'); },
    (body) => { body.agents_indexes[0].release_id = 'other'; },
    (body) => { body.agents_indexes[0].rule_set_id = '../bad'; },
  ]) {
    const body = good(); mutate(body);
    if (body.snapshot.agents_indexes_hash !== '0'.repeat(64)) body.snapshot.agents_indexes_hash = sha256Hex(canonicalJson(body.agents_indexes));
    assert.throws(() => validateAgentsIndexes(body, refs), /AGENTS/);
  }
});

test('npm pack contains runtime helper and resolver imports it from the packed layout', () => {
  const root = fileURLToPath(new URL('../', import.meta.url));
  const packed = JSON.parse(execFileSync('npm', ['pack', '--dry-run', '--json', '--ignore-scripts', '--cache', '/private/tmp/mt-cli-agents-npm-cache'], { cwd: root, encoding: 'utf8' }));
  const names = packed[0].files.map((file) => file.path);
  assert.ok(names.includes('scripts/agents-index.mjs'));
  assert.ok(names.includes('scripts/resolve-effective-rules.mjs'));
  assert.ok(!names.includes('scripts/agents-index.test.mjs'));
});

test('consumes the actual Runner createAgentsIndex fixture with prefixed hash and unchanged bytes', async () => {
  // Generated from mdp-coding-rules-intake/scripts/agents-index.mjs:createAgentsIndex.
  const { readFile } = await import('node:fs/promises');
  const index = JSON.parse(await readFile(new URL('./fixtures/agents-index-runner.json', import.meta.url), 'utf8'));
  assert.match(index.content_hash, /^sha256:[a-f0-9]{64}$/);
  const item = { ...entry(), index };
  const body = { agents_indexes: [item], snapshot: { agents_indexes_hash: sha256Hex(canonicalJson([item])) } };
  assert.equal(validateAgentsIndexes(body, [{ rule_set_id: 'frontend-l1', release_id: 'release-1' }]), true);
  const rendered = renderAgentsIndexes([item], local, refs);
  assert.equal(rendered.files[0].content, index.content.replace('`rules/db.md`', '`.mdp/rules/company/db--actual.md`'));
  assert.deepEqual(rendered.warnings, []);
});


test('accepts exactly 5 MiB of UTF-8 including worst-case JSON escaping and rejects one extra byte', () => {
  const refs = [{ rule_set_id: 'frontend-l1', release_id: 'release-1' }];
  const validate = content => {
    const entries = [entry(content, [])];
    return validateAgentsIndexes({ agents_indexes: entries, snapshot: { agents_indexes_hash: sha256Hex(canonicalJson(entries)) } }, refs);
  };
  for (const content of ['x'.repeat(AGENTS_INDEX_MAX_BYTES), '\u0001'.repeat(AGENTS_INDEX_MAX_BYTES),
    '规'.repeat(Math.floor(AGENTS_INDEX_MAX_BYTES / 3)) + 'xx']) {
    assert.equal(Buffer.byteLength(content), AGENTS_INDEX_MAX_BYTES);
    assert.equal(validate(content), true);
    assert.throws(() => validate(content + 'x'), { code: 'RULE_BUNDLE_AGENTS_INDEX_INVALID' });
  }
  const oversized = entry('small', []);
  oversized.index.warnings = [{ code: 'test', message: 'x'.repeat(AGENTS_INDEX_MAX_JSON_BYTES) }];
  const entries = [oversized];
  assert.throws(() => validateAgentsIndexes({ agents_indexes: entries, snapshot: { agents_indexes_hash: sha256Hex(canonicalJson(entries)) } }, refs), { code: 'RULE_BUNDLE_AGENTS_INDEX_INVALID' });
});
