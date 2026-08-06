"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.sortProperty = void 0;
function sortProperty(data, props) {
    if (!data)
        return;
    props.forEach((key) => {
        if (data[key] !== undefined) {
            const value = data[key];
            delete data[key];
            data[key] = value;
        }
    });
}
exports.sortProperty = sortProperty;
