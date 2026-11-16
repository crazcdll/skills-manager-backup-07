#!/usr/bin/env node

/**
 * Skill 依赖检查脚本
 *
 * 用法：
 *   node scripts/check-deps.js                  # 检查依赖是否存在
 *   node scripts/check-deps.js --install        # 检查并自动安装缺失依赖
 *   node scripts/check-deps.js --check-update   # 检查是否有版本更新（不执行更新）
 *   node scripts/check-deps.js --update         # 检查并执行版本更新
 *   node scripts/check-deps.js --self-check     # 仅检查当前 Skill 自身是否有远端更新
 *   node scripts/check-deps.js --self-update    # 检查并更新当前 Skill 自身到最新版本
 *
 * 执行顺序：
 *   1. 将所有疑似依赖注册到 fe-rd-workflow/skills.json
 *   2. 检查 Skill 依赖是否存在
 *   3. 如果需要安装，则先确保 Node 版本满足要求，再执行安装
 *   4. 检查版本是否满足 min_version 要求（--check-update / --update）
 *   5. 检查当前 Skill 自身是否有远端更新（--self-check / --self-update）
 *   6. 输出检查报告
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execSync } = require('child_process');

const DEPS_JSON = require("./skill-deps.json");
const REQUIRED_NODE_MAJOR = 20;
const SKILLS_JSON_PATH = path.resolve(__dirname, '..', 'skills.json');
const MAIN_SKILL_NAME = 'fe-rd-workflow';
const SELF_SKILL_MD_PATH = path.resolve(__dirname, '..', 'SKILL.md');

const DEPS = DEPS_JSON;

function getWorkspaceRoot() {
  // 优先使用基于 __dirname 的固定路径：scripts/ -> fe-rd-workflow/ -> skills/ -> duo-skills(仓库根)
  const scriptBasedRoot = path.resolve(__dirname, '..', '..', '..');
  // 验证该路径下确实有 .claude/skills/ 目录（skill 安装位置）
  if (fs.existsSync(path.join(scriptBasedRoot, '.claude', 'skills'))) {
    return scriptBasedRoot;
  }

  // 回退：遍历查找 .catpaw 或 .claude
  const candidates = [process.cwd(), scriptBasedRoot];
  for (const candidate of candidates) {
    let workspaceRoot = candidate;
    while (workspaceRoot !== path.dirname(workspaceRoot)) {
      if (fs.existsSync(path.join(workspaceRoot, '.catpaw')) || fs.existsSync(path.join(workspaceRoot, '.claude'))) {
        return workspaceRoot;
      }
      workspaceRoot = path.dirname(workspaceRoot);
    }
  }

  return scriptBasedRoot;
}

function getSearchPaths(workspaceRoot) {
  const home = process.env.HOME || process.env.USERPROFILE || '';
  return [
    {
      label: '当前 skills 工作区',
      pattern: path.resolve(__dirname, '..', '..', '{name}', 'SKILL.md'),
      template: '{workspace_root}/{name}/SKILL.md',
    },
    {
      label: '项目级 CatPaw Skill',
      pattern: path.join(workspaceRoot, '.catpaw/skills/{name}/SKILL.md'),
      template: '{work_root}/.catpaw/skills/{name}/SKILL.md',
    },
    {
      label: '项目级 CatPaw 市场 Skill',
      pattern: path.join(workspaceRoot, '.catpaw/skills/skills-market/{name}/SKILL.md'),
      template: '{work_root}/.catpaw/skills/skills-market/{name}/SKILL.md',
    },
    {
      label: '项目级 Claude Skill',
      pattern: path.join(workspaceRoot, '.claude/skills/{name}/SKILL.md'),
      template: '{work_root}/.claude/skills/{name}/SKILL.md',
    },
    {
      label: '用户级 Claude Skill',
      pattern: path.join(home, '.claude/skills/{name}/SKILL.md'),
      template: '~/.claude/skills/{name}/SKILL.md',
    },
    {
      label: '用户级 Claude 市场 Skill',
      pattern: path.join(home, '.claude/skills-market/{name}/SKILL.md'),
      template: '~/.claude/skills-market/{name}/SKILL.md',
    },
    {
      label: '用户级 CatPaw Skill',
      pattern: path.join(home, '.catpaw/skills/{name}/SKILL.md'),
      template: '~/.catpaw/skills/{name}/SKILL.md',
    },
    {
      label: '用户级 CatPaw 市场 Skill',
      pattern: path.join(home, '.catpaw/skills/skills-market/{name}/SKILL.md'),
      template: '~/.catpaw/skills/skills-market/{name}/SKILL.md',
    },
    {
      label: '用户级 OpenClaw Skill',
      pattern: path.join(home, '.openclaw/skills/{name}/SKILL.md'),
      template: '~/.openclaw/skills/{name}/SKILL.md',
    },
  ];
}

function findSkill(name, searchPaths) {
  for (const sp of searchPaths) {
    const skillPath = sp.pattern.replace('{name}', name);
    if (fs.existsSync(skillPath)) {
      return { resolvedName: name, path: skillPath, status: 'found', source: sp.label };
    }
  }
  return null;
}

function findAlternativeSkill(dep, searchPaths) {
  for (const altName of dep.alternatives) {
    const result = findSkill(altName, searchPaths);
    if (result) {
      return { ...result, resolvedName: altName, status: 'alternative_found' };
    }
  }
  return null;
}

function resolveInstalledSkill(dep, searchPaths) {
  return findSkill(dep.name, searchPaths) || findAlternativeSkill(dep, searchPaths);
}

// ─── 版本管理 ────────────────────────────────────────────────────────────────

/**
 * 从 SKILL.md 文件中提取 YAML frontmatter 中的 version 字段
 * @param {string} skillPath - SKILL.md 的完整路径
 * @returns {string|null} 版本号，如 "1.0.0"；未找到则返回 null
 */
function getSkillVersion(skillPath) {
  if (!skillPath || !fs.existsSync(skillPath)) {
    return null;
  }

  try {
    const content = fs.readFileSync(skillPath, 'utf8');
    // 匹配 YAML frontmatter: --- ... ---
    const frontmatterMatch = content.match(/^---\s*\n([\s\S]*?)\n---/);
    if (!frontmatterMatch) {
      return null;
    }

    const frontmatter = frontmatterMatch[1];
    // 提取 version 字段（支持 "1.0.0" 和 1.0.0 两种格式）
    const versionMatch = frontmatter.match(/^version:\s*["']?([^"'\s]+)["']?\s*$/m);
    if (versionMatch) {
      return versionMatch[1].trim();
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * 从 .mtskills-source.jsonl 中获取指定 skill 的安装来源信息
 * @param {string} skillName - Skill 名称
 * @param {string} workspaceRoot - 工作区根目录
 * @returns {object|null} 来源记录，包含 sourceType、installedAt 等
 */
function getSkillSource(skillName, workspaceRoot) {
  const sourceFilePath = path.join(workspaceRoot, '.claude', 'skills', '.mtskills-source.jsonl');
  if (!fs.existsSync(sourceFilePath)) {
    return null;
  }

  try {
    const lines = fs.readFileSync(sourceFilePath, 'utf8').trim().split('\n');
    for (const line of lines) {
      if (!line.trim()) continue;
      const record = JSON.parse(line);
      if (record.skillName === skillName) {
        return record;
      }
    }
  } catch {}

  return null;
}

/**
 * 比较两个 semver 版本号
 * @param {string} v1 - 版本号1，如 "1.2.3"
 * @param {string} v2 - 版本号2，如 "1.3.0"
 * @returns {number} v1 < v2 返回 -1，v1 === v2 返回 0，v1 > v2 返回 1
 */
function compareVersions(v1, v2) {
  if (!v1 || !v2) return 0;
  const parts1 = v1.replace(/^v/, '').split('.').map(Number);
  const parts2 = v2.replace(/^v/, '').split('.').map(Number);
  const maxLen = Math.max(parts1.length, parts2.length);

  for (let i = 0; i < maxLen; i++) {
    const p1 = parts1[i] || 0;
    const p2 = parts2[i] || 0;
    if (p1 < p2) return -1;
    if (p1 > p2) return 1;
  }
  return 0;
}

/**
 * 检查所有已安装 Skill 的版本是否满足 min_version 要求
 * @param {Array} results - 依赖检查结果数组
 * @returns {Array} 需要更新的 Skill 列表
 */
function checkUpdates(results, searchPaths) {
  const needUpdate = [];

  for (const result of results) {
    // 跳过缺失的 Skill
    if (result.status === 'missing') continue;
    // 跳过没有 min_version 要求的（如 citadel 这种 system-command）
    if (!result.min_version) continue;

    const localVersion = getSkillVersion(result.path);
    if (localVersion === null) {
      // SKILL.md 中没有 version 字段，无法判断，标记为未知
      needUpdate.push({
        ...result,
        localVersion: null,
        minVersion: result.min_version,
        updateReason: '无法获取本地版本号，建议更新',
      });
      continue;
    }

    if (compareVersions(localVersion, result.min_version) < 0) {
      needUpdate.push({
        ...result,
        localVersion,
        minVersion: result.min_version,
        updateReason: `本地版本 ${localVersion} 低于最低要求 ${result.min_version}`,
      });
    }
  }

  return needUpdate;
}

/**
 * 使用 mtskills pull 更新指定 Skill
 * @param {object} skill - 需要更新的 Skill 信息
 * @param {string} workspaceRoot - 工作区根目录
 * @returns {boolean} 更新是否成功
 */
function updateSkill(skill, workspaceRoot) {
  try {
    const source = getSkillSource(skill.name, workspaceRoot);
    if (!source) {
      // 没有来源记录，使用 mtskills i 重新安装
      console.log(`  ⚠️ ${skill.name} 无安装来源记录，尝试重新安装...`);
      if (!commandExistsWithRequiredNode('mtskills --version')) {
        console.log('  安装 mtskills CLI...');
        runCommandWithRequiredNode('npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com');
      }
      runCommandWithRequiredNode(`mtskills i ${skill.name}`);
    } else {
      // 有来源记录，使用 mtskills pull 拉取更新
      console.log(`  使用 mtskills pull 更新 ${skill.name}...`);
      runCommandWithRequiredNode(`mtskills pull ${skill.name}`);
    }

    // 验证更新后的版本
    const searchPaths = getSearchPaths(workspaceRoot);
    const updated = findSkill(skill.name, searchPaths);
    if (updated) {
      const newVersion = getSkillVersion(updated.path);
      console.log(`  ✅ ${skill.name} 更新完成${newVersion ? `，当前版本: ${newVersion}` : ''}`);
      return true;
    }

    console.log(`  ⚠️ ${skill.name} 更新命令已执行，但无法确认结果`);
    return true;
  } catch (error) {
    console.log(`  ❌ ${skill.name} 更新失败: ${error.message.split('\n')[0]}`);
    return false;
  }
}

// ─── Node 版本管理 ──────────────────────────────────────────────────────────

function detectNodeManager() {
  const home = os.homedir();
  const nvmScript = path.join(home, '.nvm', 'nvm.sh');

  if (fs.existsSync(nvmScript)) {
    return {
      name: 'nvm',
      commandPrefix: `source "${nvmScript}" && nvm install ${REQUIRED_NODE_MAJOR} >/dev/null && nvm use ${REQUIRED_NODE_MAJOR} >/dev/null`,
    };
  }

  try {
    execSync('fnm --version', { stdio: 'pipe' });
    return {
      name: 'fnm',
      commandPrefix: `eval "$(fnm env --use-on-cd)" && fnm install ${REQUIRED_NODE_MAJOR} >/dev/null && fnm use ${REQUIRED_NODE_MAJOR}`,
    };
  } catch {}

  try {
    execSync('volta --version', { stdio: 'pipe' });
    return {
      name: 'volta',
      commandPrefix: `volta install node@${REQUIRED_NODE_MAJOR} >/dev/null && volta run node@${REQUIRED_NODE_MAJOR}`,
      wrapper: 'volta',
    };
  } catch {}

  try {
    execSync('asdf --version', { stdio: 'pipe' });
    return {
      name: 'asdf',
      commandPrefix: `asdf install nodejs ${REQUIRED_NODE_MAJOR}.x >/dev/null || true && asdf shell nodejs ${REQUIRED_NODE_MAJOR}.x`,
    };
  } catch {}

  return null;
}

function runCommandWithRequiredNode(command) {
  const currentMajor = Number(process.versions.node.split('.')[0]);

  if (currentMajor >= REQUIRED_NODE_MAJOR) {
    execSync(command, { stdio: 'inherit' });
    return;
  }

  const manager = detectNodeManager();
  if (!manager) {
    throw new Error(
      `当前 Node.js 版本为 ${process.versions.node}，低于要求的 ${REQUIRED_NODE_MAJOR}。` +
      `未检测到可用的版本管理器（nvm/fnm/volta/asdf），无法自动切换后安装。`
    );
  }

  console.log(`  检测到 Node.js ${process.versions.node}，将通过 ${manager.name} 切换到 Node ${REQUIRED_NODE_MAJOR} 后执行安装...`);

  if (manager.wrapper === 'volta') {
    execSync(`/bin/bash -lc '${manager.commandPrefix} ${command}'`, { stdio: 'inherit' });
    return;
  }

  execSync(`/bin/bash -lc '${manager.commandPrefix} && ${command}'`, { stdio: 'inherit' });
}

function commandExists(command) {
  try {
    execSync(command, { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

function commandExistsWithRequiredNode(command) {
  const currentMajor = Number(process.versions.node.split('.')[0]);
  if (currentMajor >= REQUIRED_NODE_MAJOR) {
    return commandExists(command);
  }

  const manager = detectNodeManager();
  if (!manager) {
    return false;
  }

  try {
    if (manager.wrapper === 'volta') {
      execSync(`/bin/bash -lc '${manager.commandPrefix} ${command}'`, { stdio: 'pipe' });
      return true;
    }

    execSync(`/bin/bash -lc '${manager.commandPrefix} && ${command}'`, { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

// ─── Skill 记录构建 ──────────────────────────────────────────────────────────

function getSkillRuntime(dep) {
  if (dep.name === 'citadel') {
    return 'oa-skills';
  }
  return 'mtskills';
}

function buildSkillRecord(dep, workspaceRoot) {
  const runtime = getSkillRuntime(dep);
  // max-material-dev 是由 frontend-engineer-agent 子 Agent 调用的
  const usedBy = (dep.name === 'max-material-dev') ? ['frontend-engineer-agent'] : [MAIN_SKILL_NAME];
  const record = {
    name: dep.name,
    type: runtime === 'oa-skills' ? 'system-command' : 'skill',
    runtime,
    purpose: dep.purpose,
    phase: dep.phase,
    used_by: usedBy,
    alternatives: dep.alternatives,
    min_version: dep.min_version || '',
  };

  if (dep.name === 'citadel') {
    record.command = 'oa-skills citadel';
    record.npm_package = '@it/oa-skills';
    record.npm_registry = 'http://r.npm.sankuai.com';
    record.install_cmd = 'npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com';
    record.check_cmd = 'oa-skills citadel --help';
    record.update_cmd = 'npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com';
    return record;
  }

  record.search_paths = getSearchPaths(workspaceRoot).map(item => (item.template || item.pattern).replace(/\\/g, '/'));
  record.install_cmd = `mtskills i ${dep.name}`;
  record.check_cmd = 'find skill file by search_paths';
  record.update_cmd = `mtskills pull ${dep.name}`;
  return record;
}

function syncSkillsJson(workspaceRoot) {
  let existing = {};

  if (fs.existsSync(SKILLS_JSON_PATH)) {
    try {
      existing = JSON.parse(fs.readFileSync(SKILLS_JSON_PATH, 'utf8'));
    } catch {
      existing = {};
    }
  }

  const requiredSkills = DEPS
    .filter(dep => dep.required)
    .map(dep => buildSkillRecord(dep, workspaceRoot));
  const optionalSkills = DEPS
    .filter(dep => !dep.required)
    .map(dep => buildSkillRecord(dep, workspaceRoot));

  const skillsJson = {
    meta: {
      name: MAIN_SKILL_NAME,
      version: existing.meta && existing.meta.version ? existing.meta.version : '1.0.0',
      description: 'fe-rd-workflow 总线 Skill 的依赖注册与系统要求',
      created_at: existing.meta && existing.meta.created_at ? existing.meta.created_at : new Date().toISOString().slice(0, 10),
      last_updated: new Date().toISOString().slice(0, 10),
    },
    required_skills: requiredSkills,
    optional_skills: optionalSkills,
    system_requirements: [
      {
        name: 'Node.js',
        min_version: String(REQUIRED_NODE_MAJOR),
        reason: 'mtskills、oa-skills 和依赖安装流程要求 Node.js >= 20',
        install_method: `nvm install ${REQUIRED_NODE_MAJOR} && nvm use ${REQUIRED_NODE_MAJOR}`,
      },
    ],
    dependency_check: {
      type: 'node-script',
      location: 'scripts/check-deps.js',
      trigger: '读取主 SKILL.md 后立即执行',
      behavior: [
        '先同步 skills.json 中的疑似依赖清单',
        '如需安装依赖，先校验并切换到所需 Node 版本',
        '最后执行 Skill 依赖安装和环境依赖安装',
        '使用 --check-update 检查版本更新',
        '使用 --update 检查并执行版本更新',
      ],
      exit_codes: {
        0: '全量依赖就绪，流程可继续',
        1: '任意依赖缺失、Node 版本切换失败或安装失败，流程终止',
        2: '存在版本更新可用（仅 --check-update 模式）',
      },
    },
  };

  fs.writeFileSync(SKILLS_JSON_PATH, JSON.stringify(skillsJson, null, 2) + '\n', 'utf8');
  console.log(`📝 已同步疑似依赖到 ${SKILLS_JSON_PATH}`);
}

// ─── 安装与环境检查 ─────────────────────────────────────────────────────────

function installSkill(dep, searchPaths) {
  try {
    const existing = resolveInstalledSkill(dep, searchPaths);
    if (existing) {
      console.log(`  跳过 ${dep.name}，已存在: ${existing.resolvedName} (${existing.source})`);
      return true;
    }

    if (!commandExistsWithRequiredNode('mtskills --version')) {
      console.log('  安装 mtskills CLI...');
      runCommandWithRequiredNode('npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com');
    }

    console.log(`  安装 ${dep.name}...`);
    runCommandWithRequiredNode(`mtskills i ${dep.name}`);

    const installed = resolveInstalledSkill(dep, searchPaths);
    if (!installed) {
      console.log(`  ⚠️ 安装命令执行完成，但仍未找到 ${dep.name}`);
      return false;
    }

    return true;
  } catch (error) {
    console.log(`  ⚠️ 安装失败: ${error.message.split('\n')[0]}`);
    return false;
  }
}

function checkEnvironment() {
  const issues = [];

  try {
    execSync('npm list -g @it/oa-skills --depth=0', { stdio: 'pipe' });
  } catch {
    issues.push({
      name: '@it/oa-skills',
      fix: 'npm install -g @it/oa-skills@latest --registry=http://r.npm.sankuai.com',
    });
  }

  try {
    execSync('fedo --version', { stdio: 'pipe' });
  } catch {
    issues.push({
      name: '@ee/fedo-cli',
      fix: 'npm install -g @ee/fedo-cli --registry=http://r.npm.sankuai.com',
    });
  }

  return issues;
}

function installEnvironmentIssues(issues) {
  for (const issue of issues) {
    console.log(`  安装环境依赖 ${issue.name}...`);
    runCommandWithRequiredNode(issue.fix);
  }
}

// ─── 格式化输出 ─────────────────────────────────────────────────────────────

function formatResult(result) {
  if (result.status === 'found') {
    return `  ✅ ${result.name} → ${result.resolvedName}`;
  }
  if (result.status === 'alternative_found') {
    return `  ✅ ${result.name} → 替代: ${result.resolvedName}`;
  }
  return `  ❌ ${result.name} → 缺失${result.alternatives.length ? ` (替代: ${result.alternatives.join('/')})` : ''}`;
}

function formatUpdateResult(item) {
  const local = item.localVersion || '未知';
  const min = item.minVersion;
  return `  🔄 ${item.name} → 本地: ${local}, 最低要求: ${min} (${item.updateReason})`;
}

// ─── 主流程 ──────────────────────────────────────────────────────────────────

// ─── 当前 Skill 自身更新检查 ─────────────────────────────────────────────────

/**
 * 从远端 mtskills 平台获取指定 Skill 的最新信息
 * @param {string} skillName - Skill 名称
 * @returns {object|null} 远端 Skill 信息，包含 version、updated 等
 */
function getRemoteSkillInfo(skillName) {
  try {
    const output = execSync(`mtskills search ${skillName} 2>/dev/null`, {
      encoding: 'utf8',
      timeout: 30000,
    });

    // 解析搜索结果，提取版本和更新时间
    const versionMatch = output.match(/version:\s*(.+)/);
    const updatedMatch = output.match(/updated:\s*(\d+)/);

    const result = {};
    if (versionMatch) {
      result.version = versionMatch[1].trim();
    }
    if (updatedMatch) {
      result.updatedAt = parseInt(updatedMatch[1], 10);
    }

    return Object.keys(result).length > 0 ? result : null;
  } catch {
    return null;
  }
}

/**
 * 检查当前 Skill 自身是否有远端更新
 * @returns {object} 检查结果 { hasUpdate, localVersion, remoteVersion, remoteUpdatedAt }
 */
function checkSelfUpdate() {
  const localVersion = getSkillVersion(SELF_SKILL_MD_PATH);
  const remoteInfo = getRemoteSkillInfo(MAIN_SKILL_NAME);

  const result = {
    name: MAIN_SKILL_NAME,
    localVersion: localVersion || '未知',
    remoteVersion: remoteInfo ? (remoteInfo.version || '未知') : '无法获取',
    remoteUpdatedAt: remoteInfo ? remoteInfo.updatedAt : null,
    hasUpdate: false,
    reason: '',
  };

  if (!remoteInfo) {
    result.reason = '无法获取远端版本信息（可能网络问题或 mtskills 未安装）';
    return result;
  }

  // 比较版本号
  if (localVersion && remoteInfo.version) {
    const cmp = compareVersions(localVersion, remoteInfo.version);
    if (cmp < 0) {
      result.hasUpdate = true;
      result.reason = `本地版本 ${localVersion} 低于远端版本 ${remoteInfo.version}`;
    } else {
      result.reason = `本地版本 ${localVersion} 与远端版本 ${remoteInfo.version} 一致或更高`;
    }
  } else if (remoteInfo.updatedAt) {
    // 如果无法获取版本号，通过本地文件的修改时间与远端更新时间对比
    try {
      const localStat = fs.statSync(SELF_SKILL_MD_PATH);
      const localModifiedTime = localStat.mtimeMs;
      if (remoteInfo.updatedAt > localModifiedTime) {
        result.hasUpdate = true;
        const remoteDate = new Date(remoteInfo.updatedAt).toISOString().slice(0, 10);
        const localDate = new Date(localModifiedTime).toISOString().slice(0, 10);
        result.reason = `远端更新时间 (${remoteDate}) 晚于本地修改时间 (${localDate})`;
      } else {
        result.reason = '本地修改时间与远端更新时间一致或更新';
      }
    } catch {
      result.reason = '无法读取本地 SKILL.md 修改时间';
    }
  } else {
    result.reason = '无法比较版本：本地和远端均无可用版本信息';
  }

  return result;
}

/**
 * 执行当前 Skill 自身的更新
 * @param {string} workspaceRoot - 工作区根目录
 * @returns {boolean} 更新是否成功
 */
function updateSelfSkill(workspaceRoot) {
  try {
    // 检查是否有安装来源记录
    const source = getSkillSource(MAIN_SKILL_NAME, workspaceRoot);

    // 先备份当前 SKILL.md 的 version
    const oldVersion = getSkillVersion(SELF_SKILL_MD_PATH);

    if (source) {
      console.log(`  使用 mtskills pull 更新 ${MAIN_SKILL_NAME}...`);
      runCommandWithRequiredNode(`mtskills pull ${MAIN_SKILL_NAME}`);
    } else {
      // 没有来源记录，使用 mtskills i 重新安装
      console.log(`  ⚠️ ${MAIN_SKILL_NAME} 无安装来源记录，尝试重新安装...`);
      if (!commandExistsWithRequiredNode('mtskills --version')) {
        console.log('  安装 mtskills CLI...');
        runCommandWithRequiredNode('npm i -g @mtfe/mtskills --registry=http://r.npm.sankuai.com');
      }
      runCommandWithRequiredNode(`mtskills i ${MAIN_SKILL_NAME}`);
    }

    // 验证更新
    const newVersion = getSkillVersion(SELF_SKILL_MD_PATH);
    if (newVersion && newVersion !== oldVersion) {
      console.log(`  ✅ ${MAIN_SKILL_NAME} 更新完成: ${oldVersion || '未知'} → ${newVersion}`);
      return true;
    }

    // 即使版本号相同，pull 可能更新了其他文件
    console.log(`  ✅ ${MAIN_SKILL_NAME} 更新命令已执行${newVersion ? `，当前版本: ${newVersion}` : ''}`);
    return true;
  } catch (error) {
    console.log(`  ❌ ${MAIN_SKILL_NAME} 更新失败: ${error.message.split('\n')[0]}`);
    return false;
  }
}

function main() {
  const args = process.argv.slice(2);
  const autoInstall = args.includes('--install');
  const checkUpdate = args.includes('--check-update');
  const autoUpdate = args.includes('--update');
  const selfCheck = args.includes('--self-check');
  const selfUpdate = args.includes('--self-update');
  const workspaceRoot = getWorkspaceRoot();

  // ── 0. 仅自身更新检查模式 ──────────────────────────────────────────────
  // --self-check / --self-update 不依赖其他 Skill，直接执行自身更新检查
  if (selfCheck || selfUpdate) {
    if (!checkUpdate && !autoUpdate) {
      // 纯自身检查模式，跳过依赖检查
      console.log('🔍 正在检查当前 Skill 自身的远端更新...\n');
      const selfResult = checkSelfUpdate();

      if (selfResult.hasUpdate) {
        console.log(`\n  🔄 发现远端有新版本可用！`);

        if (selfCheck) {
          console.log('\n  使用 --self-update 参数可更新当前 Skill 到最新版本。');
          process.exit(2);
        }

        if (selfUpdate) {
          console.log('\n🔧 开始更新当前 Skill...\n');
          const success = updateSelfSkill(workspaceRoot);
          if (success) {
            console.log('\n✅ 当前 Skill 更新完成！');
            syncSkillsJson(workspaceRoot);
          } else {
            console.log('\n❌ 当前 Skill 更新失败，请手动执行: mtskills pull fe-rd-workflow');
          }
        }
      } else {
        console.log('\n  ✅ 当前 Skill 已是最新版本。');
      }

      return;
    }
    // selfCheck/selfUpdate 与 checkUpdate/autoUpdate 组合使用时，走完整检查流程
  }

  syncSkillsJson(workspaceRoot);

  const searchPaths = getSearchPaths(workspaceRoot);
  const results = [];

  console.log('🔍 正在检查 Skill 依赖...\n');

  for (const dep of DEPS) {
    let result = findSkill(dep.name, searchPaths);
    if (!result) {
      result = findAlternativeSkill(dep, searchPaths);
    }
    if (!result) {
      result = { resolvedName: dep.name, path: '', status: 'missing', source: '' };
    }
    results.push({ ...dep, ...result });
  }

  // ── 1. 存在性检查 ──────────────────────────────────────────────────────
  const missingRequired = results.filter(result => result.required && result.status === 'missing');

  if (missingRequired.length === 0) {
    console.log('✅ 全量依赖检查通过！\n');
    for (const result of results) {
      console.log(formatResult(result));
    }
    console.log('');
  } else {
    console.log('❌ 依赖检查未通过，流程终止。\n');
    console.log('缺失的必选 Skill：');
    for (const result of missingRequired) {
      console.log(formatResult(result));
    }

    if (autoInstall) {
      console.log('\n🔧 尝试自动安装缺失的 Skill...\n');
      try {
        for (const result of missingRequired) {
          const installed = installSkill(result, searchPaths);
          if (!installed) {
            console.log(`\n❌ 自动安装失败：${result.name} 未能安装成功，停止重试。`);
            process.exit(1);
          }
        }
      } catch (error) {
        console.log(`\n❌ 自动安装失败：${error.message}`);
        process.exit(1);
      }

      console.log('\n🔄 重新检查依赖...\n');
      main();
      return;
    }

    console.log('\n请安装缺失的必选 Skill 后重试。提示：使用 --install 参数可自动安装。');
    process.exit(1);
  }

  // ── 2. 环境依赖检查 ────────────────────────────────────────────────────
  const envIssues = checkEnvironment();
  if (envIssues.length > 0) {
    console.log('❌ 环境依赖缺失（必选），流程终止：');
    for (const issue of envIssues) {
      console.log(`  ❌ ${issue.name} → ${issue.fix}`);
    }

    if (autoInstall) {
      console.log('\n🔧 尝试自动安装环境依赖...\n');
      try {
        installEnvironmentIssues(envIssues);
        console.log('\n✅ 环境依赖安装完成，重新检查...\n');
        const recheckIssues = checkEnvironment();
        if (recheckIssues.length > 0) {
          console.log('\n❌ 环境依赖安装后仍未就绪：');
          for (const issue of recheckIssues) {
            console.log(`  ❌ ${issue.name}`);
          }
          process.exit(1);
        }
      } catch (error) {
        console.log(`\n❌ 环境依赖安装失败：${error.message}`);
        process.exit(1);
      }
    } else {
      console.log('\n请安装缺失的环境依赖后重试。提示：使用 --install 参数可自动安装。');
      process.exit(1);
    }
  }

  // ── 3. 版本更新检查 ────────────────────────────────────────────────────
  if (checkUpdate || autoUpdate) {
    console.log('🔄 正在检查 Skill 版本更新...\n');

    const needUpdate = checkUpdates(results, searchPaths);

    if (needUpdate.length === 0) {
      console.log('✅ 所有 Skill 版本均满足要求，无需更新。\n');
    } else {
      console.log(`⚠️ 发现 ${needUpdate.length} 个 Skill 需要更新：\n`);
      for (const item of needUpdate) {
        console.log(formatUpdateResult(item));
      }

      if (checkUpdate) {
        // 仅检查模式：输出提示后以 exit code 2 退出
        console.log('\n使用 --update 参数可执行更新。');
        process.exit(2);
      }

      if (autoUpdate) {
        console.log('\n🔧 开始执行 Skill 更新...\n');
        let allSuccess = true;
        for (const item of needUpdate) {
          const success = updateSkill(item, workspaceRoot);
          if (!success) {
            allSuccess = false;
            console.log(`  ⚠️ ${item.name} 更新失败，流程将继续但建议手动处理`);
          }
        }

        if (allSuccess) {
          console.log('\n✅ 所有 Skill 更新完成！');
        } else {
          console.log('\n⚠️ 部分 Skill 更新失败，请手动处理。');
        }
      }
    }
  }

  // ── 4. 当前 Skill 自身更新检查 ────────────────────────────────────────
  if (selfCheck || selfUpdate || checkUpdate || autoUpdate) {
    console.log('\n🔍 正在检查当前 Skill 自身的远端更新...\n');

    const selfResult = checkSelfUpdate();

    console.log(`  📦 Skill: ${selfResult.name}`);
    console.log(`  📍 本地版本: ${selfResult.localVersion}`);
    console.log(`  🌐 远端版本: ${selfResult.remoteVersion}`);
    console.log(`  💡 ${selfResult.reason}`);

    if (selfResult.hasUpdate) {
      console.log(`\n  🔄 发现远端有新版本可用！`);

      if (selfCheck || checkUpdate) {
        console.log('\n  使用 --self-update 参数可更新当前 Skill 到最新版本。');
        if (!checkUpdate && !autoUpdate) {
          // 仅 --self-check 模式，以 exit code 2 提示有更新
          process.exit(2);
        }
      }

      if (selfUpdate || autoUpdate) {
        console.log('\n🔧 开始更新当前 Skill...\n');
        const success = updateSelfSkill(workspaceRoot);
        if (success) {
          console.log('\n✅ 当前 Skill 更新完成！');
          // 更新后重新同步 skills.json
          syncSkillsJson(workspaceRoot);
        } else {
          console.log('\n❌ 当前 Skill 更新失败，请手动执行: mtskills pull fe-rd-workflow');
        }
      }
    } else {
      console.log('\n  ✅ 当前 Skill 已是最新版本。');
    }
  }

  // ── 5. Node 版本警告 ───────────────────────────────────────────────────
  const currentMajor = Number(process.versions.node.split('.')[0]);
  if (currentMajor < REQUIRED_NODE_MAJOR) {
    console.log(
      `\n⚠️ 当前 Node.js 版本为 ${process.versions.node}，低于推荐的 ${REQUIRED_NODE_MAJOR}。` +
      '如需执行安装，请先切换 Node 版本或使用 --install 让脚本自动尝试切换。'
    );
  }

  console.log('\n流程继续执行。');
}

main();
