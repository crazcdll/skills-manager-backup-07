import type { DataSourceConfig } from '@meishi/duo-protocol';
import type { PropScope } from './propFromTransformer';
export interface DataSourceMapScope {
    dataSource(body: (scope: DataSourceScope) => void): void;
}
export interface DataSourceScope {
    dataSourceId(dataSourceId: string): void;
    requestProps(body: (scope: PropScope) => void): void;
    currentData(body: (scope: PropScope) => void): void;
    bizRespStatus(body: (scope: BizRespStatusScope) => void): void;
    submitBizRespStatus(body: (scope: SubmitBizRespStatusScope) => void): void;
    checkBizRespStatus(body: (scope: CheckBizRespStatusScope) => void): void;
}
export interface BizRespStatusScope extends PropScope {
    errorToast(errorToast: boolean): void;
    errorNoReturnStruct(errorNoReturnStruct: boolean): void;
}
export interface SubmitBizRespStatusScope extends PropScope {
    errorToast(errorToast: boolean): void;
}
export interface CheckBizRespStatusScope extends PropScope {
    errorToast(errorToast: boolean): void;
}
export interface FromTransformerOption {
    formatExpression?: boolean;
}
export declare function dataSourceMapFromTransformer(option?: FromTransformerOption): (body: (scope: DataSourceMapScope) => void) => {
    [key: string]: DataSourceConfig;
};
