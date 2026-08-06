"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.dataSourceMapFromGroovy = void 0;
const fromGroovy_1 = require("../groovy/fromGroovy");
const dataSourceMapFromTransformer_1 = require("./dataSourceMapFromTransformer");
function dataSourceMapFromGroovy(data) {
    const dataSourceMapFrom = (0, dataSourceMapFromTransformer_1.dataSourceMapFromTransformer)();
    return (0, fromGroovy_1.fromGroovy)(data, dataSourceMapFrom);
}
exports.dataSourceMapFromGroovy = dataSourceMapFromGroovy;
