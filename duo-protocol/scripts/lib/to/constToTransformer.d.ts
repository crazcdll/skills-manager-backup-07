import { ToTransformerOption } from './type';
import { DataExpression } from '@meishi/duo-protocol/lib/page';
export declare function constToTransformer(option: ToTransformerOption): (constData?: {
    [key: string]: DataExpression;
} | undefined) => string;
