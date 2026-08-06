import type { DataExpression } from '@meishi/duo-protocol';
import type { ToTransformerOption } from './type';
export declare function propToTransformer(option: ToTransformerOption): {
    propTo: (name: string, prop: DataExpression) => string;
    propsTo: (label: string, args: (string | boolean | number)[], props: {
        [key: string]: DataExpression;
    }) => string;
};
