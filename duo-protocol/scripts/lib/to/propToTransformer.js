"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.propToTransformer = void 0;
function propToTransformer(option) {
    const functionCall = option.functionCall;
    function handleProps(label, args, props) {
        const body = Object.keys(props).map((name) => {
            const propContent = handleProp(name, props[name]);
            return propContent;
        });
        return functionCall(label, args, { body });
    }
    function handleProp(name, prop) {
        const type = getPropType(prop);
        if (type !== 'objectWithSub') {
            const content = functionCall(type, [name], { expression: prop.data || '' });
            return content;
        }
        const content = handleProps(type, [name], prop.sub);
        return content;
    }
    function getPropType(prop) {
        if (prop.dataType === 'String')
            return 'string';
        if (prop.dataType === 'Number')
            return 'number';
        if (prop.dataType === 'Boolean')
            return 'bool';
        if (prop.dataType === 'List')
            return 'array';
        if (isEmptyObj(prop.sub))
            return 'object';
        return 'objectWithSub';
    }
    function isEmptyObj(obj) {
        return !obj || !Object.keys(obj).length;
    }
    return {
        propTo: handleProp,
        propsTo: handleProps,
    };
}
exports.propToTransformer = propToTransformer;
