import { canonical, canonicalHash, PACKAGE_JSON_SCHEMA, validatePackage } from './package-contract.mjs';
import { minimalPackage } from './fixtures/minimal-package.mjs';
const read = globalThis.Deno ? (url) => Deno.readTextFile(url) : async (url) => (await import('node:fs/promises')).readFile(url, 'utf8');
const vectors = JSON.parse(await read(new URL('./fixtures/canonical-vectors.json', import.meta.url)));
for (const vector of vectors) {
  if (canonical(vector.input) !== vector.canonical || await canonicalHash(vector.input) !== vector.sha256) throw new Error(`canonical vector failed: ${vector.name}`);
}
const schema = JSON.parse(await read(new URL('../references/package.schema.json', import.meta.url)));
if (canonical(schema) !== canonical(PACKAGE_JSON_SCHEMA)) throw new Error('JSON Schema differs from executable contract');
const result = await validatePackage(await minimalPackage());
const expected = 'sha256:a810050653dad16eda2e7e80d4cfca09c39448665fbcac5cc38d0424603396be';
if (result.manifest.content_digest !== expected || result.sourceVerified || result.publishable) throw new Error('fixture contract differs');
console.log(JSON.stringify({ runtime: globalThis.Deno ? 'deno' : 'node', vectors: vectors.length, fixture_digest: expected, source_verified: result.sourceVerified, status: 'passed' }));
