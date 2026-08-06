import type { DataExpression } from '@meishi/duo-protocol';
export interface PropScope {
    string(propName: string, data: string): void;
    number(propName: string, data: string): void;
    bool(propName: string, data: string): void;
    array(propName: string, data: string): void;
    object(propName: string, data: string): void;
    objectWithSub(propName: string, body: (scope: PropScope) => void): void;
}
export interface FromTransformerOption {
    formatExpression?: boolean;
}
export declare function propFromTransformer(option?: FromTransformerOption): {
    createPropScope: (props: {
        [key: string]: DataExpression;
    }) => PropScope;
    createDataExpression: (dataType: DataExpression['dataType'], expression: string) => DataExpression;
};
