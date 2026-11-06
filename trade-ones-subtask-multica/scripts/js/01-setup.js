(async () => {
  const TASKS = __TASKS__;
  if (!TASKS || !TASKS.length) return JSON.stringify({ error: 'TASKS 为空，没有可创建的需求' });

  const uniqueIssues = [...new Map(TASKS.map(t => [t.issueId, t])).values()];
  const uniqueProjects = [...new Set(TASKS.map(t => t.projectId))];
  const errors = [];

  // ── 需求详情：名称 / 迭代 / 标签 / pmis ─────────────────────────────
  const issueDetails = await Promise.all(uniqueIssues.map(async t => {
    try {
      const r = await fetch(
        `https://ones.sankuai.com/api/proxy/issue/${t.issueId}?issueType=REQUIREMENT&projectId=${t.projectId}`,
        { headers: { Accept: 'application/json' } }
      );
      const d = await r.json();
      const it = d.data || {};
      if (!it.name) {
        errors.push({ kind: 'issue', issueId: t.issueId, code: d.code, msg: d.message || d.msg || 'no data' });
        return { issueId: t.issueId };
      }
      return {
        issueId: t.issueId,
        name: it.name?.displayValue || it.name,
        iterationId: it.iterationId,              // { id, value, displayValue }
        iterationName: it.iterationId?.displayValue,
        labels: it.labels?.value,                 // [{ id, displayValue }]
        customField23767: it.customField23767,    // { id, value }
        priority: it.priority?.value
      };
    } catch (e) {
      errors.push({ kind: 'issue', issueId: t.issueId, msg: String(e) });
      return { issueId: t.issueId };
    }
  }));
  const issueMap = Object.fromEntries(issueDetails.map(d => [d.issueId, d]));

  // ── subtypeId：按 projectId 取默认 DEVTASK 子类型 ───────────────────
  const subtypeResults = await Promise.all(uniqueProjects.map(async pid => {
    try {
      const r = await fetch(
        `https://ones.sankuai.com/api/proxy/projects/${pid}/subtype/list?objectType=DEVTASK&forCreate=true`
      );
      const d = await r.json();
      const items = d.data?.items || [];
      const def = items.find(s => s.active && s.isDefault) || items.find(s => s.active);
      if (!def) errors.push({ kind: 'subtype', projectId: pid, code: d.code, msg: 'no active subtype' });
      return { projectId: pid, subtypeId: def?.id };
    } catch (e) {
      errors.push({ kind: 'subtype', projectId: pid, msg: String(e) });
      return { projectId: pid };
    }
  }));
  const subtypeMap = Object.fromEntries(subtypeResults.map(s => [s.projectId, s.subtypeId]));

  // ── 迭代列表：用来按排期表头日期定位「本周迭代」 ────────────────────
  // 需求可能已被挪到下周迭代，只看需求自身迭代会匹配错周、导致重复创建
  const iterationResults = await Promise.all(uniqueProjects.map(async pid => {
    try {
      const r = await fetch(`https://ones.sankuai.com/api/proxy/projects/${pid}/iterations`, {
        headers: { Accept: 'application/json' }
      });
      const d = await r.json();
      const items = (d.data?.items || []).map(i => ({
        id: i.id?.value ?? i.id,
        name: i.name,
        start: i.startTime,
        end: i.endTime,
        active: i.active !== false
      }));
      if (!items.length) errors.push({ kind: 'iteration', projectId: pid, code: d.code, msg: '迭代列表为空' });
      return { projectId: pid, items };
    } catch (e) {
      errors.push({ kind: 'iteration', projectId: pid, msg: String(e) });
      return { projectId: pid, items: [] };
    }
  }));
  const iterations = Object.fromEntries(iterationResults.map(x => [x.projectId, x.items]));

  return JSON.stringify({ issueMap, subtypeMap, iterations, errors });
})()
