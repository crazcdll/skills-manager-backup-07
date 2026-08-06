"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.constFromTransformer = void 0;
const propFromTransformer_1 = require("./propFromTransformer");
function constFromTransformer(option = {}) {
    const { createPropScope } = (0, propFromTransformer_1.propFromTransformer)(option);
    function createConstDataScope(constData) {
        const scope = {
            constant(body) {
                const propScope = createPropScope(constData);
                body(propScope);
            },
        };
        return scope;
    }
    function constDataFrom(body) {
        const constData = {};
        const constDataScope = createConstDataScope(constData);
        body(constDataScope);
        return constData;
    }
    return constDataFrom;
}
exports.constFromTransformer = constFromTransformer;
