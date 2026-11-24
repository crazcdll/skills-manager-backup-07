"""Run the platform rule installer and prepare this review's L2 input."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


RUNNER = (Path(__file__).resolve().parents[2] / "mt-code-standards-setup"
          / "scripts" / "sync-effective-rules-with-sso.mjs")
RECEIPT_SCHEMA = "mt-rule-bundle-install/v1"
NON_DELIVERY = {"repository_not_registered", "no_effective_l2"}


class BundleError(ValueError):
    pass


def read_json(data):
    value = json.loads(data)
    if not isinstance(value, dict):
        raise BundleError("invalid_receipt")
    return value


def render_l2(rules_root, receipt, repo, explicit_domain):
    if receipt.get("schema_version") != RECEIPT_SCHEMA:
        raise BundleError("unsupported_receipt_schema")
    if receipt.get("status") not in ("installed", "not_modified") or receipt.get("stage") != "cr":
        raise BundleError("invalid_receipt")
    snapshot = receipt.get("snapshot_id")
    files = receipt.get("managed_files")
    refs = receipt.get("release_refs")
    if not (isinstance(snapshot, str) and snapshot and isinstance(files, list)
            and all(isinstance(p, str) for p in files) and len(files) == len(set(files))
            and isinstance(refs, list) and all(isinstance(r, dict) for r in refs)):
        raise BundleError("invalid_receipt")
    team_paths = sorted(p for p in files if p.startswith("team/"))
    releases = {(r.get("rule_set_id"), r.get("release_id"))
                for r in refs if r.get("scope_level") == "L2"}
    target = receipt.get("target") or {}
    domain = receipt.get("standard_domain")
    if (target.get("canonical_key") != repo.lower()
            or domain not in {"frontend", "backend"}
            or (explicit_domain and domain != explicit_domain)):
        raise BundleError("receipt_identity_mismatch")

    kind = receipt.get("bundle_kind")
    mode = receipt.get("delivery_mode")
    reason = receipt.get("selection_reason")
    if kind not in ("effective", "l1") or mode not in ("l1_l2", "l1_only"):
        raise BundleError("invalid_delivery_mode")
    if mode == "l1_only":
        if team_paths or releases:
            raise BundleError("invalid_delivery_mode")
        if reason not in NON_DELIVERY:
            raise BundleError("l2_not_accessible" if reason == "l2_not_accessible" else "l2_delivery_unconfirmed")
        return [], ""
    if kind != "effective" or not team_paths or not releases:
        raise BundleError("l2_files_missing")

    manifest = read_json((rules_root / ".mt-effective-rule-bundle.json").read_bytes())
    if any(manifest.get(key) != receipt[key] for key in ("snapshot_id", "managed_files", "release_refs", "stage")):
        raise BundleError("manifest_mismatch")
    if manifest.get("standard_domain") != domain:
        raise BundleError("manifest_mismatch")
    resolution = manifest.get("resolution") or {}
    if (manifest.get("schema_version") != "mt-effective-rule-bundle-manifest/v8"
            or any(resolution.get(key) != receipt.get(key) for key in
                   ("target", "bundle_kind", "delivery_mode", "selection_reason", "standard_domain", "stage"))):
        raise BundleError("manifest_mismatch")

    identities = manifest.get("managed_file_releases") or {}
    hashes = manifest["managed_file_hashes"]
    sizes = manifest["managed_file_sizes"]
    inventory, sections, seen = [], [], set()
    for path in team_paths:
        parts = path.split("/")
        if (len(parts) < 4 or parts[0] != "team" or parts[1] not in ("fe", "java")
                or any(p in ("", ".", "..") for p in parts)
                or re.search(r"[\\\x00-\x1f\x7f]", path) or not path.lower().endswith(".md")):
            raise BundleError("invalid_l2_path")
        owner = identities.get(path)
        if owner is None or (owner.get("rule_set_id"), owner.get("release_id")) not in releases:
            raise BundleError("l2_release_mismatch")
        rule_set = owner["rule_set_id"]
        if not isinstance(rule_set, str) or not rule_set or re.search(r"[/\\\x00-\x1f\x7f]", rule_set):
            raise BundleError("l2_release_mismatch")
        file = rules_root.joinpath(*parts)
        if not file.is_file() or not file.resolve().is_relative_to(rules_root.resolve()):
            raise BundleError("l2_body_missing")
        content = file.read_bytes()
        if len(content) != sizes.get(path) or hashlib.sha256(content).hexdigest() != hashes.get(path):
            raise BundleError("l2_body_mismatch")
        body = content.decode("utf-8")
        label = f"{rule_set}/{parts[-1]}"
        if not body.strip() or label in seen:
            raise BundleError("invalid_l2_body")
        seen.add(label)
        sections.append(f"## {label}\n\n{body}\n")
        inventory.append({"rule_file": label, "rule_set_id": rule_set, "release_id": owner["release_id"]})
    if {(item["rule_set_id"], item["release_id"]) for item in inventory} != releases:
        raise BundleError("l2_files_missing")
    return inventory, "\n".join(sections)


def atomic_write(path, content):
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as tmp:
        tmp.write(content)
    temporary = Path(tmp.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="namespace/repository")
    parser.add_argument("--route", required=True, choices=("backend", "mixed", "general"))
    parser.add_argument("--out", required=True, type=Path, help="dedicated directory for this review run")
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.json"
    cache = out / "l2_rules.md"
    state = {"repo": args.repo, "route": args.route, "l2_rule_sets": 0}

    def finish(status, exit_code, error_code=None, **metadata):
        state.update(status=status, error_code=error_code, **metadata)
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write(manifest, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        if error_code:
            print(f"fetch-rule-bundle: {status} ({error_code})", file=sys.stderr)
        return exit_code

    finish("running", 0)
    cache.unlink(missing_ok=True)
    if not RUNNER.is_file():
        return finish("fetch_failed", 3, "runner_unavailable")

    domain = "backend" if args.route == "backend" else None
    try:
        with tempfile.TemporaryDirectory(prefix="runner-", dir=out) as scratch:
            command = ["node", str(RUNNER), "--repo-root", scratch, "--repository", args.repo,
                       "--stage", "cr", "--execution-agent", "sandbox"]
            if domain:
                command += ["--domain", domain]
            result = subprocess.run(command, capture_output=True, timeout=args.timeout)
            state["runner_exit_code"] = result.returncode
            if result.returncode:
                # The official CLI writes a bounded diagnostic code before its message.
                codes = re.findall(rb"(?m)^([A-Za-z][A-Za-z0-9_]{0,99}): ", result.stderr)
                code = codes[-1].decode("ascii") if codes else "runner_failed"
                if code == "domain_required":
                    return finish("domain_unresolved", 5, code)
                return finish("fetch_failed", 4, code)
            receipt = read_json(result.stdout)
            for key in ("schema_version", "request_id", "pull_id", "snapshot_id", "bundle_kind",
                        "delivery_mode", "selection_reason", "domain_source", "standard_domain"):
                if isinstance(receipt.get(key), str):
                    state[key] = receipt[key]
            files, body = render_l2(Path(scratch) / ".mdp" / "rules", receipt, args.repo, domain)
    except subprocess.TimeoutExpired:
        return finish("fetch_failed", 4, "runner_timeout")
    except FileNotFoundError as exc:
        code = "node_unavailable" if exc.filename == "node" else "manifest_missing"
        return finish("fetch_failed", 4, code)
    except BundleError as exc:
        return finish("fetch_failed", 4, str(exc))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return finish("fetch_failed", 4, "invalid_bundle")

    if not files:
        return finish("no_team_rules", 0)
    atomic_write(cache, body)
    return finish("loaded", 0, rules_path=str(cache), files=files,
                  l2_rule_sets=len({f["rule_set_id"] for f in files}))


if __name__ == "__main__":
    raise SystemExit(main())
