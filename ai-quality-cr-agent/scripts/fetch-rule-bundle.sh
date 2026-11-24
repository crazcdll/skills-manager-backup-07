#!/usr/bin/env bash
exec python3 "$(dirname "${BASH_SOURCE[0]}")/fetch_rule_bundle.py" "$@"
