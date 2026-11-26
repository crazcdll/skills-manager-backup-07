import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { canonical, canonicalHash, parseStrictJson, utf8, sha256, validatePackage, PACKAGE_JSON_SCHEMA, PackageContractError } from './package-contract.mjs';
import { minimalPackage, resealFixture } from './fixtures/minimal-package.mjs';

const json = (files, name) => parseStrictJson(files.get(name));
const rejects = (task, code) => assert.rejects(task, (error) => error instanceof PackageContractError && error.code === code);
const mutateContent = async (change) => {
  const files = await minimalPackage(); const content = json(files, 'content.json'); change(content);
  files.set('content.json', utf8(canonical(content))); return resealFixture(files);
};

test('validated bytes are neither verified source nor permission to publish', async () => {
  const result = await validatePackage(await minimalPackage());
  assert.equal(result.integrityVerified, true); assert.equal(result.sourceVerified, false);
  assert.equal(result.readerCoverageVerified, false); assert.equal(result.publishable, false);
  assert.deepEqual(result.counts, { sources: 1, documents: 1, rules: 1, excluded_units: 0 });
});

test('reference schema and independently generated canonical vectors match', async () => {
  const schema = JSON.parse(await readFile(new URL('../references/package.schema.json', import.meta.url), 'utf8'));
  assert.equal(canonical(schema), canonical(PACKAGE_JSON_SCHEMA));
  const vectors = JSON.parse(await readFile(new URL('./fixtures/canonical-vectors.json', import.meta.url), 'utf8'));
  for (const vector of vectors) { assert.equal(canonical(vector.input), vector.canonical); assert.equal(await canonicalHash(vector.input), vector.sha256); }
});

test('strict JSON rejects duplicate keys, invalid Unicode, NUL, numbers and nesting', () => {
  for (const input of ['{"a":1,"a":2}', '{"a":1,"\\u0061":2}', '"\\ud800"', '"\\u0000"', '1.0', '1e1', '-0', '9007199254740992', '[1,]', '\ufeff{}', '['.repeat(34) + '0' + ']'.repeat(34)]) {
    assert.throws(() => parseStrictJson(utf8(input)), PackageContractError, input);
  }
  assert.throws(() => parseStrictJson(new Uint8Array([0xc0, 0xaf])), /UTF-8/);
});

test('canonical refuses class objects, sparse arrays, accessors and symbols without invoking getters', () => {
  const array = [1]; delete array[0]; array.foo = 1;
  let invoked = false; const getter = {}; Object.defineProperty(getter, 'a', { enumerable: true, get() { invoked = true; return 1; } });
  const arrayGetter = []; Object.defineProperty(arrayGetter, '0', { enumerable: true, get() { invoked = true; return 1; } });
  const symbol = [1]; symbol[Symbol('x')] = 1;
  for (const input of [new Date(), array, getter, arrayGetter, symbol, { a: undefined }]) assert.throws(() => canonical(input), PackageContractError);
  assert.equal(invoked, false);
});

test('changing content or confirmation cannot reuse confirmation', async () => {
  const files = await minimalPackage(); const value = json(files, 'confirmation.json'); value.content_digest = `sha256:${'a'.repeat(64)}`;
  files.set('confirmation.json', utf8(canonical(value)));
  await rejects(validatePackage(files), 'PACKAGE_CONFIRMATION_INVALID');
  const tampered = await minimalPackage(); tampered.set('content.json', utf8('{}'));
  await rejects(validatePackage(tampered), 'PACKAGE_SCHEMA_INVALID');
});

test('confirmed packages accept current metadata or the complete valid legacy pair without rewriting the payload', async () => {
  const pkg = (fields) => mutateContent(c => {
    const rule = c.rules[0];
    rule.metadata = { ruleTitle:rule.title, ruleType:rule.rule_type, description:rule.title, level:'L2', ruleVersion:'0.0.1', language:[], framework:[], severity:[], ...fields };
  });
  for (const shape of [{}, {category:['business'], status:['closed']}]) {
    const files = await pkg(shape), before = structuredClone(files);
    const { content } = await validatePackage(files);
    assert.deepEqual(Object.hasOwn(content.rules[0].metadata,'category'), Object.hasOwn(shape,'category'));
    assert.deepEqual(files, before);
  }
  for (const shape of [{category:['business']}, {status:['closed']}, {category:[],status:['open']}, {category:['business'],status:['unknown']}]) {
    await rejects(validatePackage(await pkg(shape)), 'PACKAGE_SCHEMA_INVALID');
  }
});

test('unsupported updates and invented identity fields fail closed', async () => {
  for (const change of [(m) => { m.operation = 'replace'; }, (m) => { m.rule_set.rule_set_id = 'fake'; }, (m) => { m.scope_level = 'L1'; }]) {
    const files = await minimalPackage(); const manifest = json(files, 'manifest.json'); change(manifest); files.set('manifest.json', utf8(canonical(manifest)));
    await rejects(validatePackage(files), 'PACKAGE_SCHEMA_INVALID');
  }
});

test('all rules must appear once in their own physical document', async () => {
  await rejects(validatePackage(await mutateContent((c) => { c.documents[0].content.push({ type: 'rule', rule_ref: 'rule_one' }); })), 'PACKAGE_REFERENCE_INVALID');
  await rejects(validatePackage(await mutateContent((c) => { c.rules[0].document_ref = 'not_found'; })), 'PACKAGE_REFERENCE_INVALID');
});

test('coverage gaps, duplicated units and missing source association reject', async () => {
  await rejects(validatePackage(await mutateContent((c) => { c.coverage[0].byte_start = 1; })), 'PACKAGE_COVERAGE_INVALID');
  await rejects(validatePackage(await mutateContent((c) => { c.coverage.push(structuredClone(c.coverage[0])); })), 'PACKAGE_REFERENCE_INVALID');
  await rejects(validatePackage(await mutateContent((c) => { c.coverage[0].targets = ['document_one']; })), 'PACKAGE_COVERAGE_INVALID');
});

test('same byte hash cannot justify modified text claimed as source extract', async () => {
  await rejects(validatePackage(await mutateContent((c) => { c.rules[0].body[0].text = '改写后的要求'; })), 'PACKAGE_PROVENANCE_INVALID');
  await rejects(validatePackage(await mutateContent((c) => { c.rules[0].body[0].provenance.source_spans[0].sha256 = `sha256:${'f'.repeat(64)}`; })), 'PACKAGE_HASH_MISMATCH');
});

test('examples need explicit per-role omission reasons and resolution', async () => {
  await rejects(validatePackage(await mutateContent((c) => { c.rules[0].omissions = []; })), 'PACKAGE_OMISSION_INVALID');
  await rejects(validatePackage(await mutateContent((c) => { c.resolutions = []; })), 'PACKAGE_OMISSION_INVALID');
});

test('index must bind actual source references, cover documents, and contain no invented rows', async () => {
  const files = await minimalPackage(); files.set('AGENTS.md', utf8(new TextDecoder().decode(files.get('AGENTS.md')).replace('rules/errors.md', 'rules/missing.md')));
  await rejects(validatePackage(await resealFixture(files)), 'PACKAGE_INDEX_INVALID');
  await rejects(validatePackage(await mutateContent((c) => { c.agents_index.bindings[0].document_ref = 'not_found'; })), 'PACKAGE_INDEX_INVALID');
});

test('two-column packages validate real relative references and reject unmatched or empty cells', async () => {
  const table = '| 规则文件 | 触发条件 |\n| --- | --- |\n';
  const validate = async (row) => {
    const files = await minimalPackage();
    files.set('AGENTS.md', utf8(table + row));
    return validatePackage(await resealFixture(files));
  };
  await validate('| rules/errors.md | 处理异常时 |\n');
  for (const row of ['| rules/other.md | 处理异常时 |', '| rules/errors.md |  |', '|  | 处理异常时 |', '']) await rejects(validate(row), 'PACKAGE_INDEX_INVALID');
});

test('source bytes and source manifest have a single binding', async () => {
  const files = await minimalPackage(); files.set('sources/source_one.md', utf8('other source'));
  await rejects(validatePackage(await resealFixture(files)), 'PACKAGE_SOURCE_INVALID');
  const extra = await minimalPackage(); extra.set('unlisted.txt', utf8('unlisted'));
  await rejects(validatePackage(extra), 'PACKAGE_FILES_INVALID');
});

test('source SHA uses exact bytes including CRLF and decomposed Unicode', async () => {
  assert.notEqual(await sha256(utf8('a\r\n')), await sha256(utf8('a\n')));
  assert.notEqual(await sha256(utf8('é')), await sha256(utf8('e\u0301')));
});

test('frozen invalid package cases reject without repairing the payload', async () => {
  const cases = JSON.parse(await readFile(new URL('./fixtures/invalid-cases.json', import.meta.url), 'utf8'));
  for (const fixture of cases) {
    const files = await minimalPackage(); const input = json(files, fixture.file);
    let parent = input; for (const field of fixture.path.slice(0, -1)) parent = parent[field];
    parent[fixture.path.at(-1)] = fixture.value;
    files.set(fixture.file, utf8(canonical(input)));
    await rejects(validatePackage(files), fixture.code);
  }
});

test('checked-in minimal package exactly matches producer output', async () => {
  for (const [path,bytes] of await minimalPackage()) {
    assert.deepEqual(new Uint8Array(await readFile(new URL(`./fixtures/minimal-package/${path}`, import.meta.url))), bytes, path);
  }
});
