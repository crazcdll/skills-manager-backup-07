"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.escapeRegExp = exports.ESCAPE_REGEXP = void 0;
exports.ESCAPE_REGEXP = /[.*+?^${}()|[\]\\]/g;
// 转义正则的特殊字符
function escapeRegExp(str) {
    return str.replace(exports.ESCAPE_REGEXP, '\\$&');
}
exports.escapeRegExp = escapeRegExp;
