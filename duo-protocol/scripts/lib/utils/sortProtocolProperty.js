"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.sortProtocolProperty = void 0;
const sortProperty_1 = require("./sortProperty");
const sortNodeProperty_1 = require("./sortNodeProperty");
function sortProtocolProperty(protocol) {
    (0, sortProperty_1.sortProperty)(protocol, [
        'duoVersion',
        'pageId',
        'pageProtocolId',
        'pageProtocolVersion',
        'pageBuildConfig',
        'dependencies',
        'ohDependencies',
        'componentsMap',
        'dynamicDataConfig',
        'struct',
        'logics',
    ]);
    (0, sortProperty_1.sortProperty)(protocol.dynamicDataConfig, ['constData', 'dataSourceMap']);
    (0, sortNodeProperty_1.sortNodeProperty)(protocol.struct);
    (0, sortNodeProperty_1.sortNodeProperty)(protocol.logics);
    return protocol;
}
exports.sortProtocolProperty = sortProtocolProperty;
