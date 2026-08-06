import type { PageNode } from '@meishi/duo-protocol';
import type { PropScope } from './propFromTransformer';
export interface GlobalScope extends ListScope, NodeScope, EventScope, PropScope, PropConfigScope {
}
export interface ListScope {
    node(nodeName: string, materialId: string, body: (scope: NodeScope) => void): void;
    include(nodeName: `nodes/${string}.groovy`): void;
}
export interface NodeScope {
    label(label: string): void;
    nodeId(nodeId: string): void;
    nodeType(nodeType: PageNode['nodeType']): void;
    materialType(materialType: PageNode['materialType']): void;
    key(data: string): void;
    xIf(data: string): void;
    xFor(data: string): void;
    props(body: (scope: PropScope) => void): void;
    propConfig(propName: string, body: (scope: PropConfigScope) => void): void;
    style(styleName: string, body: (scope: PropScope) => void): void;
    on(eventName: string, body: (scope: EventScope) => void): void;
    buildConfig(body: (scope: AnyScope) => void): void;
    slot(slotName: string, body: (scope: ListScope) => void): void;
}
export interface EventScope {
    callMethod(notifyNodeName: string, notifyEventName: string): void;
    condition(data: string): void;
    lock(lock: boolean): void;
    props(body: (scope: PropScope) => void): void;
    transparentArg(from: string, to: string): void;
}
export interface PropConfigScope {
    updateBy(updateBy: string): void;
    isRequestArg(isRequestArg: boolean): void;
    lock(lock: boolean): void;
}
export interface AnyScope {
    [key: string]: (valueOrBody: string | number | boolean | null | ((scope: AnyScope) => void)) => void;
}
export interface StructFromTransformerOption {
    formatExpression?: boolean;
    handleSplit: (nodeName: `nodes/${string}.groovy`) => PageNode;
}
export declare function structFromTransformer(option: StructFromTransformerOption): (body: (s: ListScope) => void) => PageNode[];
