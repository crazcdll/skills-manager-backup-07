"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.dataSourceMapFromTransformer = void 0;
const propFromTransformer_1 = require("./propFromTransformer");
function dataSourceMapFromTransformer(option = {}) {
    const { createPropScope } = (0, propFromTransformer_1.propFromTransformer)(option);
    function createDataSourceMapScope(dataSourceMap) {
        const scope = {
            dataSource(body) {
                const dataSourceScope = createDataSourceScope(dataSourceMap);
                body(dataSourceScope);
            },
        };
        return scope;
    }
    function createDataSourceScope(dataSourceMap) {
        const dataSource = {};
        const scope = {
            dataSourceId(dataSourceId) {
                dataSourceMap[dataSourceId] = dataSource;
            },
            requestProps(body) {
                dataSource.reqProps = {};
                const propScope = createPropScope(dataSource.reqProps);
                body(propScope);
            },
            currentData(body) {
                dataSource.currentData = {};
                const propScope = createPropScope(dataSource.currentData);
                body(propScope);
            },
            bizRespStatus(body) {
                dataSource.bizRespStatus = {};
                const bizRespStatusScope = createBizRespStatusScope(dataSource.bizRespStatus);
                body(bizRespStatusScope);
            },
            submitBizRespStatus(body) {
                dataSource.submitBizRespStatus = {};
                const submitBizRespStatusScope = createSubmitBizRespStatusScope(dataSource.submitBizRespStatus);
                body(submitBizRespStatusScope);
            },
            checkBizRespStatus(body) {
                dataSource.checkBizRespStatus = {};
                const checkBizRespStatusScope = createCheckBizRespStatusScope(dataSource.checkBizRespStatus);
                body(checkBizRespStatusScope);
            },
        };
        return scope;
    }
    function createBizRespStatusScope(props) {
        const scope = Object.assign(Object.assign({}, createPropScope(props)), { errorToast(errorToast) {
                props.errorToast = errorToast;
            },
            errorNoReturnStruct(errorNoReturnStruct) {
                props.errorNoReturnStruct = errorNoReturnStruct;
            } });
        return scope;
    }
    function createSubmitBizRespStatusScope(props) {
        const scope = Object.assign(Object.assign({}, createPropScope(props)), { errorToast(errorToast) {
                props.errorToast = errorToast;
            } });
        return scope;
    }
    function createCheckBizRespStatusScope(props) {
        const scope = Object.assign(Object.assign({}, createPropScope(props)), { errorToast(errorToast) {
                props.errorToast = errorToast;
            } });
        return scope;
    }
    function dataSourceMapFrom(body) {
        const dataSourceMap = {};
        const dataSourceMapScope = createDataSourceMapScope(dataSourceMap);
        body(dataSourceMapScope);
        return dataSourceMap;
    }
    return dataSourceMapFrom;
}
exports.dataSourceMapFromTransformer = dataSourceMapFromTransformer;
