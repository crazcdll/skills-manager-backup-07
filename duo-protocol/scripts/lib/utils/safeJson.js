"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.safeJson = void 0;
function safeJson(str) {
    if (!str)
        return;
    try {
        return JSON.parse(str);
    }
    catch (e) {
        return;
    }
}
exports.safeJson = safeJson;
