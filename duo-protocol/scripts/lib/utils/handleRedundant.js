"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.attachProtocolRedundant = exports.removeProtocolRedundant = void 0;
const iterateNode_1 = require("./iterateNode");
function removeProtocolRedundant(list) {
    (0, iterateNode_1.iterateNode)(list, ({ node }) => {
        delete node.nodeId;
        if (node.nodeType !== 'LIST_CONTAINER') {
            // @ts-ignore
            delete node.nodeType;
        }
        delete node.materialType;
    });
}
exports.removeProtocolRedundant = removeProtocolRedundant;
function attachProtocolRedundant(list, componentsMap) {
    (0, iterateNode_1.iterateNode)(list, ({ node }) => {
        const component = componentsMap[node.materialId];
        if (!node.nodeType) {
            node.nodeType = component.type === 'logic' ? 'HANDLER_MODULE' : 'NORMAL_MODULE';
        }
        node.materialType = component.materialType;
    });
}
exports.attachProtocolRedundant = attachProtocolRedundant;
