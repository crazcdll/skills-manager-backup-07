import type { Token } from './tokenize';
export type AstNodeType = 'Literal' | 'Identifier' | 'Function' | 'FunctionCall' | 'Expression' | 'Block';
export interface AstNodeBase {
    type: AstNodeType;
}
export type AstNode = LiteralNode | IdentifierNode | FunctionNode | FunctionCallNode | ExpressionNode | BlockNode;
export interface LiteralNode extends AstNodeBase {
    type: 'Literal';
    value: any;
}
export interface IdentifierNode extends AstNodeBase {
    type: 'Identifier';
    value: string;
}
export interface FunctionNode extends AstNodeBase {
    type: 'Function';
    body: AstNode[];
}
export interface FunctionCallNode extends AstNodeBase {
    type: 'FunctionCall';
    func: IdentifierNode;
    args: AstNode[];
}
export interface ExpressionNode extends AstNodeBase {
    type: 'Expression';
    value: string;
}
export interface BlockNode extends AstNodeBase {
    type: 'Block';
    body: AstNode[];
}
export declare function parse(tokens: Token[]): BlockNode;
