"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.tokenize = void 0;
const dedent_1 = require("../utils/dedent");
const unquote_1 = require("./unquote");
// 这个map的顺序也是需要保证的。
// 比如 expression 需要在 openCurly 前面；trueValue等需要在identifier前面
const REGEXPS = {
    expression: /\{\{[\s\S]*?\}\}/,
    string: /'(?:\\'|[^'\n])*'/,
    stringDouble: /"(?:\\"|[^"\n])*"/,
    trueValue: /\btrue\b/,
    falseValue: /\bfalse\b/,
    nullValue: /\bnull\b/,
    openParen: /\(/,
    closeParen: /\)/,
    openCurly: /\{/,
    closeCurly: /\}/,
    comma: /,/,
    identifier: /[a-zA-Z_$][a-zA-Z\d_$]*/,
    number: /\d*\.\d+|\d+/,
    empty: /\s+/,
};
const REGEXP_KEYS = Object.keys(REGEXPS);
const REGEXP_STR = `${REGEXP_KEYS.map((key) => `(${REGEXPS[key].source})`).join('|')}`;
const REGEXP = new RegExp(REGEXP_STR, 'g');
function tokenize(expr) {
    REGEXP.lastIndex = 0;
    let offset = 0;
    const len = expr.length;
    const tokens = [];
    while (offset < len) {
        const match = REGEXP.exec(expr);
        if (!match || offset !== match.index) {
            throw new Error(`Unexpected char ${JSON.stringify(expr[offset])} at ${offset}`);
        }
        const s = offset;
        offset = REGEXP.lastIndex;
        const tokenInfo = handleToken(match);
        if (!tokenInfo)
            continue;
        const token = Object.assign({ s, e: offset }, tokenInfo);
        tokens.push(token);
    }
    return tokens;
}
exports.tokenize = tokenize;
function handleToken(match) {
    const value = match[0];
    const matchIndex = match.findIndex((item, index) => index && item);
    const matchType = REGEXP_KEYS[matchIndex - 1];
    if (matchType === 'empty') {
        return;
    }
    if (matchType === 'string' || matchType === 'stringDouble') {
        return { type: 'literal', value: (0, unquote_1.unquoteGroovySingleDouble)(value) };
    }
    if (matchType === 'number') {
        return { type: 'literal', value: +value };
    }
    if (matchType === 'trueValue') {
        return { type: 'literal', value: true };
    }
    if (matchType === 'falseValue') {
        return { type: 'literal', value: false };
    }
    if (matchType === 'nullValue') {
        return { type: 'literal', value: null };
    }
    if (matchType === 'expression') {
        return { type: 'expression', value: getExpression(value) };
    }
    return { type: matchType, value };
}
function getExpression(expression) {
    const value = expression.substring(2, expression.length - 2);
    if (!value.includes('\n'))
        return value.trim();
    return (0, dedent_1.dedent)(value);
}
