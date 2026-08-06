"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.structFromTransformer = void 0;
const propFromTransformer_1 = require("./propFromTransformer");
function structFromTransformer(option) {
    const { handleSplit } = option;
    const { createPropScope, createDataExpression, } = (0, propFromTransformer_1.propFromTransformer)(option);
    function createListScope(list) {
        const scope = {
            node(nodeName, materialId, body) {
                const node = { materialId, resource: { nodeName } };
                list.push(node);
                const nodeScope = createNodeScope(node);
                body(nodeScope);
            },
            include(nodeName) {
                const node = handleSplit(nodeName);
                list.push(node);
            },
        };
        return scope;
    }
    function createNodeScope(node) {
        const scope = {
            label(label) {
                node.resource.label = label;
            },
            nodeId(nodeId) {
                node.nodeId = nodeId;
            },
            nodeType(nodeType) {
                node.nodeType = nodeType;
            },
            materialType(materialType) {
                node.materialType = materialType;
            },
            key(data) {
                if (!node.resource.advanced)
                    node.resource.advanced = {};
                node.resource.advanced.iterateKey = createDataExpression('String', data);
            },
            xIf(data) {
                if (!node.resource.advanced)
                    node.resource.advanced = {};
                node.resource.advanced.displayRule = createDataExpression('Boolean', data);
            },
            xFor(data) {
                if (!node.resource.advanced)
                    node.resource.advanced = {};
                node.resource.advanced.items = createDataExpression('List', data);
            },
            props(body) {
                node.resource.props = {};
                const propScope = createPropScope(node.resource.props);
                body(propScope);
            },
            propConfig(propName, body) {
                if (!node.resource.propConfig)
                    node.resource.propConfig = {};
                const propConfig = {};
                node.resource.propConfig[propName] = propConfig;
                const propConfigScope = createPropConfigScope(propConfig);
                body(propConfigScope);
            },
            style(styleName, body) {
                if (!node.resource.styles)
                    node.resource.styles = {};
                const sub = {};
                node.resource.styles[styleName] = {
                    dataType: 'Object',
                    __resolveType__: 'BACK_END',
                    sub,
                };
                const subPropScope = createPropScope(sub);
                body(subPropScope);
            },
            on(eventName, body) {
                if (!node.resource.events)
                    node.resource.events = {};
                if (!node.resource.events.emit)
                    node.resource.events.emit = {};
                if (!node.resource.events.emit[eventName])
                    node.resource.events.emit[eventName] = [];
                const event = {};
                node.resource.events.emit[eventName].push(event);
                const eventScope = createEventScope(event);
                body(eventScope);
            },
            buildConfig(body) {
                const buildConfig = {};
                node.resource.buildConfig = buildConfig;
                const anyScope = createAnyScope(buildConfig);
                body(anyScope);
            },
            slot(slotName, body) {
                if (!node.slots)
                    node.slots = {};
                const slot = [];
                node.slots[slotName] = slot;
                const listScope = createListScope(slot);
                body(listScope);
            },
        };
        return scope;
    }
    function createPropConfigScope(propConfig) {
        const scope = {
            updateBy(updateBy) {
                propConfig.updateBy = updateBy;
            },
            isRequestArg(isRequestArg) {
                propConfig.isRequestArg = isRequestArg;
            },
            lock(lock) {
                propConfig.lock = lock;
            },
        };
        return scope;
    }
    function createEventScope(event) {
        const scope = {
            callMethod(notifyNodeName, notifyEventName) {
                event.notifyNodeName = notifyNodeName;
                event.notifyEventName = notifyEventName;
            },
            condition(data) {
                event.emitCondition = createDataExpression('Boolean', data);
            },
            lock(lock) {
                event.lock = lock;
            },
            props(body) {
                event.props = {};
                const eventPropScope = createPropScope(event.props);
                body(eventPropScope);
            },
            transparentArg(from, to) {
                if (!event.transparentArg)
                    event.transparentArg = [];
                event.transparentArg.push({ from, to });
            },
        };
        return scope;
    }
    function createAnyScope(obj) {
        return new Proxy(obj, {
            get(target, p) {
                const isArrayItem = p === 'array_item';
                if (isArrayItem && !Array.isArray(target)) {
                    target.__array = target.__array || [];
                }
                const func = (valueOrBody) => {
                    let value = typeof valueOrBody === 'function' ? {} : valueOrBody;
                    if (typeof valueOrBody === 'function') {
                        const anyScope = createAnyScope(value);
                        valueOrBody(anyScope);
                        if (value && value.__array) {
                            value = value.__array;
                        }
                    }
                    if (isArrayItem) {
                        if (Array.isArray(target)) {
                            target.push(value);
                        }
                        else {
                            target.__array.push(value);
                        }
                    }
                    else {
                        target[p] = value;
                    }
                };
                return func;
            }
        });
    }
    function structFrom(body) {
        const list = [];
        const listScope = createListScope(list);
        body(listScope);
        return list;
    }
    return structFrom;
}
exports.structFromTransformer = structFromTransformer;
