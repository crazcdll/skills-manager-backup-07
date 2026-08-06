"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.constToTransformer = void 0;
const propToTransformer_1 = require("./propToTransformer");
function constToTransformer(option) {
    const { propsTo } = (0, propToTransformer_1.propToTransformer)(option);
    function constTo(constData) {
        return propsTo('constant', [], constData || {}) + '\n';
    }
    return constTo;
}
exports.constToTransformer = constToTransformer;
