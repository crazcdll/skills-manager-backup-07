import { DataSourceConfig } from '@meishi/duo-protocol';
import { ToTransformerOption } from './type';
export declare function dataSourceMapToTransformer(option: ToTransformerOption): (dataSourceMap: {
    [key: string]: DataSourceConfig;
}) => string;
