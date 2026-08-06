import type { PageNode } from '@meishi/duo-protocol';
import type { ToTransformerOption } from './type';
export declare function structToTransformer(option: ToTransformerOption): (struct: PageNode[], forSplit: boolean) => string;
