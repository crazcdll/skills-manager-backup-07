"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.iterateNode = void 0;
function iterateNode(nodes, visitor) {
    if (!(nodes === null || nodes === void 0 ? void 0 : nodes.length))
        return;
    const helper = (list, parent, slotName) => {
        return list.some((node, index) => {
            const visitorResult = visitor({ node, index, parent, slotName });
            if (visitorResult) {
                if (visitorResult.continue)
                    return;
                if (visitorResult.break)
                    return true;
            }
            const slots = node.slots;
            if (!slots)
                return;
            return Object.keys(slots).some((slotName) => helper(slots[slotName], node, slotName));
        });
    };
    helper(nodes);
}
exports.iterateNode = iterateNode;
