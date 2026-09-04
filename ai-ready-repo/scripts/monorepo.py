#!/usr/bin/env python3
"""Discover manifest-declared mono-repo members and aggregate their scores."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Callable


class MonoRepoError(ValueError):
    """The mono-repo manifest or member score set is invalid."""


DIM_KEYS = (
    "dim1a",
    "dim1b",
    "dim2",
    "dim3",
    "dim4",
    "dim5",
    "dim6",
    "dim7",
    "dim8",
    "dim9",
    "dim10",
)


def _workspace_patterns_from_package_json(path: Path) -> list[str] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    workspaces = data.get("workspaces")
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages")
    if workspaces is None:
        return None
    if not isinstance(workspaces, list) or not all(isinstance(item, str) for item in workspaces):
        raise MonoRepoError("package.json#workspaces 必须是字符串数组或包含 packages 字符串数组")
    return workspaces


def _workspace_patterns_from_pnpm(path: Path) -> list[str] | None:
    if not path.is_file():
        return None
    try:
        import yaml
    except ImportError as exc:
        raise MonoRepoError("解析 pnpm-workspace.yaml 需要安装 PyYAML") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    packages = data.get("packages") if isinstance(data, dict) else None
    if not isinstance(packages, list) or not all(isinstance(item, str) for item in packages):
        raise MonoRepoError("pnpm-workspace.yaml#packages 必须是字符串数组")
    return packages


def _modules_from_maven(path: Path) -> list[str] | None:
    if not path.is_file():
        return None
    root = ET.parse(path).getroot()
    modules = [
        (node.text or "").strip()
        for node in root.findall(".//{*}modules/{*}module")
        if (node.text or "").strip()
    ]
    return modules or None


def _modules_from_gradle(path: Path) -> list[str] | None:
    if not path.is_file():
        return None
    text = re.sub(r"//.*", "", path.read_text(encoding="utf-8"))
    argument_blocks = re.findall(r"(?ms)^\s*include\s*\((.*?)\)", text)
    argument_blocks.extend(re.findall(r"(?m)^\s*include\s+([^\n]+)", text))
    modules: list[str] = []
    for block in argument_blocks:
        for match in re.finditer(r"(['\"])(.*?)\1", block):
            module = match.group(2).strip().strip(":").replace(":", "/")
            if module:
                modules.append(module)
    return modules or None


def _safe_relative_member(root: Path, candidate: Path) -> str:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise MonoRepoError(f"成员位于仓库根目录之外: {candidate}") from exc
    if relative == Path("."):
        raise MonoRepoError("mono-repo 根目录不能作为子仓库成员")
    if not resolved.is_dir():
        raise MonoRepoError(f"声明的成员目录不存在: {relative.as_posix()}")
    return relative.as_posix()


def _expand_workspace_patterns(root: Path, patterns: list[str]) -> list[str]:
    included: set[str] = set()
    excluded: set[str] = set()
    for raw_pattern in patterns:
        is_exclusion = raw_pattern.startswith("!")
        pattern = raw_pattern[1:] if is_exclusion else raw_pattern
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise MonoRepoError(f"成员位于仓库根目录之外: {raw_pattern}")
        matches = [path for path in root.glob(pattern) if path.is_dir()]
        if not matches and not is_exclusion:
            raise MonoRepoError(f"工作区模式未匹配任何目录: {raw_pattern}")
        target = excluded if is_exclusion else included
        target.update(_safe_relative_member(root, path) for path in matches)
    return sorted(included - excluded)


def discover_members(root: Path) -> dict:
    """Return the declared first-level logical repositories under ``root``."""
    root = root.resolve()
    pnpm = _workspace_patterns_from_pnpm(root / "pnpm-workspace.yaml")
    if pnpm is not None:
        members = _expand_workspace_patterns(root, pnpm)
        if not members:
            raise MonoRepoError("pnpm-workspace.yaml 没有声明任何成员")
        return {"is_monorepo": True, "manifest": "pnpm-workspace.yaml", "members": members}

    package = _workspace_patterns_from_package_json(root / "package.json")
    if package is not None:
        members = _expand_workspace_patterns(root, package)
        if not members:
            raise MonoRepoError("package.json#workspaces 没有声明任何成员")
        return {"is_monorepo": True, "manifest": "package.json#workspaces", "members": members}

    maven = _modules_from_maven(root / "pom.xml")
    if maven is not None:
        members = sorted({_safe_relative_member(root, root / item) for item in maven})
        return {"is_monorepo": bool(members), "manifest": "pom.xml#modules", "members": members}

    for filename in ("settings.gradle.kts", "settings.gradle"):
        gradle = _modules_from_gradle(root / filename)
        if gradle is not None:
            members = sorted({_safe_relative_member(root, root / item) for item in gradle})
            return {
                "is_monorepo": bool(members),
                "manifest": f"{filename}#include",
                "members": members,
            }

    return {"is_monorepo": False, "manifest": None, "members": []}


def level_for_score(score: float) -> str:
    if score >= 90:
        return "优秀"
    if score >= 75:
        return "良好"
    if score >= 50:
        return "及格"
    return "不及格"


def aggregate_scores(results: list[dict]) -> dict:
    """Return an equal-weight average only when every declared member succeeded."""
    if not results:
        raise MonoRepoError("没有可聚合的子仓库评分")
    failures = []
    members = []
    scores: list[Decimal] = []
    for result in results:
        path = result.get("path", "<unknown>")
        if result.get("_status") != "ok":
            failures.append(f"{path}: {result.get('_error', result.get('_status', 'unknown error'))}")
            continue
        score = result.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
            failures.append(f"{path}: score 缺失或超出 [0,100]")
            continue
        normalized = float(score)
        scores.append(Decimal(str(normalized)))
        members.append({"path": path, "score": normalized})
    if failures:
        raise MonoRepoError("子仓库评分未全部成功: " + "; ".join(failures))
    average = (sum(scores) / Decimal(len(scores))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    score = float(average)
    return {
        "score": score,
        "level": level_for_score(score),
        "member_count": len(members),
        "members": members,
    }


def compose_monorepo_result(discovery: dict, member_results: list[dict]) -> dict:
    """Build the public mono-repo score while preserving every member result."""
    aggregate = aggregate_scores(member_results)
    dimension_scores: dict[str, float] = {}
    for key in DIM_KEYS:
        values: list[Decimal] = []
        for member in member_results:
            value = member.get("dim_scores", {}).get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 100:
                raise MonoRepoError(f"{member.get('path', '<unknown>')}: dim_scores.{key} 非法")
            values.append(Decimal(str(value)))
        average = (sum(values) / Decimal(len(values))).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        dimension_scores[key] = float(average)
    return {
        "repo_type": "mono-repo",
        "score": aggregate["score"],
        "level": aggregate["level"],
        "manifest": discovery.get("manifest"),
        "member_count": aggregate["member_count"],
        "dim_scores": dimension_scores,
        "dim_notes": {},
        "highlights": [],
        "main_gaps": [],
        "members": member_results,
    }


def score_checkout(
    repo_dir: Path,
    commit: str,
    score_one: Callable[[Path, str], dict],
) -> dict:
    """Score one repository or every manifest-declared mono-repo member."""
    discovery = discover_members(repo_dir)
    if not discovery["is_monorepo"]:
        return score_one(repo_dir, commit)

    member_results: list[dict] = []
    for relative_path in discovery["members"]:
        member_path = repo_dir / relative_path
        try:
            result = dict(score_one(member_path, commit))
        except Exception as exc:  # noqa: BLE001
            result = {"_status": "error", "_error": f"{type(exc).__name__}: {exc}"}
        result["path"] = relative_path
        member_results.append(result)

    try:
        result = compose_monorepo_result(discovery, member_results)
    except MonoRepoError as exc:
        return {
            "_status": "member_error",
            "_error": str(exc),
            "repo_type": "mono-repo",
            "manifest": discovery["manifest"],
            "member_count": len(member_results),
            "members": member_results,
        }
    result["_status"] = "ok"
    return result


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI-Ready mono-repo 成员发现与分数聚合")
    subparsers = parser.add_subparsers(dest="command", required=True)
    discover = subparsers.add_parser("discover", help="发现构建清单声明的子仓库")
    discover.add_argument("--root", required=True)
    aggregate = subparsers.add_parser("aggregate", help="等权聚合全部子仓库评分")
    aggregate.add_argument("--input", required=True, help="子仓库评分 JSON 数组")
    args = parser.parse_args(argv)
    try:
        if args.command == "discover":
            payload = discover_members(Path(args.root))
        else:
            results = json.loads(Path(args.input).read_text(encoding="utf-8"))
            if not isinstance(results, list):
                raise MonoRepoError("聚合输入必须是 JSON 数组")
            payload = aggregate_scores(results)
    except (MonoRepoError, json.JSONDecodeError, ET.ParseError, OSError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
