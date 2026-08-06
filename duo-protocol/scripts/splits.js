const split = require('./lib/index');
const fs = require('fs');
const path=require('path')

// TODO:
const duoJsonPath = path.resolve(__dirname, ${生成的协议目录,需要替换成真实目录});
const json = fs.readFileSync(duoJsonPath, 'utf-8');

const temp = split.toGroovy({protocol: JSON.parse(json)});

console.log(temp);

// 遍历temp对象，把key作为文件名，value作为文件内容，写入到当前目录下的output文件夹中
Object.keys(temp).forEach(key => {
    if (temp[key] === undefined) return;
    const filePath = path.resolve(__dirname, 'output', key);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, temp[key], 'utf-8');
});

