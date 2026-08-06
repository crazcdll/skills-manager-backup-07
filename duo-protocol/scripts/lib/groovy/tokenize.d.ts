export interface Token {
    s: number;
    e: number;
    type: TokenType;
    value: string | number | boolean | null;
}
export type TokenType = 'identifier' | 'literal' | 'expression' | 'comma' | 'openParen' | 'closeParen' | 'openCurly' | 'closeCurly';
export declare function tokenize(expr: string): Token[];
