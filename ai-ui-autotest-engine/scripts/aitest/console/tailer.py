#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增量 tail：把 run 的事件流 / 步骤流 / CLI 遥测流按行读出。

唯一状态是每个文件的 `(inode, offset)`：
  · 新文件 / 被截断 / 轮转 → offset 归零并全量回放（让后打开的页面看到完整历史）；
  · 文件被 post-clean 删除 → 自动剔除状态。
"""
import json
import os


class Tailer:
    def __init__(self):
        self._files = {}   # path -> {"inode": int, "offset": int}

    def _new_lines(self, path):
        try:
            st = os.stat(path)
        except OSError:
            self._files.pop(path, None)
            return []
        inode = getattr(st, "st_ino", 0)
        state = self._files.get(path)
        if state is None or state["inode"] != inode or st.st_size < state["offset"]:
            state = {"inode": inode, "offset": 0}
        self._files[path] = state
        out = []
        try:
            with open(path, encoding="utf-8") as f:
                f.seek(state["offset"])
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
                state["offset"] = f.tell()
        except OSError:
            pass
        return out

    def poll(self, runs):
        """返回 [(source, task, run, case_index, record, device)，...]。

        source ∈ {"event", "step"}。
        """
        results = []
        for r in runs:
            rundir = r.get("run_dir")
            if not rundir:
                continue
            device = r.get("device_serial", "")
            ep = os.path.join(rundir, "audit", "run-events.jsonl")
            for rec in self._new_lines(ep):
                results.append(("event", r["task"], r["run"], None, rec, device))
            cases_root = os.path.join(rundir, "cases")
            try:
                names = sorted(n for n in os.listdir(cases_root)
                               if os.path.isdir(os.path.join(cases_root, n)))
            except OSError:
                names = []
            for idx, name in enumerate(names):
                sp = os.path.join(cases_root, name, "steps.jsonl")
                for rec in self._new_lines(sp):
                    results.append(("step", r["task"], r["run"], idx, rec, device))
        return results

    def poll_file(self, path):
        """读取任意 append-only JSONL（用于 CLI 遥测流）。"""
        return self._new_lines(path)
