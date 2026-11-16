#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


HIGH_VALUE_BUSINESS_DOCS = [
    "main-page.md",
    "store-state.md",
    "api-interfaces.md",
    "routing.md",
    "utils-tools.md",
    "performance.md",
    "modules-desc.md",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare a repository knowledge base against a benchmark.")
    parser.add_argument("--repo", required=True, help="Target repository root path.")
    parser.add_argument("--benchmark", help="Benchmark repository root path or knowledge path.")
    parser.add_argument(
        "--benchmark-profile",
        help="Path to a benchmark profile JSON file exported from a benchmark knowledge base.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when the target repo is below benchmark floor.",
    )
    return parser.parse_args()


def resolve_knowledge_dir(path_str: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if path.name == "knowledge":
        knowledge_dir = path
    else:
        knowledge_dir = path / "knowledge"
    if not knowledge_dir.exists() or not knowledge_dir.is_dir():
        raise SystemExit(f"Knowledge dir not found: {knowledge_dir}")
    return knowledge_dir


def load_profile(path_str: str) -> dict:
    path = Path(path_str).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise SystemExit(f"Benchmark profile not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def relative_files(base: Path) -> list[str]:
    return sorted(
        [
            str(path.relative_to(base))
            for path in base.rglob("*")
            if path.is_file() and "__pycache__" not in str(path)
        ]
    )


def files_in_dir(base: Path, dirname: str) -> list[str]:
    root = base / dirname
    if not root.exists():
        return []
    return sorted(
        [str(path.relative_to(base)) for path in root.rglob("*") if path.is_file()]
    )


def business_doc_names(base: Path) -> list[str]:
    root = base / "business"
    if not root.exists():
        return []
    return sorted([path.name for path in root.glob("*.md") if path.is_file()])


def module_doc_names(base: Path) -> list[str]:
    root = base / "modules"
    if not root.exists():
        return []
    return sorted([path.name for path in root.glob("*.md") if path.is_file()])


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def module_tokens(base: Path) -> list[str]:
    root = base / "modules"
    if not root.exists():
        return []

    tokens: list[str] = []
    for path in root.glob("*.md"):
        if not path.is_file():
            continue
        stem = normalize_text(path.stem)
        tokens.append(stem)
        try:
            first_line = path.read_text(encoding="utf-8").splitlines()[0]
            if first_line.startswith("#"):
                tokens.append(normalize_text(first_line.lstrip("# ").strip()))
        except Exception:
            pass
    return sorted(set(filter(None, tokens)))


def print_list(title: str, items: list[str]) -> None:
    print(title)
    if not items:
        print("- none")
        return
    for item in items:
        print(f"- {item}")


def capability_match_report(repo_tokens: list[str], capability_groups: list[dict]) -> tuple[list[str], list[str]]:
    matched: list[str] = []
    missing: list[str] = []

    for group in capability_groups:
        group_id = group.get("id", "unknown")
        aliases = [normalize_text(alias) for alias in group.get("aliases", [])]
        hit = False
        for token in repo_tokens:
            for alias in aliases:
                if alias and alias in token:
                    hit = True
                    break
            if hit:
                break
        if hit:
            matched.append(group_id)
        else:
            missing.append(group_id)
    return matched, missing


def compare_with_profile(repo_knowledge: Path, profile: dict, strict: bool) -> int:
    repo_files = relative_files(repo_knowledge)
    repo_business = business_doc_names(repo_knowledge)
    repo_modules = module_doc_names(repo_knowledge)
    repo_module_token_list = module_tokens(repo_knowledge)

    benchmark_name = profile.get("name", "benchmark-profile")
    benchmark_source = profile.get("source", {})
    benchmark_files = profile.get("files", [])
    benchmark_business = profile.get("business_docs", [])
    benchmark_modules = profile.get("module_docs", [])
    high_value_business = profile.get("high_value_business_docs", HIGH_VALUE_BUSINESS_DOCS)
    capability_groups = profile.get("required_module_capabilities", [])
    targets = profile.get("targets", {})
    business_docs_min = int(targets.get("business_docs_min", len(benchmark_business)))
    module_docs_floor_min = int(targets.get("module_docs_floor_min", 6))
    recommended_module_docs_min = int(
        targets.get("recommended_module_docs_min", max(module_docs_floor_min, len(benchmark_modules)))
    )
    capability_ratio_floor_min = float(targets.get("module_capability_ratio_floor_min", 0.7))

    missing_files = sorted(set(benchmark_files) - set(repo_files))
    missing_business = sorted(set(benchmark_business) - set(repo_business))
    missing_high_value_business = [
        name for name in high_value_business if name in benchmark_business and name not in repo_business
    ]

    module_count_repo = len(repo_modules)
    module_count_benchmark = len(benchmark_modules)
    module_ratio = (
        module_count_repo / module_count_benchmark if module_count_benchmark else 1.0
    )
    matched_capabilities, missing_capabilities = capability_match_report(
        repo_module_token_list, capability_groups
    )
    capability_ratio = (
        len(matched_capabilities) / len(capability_groups) if capability_groups else 1.0
    )

    print(f"Repo knowledge: {repo_knowledge}")
    print(f"Benchmark profile: {benchmark_name}")
    if benchmark_source:
        print(
            f"Benchmark source: {benchmark_source.get('repo', 'unknown')}@{benchmark_source.get('branch', 'unknown')}"
        )
    print("")
    print("Counts:")
    print(f"- repo_files={len(repo_files)}")
    print(f"- benchmark_files={len(benchmark_files)}")
    print(f"- repo_business={len(repo_business)}")
    print(f"- benchmark_business={len(benchmark_business)}")
    print(f"- repo_modules={module_count_repo}")
    print(f"- benchmark_modules={module_count_benchmark}")
    print(f"- benchmark_reference_module_ratio={module_ratio:.2f}")
    if capability_groups:
        print(f"- matched_module_capabilities={len(matched_capabilities)}")
        print(f"- required_module_capabilities={len(capability_groups)}")
        print(f"- capability_ratio={capability_ratio:.2f}")
    print("")

    print_list("Missing high-value business docs:", missing_high_value_business)
    print("")
    print_list("Missing business docs:", missing_business)
    print("")
    if capability_groups:
        print_list("Missing semantic module capabilities:", missing_capabilities)
        print("")

    target_module_count = max(module_count_repo, recommended_module_docs_min)
    print("Suggested targets:")
    print(f"- business_docs_target>={business_docs_min}")
    print(f"- modules_target>={target_module_count}")
    print("- keep benchmark high-value business docs at full parity")
    if capability_groups:
        print(f"- semantic_module_capabilities_target>={len(capability_groups)}")
    print("- use benchmark files as references, not as a copy list")
    print("- exceed benchmark in onboarding / faq / adr or module granularity")

    below_floor = (
        bool(missing_high_value_business)
        or len(repo_business) < business_docs_min
        or module_count_repo < module_docs_floor_min
        or capability_ratio < capability_ratio_floor_min
    )
    if below_floor:
        print("")
        print("Benchmark status: below floor")
    elif missing_business or module_count_repo < recommended_module_docs_min or missing_capabilities:
        print("")
        print("Benchmark status: near parity but not fully aligned")
    else:
        print("")
        print("Benchmark status: at or above parity")

    if missing_files:
        print("")
        print_list("Benchmark reference files not mirrored by name (informational only):", missing_files[:80])

    if strict and below_floor:
        return 2
    return 0


def main() -> int:
    args = parse_args()
    repo_knowledge = resolve_knowledge_dir(args.repo)
    if not args.benchmark and not args.benchmark_profile:
        raise SystemExit("Provide either --benchmark or --benchmark-profile")
    if args.benchmark and args.benchmark_profile:
        raise SystemExit("Use either --benchmark or --benchmark-profile, not both")

    if args.benchmark_profile:
        profile = load_profile(args.benchmark_profile)
        return compare_with_profile(repo_knowledge, profile, args.strict)

    benchmark_knowledge = resolve_knowledge_dir(args.benchmark)

    repo_files = relative_files(repo_knowledge)
    benchmark_files = relative_files(benchmark_knowledge)
    repo_business = business_doc_names(repo_knowledge)
    benchmark_business = business_doc_names(benchmark_knowledge)
    repo_modules = module_doc_names(repo_knowledge)
    benchmark_modules = module_doc_names(benchmark_knowledge)

    missing_files = sorted(set(benchmark_files) - set(repo_files))
    missing_business = sorted(set(benchmark_business) - set(repo_business))
    missing_high_value_business = [
        name for name in HIGH_VALUE_BUSINESS_DOCS if name in benchmark_business and name not in repo_business
    ]
    extra_business = sorted(set(repo_business) - set(benchmark_business))

    module_count_repo = len(repo_modules)
    module_count_benchmark = len(benchmark_modules)
    module_ratio = (
        module_count_repo / module_count_benchmark if module_count_benchmark else 1.0
    )

    print(f"Repo knowledge: {repo_knowledge}")
    print(f"Benchmark knowledge: {benchmark_knowledge}")
    print("")
    print("Counts:")
    print(f"- repo_files={len(repo_files)}")
    print(f"- benchmark_files={len(benchmark_files)}")
    print(f"- repo_business={len(repo_business)}")
    print(f"- benchmark_business={len(benchmark_business)}")
    print(f"- repo_modules={module_count_repo}")
    print(f"- benchmark_modules={module_count_benchmark}")
    print(f"- module_ratio={module_ratio:.2f}")
    print("")

    print_list("Missing high-value business docs:", missing_high_value_business)
    print("")
    print_list("Missing business docs:", missing_business)
    print("")
    print_list("Extra business docs:", extra_business)
    print("")
    print_list("Missing benchmark files:", missing_files[:80])
    print("")

    print("Suggested targets:")
    target_business_count = max(len(repo_business), len(benchmark_business))
    target_module_count = max(module_count_repo, module_count_benchmark + 1)
    print(f"- business_docs_target>={target_business_count}")
    print(f"- modules_target>={target_module_count}")
    print("- keep benchmark high-value business docs at full parity")
    print("- exceed benchmark in onboarding / faq / adr or module granularity")

    below_floor = bool(missing_high_value_business) or module_ratio < 0.8
    if below_floor:
        print("")
        print("Benchmark status: below floor")
    elif missing_business or module_count_repo < module_count_benchmark:
        print("")
        print("Benchmark status: near parity but not fully aligned")
    else:
        print("")
        print("Benchmark status: at or above parity")

    if args.strict and below_floor:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
