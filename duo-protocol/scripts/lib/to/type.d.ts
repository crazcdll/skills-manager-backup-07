export interface ToTransformerOption {
    functionCall(name: string, args: (string | boolean | number)[], extra?: {
        body?: string[];
        expression?: string;
    }): string;
}
