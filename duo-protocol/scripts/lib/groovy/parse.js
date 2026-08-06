"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.parse = void 0;
function tokenFuncCallName(token, instance) {
    instance.push({
        type: 'FunctionCall',
        func: {
            type: 'Identifier',
            value: token.value
        },
        args: [],
    });
}
function tokenFuncCallLiteralArg(token, instance) {
    instance.get().args.push({
        type: 'Literal',
        value: token.value,
    });
}
function tokenFuncCallExpressionArg(token, instance) {
    instance.get().args.push({
        type: 'Expression',
        value: token.value,
    });
}
function astSub(subAst, instance) {
    instance.get().args.push({
        type: 'Function',
        body: subAst.body,
    });
}
const states = {
    expectFuncName: {
        stateToMap: {
            identifier: { toState: 'afterFuncName', handler: tokenFuncCallName },
        },
        completable: true,
    },
    afterFuncName: {
        stateToMap: {
            openParen: { toState: 'expectFuncArg' },
            literal: { toState: 'expectFuncName', handler: tokenFuncCallLiteralArg },
            openCurly: {
                type: 'ast',
                subHandler: astSub,
                endToken: { closeCurly: 'expectFuncName' },
            },
            expression: { toState: 'expectFuncName', handler: tokenFuncCallExpressionArg },
        },
    },
    expectFuncArg: {
        stateToMap: {
            literal: { toState: 'afterFuncArg', handler: tokenFuncCallLiteralArg },
        },
    },
    afterFuncArg: {
        stateToMap: {
            comma: { toState: 'expectFuncArg' },
            closeParen: { toState: 'afterFuncCloseParen' },
        },
    },
    afterFuncCloseParen: {
        stateToMap: {
            identifier: { toState: 'afterFuncName', handler: tokenFuncCallName },
            expression: { toState: 'expectFuncName', handler: tokenFuncCallExpressionArg },
            openCurly: {
                type: 'ast',
                subHandler: astSub,
                endToken: { closeCurly: 'expectFuncName' },
            },
        },
        completable: true,
    },
};
function parse(tokens) {
    const root = { type: 'Block', body: [] };
    const stack = [];
    let currentBlock = root;
    const instance = {
        push(ast) {
            currentBlock.body.push(ast);
        },
        get() {
            return currentBlock.body[currentBlock.body.length - 1];
        },
    };
    let stateType = 'expectFuncName';
    let i = 0;
    const len = tokens.length;
    let state;
    while (i < len) {
        state = states[stateType];
        const token = tokens[i];
        const stateTo = state.stateToMap[token.type];
        if (!stateTo) {
            const parent = stack[stack.length - 1];
            if (parent === null || parent === void 0 ? void 0 : parent.stateTo.endToken[token.type]) {
                stack.pop();
                const subAst = currentBlock;
                currentBlock = parent.block;
                parent.stateTo.subHandler(subAst, instance);
                i += 1;
                continue;
            }
            throw new Error(`Unexpected token ${JSON.stringify(token.value)} at ${token.s}`);
        }
        if (stateTo.type === 'ast') {
            stack.push({ block: currentBlock, stateTo });
            currentBlock = { type: 'Block', body: [] };
            stateType = 'expectFuncName';
        }
        else {
            if (stateTo.handler)
                stateTo.handler(token, instance);
            stateType = stateTo.toState;
        }
        i += 1;
    }
    state = states[stateType];
    if (stack.length || !state.completable) {
        const endToken = tokens[tokens.length - 1];
        throw new Error(`Unexpected end ${JSON.stringify(endToken.value)} at ${endToken.e}`);
    }
    return root;
}
exports.parse = parse;
