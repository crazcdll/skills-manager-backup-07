import type { DataExpression } from '@meishi/duo-protocol';
import type { PropScope } from './propFromTransformer';
export interface ConstDataScope {
    constant(body: (scope: PropScope) => void): void;
}
export interface FromTransformerOption {
    formatExpression?: boolean;
}
export declare function constFromTransformer(option?: FromTransformerOption): (body: (s: ConstDataScope) => void) => {
    [key: string]: DataExpression;
};
