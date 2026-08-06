#!/usr/bin/env node

/**
 * Skill 依赖检查脚本
 *
 * 用法：
 *   node scripts/check-deps.js [--install]
 *
 *   --install  检测到缺失的必选 Skill 时，自动尝试安装
 *
 * 检查逻辑：
 *   1. 按优先级路径搜索每个依赖 Skill 的 SKILL.md
 *   2. 主 Skill 不存在时，尝试替代 Skill
 *   3. 汇总结果：必选缺失 → 终止；可选缺失 → 警告
 *   4. 输出检查报告
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ============================================================
// 依赖 Skill 清单（与 SKILL.md 保持一致）
// ============================================================
const DEPS = [
  { name: 'citadel',              required: true,  purpose: '学城文档阅读、创建、查询、管理',           phase: '全流程',          alternatives: ['km-doc-tools'] },
  { name: 'duo-docs',             required: true,  purpose: '前端技术方案编写（含来源标识）',             phase: '阶段二/四/五',    alternatives: [] },
  { name: 'draw-io-km',           required: false, purpose: '绘制架构图/流程图',                        phase: '技术方案',        alternatives: ['kmdrawio', 'drawio-generator'] },
  { name: 'duo-fedo',             required: false, purpose: 'duo 迭代管理、开发任务管理',                phase: '全流程',          alternatives: ['ee-fedo'] },
  { name: 'ee-code',              required: false, purpose: 'Draft PR 创建、CR 自动化报告',              phase: '代码开发',        alternatives: ['code-cli'] },
  { name: 'max-leez',             required: false, purpose: 'Max 组件库',                                phase: '代码开发',        alternatives: [] },
  { name: 'max-component-development', required: false, purpose: 'yooz 物料开发', phase: '代码开发',    alternatives: [] },
  { name: 'trade-code-reviewer',  required: false, purpose: '代码审查报告',                              phase: '代码开发',        alternatives: [] },
  { name: 'catpaw-daxiang',       required: false, purpose: '大象消息通知',                              phase: '任务终止/阶段完成', alternatives: [] },
];

// ============================================================
// 搜索路径（优先级从高到低）
// ============================================================
function getSearchPaths(workspaceRoot) {
  const home = process.env.HOME || process.env.USERPROFILE || '';
  return [
    { label: '项目级 Skill', pattern: path.join(workspaceRoot, '.catpaw/skills/{name}/SKILL.md') },
    { label: '项目级市场 Skill', pattern: path.join(workspaceRoot, '.catpaw/skills/skills-market/{name}/SKILL.md') },
    { label: '项目级 .claude Skill', pattern: path.join(workspaceRoot, '.claude/skills/{name}/SKILL.md') },
    { label: '用户级 Claude Skill', pattern: path.join(home, '.claude/skills/{name}/SKILL.md') },
    { label: '用户级 Claude 市场 Skill', pattern: path.join(home, '.claude/skills-market/{name}/SKILL.md') },
    { label: '用户级 CatPaw Skill', pattern: path.join(home, '.catpaw/skills/{name}/SKILL.md') },
    { label: '用户级市场 Skill', pattern: path.join(home, '.catpaw/skills/skills-market/{name}/SKILL.md') },
    { label: 'OpenClaw Skill', pattern: path.join(home, '.openclaw/skills/{name}/SKILL.md') },
  ];
}

// ============================================================
// 查找 Skill
// ============================================================
function findSkill(name, searchPaths) {
  for (const sp of searchPaths) {
    const p = sp.pattern.replace('{name}', name);
    if (fs.existsSync(p)) return { resolvedName: name, path: p, status: 'found', source: sp.label };
  }
  return null;
}

function findAlternativeSkill(dep, searchPaths) {
  for (const altName of dep.alternatives) {
    const result = findSkill(altName, searchPaths);
    if (result) {
      result.resolvedName = altName;
      result.status = 'alternative_found';
      return result;
    }
  }
  return null;
}

// ============================================================
// 安装 Skill
// ============================================================
function installSkill(name) {
  try {
    try { execSync('mtskills --version', { stdio: 'pipe' }); } catch {
      console.log('  安装 mtskills CLI...');
      execSync('npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com', { stdio: 'inherit' });
    }
    console.log(`  安装 ${name}...`);
    execSync(`mtskills i ${name}`, { stdio: 'inherit' });
    return true;
  } catch (e) {
    console.log(`  ⚠️ 安装失败: ${e.message.split('\n')[0]}`);
    return false;
  }
}

// ============================================================
// 环境检查
// ============================================================
function checkEnvironment() {
  const issues = [];
  try {
    execSync('npm list -g @it/oa-skills --depth=0', { stdio: 'pipe' });
  } catch {
    issues.push({ name: '@it/oa-skills', fix: 'npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com' });
  }
  try {
    execSync('fedo --version', { stdio: 'pipe' });
  } catch {
    issues.push({ name: '@ee/fedo-cli', fix: 'npm install -g @ee/fedo-cli --registry=http://r.npm.sankuai.com' });
  }
  return issues;
}

// ============================================================
// 格式化输出（使用列表格式避免终端宽度问题）
// ============================================================
function formatResult(r) {
  const req = r.required ? '必选' : '可选';
  if (r.status === 'found') {
    return `  ✅ ${r.name} (${req}) → ${r.resolvedName}`;
  } else if (r.status === 'alternative_found') {
    return `  ✅ ${r.name} (${req}) → 替代: ${r.resolvedName}`;
  } else {
    return `  ❌ ${r.name} (${req}) → 缺失${r.alternatives.length ? ` (替代: ${r.alternatives.join('/')})` : ''}`;
  }
}

// ============================================================
// 主流程
// ============================================================
function main() {
  const args = process.argv.slice(2);
  const autoInstall = args.includes('--install');

  // 自动检测 workspace 根目录
  let workspaceRoot = process.cwd();
  while (workspaceRoot !== path.dirname(workspaceRoot)) {
    if (fs.existsSync(path.join(workspaceRoot, '.catpaw')) || fs.existsSync(path.join(workspaceRoot, '.claude'))) {
      break;
    }
    workspaceRoot = path.dirname(workspaceRoot);
  }

  const searchPaths = getSearchPaths(workspaceRoot);
  const results = [];

  console.log('🔍 正在检查 Skill 依赖...\n');

  for (const dep of DEPS) {
    let result = findSkill(dep.name, searchPaths);
    if (!result) result = findAlternativeSkill(dep, searchPaths);
    if (!result) result = { resolvedName: dep.name, path: '', status: 'missing', source: '' };
    results.push({ ...dep, ...result });
  }

  const missingRequired = results.filter(r => r.required && r.status === 'missing');
  const missingOptional = results.filter(r => !r.required && r.status === 'missing');

  if (missingRequired.length === 0) {
    console.log('✅ 依赖检查通过！\n');
    for (const r of results) {
      console.log(formatResult(r));
    }
    if (missingOptional.length > 0) {
      console.log(`\n⚠️ ${missingOptional.length} 个可选 Skill 缺失（不影响主流程，部分功能将被跳过）`);
    }
    console.log('\n流程继续执行。');
  } else {
    console.log('❌ 依赖检查未通过，流程终止。\n');
    console.log('必选 Skill 缺失：');
    for (const r of missingRequired) {
      console.log(formatResult(r));
    }
    if (missingOptional.length > 0) {
      console.log('\n可选 Skill 缺失（不影响主流程）：');
      for (const r of missingOptional) {
        console.log(formatResult(r));
      }
    }

    if (autoInstall) {
      console.log('\n🔧 尝试自动安装缺失的必选 Skill...\n');
      for (const r of missingRequired) {
        installSkill(r.name);
      }
      console.log('\n🔄 重新检查依赖...\n');
      main();
      return;
    }

    console.log('\n请安装缺失的必选 Skill 后重试。提示：使用 --install 参数可自动安装。');
    process.exit(1);
  }

  // 环境检查
  const envIssues = checkEnvironment();
  if (envIssues.length > 0) {
    console.log('\n⚠️ 环境依赖缺失：');
    for (const issue of envIssues) {
      console.log(`  ❌ ${issue.name} → ${issue.fix}`);
    }
  }
}

main();
