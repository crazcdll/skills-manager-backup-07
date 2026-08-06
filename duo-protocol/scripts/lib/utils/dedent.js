"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.dedent = void 0;
function dedent(string) {
    const lines = string.split('\n');
    let minIndent = -1;
    lines.forEach(function (l) {
        if (!l.trim())
            return;
        const match = l.match(/^(\s+)\S+/);
        const indent = match ? match[1].length : 0;
        minIndent = minIndent === -1 ? indent : Math.min(minIndent, indent);
    });
    if (minIndent === -1) {
        return string;
    }
    const result = lines
        .map((l) => l[0] === ' ' ? l.substring(minIndent) : l)
        .join('\n')
        .replace(/^\n+/, '')
        .replace(/\n+$/, '');
    return result;
}
exports.dedent = dedent;
