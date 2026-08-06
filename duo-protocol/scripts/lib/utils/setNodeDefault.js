"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.setNodeDefault = void 0;
const iterateNode_1 = require("./iterateNode");
function setNodeDefault(list) {
    (0, iterateNode_1.iterateNode)(list, ({ node }) => {
        if (!node.resource.events)
            node.resource.events = {};
        if (node.nodeType === 'LIST_CONTAINER')
            return;
        if (node.nodeType === 'NORMAL_MODULE') {
            if (!node.resource.props)
                node.resource.props = {};
            if (!node.resource.styles)
                node.resource.styles = {};
            if (!node.resource.advanced)
                node.resource.advanced = {};
        }
        if (node.resource.events.emit) {
            Object.values(node.resource.events.emit).forEach((events) => {
                events.forEach((event) => {
                    if (!event.props)
                        event.props = {};
                    if (!event.transparentArg)
                        event.transparentArg = [];
                    if (event.lock == null)
                        event.lock = false;
                });
            });
        }
    });
    return list;
}
exports.setNodeDefault = setNodeDefault;
