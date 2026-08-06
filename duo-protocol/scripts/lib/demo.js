"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const tslib_1 = require("tslib");
const fs = require("fs-extra");
const path = require("path");
const demoPath_1 = require("./demoPath");
const transformer_1 = require("./transformer");
const sortProtocolProperty_1 = require("./utils/sortProtocolProperty");
const iterateNode_1 = require("./utils/iterateNode");
function demo() {
    return tslib_1.__awaiter(this, void 0, void 0, function* () {
        const originalProtocol = yield fs.readJSON(path.join(demoPath_1.DEMO_PATH, './protocol.json'));
        // 删除 nodeId
        (0, iterateNode_1.iterateNode)(originalProtocol.struct, ({ node }) => { delete node.nodeId; });
        (0, iterateNode_1.iterateNode)(originalProtocol.logics, ({ node }) => { delete node.nodeId; });
        // 字段排序
        (0, sortProtocolProperty_1.sortProtocolProperty)(originalProtocol);
        // json 转 groovy
        const groovyProtocol = (0, transformer_1.toGroovy)({ protocol: originalProtocol });
        // groovy 转 json
        const protocol = (0, transformer_1.fromGroovy)({
            pageId: originalProtocol.pageId,
            pageProtocolId: originalProtocol.pageProtocolId,
            pageProtocolVersion: originalProtocol.pageProtocolVersion,
            groovyProtocol,
        });
        // 保存文件
        const promises = [
            // 删除冗余字段、字段排序后的协议
            fs.writeFile(path.join(demoPath_1.DEMO_PATH, './protocol.sorted.json'), JSON.stringify(originalProtocol, null, 2) + '\n', 'utf-8'),
            // 转 groovy，再转回来的协议
            fs.writeFile(path.join(demoPath_1.DEMO_PATH, './protocol.new.json'), JSON.stringify(protocol, null, 2) + '\n', 'utf-8'),
            // groovy 协议
            ...Object.keys(groovyProtocol).map((file) => tslib_1.__awaiter(this, void 0, void 0, function* () {
                const content = groovyProtocol[file];
                if (!content)
                    return;
                const targetFile = path.join(demoPath_1.DEMO_PATH, 'output', file);
                yield fs.ensureFile(targetFile);
                return fs.writeFile(targetFile, content, 'utf-8');
            }))
        ];
        yield Promise.all(promises);
    });
}
demo().catch((e) => console.error(e));
