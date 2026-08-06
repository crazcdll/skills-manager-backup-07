"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.dataSourceMapToTransformer = void 0;
const propToTransformer_1 = require("./propToTransformer");
function dataSourceMapToTransformer(option) {
    const functionCall = option.functionCall;
    const { propsTo, propTo } = (0, propToTransformer_1.propToTransformer)(option);
    function dataSourceMapTo(dataSourceMap) {
        return Object.keys(dataSourceMap)
            .map((dataSourceId) => handleDataSource(dataSourceMap[dataSourceId], dataSourceId))
            .join('\n\n') + '\n';
    }
    function handleDataSource(dataSource, dataSourceId) {
        const body = [functionCall('dataSourceId', [dataSourceId])];
        if (dataSource.reqProps) {
            body.push(propsTo('requestProps', [], dataSource.reqProps));
        }
        if (dataSource.currentData) {
            body.push(propsTo('currentData', [], dataSource.currentData));
        }
        if (dataSource.bizRespStatus) {
            body.push(handleBizRespStatus(dataSource.bizRespStatus));
        }
        if (dataSource.submitBizRespStatus) {
            body.push(handleSubmitBizRespStatus(dataSource.submitBizRespStatus));
        }
        if (dataSource.checkBizRespStatus) {
            body.push(handleCheckBizRespStatus(dataSource.checkBizRespStatus));
        }
        // 添加空行
        const newBody = [body.join('\n\n')];
        return functionCall('dataSource', [], { body: newBody });
    }
    function handleBizRespStatus(bizRespStatus) {
        const body = [];
        if (bizRespStatus.isError) {
            body.push(propTo('isError', bizRespStatus.isError));
        }
        if (bizRespStatus.errorMsg) {
            body.push(propTo('errorMsg', bizRespStatus.errorMsg));
        }
        if (bizRespStatus.extra) {
            body.push(propTo('extra', bizRespStatus.extra));
        }
        if (bizRespStatus.errorToast != null) {
            body.push(functionCall('errorToast', [bizRespStatus.errorToast]));
        }
        if (bizRespStatus.errorNoReturnStruct != null) {
            body.push(functionCall('errorNoReturnStruct', [bizRespStatus.errorNoReturnStruct]));
        }
        return functionCall('bizRespStatus', [], { body });
    }
    function handleSubmitBizRespStatus(submitBizRespStatus) {
        const body = [];
        if (submitBizRespStatus.isError) {
            body.push(propTo('isError', submitBizRespStatus.isError));
        }
        if (submitBizRespStatus.errorMsg) {
            body.push(propTo('errorMsg', submitBizRespStatus.errorMsg));
        }
        if (submitBizRespStatus.extra) {
            body.push(propTo('extra', submitBizRespStatus.extra));
        }
        if (submitBizRespStatus.errorToast != null) {
            body.push(functionCall('errorToast', [submitBizRespStatus.errorToast]));
        }
        return functionCall('submitBizRespStatus', [], { body });
    }
    function handleCheckBizRespStatus(checkBizRespStatus) {
        const body = [];
        if (checkBizRespStatus.isError) {
            body.push(propTo('isError', checkBizRespStatus.isError));
        }
        if (checkBizRespStatus.errorMsg) {
            body.push(propTo('errorMsg', checkBizRespStatus.errorMsg));
        }
        if (checkBizRespStatus.extra) {
            body.push(propTo('extra', checkBizRespStatus.extra));
        }
        if (checkBizRespStatus.errorToast != null) {
            body.push(functionCall('errorToast', [checkBizRespStatus.errorToast]));
        }
        return functionCall('checkBizRespStatus', [], { body });
    }
    return dataSourceMapTo;
}
exports.dataSourceMapToTransformer = dataSourceMapToTransformer;
