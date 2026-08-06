"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.sortNodeProperty = void 0;
const iterateNode_1 = require("./iterateNode");
const sortProperty_1 = require("./sortProperty");
function sortNodeProperty(list) {
    (0, iterateNode_1.iterateNode)(list, ({ node }) => {
        var _a;
        (0, sortProperty_1.sortProperty)(node, [
            'materialId',
            'nodeId',
            'nodeType',
            'materialType',
            'resource',
            'slots',
        ]);
        (0, sortProperty_1.sortProperty)(node.resource, [
            'nodeName',
            'label',
            'advanced',
            'props',
            'propConfig',
            'styles',
            'events',
            'buildConfig',
        ]);
        if (node.resource.propConfig) {
            Object.values(node.resource.propConfig).forEach((propConfig) => {
                (0, sortProperty_1.sortProperty)(propConfig, ['updateBy', 'isRequestArg', 'lock']);
            });
        }
        (0, sortProperty_1.sortProperty)(node.resource.advanced, ['displayRule', 'iterateKey', 'items']);
        if ((_a = node.resource.events) === null || _a === void 0 ? void 0 : _a.emit) {
            Object.values(node.resource.events.emit).forEach((events) => {
                events.forEach((event) => {
                    (0, sortProperty_1.sortProperty)(event, [
                        'notifyNodeName',
                        'notifyEventName',
                        'lock',
                        'props',
                        'transparentArg',
                    ]);
                });
            });
        }
        // 后端返回的 slots 顺序不稳定，需要排序
        if (node.slots) {
            // 已知的 slot 顺序
            const slotKeys = [
                'renderModuleNodes',
                'renderTopChildren',
                'renderTop',
                'renderContent',
                'renderBottom',
                'renderBackground',
                'renderLeft',
                'renderRight',
            ];
            // 其他 slot 按 alphabet 排序
            Object.keys(node.slots).sort().forEach((slotKey) => {
                // 这里会有2次遍历，没关系
                if (!slotKeys.includes(slotKey)) {
                    slotKeys.push(slotKey);
                }
            });
            (0, sortProperty_1.sortProperty)(node.slots, slotKeys);
        }
    });
    return list;
}
exports.sortNodeProperty = sortNodeProperty;
