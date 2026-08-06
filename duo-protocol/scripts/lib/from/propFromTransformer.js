"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.propFromTransformer = void 0;
const dedent_1 = require("../utils/dedent");
function propFromTransformer(option = {}) {
    function createPropScope(props) {
        const scope = {
            string(propName, data) {
                props[propName] = createDataExpression('String', data);
            },
            number(propName, data) {
                props[propName] = createDataExpression('Number', data);
            },
            bool(propName, data) {
                props[propName] = createDataExpression('Boolean', data);
            },
            array(propName, data) {
                props[propName] = createDataExpression('List', data);
            },
            object(propName, data) {
                props[propName] = createDataExpression('Object', data);
            },
            objectWithSub(propName, body) {
                const sub = {};
                props[propName] = { dataType: 'Object', __resolveType__: 'BACK_END', sub };
                const subPropScope = createPropScope(sub);
                body(subPropScope);
            },
        };
        return scope;
    }
    function createDataExpression(dataType, expression) {
        let data = expression;
        if (option.formatExpression) {
            data = data.includes('\n') ? (0, dedent_1.dedent)(data) : data.trim();
        }
        return { dataType, __resolveType__: 'BACK_END', data };
    }
    return { createPropScope, createDataExpression };
}
exports.propFromTransformer = propFromTransformer;
