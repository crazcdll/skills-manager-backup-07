#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from datetime import date
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize a repository knowledge base scaffold.")
    parser.add_argument("--repo", required=True, help="Target repository root path.")
    parser.add_argument(
        "--mode",
        choices=["auto", "minimum", "standard"],
        default="auto",
        help="Scaffold size. auto upgrades complex repositories to standard.",
    )
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Module slug to create in knowledge/modules/. Repeatable.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files created by this script.",
    )
    return parser.parse_args()


def render_template(template_path: Path, replacements: dict[str, str]) -> str:
    content = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def write_file(destination: Path, content: str, force: bool) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        return "skipped"
    destination.write_text(content, encoding="utf-8")
    return "written"


def module_title_from_slug(slug: str) -> str:
    parts = [part for part in slug.replace("_", "-").split("-") if part]
    if not parts:
        return "Core Module"
    return " ".join(part.capitalize() for part in parts)


def count_matching_dirs(repo: Path, pattern: str) -> int:
    return len([path for path in repo.glob(pattern) if path.is_dir()])


def detect_repo_complexity(repo: Path) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    page_count = count_matching_dirs(repo, "src/**/pages/*")
    reducer_count = count_matching_dirs(repo, "src/**/store/reducers/*")
    has_service = any(path.is_dir() for path in repo.glob("src/**/service"))
    has_datasource = any(path.is_dir() for path in repo.glob("src/**/datasource"))
    has_utils = any(path.is_dir() for path in repo.glob("src/**/utils"))
    has_map = any(path.is_dir() for path in repo.glob("src/**/map"))
    multi_entry = len([path for path in repo.glob("src/**/App.tsx") if path.is_file()]) >= 1 and len(
        [path for path in repo.glob("src/**/index.tsx") if path.is_file()]
    ) >= 1

    if page_count >= 3:
        reasons.append(f"pages={page_count}")
    if reducer_count >= 5:
        reasons.append(f"reducers={reducer_count}")
    if has_service and has_datasource and has_utils:
        reasons.append("has_service_datasource_utils_layers")
    if has_map:
        reasons.append("has_map_flow")
    if multi_entry:
        reasons.append("has_multiple_entry_files")

    return len(reasons) >= 2, reasons


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).expanduser().resolve()
    if not repo.exists() or not repo.is_dir():
        raise SystemExit(f"Repo path not found: {repo}")

    skill_dir = Path(__file__).resolve().parent.parent
    templates_dir = skill_dir / "assets" / "templates"
    knowledge_dir = repo / "knowledge"

    today = date.today().isoformat()
    repo_name = repo.name
    owner = repo.owner()

    base_replacements = {
        "REPO_NAME": repo_name,
        "TODAY": today,
        "OWNER": owner,
        "REPO_PATH": str(repo),
    }

    files_minimum = {
        "README.template.md": "knowledge/README.md",
        "Agent.template.md": "knowledge/Agent.md",
        "onboarding-0-reading-path.template.md": "knowledge/onboarding/0-reading-path.md",
        "business-main-page.template.md": "knowledge/business/main-page.md",
        "business-api-interfaces.template.md": "knowledge/business/api-interfaces.md",
        "business-store-state.template.md": "knowledge/business/store-state.md",
        "faq-troubleshooting.template.md": "knowledge/faq/troubleshooting.md",
        "business-template.md": "knowledge/_templates/business-template.md",
        "module.template.md": "knowledge/_templates/module-template.md",
        "faq-template.md": "knowledge/_templates/faq-template.md",
        "adr-template.md": "knowledge/_templates/adr-template.md",
    }
    files_standard = {
        **files_minimum,
        "onboarding-1-repo-map.template.md": "knowledge/onboarding/1-repo-map.md",
        "onboarding-2-first-task-guide.template.md": "knowledge/onboarding/2-first-task-guide.md",
        "business-routing.template.md": "knowledge/business/routing.md",
        "business-utils-tools.template.md": "knowledge/business/utils-tools.md",
        "business-performance.template.md": "knowledge/business/performance.md",
        "business-modules-desc.template.md": "knowledge/business/modules-desc.md",
        "faq-common-questions.template.md": "knowledge/faq/common-questions.md",
        "adr-0001-knowledge-structure.template.md": "knowledge/adr/0001-knowledge-structure.md",
        "adr-0002-core-architecture-choice.template.md": "knowledge/adr/0002-core-architecture-choice.md",
    }

    is_complex, complexity_reasons = detect_repo_complexity(repo)
    selected_mode = args.mode
    if args.mode == "auto":
        selected_mode = "standard" if is_complex else "minimum"

    selected = files_minimum if selected_mode == "minimum" else files_standard
    results: list[tuple[str, str]] = []

    knowledge_dir.mkdir(parents=True, exist_ok=True)
    for template_name, relative_output in selected.items():
        template_path = templates_dir / template_name
        output_path = repo / relative_output
        rendered = render_template(template_path, base_replacements)
        status = write_file(output_path, rendered, args.force)
        results.append((relative_output, status))

    module_template = templates_dir / "module.template.md"
    for slug in args.module:
        replacements = {
            **base_replacements,
            "MODULE_NAME": module_title_from_slug(slug),
            "MODULE_SLUG": slug,
        }
        output_path = repo / "knowledge" / "modules" / f"{slug}.md"
        rendered = render_template(module_template, replacements)
        status = write_file(output_path, rendered, args.force)
        results.append((f"knowledge/modules/{slug}.md", status))

    print(f"Knowledge scaffold ready for: {repo}")
    print(f"Mode requested: {args.mode}")
    print(f"Mode selected: {selected_mode}")
    print(f"Repo complexity: {'complex' if is_complex else 'simple'}")
    if complexity_reasons:
        print("Complexity signals:")
        for reason in complexity_reasons:
            print(f"- {reason}")
    print("Files:")
    for path, status in results:
        print(f"- [{status}] {path}")
    print("")
    print("Next:")
    print("- Fill README.md and Agent.md first.")
    print("- Use real code paths, interfaces, and store fields.")
    print("- Add 3 to 5 core module docs before expanding further.")
    if is_complex:
        print("- This repo looks complex; do not stop at minimum-quality coverage.")
        print("- Add routing/utils/performance/modules-desc and at least 6 module docs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
