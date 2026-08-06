"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.evaluate = void 0;
function evaluate(ast, scope) {
    const evaluatorMap = {
        Literal: (ast) => ast.value,
        Identifier: (ast) => {
            const value = scope[ast.value];
            if (value === undefined) {
                throw new Error(`Unknown identifier, ${ast.value} is not defined`);
            }
            return value;
        },
        Function: (ast) => ((newScope) => {
            ast.body.forEach((ast) => evaluate(ast, newScope));
        }),
        FunctionCall: (ast) => {
            const fn = evaluate(ast.func, scope);
            const args = ast.args.map((arg) => evaluate(arg, scope));
            return fn(...args);
        },
        Expression: (ast) => ast.value,
        Block: (ast) => {
            ast.body.forEach((ast) => evaluate(ast, scope));
        },
    };
    return evaluatorMap[ast.type](ast);
}
exports.evaluate = evaluate;
