"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.fromGroovy = void 0;
const tokenize_1 = require("./tokenize");
const parse_1 = require("./parse");
const evaluate_1 = require("./evaluate");
function fromGroovy(data, createScope) {
    const tokens = (0, tokenize_1.tokenize)(data);
    const ast = (0, parse_1.parse)(tokens);
    const result = createScope((scope) => {
        (0, evaluate_1.evaluate)(ast, scope);
    });
    return result;
}
exports.fromGroovy = fromGroovy;
