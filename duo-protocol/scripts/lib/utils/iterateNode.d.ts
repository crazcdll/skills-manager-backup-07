import type { PageNode } from '@meishi/duo-protocol';
export interface IterateNodeVisitorResult {
    break?: boolean;
    continue?: boolean;
}
export interface IterateNodeVisitorInfo {
    node: PageNode;
    index: number;
    parent?: PageNode;
    slotName?: string;
}
export interface IterateNodeVisitor {
    (info: IterateNodeVisitorInfo): IterateNodeVisitorResult | undefined | void | null;
}
export declare function iterateNode(nodes: PageNode[] | undefined, visitor: IterateNodeVisitor): void;
