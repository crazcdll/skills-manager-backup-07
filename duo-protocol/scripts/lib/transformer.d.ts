import type { PageNode, PageProtocol } from '@meishi/duo-protocol';
export interface ToGroovyOptions {
    protocol: PageProtocol;
}
export interface FromGroovyOptions {
    pageId: string;
    pageProtocolId: string;
    pageProtocolVersion: string;
    groovyProtocol: GroovyProtocol;
}
export interface GroovyProtocol {
    'dependencies.json': string;
    'ohDependencies.json': string | undefined;
    'componentsMap.json': string;
    'pageBuildConfig.json': string;
    'scripts/firstScreenModulePaths.json': string | undefined;
    'scripts/buildCustom.js': string | undefined;
    'scripts/mrnConfigCustom.js': string | undefined;
    'constData.groovy': string;
    'dataSourceMap.groovy': string;
    'struct.groovy': string;
    'logics.groovy': string;
    [key: `nodes/${string}.groovy`]: string | undefined;
}
export declare function toGroovy(opts: ToGroovyOptions): GroovyProtocol;
export declare function handleSplit(struct: PageNode[]): {
    [x: `nodes/${string}.groovy`]: string;
};
export declare function fromGroovy(opts: FromGroovyOptions): PageProtocol;
