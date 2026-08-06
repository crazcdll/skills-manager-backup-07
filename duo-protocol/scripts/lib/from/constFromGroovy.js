"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.constFromGroovy = void 0;
const fromGroovy_1 = require("../groovy/fromGroovy");
const constFromTransformer_1 = require("./constFromTransformer");
function constFromGroovy(data) {
    const constFrom = (0, constFromTransformer_1.constFromTransformer)();
    return (0, fromGroovy_1.fromGroovy)(data, constFrom);
}
exports.constFromGroovy = constFromGroovy;
