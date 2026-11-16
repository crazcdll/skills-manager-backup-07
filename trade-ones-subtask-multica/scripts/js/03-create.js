(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // 当前批次（≤4 个任务），由 run_js.py 切片注入
  const ALL_TASKS         = __TASKS__;
  const WEEK_NUM          = __WEEK_NUM__;
  const WEEK_ITERATION_ID = __WEEK_ITERATION_ID__;

  // ── 创建前实时查已有子任务（只看当前需求的直接子任务）───────────────
  const uniqueIssueIds = [...new Set(ALL_TASKS.map(t => t.issueId))];
  const freshExistingMap = {};
  for (const issueId of uniqueIssueIds) {
    const body = {
      issueId,
      query: [{ type: 'TERMS', fieldType: 'component_parent', field: 'parentId', valueList: [issueId], group: 1 }],
      displayFieldList: ['id', 'name', 'assigned', 'iterationId'],
      isParentsInTreeMode: true
    };
    const r = await fetch(
      'https://ones.sankuai.com/api/proxy/filter/query/listpage/issue?projectId=&type=DEVTASK&cn=1&sn=100&displayType=REQUIREMENT_SON_DEVTASK&expanded=false&state=ALL&issueAssociateType=REQUIREMENT_SON_DEVTASK&archiveSpaceFilter=false&includeOtherFatherAndSon=false',
      { method: 'POST', headers: { 'Content-Type': 'application/json;charset=UTF-8', Accept: 'application/json' }, body: JSON.stringify(body) }
    );
    const d = await r.json();
    freshExistingMap[issueId] = (d.data?.items || []).map(c => ({
      id: c.id?.value,
      name: c.name?.displayValue,
      assignedMisId: c.assigned?.value,
      iterationId: c.iterationId?.value
    }));
  }

  const results = [];
  for (const t of ALL_TASKS) {
    // ── 三层重复检测：本周迭代 → W{n}- 前缀 → 任务名完全一致 ──────────
    const children = freshExistingMap[t.issueId] || [];
    let existingId = null, skipReason = null;
    for (const c of children) {
      if ((c.assignedMisId || '').toLowerCase() !== (t.uid || '').toLowerCase()) continue;
      if (WEEK_ITERATION_ID && String(c.iterationId) === String(WEEK_ITERATION_ID)) {
        existingId = c.id; skipReason = '本周iterationId匹配'; break;
      }
      if (!c.iterationId && c.name?.startsWith('W' + WEEK_NUM + '-')) {
        existingId = c.id; skipReason = '任务名前缀匹配'; break;
      }
      if (c.name === t.taskTitle) {
        existingId = c.id; skipReason = '任务名完全匹配'; break;
      }
    }
    if (existingId) {
      results.push({ ...t, newId: existingId, status: '已存在', skipReason, isSuccess: true });
      continue;
    }

    // ── 创建：parentId 必须是排期表里的需求 ID，不得换成父需求 ────────
    const createBody = {
      projectId:        t.projectId,
      type:             'DEVTASK',
      parentId:         t.issueId,
      assigned:         t.uid,
      priority:         2,
      subtypeId:        t.subtypeId,
      customField23767: t.pmisId,
      name:             t.taskTitle,
      iterationId:      t.iterationId,
      expectTime:       t.duration,
      unit:             'date',
      expectStart:      t.expectStart,
      expectClose:      t.expectClose
    };
    const cr = await fetch('https://ones.sankuai.com/api/proxy/fastIssue', {
      method: 'POST',
      headers: { Accept: 'application/json, text/plain, */*', 'Content-Type': 'application/json;charset=UTF-8' },
      body: JSON.stringify(createBody)
    });
    const cd = await cr.json();
    const newId = cd.data?.id?.value;

    // 继承需求标签（创建成功后等 200ms 再 PUT）
    let labelCode = null;
    if (newId && t.labelIds?.length) {
      await sleep(200);
      const lr = await fetch(`https://ones.sankuai.com/api/proxy/issue/${newId}`, {
        method: 'PUT',
        headers: { Accept: 'application/json, text/plain, */*', 'Content-Type': 'application/json;charset=UTF-8' },
        body: JSON.stringify({ labels: t.labelIds })
      });
      labelCode = (await lr.json()).code;
    }

    // fastIssue 成功返回 201，也视为成功
    const isSuccess = (cd.code === 200 || cd.code === 201 || newId != null);
    results.push({
      ...t, newId,
      status: isSuccess ? '新创建' : `创建失败(${cd.code})`,
      errMsg: isSuccess ? null : (cd.message || cd.msg || ''),
      isSuccess, labelCode
    });
    await sleep(500);
  }

  return JSON.stringify(results);
})()
