#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

case "${1:-}" in
  "")
    cargo build --manifest-path rs/Cargo.toml --release
    install -m 755 rs/target/release/km bin/km-darwin-arm64
    ;;
  --all)
    cargo build --manifest-path rs/Cargo.toml --release
    cargo zigbuild --manifest-path rs/Cargo.toml --release --target x86_64-unknown-linux-musl
    cargo zigbuild --manifest-path rs/Cargo.toml --release --target x86_64-pc-windows-gnu
    install -m 755 rs/target/release/km bin/km-darwin-arm64
    install -m 755 rs/target/x86_64-unknown-linux-musl/release/km bin/km-linux-amd64
    install -m 755 rs/target/x86_64-pc-windows-gnu/release/km.exe bin/km-windows-x64.exe
    ;;
  *)
    echo "用法: scripts/build.sh [--all]" >&2
    exit 1
    ;;
esac
