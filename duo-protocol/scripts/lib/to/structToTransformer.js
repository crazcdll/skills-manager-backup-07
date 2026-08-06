"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.structToTransformer = void 0;
const propToTransformer_1 = require("./propToTransformer");
function structToTransformer(option) {
    const functionCall = option.functionCall;
    const { propsTo } = (0, propToTransformer_1.propToTransformer)(option);
    function structTo(struct, forSplit) {
        return struct.map((node) => handleNode(node, forSplit)).join('\n\n') + '\n';
    }
    function handleNode(node, forSplit) {
        var _a, _b, _c, _d, _e;
        const resource = node.resource;
        const advanced = resource.advanced;
        if (!forSplit && ((_a = resource.buildConfig) === null || _a === void 0 ? void 0 : _a.splitFile)) {
            return functionCall('include', [`nodes/${resource.nodeName}.groovy`]);
        }
        const body = [functionCall('label', [resource.label])];
        if (node.nodeId) {
            body.push(functionCall('nodeId', [node.nodeId]));
        }
        if (node.nodeType) {
            body.push(functionCall('nodeType', [node.nodeType]));
        }
        if (node.materialType) {
            body.push(functionCall('materialType', [node.materialType]));
        }
        if (((_b = advanced === null || advanced === void 0 ? void 0 : advanced.iterateKey) === null || _b === void 0 ? void 0 : _b.data) != null) {
            body.push(functionCall('key', [], { expression: advanced.iterateKey.data || '' }));
        }
        if (((_c = advanced === null || advanced === void 0 ? void 0 : advanced.displayRule) === null || _c === void 0 ? void 0 : _c.data) != null) {
            body.push(functionCall('xIf', [], { expression: advanced.displayRule.data || '' }));
        }
        if (((_d = advanced === null || advanced === void 0 ? void 0 : advanced.items) === null || _d === void 0 ? void 0 : _d.data) != null) {
            body.push(functionCall('xFor', [], { expression: advanced.items.data || '' }));
        }
        if (!isEmptyObj(resource.props)) {
            body.push(propsTo('props', [], resource.props));
        }
        if (!isEmptyObj(resource.propConfig)) {
            body.push(...handlePropConfigs(resource.propConfig));
        }
        if (!isEmptyObj(resource.styles)) {
            body.push(...handleStyles(resource.styles));
        }
        if (!isEmptyObj((_e = resource.events) === null || _e === void 0 ? void 0 : _e.emit)) {
            body.push(...handleEvents(resource.events.emit));
        }
        if (!isEmptyObj(resource.buildConfig)) {
            body.push(handleAny('buildConfig', resource.buildConfig));
        }
        if (!isEmptyObj(node.slots)) {
            body.push(...handleSlots(node.slots));
        }
        return functionCall('node', [resource.nodeName, node.materialId], { body });
    }
    function handleStyles(styles) {
        const result = Object.keys(styles).map((name) => {
            const styleContent = propsTo('style', [name], styles[name].sub);
            return styleContent;
        });
        return result;
    }
    function handlePropConfigs(propConfigs) {
        const result = Object.keys(propConfigs).map((name) => {
            const styleContent = handlePropConfig(name, propConfigs[name]);
            return styleContent;
        });
        return result;
    }
    function handlePropConfig(name, propConfig) {
        const body = [];
        if (propConfig.updateBy) {
            body.push(functionCall('updateBy', [propConfig.updateBy]));
        }
        if (propConfig.isRequestArg != null) {
            body.push(functionCall('isRequestArg', [propConfig.isRequestArg]));
        }
        if (propConfig.lock != null) {
            body.push(functionCall('lock', [propConfig.lock]));
        }
        return functionCall('propConfig', [name], { body });
    }
    function handleEvents(events) {
        const result = [];
        Object.keys(events).forEach((name) => {
            const content = events[name].map((event) => handleEvent(name, event));
            result.push(...content);
        });
        return result;
    }
    function handleEvent(name, event) {
        var _a;
        const body = [
            functionCall('callMethod', [event.notifyNodeName, event.notifyEventName]),
        ];
        if (!isEmptyObj(event.emitCondition)) {
            body.push(functionCall('condition', [], { expression: event.emitCondition.data || '' }));
        }
        if (event.lock) { // 默认为 false
            body.push(functionCall('lock', [event.lock]));
        }
        if (!isEmptyObj(event.props)) {
            body.push(propsTo('props', [], event.props));
        }
        if ((_a = event.transparentArg) === null || _a === void 0 ? void 0 : _a.length) {
            const transparentArg = event.transparentArg.map((item) => {
                return functionCall('transparentArg', [item.from, item.to]);
            });
            body.push(...transparentArg);
        }
        return functionCall('on', [name], { body });
    }
    function handleSlots(slots) {
        const result = Object.keys(slots).map((name) => {
            const body = slots[name].map((node) => handleNode(node, false));
            const slotContent = functionCall('slot', [name], { body });
            return slotContent;
        });
        return result;
    }
    function handleAny(name, value) {
        if (!value || typeof value !== 'object') {
            return functionCall(name, [value]);
        }
        // array 当对象处理吧
        const isArr = Array.isArray(value);
        const body = Object.keys(value).map((key) => {
            return handleAny(isArr ? 'array_item' : key, value[key]);
        });
        return functionCall(name, [], { body });
    }
    function isEmptyObj(obj) {
        return !obj || !Object.keys(obj).length;
    }
    return structTo;
}
exports.structToTransformer = structToTransformer;
