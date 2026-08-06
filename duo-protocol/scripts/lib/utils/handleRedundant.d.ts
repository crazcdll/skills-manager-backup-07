import type { PageNode, PageProtocol } from '@meishi/duo-protocol';
export declare function removeProtocolRedundant(list?: PageNode[]): void;
export declare function attachProtocolRedundant(list: PageNode[] | undefined, componentsMap: PageProtocol['componentsMap']): void;
