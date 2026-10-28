#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IntakeContext —— 信息收集结果（workspace 级状态）读写。

位置：`$STATE/run/tasks/<task_id>/intake.json`（**workspace 级 = 该子 Agent 私有**）。
它承载的是「**输入**」而非「run 产物」：同一个 task 内多个 run 复用同一份，
且不受 run 级清理影响。

放在 `shared/`（而非 provisioning）：`execution/` 层的消费方
（flow_init / steps_generator / placeholder_resolver）需要读它，
而 `execution → provisioning` 是禁止的跨层依赖（架构守卫规则 7）。

并发：写入走 `write_json_atomic`（tmp + os.replace），读容错为 `{}`。
"""
import time

from shared.json_utils import read_json, write_json_atomic
from shared.paths import get_active_task, intake_path

_VERSION = 1


class IntakeContext:
    """单个 task 的收集上下文（惰性加载 + 原子写回）。"""

    def __init__(self, task_id: str = None):
        self.task_id = str(task_id or get_active_task()).strip()
        self._data = None

    @property
    def path(self) -> str:
        return intake_path(self.task_id)

    def load(self) -> dict:
        if self._data is None:
            raw = read_json(self.path, default={})
            data = raw if isinstance(raw, dict) else {}
            data.setdefault("version", _VERSION)
            data.setdefault("task_id", self.task_id)
            answers = data.get("answers")
            data["answers"] = dict(answers) if isinstance(answers, dict) else {}
            seeds = data.get("pending_seeds")
            data["pending_seeds"] = dict(seeds) if isinstance(seeds, dict) else {}
            pinned = data.get("pinned")
            data["pinned"] = list(pinned) if isinstance(pinned, list) else []
            self._data = data
        return self._data

    def save(self):
        data = self.load()
        data["version"] = _VERSION
        data["task_id"] = self.task_id
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        write_json_atomic(self.path, data)

    # ── 答案读写（presence == resolved）──────────────────────────
    @property
    def answers(self) -> dict:
        return self.load()["answers"]

    @property
    def pending_seeds(self) -> dict:
        """已预置但**依赖尚未就绪**的值（{id: value}）。

        语义：`input-seed` 收到的值若其 depends_on 只是「依赖未回答」（而非
        谓词为假），先挂起于此，待依赖就绪后由 driver 自动落値 —— 既保证用户
        已给的值不外泄到不适用环境，又保证不会被重复提问。
        """
        return self.load()["pending_seeds"]

    def get(self, qid: str, default=None):
        return self.answers.get(qid, default)

    def is_resolved(self, qid: str) -> bool:
        return qid in self.answers

    def resolve(self, qid: str, value):
        """写入一条答案并落盘（可空值：表示"已回答但为空"）。"""
        self.answers[qid] = value
        self.save()

    @property
    def pinned(self) -> set:
        """被用户显式覆盖过的**派生题** id 集合（引擎不再重算这些字段）。

        语义：派生值默认是「当前输入的纯函数」，每轮重算；但用户经 `input-seed`
        显式给了值的派生题（如 `resource_mis` 允许改用其他 MIS）属于「用户覆盖」，
        必须尊重，不得被重算冲掉。
        """
        return set(self.load()["pinned"])

    def pin(self, qid: str):
        """标记某派生题已被用户显式覆盖（幂等）。"""
        data = self.load()
        pinned = data["pinned"]
        if qid not in pinned:
            pinned.append(str(qid))
            self.save()

    def invalidate(self, qids) -> list:
        """级联失效：移除「已落库答案」「挂起预置值」以及对应的覆盖标记。

        用于环境/依赖变更后的失效传播（如 `env_type` 由 A 切到 C 后，仅线上
        适用的 `ptest` 必须一并清除），避免旧值残留并被 `build_env_from_intake`
        重新带入 env。仅在有变更时落盘；返回实际移除的 id 列表（供调用方留痕）。
        """
        data = self.load()
        pinned = data["pinned"]
        removed = []
        for qid in qids:
            if qid in self.answers:
                self.answers.pop(qid, None)
                removed.append(qid)
            if qid in self.pending_seeds:
                self.pending_seeds.pop(qid, None)
                removed.append(qid)
            if qid in pinned:
                pinned.remove(qid)
        if removed:
            self.save()
        return removed

    # ── 下发指针（input-next / input-answer 的硬门禁状态）──────────
    #
    # 语义：`input-next` 每下发一题就把该题 id 记为「当前下发指针」；
    # `input-answer` 只接受「指针所指的那一题」。这样即使 AI 试图批量/跳答，
    # 也会因 id 不匹配被直接拒绝 —— 把「一题一答」从文档约定变成机制事实。

    @property
    def _dispatch(self) -> dict:
        dispatch = self.load().get("dispatch")
        return dispatch if isinstance(dispatch, dict) else {}

    def dispatched_id(self):
        """当前已下发、尚未提交的题目 id（无则 None）。"""
        return self._dispatch.get("id") or None

    def set_dispatched(self, qid: str):
        """记录当前下发指针（input-next 调用）。"""
        data = self.load()
        data["dispatch"] = {"id": str(qid), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.save()

    def clear_dispatched(self):
        """清空下发指针（题目提交完成 / 收集结束）。"""
        data = self.load()
        if data.get("dispatch"):
            data["dispatch"] = {}
            self.save()


# ═══════════════════════════════════════════════════════════════════
# 便捷函数（供 execution 层消费方使用）
# ═══════════════════════════════════════════════════════════════════

def read_intake(task_id: str = None) -> dict:
    """读取本 workspace 的收集答案（不存在时为空 dict）。"""
    return IntakeContext(task_id).answers


def update_intake(answers: dict, task_id: str = None):
    """合并写入若干答案（不覆盖未涉及字段）。"""
    ctx = IntakeContext(task_id)
    ctx.answers.update(dict(answers or {}))
    ctx.save()
