"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.indent = void 0;
function indent(str, w = 2) {
    const _w = 'number' == typeof w ? new Array(w + 1).join(' ') : w;
    return str
        .split(/\n/)
        .map((l) => (l ? _w + l : l))
        .join('\n');
}
exports.indent = indent;
