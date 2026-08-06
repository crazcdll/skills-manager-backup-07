import type { PageNode } from '@meishi/duo-protocol';
export interface SplitNodeMap {
    [key: `nodes/${string}.groovy`]: string | undefined;
}
export declare function structFromGroovy(data: string, splitNodeMap?: SplitNodeMap): PageNode[];
