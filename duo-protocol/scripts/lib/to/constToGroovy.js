"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.constToGroovy = void 0;
const toGroovyFunctionCall_1 = require("./toGroovyFunctionCall");
const constToTransformer_1 = require("./constToTransformer");
exports.constToGroovy = (0, constToTransformer_1.constToTransformer)({ functionCall: toGroovyFunctionCall_1.toGroovyFunctionCall });
