#!/usr/bin/env node
/**
 * 检测本次改动新引入的依赖中，哪些引入了重复依赖
 * 只关注新增依赖导致的重复问题
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// 颜色输出
const colors = {
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
  gray: '\x1b[90m',
  reset: '\x1b[0m'
};

function log(color, message) {
  const colorCode = colors[color] || colors.reset;
  console.log(`${colorCode}${message}${colors.reset}`);
}

// 解析yarn.lock文件，返回包名->版本列表的映射
function parseYarnLock(content) {
  const packages = new Map();
  const lines = content.split('\n');

  let currentPkgKey = null;
  let currentVersion = null;
  let blockStartLine = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // 跳过注释和空行
    if (line.startsWith('#') || line.trim() === '') {
      continue;
    }

    // 检测包名行 (可能带引号也可能不带)
    // 格式: "@scope/pkg@^1.0.0": 或 react@16.13.1:
    const isQuotedPkg = line.startsWith('"') && line.endsWith('":');
    const isPlainPkg = line.match(/^[^"\s]+@.+:$/);

    if (isQuotedPkg || isPlainPkg) {
      if (isQuotedPkg) {
        currentPkgKey = line.slice(1, -2); // 去掉"和":
      } else {
        currentPkgKey = line.slice(0, -1); // 去掉:
      }
      blockStartLine = i;
      currentVersion = null;
    }
    // 检测version行
    else if (line.startsWith('  version') && currentPkgKey) {
      const versionMatch = line.match(/version "([^"]+)"/);
      if (versionMatch) {
        currentVersion = versionMatch[1];

        // 解析包名（可能有多个，逗号分隔）
        const pkgRefs = currentPkgKey.split(',').map(s => s.trim().replace(/^"/, '').replace(/"$/, ''));
        for (const pkgRef of pkgRefs) {
          const atIndex = pkgRef.lastIndexOf('@');
          if (atIndex > 0) {
            const pkgName = pkgRef.substring(0, atIndex);
            if (!packages.has(pkgName)) {
              packages.set(pkgName, new Map()); // version -> [entries]
            }
            const versionMap = packages.get(pkgName);
            if (!versionMap.has(currentVersion)) {
              versionMap.set(currentVersion, []);
            }
            versionMap.get(currentVersion).push({
              key: pkgRef,
              version: currentVersion,
              lineNumber: blockStartLine
            });
          }
        }
      }
    }
  }

  return packages;
}

// 获取git diff中新增的依赖条目
function getNewlyAddedPackages() {
  try {
    const diff = execSync('git diff HEAD -- yarn.lock', { encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 });
    const lines = diff.split('\n');

    const newPackages = new Map(); // pkgName -> Set of versions
    let inAddedBlock = false;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // 检测到新增块开始
      if (line.startsWith('@@')) {
        inAddedBlock = true;
        continue;
      }

      // 检测新增行（以+开头，但不是文件头）
      if (line.startsWith('+') && !line.startsWith('+++')) {
        // 检测包名行 (可能带引号也可能不带)
        // 格式: +"@scope/pkg@^1.0.0": 或 +react@^16.9.0:
        if ((line.startsWith('+"') && line.endsWith('":')) || 
            (line.match(/^\+[^"\s]+@.+:$/))) {
          let pkgKey;
          if (line.startsWith('+"')) {
            pkgKey = line.slice(2, -2); // 去掉+"和":
          } else {
            pkgKey = line.slice(1, -1); // 去掉+和:
          }
          const pkgRefs = pkgKey.split(',').map(s => s.trim());

          // 继续读取找version
          let j = i + 1;
          while (j < lines.length && j < i + 10) {
            const nextLine = lines[j];
            if (nextLine.startsWith('-')) break; // 块结束
            if (nextLine.startsWith('+  version')) {
              const versionMatch = nextLine.match(/version "([^"]+)"/);
              if (versionMatch) {
                const version = versionMatch[1];
                for (const pkgRef of pkgRefs) {
                  const atIndex = pkgRef.lastIndexOf('@');
                  if (atIndex > 0) {
                    const pkgName = pkgRef.substring(0, atIndex);
                    if (!newPackages.has(pkgName)) {
                      newPackages.set(pkgName, new Set());
                    }
                    newPackages.get(pkgName).add(version);
                  }
                }
              }
              break;
            }
            j++;
          }
        }
      }
    }

    return newPackages;
  } catch (e) {
    log('red', `获取git diff失败: ${e.message}`);
    return new Map();
  }
}

// 获取HEAD版本的yarn.lock
function getHeadYarnLock() {
  try {
    return execSync('git show HEAD:yarn.lock', { encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 });
  } catch (e) {
    log('red', `获取HEAD版本yarn.lock失败: ${e.message}`);
    return null;
  }
}

// 获取当前工作区的yarn.lock
function getCurrentYarnLock() {
  try {
    return fs.readFileSync(path.join(process.cwd(), 'yarn.lock'), 'utf8');
  } catch (e) {
    log('red', `读取当前yarn.lock失败: ${e.message}`);
    return null;
  }
}

// 分析重复情况
function analyzeDuplicates(headPackages, currentPackages, newPackages) {
  const results = [];

  for (const [pkgName, newVersions] of newPackages) {
    const currentVersions = currentPackages.get(pkgName);
    const headVersions = headPackages.get(pkgName);

    if (!currentVersions) continue;

    const currentVersionList = [...currentVersions.keys()];
    const headVersionList = headVersions ? [...headVersions.keys()] : [];

    // 检查是否引入了重复
    if (currentVersionList.length > 1) {
      // 判断哪些是新增的版本
      const trulyNewVersions = [...newVersions].filter(v => !headVersionList.includes(v));
      const existingVersions = currentVersionList.filter(v => headVersionList.includes(v));

      if (trulyNewVersions.length > 0) {
        results.push({
          name: pkgName,
          allVersions: currentVersionList,
          newVersions: trulyNewVersions,
          existingVersions: existingVersions,
          isNewDuplicate: headVersionList.length <= 1, // 如果HEAD只有一个版本或没有，说明本次引入了重复
          headVersions: headVersionList
        });
      }
    }
  }

  return results;
}

// 查找引入该依赖的上级依赖（依赖分析）
function findDependentPackages(targetPkg, targetVersion) {
  const dependents = [];
  try {
    // 使用yarn命令查找依赖关系
    const output = execSync(`yarn why ${targetPkg} 2>/dev/null || true`, {
      encoding: 'utf8',
      maxBuffer: 10 * 1024 * 1024
    });

    // 解析输出，提取依赖链信息
    const lines = output.split('\n');
    let currentChain = [];

    for (const line of lines) {
      // 简单解析，提取包含版本号的行
      const match = line.match(/([@\w\/\-]+)@(\^?[\d\.]+)/);
      if (match) {
        const [, pkg, version] = match;
        if (pkg !== targetPkg) {
          currentChain.push(`${pkg}@${version}`);
        }
      }
    }

    if (currentChain.length > 0) {
      dependents.push(...currentChain.slice(-3)); // 取最后3个
    }
  } catch (e) {
    // yarn why 可能失败，忽略
  }

  return dependents;
}

// 主函数
function main() {
  log('cyan', '╔══════════════════════════════════════════════════════════╗');
  log('cyan', '║     本次改动新引入依赖的重复依赖检测报告                    ║');
  log('cyan', '╚══════════════════════════════════════════════════════════╝\n');

  // 获取新旧yarn.lock
  const headContent = getHeadYarnLock();
  const currentContent = getCurrentYarnLock();

  if (!headContent || !currentContent) {
    log('red', '错误: 无法读取yarn.lock文件');
    process.exit(1);
  }

  // 解析
  log('blue', '正在解析yarn.lock文件...\n');
  const headPackages = parseYarnLock(headContent);
  const currentPackages = parseYarnLock(currentContent);

  log('gray', `HEAD版本包数量: ${headPackages.size}`);
  log('gray', `当前版本包数量: ${currentPackages.size}\n`);

  // 获取新增依赖
  log('blue', '正在分析git diff获取新增依赖...\n');
  const newPackages = getNewlyAddedPackages();

  if (newPackages.size === 0) {
    log('green', '✓ 本次改动没有新增依赖\n');
    process.exit(0);
  }

  log('blue', `本次改动新增/修改了 ${newPackages.size} 个包的依赖:\n`);

  // 显示新增依赖列表
  for (const [pkgName, versions] of newPackages) {
    log('gray', `  • ${pkgName}: ${[...versions].join(', ')}`);
  }
  console.log('');

  // 分析重复
  const duplicates = analyzeDuplicates(headPackages, currentPackages, newPackages);

  // 分类显示结果
  const newDuplicates = duplicates.filter(d => d.isNewDuplicate);
  const expandedDuplicates = duplicates.filter(d => !d.isNewDuplicate);

  // 1. 本次新引入的重复依赖（最严重）
  if (newDuplicates.length > 0) {
    log('red', '╔══════════════════════════════════════════════════════════╗');
    log('red', '║  ⚠️  本次改动新引入的重复依赖（需要处理）                  ║');
    log('red', '╚══════════════════════════════════════════════════════════╝\n');

    for (const dup of newDuplicates) {
      log('yellow', `📦 ${dup.name}`);
      log('reset', `   HEAD版本: ${dup.headVersions.join(', ') || '无'}`);
      log('red', `   ⚠️  新增版本: ${dup.newVersions.join(', ')}`);
      log('reset', `   当前所有版本: ${dup.allVersions.join(', ')}`);

      // 建议
      const highest = dup.allVersions.sort((a, b) => {
        // 简单版本比较
        const aParts = a.split('.').map(Number);
        const bParts = b.split('.').map(Number);
        for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
          const diff = (bParts[i] || 0) - (aParts[i] || 0);
          if (diff !== 0) return diff;
        }
        return 0;
      })[0];

      log('cyan', `   💡 建议: 检查resolutions锁定到 ${highest}\n`);
    }
  }

  // 2. 加剧的重复依赖
  if (expandedDuplicates.length > 0) {
    log('yellow', '╔══════════════════════════════════════════════════════════╗');
    log('yellow', '║  📌 本次改动加剧的重复依赖（新增版本到已重复的包）          ║');
    log('yellow', '╚══════════════════════════════════════════════════════════╝\n');

    for (const dup of expandedDuplicates) {
      log('yellow', `📦 ${dup.name}`);
      log('reset', `   HEAD已有版本: ${dup.headVersions.join(', ')}`);
      log('red', `   本次新增版本: ${dup.newVersions.join(', ')}`);
      log('reset', `   现在共 ${dup.allVersions.length} 个版本\n`);
    }
  }

  // 3. 无重复的新增依赖
  const cleanNewPackages = [...newPackages.keys()].filter(pkgName => {
    return !duplicates.some(d => d.name === pkgName);
  });

  if (cleanNewPackages.length > 0) {
    log('green', '╔══════════════════════════════════════════════════════════╗');
    log('green', '║  ✅ 本次新增但无重复的依赖                                 ║');
    log('green', '╚══════════════════════════════════════════════════════════╝\n');

    for (const pkgName of cleanNewPackages) {
      const versions = [...newPackages.get(pkgName)];
      log('green', `  ✓ ${pkgName}@${versions.join(', ')}`);
    }
    console.log('');
  }

  // 总结
  log('cyan', '╔══════════════════════════════════════════════════════════╗');
  log('cyan', '║                        检测总结                           ║');
  log('cyan', '╚══════════════════════════════════════════════════════════╝');

  log('blue', `本次改动涉及 ${newPackages.size} 个依赖包`);
  log('red', `  - 新引入重复依赖: ${newDuplicates.length} 个`);
  log('yellow', `  - 加剧重复依赖: ${expandedDuplicates.length} 个`);
  log('green', `  - 无重复的新增依赖: ${cleanNewPackages.length} 个`);
  console.log('');

  // 生成JSON报告
  const report = {
    timestamp: new Date().toISOString(),
    summary: {
      totalNewPackages: newPackages.size,
      newDuplicates: newDuplicates.length,
      expandedDuplicates: expandedDuplicates.length,
      cleanPackages: cleanNewPackages.length
    },
    newDuplicates,
    expandedDuplicates,
    cleanPackages: cleanNewPackages
  };

  const reportPath = path.join(process.cwd(), 'new-deps-duplicate-report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  log('gray', `详细报告已保存: ${reportPath}\n`);

  // 返回退出码
  if (newDuplicates.length > 0) {
    log('red', '❌ 检测到本次改动新引入的重复依赖，请在resolutions中锁定版本！\n');
    process.exit(1);
  } else if (expandedDuplicates.length > 0) {
    log('yellow', '⚠️  本次改动加剧了重复依赖问题，建议检查resolutions配置\n');
    process.exit(0);
  } else {
    log('green', '✅ 本次改动引入的依赖没有造成重复依赖问题\n');
    process.exit(0);
  }
}

// 执行
main();
