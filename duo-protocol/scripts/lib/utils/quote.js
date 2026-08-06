"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.quoteSingle = exports.QUOTE_MAP = void 0;
const escapeRegExp_1 = require("./escapeRegExp");
exports.QUOTE_MAP = {
    '\b': '\\b',
    '\f': '\\f',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
    '\\': '\\\\',
    '\'': '\\\'',
};
function createCharRegexp(map) {
    const chars = Object.keys(map).map(escapeRegExp_1.escapeRegExp);
    const regexp = new RegExp(`(${chars.join('|')})`, 'g');
    return regexp;
}
// 引号解析的正则表达式
const QUOTE_REGEXP = createCharRegexp(exports.QUOTE_MAP);
// 处理字符串内的转义符号。使用单引号表示字符串。
function quoteSingle(str) {
    return `'${str.replace(QUOTE_REGEXP, (match) => exports.QUOTE_MAP[match])}'`;
}
exports.quoteSingle = quoteSingle;
