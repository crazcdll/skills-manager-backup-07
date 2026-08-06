"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.structFromGroovy = void 0;
const structFromTransformer_1 = require("./structFromTransformer");
const fromGroovy_1 = require("../groovy/fromGroovy");
function structFromGroovy(data, splitNodeMap = {}) {
    const structFrom = (0, structFromTransformer_1.structFromTransformer)({
        handleSplit(file) {
            var _a;
            const nodeData = splitNodeMap[file];
            if (!nodeData) {
                throw new Error(`找不到文件 ${file}`);
            }
            const nodes = (0, fromGroovy_1.fromGroovy)(nodeData, structFrom);
            if (nodes.length !== 1) {
                throw new Error(`节点解析错误，一个文件中只能有一个节点`);
            }
            const node = nodes[0];
            if (!((_a = node.resource.buildConfig) === null || _a === void 0 ? void 0 : _a.splitFile)) {
                node.resource.buildConfig = node.resource.buildConfig || {};
                node.resource.buildConfig.splitFile = true;
            }
            return node;
        },
    });
    return (0, fromGroovy_1.fromGroovy)(data, structFrom);
}
exports.structFromGroovy = structFromGroovy;
