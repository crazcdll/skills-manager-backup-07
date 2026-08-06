"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.unquoteGroovySingleDouble = exports.NORMAL_CHAR_UNQUOTE_MAP = void 0;
const escapeRegExp_1 = require("../utils/escapeRegExp");
// https://groovy-lang.org/syntax.html#_escaping_special_characters
exports.NORMAL_CHAR_UNQUOTE_MAP = {
    '\\b': '\b',
    '\\f': '\f',
    '\\n': '\n',
    '\\r': '\r',
    '\\s': ' ',
    '\\t': '\t',
    '\\\\': '\\',
    '\\\'': '\'',
    '\\"': '"',
};
function createCharRegexp(map) {
    const chars = Object.keys(map).map(escapeRegExp_1.escapeRegExp);
    const regexp = new RegExp(`(${chars.join('|')}|\\\\u([0-9a-fA-F]{4}))`, 'g');
    return regexp;
}
// 引号解析的正则表达式
const NORMAL_CHAR_UNQUOTE_REGEXP = createCharRegexp(exports.NORMAL_CHAR_UNQUOTE_MAP);
// 处理字符串内的转义符号
function unquoteGroovySingleDouble(str) {
    const removeCount = 1;
    return str
        .substring(removeCount, str.length - removeCount)
        .replace(NORMAL_CHAR_UNQUOTE_REGEXP, (match, group1, group2) => {
        return group2 ? String.fromCharCode(parseInt(group2, 16)) : exports.NORMAL_CHAR_UNQUOTE_MAP[match];
    });
}
exports.unquoteGroovySingleDouble = unquoteGroovySingleDouble;
