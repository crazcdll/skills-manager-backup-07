"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.fromGroovy = exports.handleSplit = exports.toGroovy = void 0;
const safeJson_1 = require("./utils/safeJson");
const iterateNode_1 = require("./utils/iterateNode");
const handleRedundant_1 = require("./utils/handleRedundant");
const sortProtocolProperty_1 = require("./utils/sortProtocolProperty");
const setNodeDefault_1 = require("./utils/setNodeDefault");
const constToGroovy_1 = require("./to/constToGroovy");
const dataSourceMapToGroovy_1 = require("./to/dataSourceMapToGroovy");
const structToGroovy_1 = require("./to/structToGroovy");
const constFromGroovy_1 = require("./from/constFromGroovy");
const dataSourceMapFromGroovy_1 = require("./from/dataSourceMapFromGroovy");
const structFromGroovy_1 = require("./from/structFromGroovy");
function toGroovy(opts) {
    var _a, _b;
    // 深拷贝。方便字段排序、删除冗余字段
    const protocol = JSON.parse(JSON.stringify(opts.protocol));
    (0, sortProtocolProperty_1.sortProtocolProperty)(protocol);
    (0, iterateNode_1.iterateNode)(protocol.struct, ({ node }) => { delete node.nodeId; });
    (0, iterateNode_1.iterateNode)(protocol.logics, ({ node }) => { delete node.nodeId; });
    (0, handleRedundant_1.removeProtocolRedundant)(protocol.struct);
    (0, handleRedundant_1.removeProtocolRedundant)(protocol.logics);
    const buildConfig = protocol.pageBuildConfig || {};
    const firstScreenModulePaths = (_a = buildConfig.commonParams.modulesLoadConfig) === null || _a === void 0 ? void 0 : _a.firstScreenModulePaths;
    const buildFunction = buildConfig.commonParams.buildFunction;
    const mrnConfigFunction = buildConfig.commonParams.mrnConfigFunction;
    const dependencies = JSON.stringify(protocol.dependencies || [], null, 2) + '\n';
    const ohDependencies = ((_b = protocol.ohDependencies) === null || _b === void 0 ? void 0 : _b.length)
        ? (JSON.stringify(protocol.ohDependencies, null, 2) + '\n')
        : undefined;
    const componentsMap = JSON.stringify(protocol.componentsMap || {}, null, 2) + '\n';
    const pageBuildConfig = JSON.stringify(Object.assign(Object.assign({}, buildConfig), { commonParams: Object.assign(Object.assign({}, buildConfig.commonParams), { modulesLoadConfig: Object.assign(Object.assign({}, buildConfig.commonParams.modulesLoadConfig), { firstScreenModulePaths: undefined }), buildFunction: undefined, mrnConfigFunction: undefined }) }), null, 2) + '\n';
    const constData = (0, constToGroovy_1.constToGroovy)(protocol.dynamicDataConfig.constData);
    const dataSourceMap = (0, dataSourceMapToGroovy_1.dataSourceMapToGroovy)(protocol.dynamicDataConfig.dataSourceMap);
    const struct = (0, structToGroovy_1.structToGroovy)(protocol.struct || [], false);
    const logics = (0, structToGroovy_1.structToGroovy)(protocol.logics || [], false);
    const splitNodes = handleSplit(protocol.struct || []);
    const result = Object.assign({ 'dependencies.json': dependencies, 'ohDependencies.json': ohDependencies, 'componentsMap.json': componentsMap, 'pageBuildConfig.json': pageBuildConfig, 'scripts/firstScreenModulePaths.json': formatJson(firstScreenModulePaths), 'scripts/buildCustom.js': buildFunction, 'scripts/mrnConfigCustom.js': mrnConfigFunction, 'constData.groovy': constData, 'dataSourceMap.groovy': dataSourceMap, 'struct.groovy': struct, 'logics.groovy': logics }, splitNodes);
    return result;
}
exports.toGroovy = toGroovy;
function handleSplit(struct) {
    const splitNodes = {};
    (0, iterateNode_1.iterateNode)(struct, ({ node }) => {
        var _a;
        if ((_a = node.resource.buildConfig) === null || _a === void 0 ? void 0 : _a.splitFile) {
            const fileName = `nodes/${node.resource.nodeName}.groovy`;
            splitNodes[fileName] = (0, structToGroovy_1.structToGroovy)([node], true);
        }
    });
    return splitNodes;
}
exports.handleSplit = handleSplit;
function formatJson(json) {
    if (!json)
        return json;
    try {
        return JSON.stringify(JSON.parse(json), null, 2) + '\n';
    }
    catch (e) {
        return json;
    }
}
function fromGroovy(opts) {
    const { groovyProtocol, pageId, pageProtocolId, pageProtocolVersion, } = opts;
    const dependencies = (0, safeJson_1.safeJson)(groovyProtocol['dependencies.json']);
    const ohDependencies = (0, safeJson_1.safeJson)(groovyProtocol['ohDependencies.json']);
    const componentsMap = (0, safeJson_1.safeJson)(groovyProtocol['componentsMap.json']);
    const pageBuildConfig = (0, safeJson_1.safeJson)(groovyProtocol['pageBuildConfig.json']);
    const constData = (0, constFromGroovy_1.constFromGroovy)(groovyProtocol['constData.groovy']);
    const dataSourceMap = (0, dataSourceMapFromGroovy_1.dataSourceMapFromGroovy)(groovyProtocol['dataSourceMap.groovy']);
    const struct = (0, structFromGroovy_1.structFromGroovy)(groovyProtocol['struct.groovy'], groovyProtocol);
    const logics = (0, structFromGroovy_1.structFromGroovy)(groovyProtocol['logics.groovy']);
    const firstScreenModulePaths = groovyProtocol['scripts/firstScreenModulePaths.json'];
    const buildCustom = groovyProtocol['scripts/buildCustom.js'];
    const mrnConfigCustom = groovyProtocol['scripts/mrnConfigCustom.js'];
    if (firstScreenModulePaths) {
        pageBuildConfig.commonParams.modulesLoadConfig = pageBuildConfig.commonParams.modulesLoadConfig || {};
        pageBuildConfig.commonParams.modulesLoadConfig.firstScreenModulePaths = firstScreenModulePaths;
    }
    if (buildCustom) {
        pageBuildConfig.commonParams.buildFunction = buildCustom;
    }
    if (mrnConfigCustom) {
        pageBuildConfig.commonParams.mrnConfigFunction = mrnConfigCustom;
    }
    (0, handleRedundant_1.attachProtocolRedundant)(struct, componentsMap);
    (0, handleRedundant_1.attachProtocolRedundant)(logics, componentsMap);
    (0, setNodeDefault_1.setNodeDefault)(struct);
    (0, setNodeDefault_1.setNodeDefault)(logics);
    const result = {
        duoVersion: '2',
        pageId,
        pageProtocolId,
        pageProtocolVersion,
        dependencies,
        ohDependencies,
        componentsMap,
        pageBuildConfig,
        dynamicDataConfig: {
            constData,
            dataSourceMap,
        },
        struct,
        logics,
    };
    (0, sortProtocolProperty_1.sortProtocolProperty)(result);
    return result;
}
exports.fromGroovy = fromGroovy;
