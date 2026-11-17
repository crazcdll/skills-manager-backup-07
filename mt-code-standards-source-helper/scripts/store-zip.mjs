import { LIMITS, PackageContractError, safeRelativePath, utf8, decodeUtf8 } from './package-contract.mjs';
const fail = (path, message) => { throw new PackageContractError('PACKAGE_ZIP_INVALID', path, message); };
const crcTable = Array.from({ length: 256 }, (_, n) => {
  for (let k = 0; k < 8; k += 1) n = n & 1 ? 0xedb88320 ^ (n >>> 1) : n >>> 1;
  return n >>> 0;
});
export function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) crc = crcTable[(crc ^ byte) & 255] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}
const join = (chunks) => { const bytes = new Uint8Array(chunks.reduce((n, chunk) => n + chunk.length, 0)); let offset = 0; for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; } return bytes; };
const make = (size) => { const bytes = new Uint8Array(size); return { bytes, view: new DataView(bytes.buffer) }; };

export function encodeStoreZip(files) {
  if (!(files instanceof Map) || !files.size || files.size > LIMITS.entries) fail('', 'ZIP 文件数量超出本版本限制。');
  const locals = [], centrals = []; let offset = 0, expanded = 0;
  for (const path of [...files.keys()].sort()) {
    safeRelativePath(path, path); const content = files.get(path);
    if (!(content instanceof Uint8Array)) fail(path, 'ZIP 文件必须是原始字节。');
    expanded += content.length; if (expanded > LIMITS.expandedBytes) fail('', 'ZIP 展开大小超过上限。');
    const name = utf8(path), crc = crc32(content);
    const local = make(30 + name.length); const l = local.view;
    l.setUint32(0, 0x04034b50, true); l.setUint16(4, 20, true); l.setUint16(6, 0x800, true);
    l.setUint16(12, 33, true); l.setUint32(14, crc, true); l.setUint32(18, content.length, true); l.setUint32(22, content.length, true);
    l.setUint16(26, name.length, true); local.bytes.set(name, 30);
    const central = make(46 + name.length); const c = central.view;
    c.setUint32(0, 0x02014b50, true); c.setUint16(4, 0x0314, true); c.setUint16(6, 20, true); c.setUint16(8, 0x800, true);
    c.setUint16(14, 33, true); c.setUint32(16, crc, true); c.setUint32(20, content.length, true); c.setUint32(24, content.length, true);
    c.setUint16(28, name.length, true); c.setUint32(38, (0o100644 << 16) >>> 0, true); c.setUint32(42, offset, true); central.bytes.set(name, 46);
    locals.push(local.bytes, content); centrals.push(central.bytes); offset += local.bytes.length + content.length;
  }
  const centralBytes = join(centrals), end = make(22), e = end.view;
  e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.size, true); e.setUint16(10, files.size, true);
  e.setUint32(12, centralBytes.length, true); e.setUint32(16, offset, true);
  const result = join([...locals, centralBytes, end.bytes]);
  if (result.length > LIMITS.zipBytes) fail('', 'ZIP 大小超过上限。');
  return result;
}

export function decodeStoreZip(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.length < 22 || bytes.length > LIMITS.zipBytes) fail('', 'ZIP 大小无效。');
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const u16 = (at) => view.getUint16(at, true), u32 = (at) => view.getUint32(at, true);
  const end = bytes.length - 22;
  if (u32(end) !== 0x06054b50 || u16(end + 4) || u16(end + 6) || u16(end + 20)) fail('', '仅支持无注释、单磁盘的标准包 ZIP。');
  const count = u16(end + 10), centralSize = u32(end + 12), centralStart = u32(end + 16);
  if (!count || count > LIMITS.entries || u16(end + 8) !== count || centralStart + centralSize !== end) fail('', 'ZIP 目录数量或边界无效。');
  const entries = []; const names = new Set(); let at = centralStart, expanded = 0;
  for (let i = 0; i < count; i += 1) {
    if (at + 46 > end || u32(at) !== 0x02014b50) fail('', 'ZIP 中央目录损坏。');
    const nameLength = u16(at + 28), extraLength = u16(at + 30), commentLength = u16(at + 32);
    if (at + 46 + nameLength + extraLength + commentLength > end || !nameLength || extraLength || commentLength || u16(at + 34) || u16(at + 6) > 20) fail('', 'ZIP 条目扩展、注释或版本不受支持。');
    const flags = u16(at + 8), method = u16(at + 10), size = u32(at + 24), mode = u32(at + 38) >>> 16;
    if (![0, 0x800].includes(flags) || method !== 0 || u32(at + 20) !== size || (mode & 0o170000) && (mode & 0o170000) !== 0o100000 || (u32(at + 38) & 0x10)) fail('', '仅支持普通文件和 STORE 方法，不支持加密、链接或目录。');
    const nameBytes = bytes.subarray(at + 46, at + 46 + nameLength);
    if (!flags && nameBytes.some((byte) => byte > 127)) fail('', '非 ASCII ZIP 文件名需要明确 UTF-8 标记。');
    const path = decodeUtf8(nameBytes, '/zip/path'); safeRelativePath(path, '/zip/path');
    if (names.has(path)) fail(path, 'ZIP 文件名重复。'); names.add(path);
    expanded += size; if (expanded > LIMITS.expandedBytes) fail('', 'ZIP 展开大小超过上限。');
    entries.push({ path, nameBytes, flags, size, crc: u32(at + 16), offset: u32(at + 42) });
    at += 46 + nameLength;
  }
  if (at !== end) fail('', 'ZIP 中央目录存在未声明数据。');
  const files = new Map(); let cursor = 0;
  for (const entry of entries.sort((a, b) => a.offset - b.offset)) {
    const p = entry.offset;
    if (p !== cursor || p + 30 > centralStart || u32(p) !== 0x04034b50) fail(entry.path, 'ZIP 本地条目重叠、缺失或含前置数据。');
    const nameLength = u16(p + 26), extraLength = u16(p + 28);
    if (u16(p + 4) > 20 || u16(p + 6) !== entry.flags || u16(p + 8) !== 0 || u32(p + 14) !== entry.crc || u32(p + 18) !== entry.size || u32(p + 22) !== entry.size || extraLength || nameLength !== entry.nameBytes.length) fail(entry.path, 'ZIP 本地条目与中央目录不一致。');
    const begin = p + 30 + nameLength, finish = begin + entry.size;
    if (finish > centralStart || entry.nameBytes.some((byte, i) => bytes[p + 30 + i] !== byte)) fail(entry.path, 'ZIP 本地路径或长度不匹配。');
    const content = bytes.slice(begin, finish);
    if (crc32(content) !== entry.crc) fail(entry.path, 'ZIP 文件 CRC 校验失败。');
    files.set(entry.path, content); cursor = finish;
  }
  if (cursor !== centralStart) fail('', 'ZIP 包含未声明的本地数据。');
  return files;
}
