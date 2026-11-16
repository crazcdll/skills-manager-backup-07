(async () => {
  const TASKS       = __TASKS__;
  const DATES       = __DATES__;
  const ISSUE_MAP   = __ISSUE_MAP__;
  const SUBTYPE_MAP = __SUBTYPE_MAP__;
  const ITERATIONS  = __ITERATIONS__;

  let scheduleMonth = null, scheduleDay = null;
  if (DATES && DATES.length > 2) {
    const m = DATES[2].match(/(\d+)\.(\d+)/);
    if (m) { scheduleMonth = parseInt(m[1], 10); scheduleDay = parseInt(m[2], 10); }
  }

  let matchedIteration = null, weekIterationSource = '';

  // ── 首选：项目迭代列表里起始日 == 排期表头第一天的那条「单周」迭代 ──
  // 需求可能已提前挪到下周迭代，所以不能只看需求自身迭代
  if (scheduleMonth && scheduleDay) {
    const projectOrder = Object.keys(ITERATIONS)
      .sort((a, b) => (ITERATIONS[b] || []).length - (ITERATIONS[a] || []).length);
    for (const pid of projectOrder) {
      const candidates = (ITERATIONS[pid] || []).filter(it => {
        if (!it.active || !it.start) return false;
        const d = new Date(it.start);
        return d.getMonth() + 1 === scheduleMonth && d.getDate() === scheduleDay;
      });
      if (!candidates.length) continue;
      const single = candidates.filter(it => !/双周|专用/.test(it.name || ''));
      const hit = (single.length ? single : candidates)
        .sort((a, b) => (a.end - a.start) - (b.end - b.start))[0];
      matchedIteration = { id: hit.id, name: hit.name };
      weekIterationSource = 'iteration-list';
      break;
    }
  }

  // ── 兜底：需求自身迭代里日期范围覆盖排期第一天的那条 ─────────────────
  if (!matchedIteration) {
    const allIterations = Object.values(ISSUE_MAP)
      .filter(v => v && v.iterationName && v.iterationId?.value)
      .map(v => ({ name: v.iterationName, id: v.iterationId.value }))
      .filter((v, i, arr) => arr.findIndex(x => x.id === v.id) === i);
    for (const iter of allIterations) {
      const dm = iter.name.match(/[（(](\d{2})(\d{2})-(\d{2})(\d{2})/);
      if (dm && scheduleMonth && scheduleDay) {
        const iterStartMd = parseInt(dm[1], 10) * 100 + parseInt(dm[2], 10);
        const iterEndMd   = parseInt(dm[3], 10) * 100 + parseInt(dm[4], 10);
        const schedMd     = scheduleMonth * 100 + scheduleDay;
        if (schedMd >= iterStartMd && schedMd <= iterEndMd) {
          matchedIteration = iter;
          weekIterationSource = 'issue-iteration';
          break;
        }
      }
    }
  }

  // ── 最后兜底：取需求里出现次数最多的迭代 ─────────────────────────────
  if (!matchedIteration) {
    const allIterations = Object.values(ISSUE_MAP)
      .filter(v => v && v.iterationName && v.iterationId?.value)
      .map(v => ({ name: v.iterationName, id: v.iterationId.value }))
      .filter((v, i, arr) => arr.findIndex(x => x.id === v.id) === i);
    const counts = {};
    for (const v of Object.values(ISSUE_MAP)) {
      const id = v?.iterationId?.value;
      if (id) counts[id] = (counts[id] || 0) + 1;
    }
    const topId = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
    matchedIteration = allIterations.find(i => String(i.id) === String(topId)) || allIterations[0];
    weekIterationSource = 'most-frequent';
  }
  if (!matchedIteration) {
    return JSON.stringify({ error: '所有需求的迭代都为空，无法确定本周迭代与周次，请先把需求排进迭代' });
  }

  const iterationName  = matchedIteration.name;
  const weekIterationId = matchedIteration.id;
  const weekNum = iterationName.match(/W(\d+)/)?.[1] || '0';
  const year    = parseInt(iterationName.match(/(\d{4})W/)?.[1] || '0', 10);

  const iterDateMatch  = iterationName.match(/[（(](\d{2})(\d{2})-/);
  const iterStartMonth = iterDateMatch ? parseInt(iterDateMatch[1], 10) : 1;
  const iterStartDay   = iterDateMatch ? parseInt(iterDateMatch[2], 10) : 1;
  const iterStartYear  = (iterStartMonth === 12 && scheduleMonth === 1) ? year + 1 : year;

  const mm = n => String(n).padStart(2, '0');
  function colToDate(colIndex) {
    const offset = Math.max(colIndex - 2, 0);
    const d = new Date(iterStartYear, iterStartMonth - 1, iterStartDay);
    let count = 0;
    while (count < offset) {
      d.setDate(d.getDate() + 1);
      if (d.getDay() !== 0 && d.getDay() !== 6) count++;
    }
    while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 1);
    return { month: d.getMonth() + 1, day: d.getDate() };
  }
  // 表头带日期时（如「周一 10.26」）直接用表头，比按迭代推算更准
  function headerDate(colIndex) {
    if (!DATES || !DATES[colIndex]) return null;
    const m = DATES[colIndex].match(/(\d{1,2})\.(\d{1,2})/);
    if (!m) return null;
    const month = parseInt(m[1], 10), day = parseInt(m[2], 10);
    const y = (iterStartMonth === 12 && month === 1) ? iterStartYear : year;
    return { month, day, year: y };
  }
  function resolveDate(colIndex) {
    const h = headerDate(colIndex);
    return h ? h : { ...colToDate(colIndex), year: iterStartYear };
  }

  // ── 组装任务列表（与即将 fastIssue 创建的任务集合一致）───────────────
  const allTasks = [];
  const invalid = [];
  for (const t of TASKS) {
    const issue = ISSUE_MAP[t.issueId] || {};
    if (!issue.name) { invalid.push({ ...t, reason: '需求详情查询失败' }); continue; }

    const startDate = resolveDate(t.colStart + 2);
    const endDate   = resolveDate(t.colEnd + 2);
    const sameDay   = startDate.month === endDate.month && startDate.day === endDate.day;
    const dateRange = sameDay
      ? `${startDate.month}.${startDate.day}`
      : `${startDate.month}.${startDate.day}-${endDate.month}.${endDate.day}`;
    const startY = startDate.year || iterStartYear;
    const endY   = endDate.year   || iterStartYear;

    allTasks.push({
      issueId:  t.issueId,
      projectId: t.projectId,
      uid:      t.uid,
      empId:    t.empId,
      person:   t.name,
      duration: t.duration,
      taskTitle: `W${weekNum}-${issue.name}`,
      dateRange,
      expectStart: new Date(`${startY}-${mm(startDate.month)}-${mm(startDate.day)}T00:00:00+08:00`).getTime(),
      expectClose: new Date(`${endY}-${mm(endDate.month)}-${mm(endDate.day)}T23:59:59.999+08:00`).getTime(),
      // 任务挂到「本周迭代」：需求可能已被挪到下周，用需求自身迭代会和排期日期不符
      iterationId:    weekIterationId,
      reqIterationId: issue.iterationId?.value,
      weekIterationId,
      subtypeId:      SUBTYPE_MAP[t.projectId],
      pmisId:         issue.customField23767?.value,
      labelIds:       (issue.labels || []).map(l => l.id),
      labelNames:     (issue.labels || []).map(l => l.displayValue).join(', '),
      reqName:        issue.name
    });
  }

  // ── 迭代一致性检测（仅提示，不阻塞）────────────────────────────────
  const iterationMismatches = Object.entries(ISSUE_MAP)
    .filter(([, v]) => v?.iterationId?.value && String(v.iterationId.value) !== String(weekIterationId))
    .map(([issueId, v]) => ({
      issueId: parseInt(issueId, 10),
      issueName: v.name,
      issueIterationId: v.iterationId?.value,
      issueIterationName: v.iterationName,
      weekIterationId,
      weekIterationName: iterationName
    }));

  // ── 每人 PD 汇总（创建前 >5pd 需确认）───────────────────────────────
  const pdByPerson = {};
  for (const t of allTasks) {
    const k = t.uid || t.person;
    if (!pdByPerson[k]) pdByPerson[k] = { person: t.person, uid: t.uid, pd: 0, tasks: 0 };
    pdByPerson[k].pd += Number(t.duration) || 0;
    pdByPerson[k].tasks += 1;
  }
  const personPd = Object.values(pdByPerson)
    .map(p => ({ ...p, pd: Math.round(p.pd * 100) / 100, over: p.pd > 5 }))
    .sort((a, b) => b.pd - a.pd);

  return JSON.stringify({
    weekNum, year, iterationName, weekIterationId, weekIterationSource,
    hasHeaderDates: (DATES || []).some(d => /周[一二三四五]/.test(d) && /\d+\.\d+/.test(d)),
    allTasks, invalid, iterationMismatches, personPd,
    totalPd: Math.round(allTasks.reduce((s, t) => s + (Number(t.duration) || 0), 0) * 100) / 100
  });
})()
