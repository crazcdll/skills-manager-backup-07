"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.toGroovyFunctionCall = void 0;
const indent_1 = require("../utils/indent");
const quote_1 = require("../utils/quote");
function expr(value) {
    return typeof value === 'string' ? (0, quote_1.quoteSingle)(value) : `${value}`;
}
const MAX_COLUMN_COUNT = 80;
const toGroovyFunctionCall = (name, args, { body, expression } = {}) => {
    if (args.length === 1 && body == null && expression == null) {
        return `${name} ${expr(args[0])}`;
    }
    let result = name;
    if (args.length) {
        result += `(${args.map(expr).join(', ')})`;
    }
    if (body != null) {
        result += ` {\n${(0, indent_1.indent)(body.join('\n'))}\n}`;
    }
    else if (expression != null) {
        const expressionContent = quoteExpression(expression);
        result += ` ${expressionContent}`;
    }
    return result;
};
exports.toGroovyFunctionCall = toGroovyFunctionCall;
function quoteExpression(expression) {
    const trim = expression.trim();
    const expressionContent = trim.includes('\n') || trim.length > MAX_COLUMN_COUNT
        ? `{{\n${(0, indent_1.indent)(expression)}\n}}`
        : `{{ ${expression} }}`;
    return expressionContent;
}
