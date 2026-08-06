"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.dataSourceMapToGroovy = void 0;
const dataSourceMapToTransformer_1 = require("./dataSourceMapToTransformer");
const toGroovyFunctionCall_1 = require("./toGroovyFunctionCall");
exports.dataSourceMapToGroovy = (0, dataSourceMapToTransformer_1.dataSourceMapToTransformer)({ functionCall: toGroovyFunctionCall_1.toGroovyFunctionCall });
