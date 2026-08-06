"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.structToGroovy = void 0;
const structToTransformer_1 = require("./structToTransformer");
const toGroovyFunctionCall_1 = require("./toGroovyFunctionCall");
exports.structToGroovy = (0, structToTransformer_1.structToTransformer)({ functionCall: toGroovyFunctionCall_1.toGroovyFunctionCall });
