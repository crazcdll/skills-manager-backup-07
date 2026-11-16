import assert from "node:assert/strict";
import test from "node:test";
import { parseCallbackError, callbackErrorDiagnostics, readCallbackErrorResponse } from "./callback-error.mjs";
const message = "当前内容含高密文档，需在安全屋环境中访问，请携带安全屋Token后重试";
const requestId = "71440c02-b61a-49c6-b59c-03f0bbe78680";
const response = (error) => ({ contentType: "application/json; charset=utf-8", body: JSON.stringify({ error }) });

test("extracts bounded public callback errors while preserving C4 instructions", () => {
  for (const text of [message, "Upstream permission check failed", "An unknown operation could not be completed"]) {
    const details = parseCallbackError(response({ code: "upstream_access_denied", message: text, request_id: requestId }));
    assert.deepEqual(details, { message: text, upstreamCode: "upstream_access_denied", requestId });
    assert.deepEqual(callbackErrorDiagnostics({ message: text, ...details }), { diagnostic_message: text, upstream_code: "upstream_access_denied", request_id: requestId });
  }
});

test("redacts the actual capability wherever an upstream error reflects it", () => {
  const token = "a".repeat(43);
  const details = parseCallbackError(response({ code: token, message: `读取失败 ${token} token=another-secret`, request_id: token }), [token]);
  assert.equal(details.upstreamCode, null);
  assert.equal(details.requestId, null);
  assert.doesNotMatch(JSON.stringify(details), /aaaaaa|another-secret/u);
  assert.doesNotMatch(JSON.stringify(callbackErrorDiagnostics({ message: `读取失败 ${token}`, upstreamCode: token, requestId: token }, [token])), /aaaaaa/u);
});

test("rejects raw bodies SQL stack invalid codes and oversized errors", () => {
  for (const text of ["SELECT token FROM secrets", "Error\n    at private (/tmp/a:1:2)", "<html>private trace</html>", "secret", "permission denied for table private_users", "SQLSTATE 42501", "PostgREST PGRST000", 'relation "private_table" does not exist']) {
    assert.equal(parseCallbackError(response({ message: text })).message, null);
  }
  for (const value of ["contains spaces", "SELECT secret FROM users", "x".repeat(101), { code: "bad" }]) {
    assert.equal(parseCallbackError(response({ code: value, message })).upstreamCode, null);
  }
  assert.deepEqual(parseCallbackError({ contentType: "text/plain", body: message }), {});
  assert.deepEqual(parseCallbackError({ contentType: "application/json", body: "not-json Bearer secret" }), {});
  assert.deepEqual(parseCallbackError(response({ message: "x".repeat(9000) })), {});
  assert.equal(parseCallbackError(response({ message: "错误".repeat(900) })).message.length, 600);
});

test("bounds streamed fetch error bodies and cancels oversized streams", async () => {
  const normal = await readCallbackErrorResponse(Response.json({ error: { message } }, { status: 403 }));
  assert.equal(parseCallbackError(normal).message, message);
  let cancelled = false;
  const body = new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(9000)); }, cancel() { cancelled = true; } });
  assert.equal((await readCallbackErrorResponse(new Response(body, { headers: { "content-type": "application/json" } }))).body, "");
  assert.equal(cancelled, true);
  let headerCancelled = false;
  const oversized = new Response(new ReadableStream({ cancel() { headerCancelled = true; } }), { headers: { "content-length": "9000" } });
  assert.equal((await readCallbackErrorResponse(oversized)).body, "");
  assert.equal(headerCancelled, true);
});
