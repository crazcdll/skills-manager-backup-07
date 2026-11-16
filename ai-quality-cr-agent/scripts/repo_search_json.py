#!/usr/bin/env python3
"""Run the bundled search CLI with isolated data and diagnostic files."""

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile


class SearchInvocationError(RuntimeError):
    pass


def _reject_constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


def _validate_results(data):
    if not isinstance(data, list):
        raise ValueError("Search JSON must be an array")
    for result in data:
        if (not isinstance(result, dict)
                or not isinstance(result.get("file"), str) or not result["file"]
                or not isinstance(result.get("hits"), list)):
            raise ValueError("Each search result must contain file and hits")
        for hit in result["hits"]:
            if (not isinstance(hit, dict) or type(hit.get("line")) is not int
                    or hit["line"] <= 0 or not isinstance(hit.get("text"), str)):
                raise ValueError("Each search hit must contain a positive line and text")


def run_search(run_dir, search_args, timeout=120):
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_dir():
        raise SearchInvocationError("--run-dir must be an existing task-owned directory")
    if not math.isfinite(timeout) or timeout <= 0:
        raise SearchInvocationError("--timeout must be positive and finite")

    # Each invocation owns its files, including failed attempts and retries.
    query_dir = Path(tempfile.mkdtemp(prefix="search_", dir=run_dir))
    stdout_path = query_dir / "stdout.json"
    stderr_path = query_dir / "stderr.log"
    command = [sys.executable, str(Path(__file__).resolve().with_name("repo_search.py")),
               *search_args, "--json"]
    try:
        with stdout_path.open("x", encoding="utf-8") as output, \
                stderr_path.open("x", encoding="utf-8") as errors:
            process = subprocess.run(command, stdout=output, stderr=errors,
                                     shell=False, check=False, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SearchInvocationError(
            f"Search timed out after {timeout}s; diagnostics: {query_dir}"
        ) from None
    except OSError as exc:
        raise SearchInvocationError(
            f"Search could not run ({type(exc).__name__}); diagnostics: {query_dir}"
        ) from None
    if process.returncode != 0:
        raise SearchInvocationError(
            f"Search failed (exit {process.returncode}); diagnostics: {query_dir}"
        )

    try:
        with stdout_path.open(encoding="utf-8") as output:
            data = json.load(output, parse_constant=_reject_constant)
        _validate_results(data)
    except (OSError, ValueError) as exc:
        location = (f" at line {exc.lineno}, column {exc.colno}"
                    if isinstance(exc, json.JSONDecodeError) else "")
        raise SearchInvocationError(
            f"Search returned invalid JSON/results{location}; diagnostics: {query_dir}"
        ) from None

    result_path = query_dir / "result.json"
    stdout_path.rename(result_path)
    # 反查埋点：追加写入 layer2_stats.jsonl（repo 仓反查命中统计，供
    # publish_results 汇总 contextHitFiles/contextHitLines，写 cr_result_json。
    # 零 LLM 参与，确定性采集；失败不影响搜索主流程。）
    try:
        hit_files = len(data)
        hit_lines = sum(len(r.get("hits", [])) for r in data)
        stats = {"resultFile": str(result_path), "hitFiles": hit_files, "hitLines": hit_lines}
        with (run_dir / "layer2_stats.jsonl").open("a", encoding="utf-8") as stats_f:
            stats_f.write(json.dumps(stats, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return result_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Existing CR_RUN_DIR for this review")
    parser.add_argument("--timeout", type=float, default=120, help="Total search timeout in seconds")
    parser.add_argument("search_args", nargs=argparse.REMAINDER,
                        help="Arguments for repo_search.py after --; --json is added automatically")
    args = parser.parse_args(argv)
    search_args = args.search_args
    if search_args[:1] == ["--"]:
        search_args = search_args[1:]
    if not search_args:
        parser.error("Pass repo_search.py arguments after --")
    try:
        result_path = run_search(args.run_dir, search_args, args.timeout)
    except (SearchInvocationError, OSError) as exc:
        print(f"[repo_search_json] {exc}", file=sys.stderr)
        return 1
    # stdout is a file path, never a mixture of search JSON and progress logs.
    print(result_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
