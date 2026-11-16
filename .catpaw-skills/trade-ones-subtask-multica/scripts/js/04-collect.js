(async () => {
  // 所有批次结果（按创建顺序拼接），由 run_js.py 注入
  const RESULTS            = __RESULTS__;
  const WEEK_ITERATION_ID  = __WEEK_ITERATION_ID__;

  const byIssue = {};
  for (const r of RESULTS) {
    if (!r.newId) continue;
    (byIssue[r.issueId] = byIssue[r.issueId] || []).push(r);
  }

  // 逐需求回查直接子任务，确认本轮每条任务真的落在 ONES 上
  const verified = [];
  for (const [issueId, rows] of Object.entries(byIssue)) {
    const body = {
      issueId: Number(issueId),
      query: [{ type: 'TERMS', fieldType: 'component_parent', field: 'parentId', valueList: [Number(issueId)], group: 1 }],
      displayFieldList: ['id', 'name', 'assigned', 'iterationId', 'expectStart', 'expectClose'],
      isParentsInTreeMode: true
    };
    const r = await fetch(
      'https://ones.sankuai.com/api/proxy/filter/query/listpage/issue?projectId=&type=DEVTASK&cn=1&sn=100&displayType=REQUIREMENT_SON_DEVTASK&expanded=false&state=ALL&issueAssociateType=REQUIREMENT_SON_DEVTASK&archiveSpaceFilter=false&includeOtherFatherAndSon=false',
      { method: 'POST', headers: { 'Content-Type': 'application/json;charset=UTF-8', Accept: 'application/json' }, body: JSON.stringify(body) }
    );
    const d = await r.json();
    const live = (d.data?.items || []).map(c => ({
      id: c.id?.value,
      name: c.name?.displayValue,
      assignedMisId: c.assigned?.value,
      iterationId: c.iterationId?.value
    }));
    const liveIds = new Set(live.map(c => String(c.id)));
    for (const row of rows) {
      const hit = live.find(c => String(c.id) === String(row.newId));
      verified.push({
        issueId: Number(issueId),
        projectId: row.projectId,
        newId: row.newId,
        taskTitle: row.taskTitle,
        person: row.person,
        uid: row.uid,
        empId: row.empId || '',
        duration: row.duration,
        dateRange: row.dateRange,
        labelNames: row.labelNames || '',
        status: row.status,
        skipReason: row.skipReason || null,
        labelCode: row.labelCode ?? null,
        found: liveIds.has(String(row.newId)),
        liveAssignedMisId: hit?.assignedMisId || null,
        liveIterationId: hit?.iterationId || null,
        liveName: hit?.name || null
      });
    }
  }

  const counts = verified.reduce((acc, v) => {
    acc.total += 1;
    if (v.status === '已存在') acc.existing += 1;
    else if (v.found) acc.created += 1;
    else acc.missing += 1;
    return acc;
  }, { total: 0, created: 0, existing: 0, missing: 0 });

  return JSON.stringify({
    verified, counts,
    weekIterationId: WEEK_ITERATION_ID,
    notFound: verified.filter(v => !v.found)
  });
})()
