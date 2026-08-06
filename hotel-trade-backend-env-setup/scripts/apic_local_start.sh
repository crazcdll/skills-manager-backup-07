#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORKSPACE_ROOT=$(cd "$SCRIPT_DIR/../../../.." && pwd)
MODE="doctor"
REPO_ROOT=""
HOST_ENV_VALUE="test"
SKIP_BUILD=0
FOREGROUND=0
DOWNLOAD_MISSING=1
TARGET_HOME="${HOME}"
INSTALL_ROOT=""
SHELL_RC=""
WRITE_SHELL_RC=0
FORCE_INSTALL=0
APPENV_DOC_URL="https://km.sankuai.com/collabpage/2712812595"
APPENV_FILE="/data/webapps/appenv"
JDK8_MAC_INTERNAL_DMG_URL="https://s3plus.sankuai.com/v1/mss_8d716098c5a046a6960916decbb8f4b2/cloudide/new-rd/jdk-8u333-macosx-x64.dmg"
AZUL_METADATA_API="https://api.azul.com/metadata/v1/zulu/packages/"

PROJECT_NAME="hotel-trade-backend"
REQUIRED_JDK_VERSION="8"
REQUIRED_MAVEN_VERSION="3.9.5"
PUB_MODULE=""
MAIN_CLASS=""
APPKEY=""
TEST_URL=""
HEALTH_URL=""
MODULE_POM=""
PROJECT_ENV_FILE=""
REPO_PERMISSION_URL=""

INSTALL_ROOT_DEFAULT=""
TOOLS_ROOT=""
DOWNLOAD_ROOT=""
PROFILE_FILE=""
PROJECT_ENV_DIR=""
M2_REPO_LOCAL=""
M2_SETTINGS=""
TARGET_HOME_ABS=""

JAVA8_HOME_RESOLVED=""
JAVA_HOME_RESOLVED=""
MVN_BIN=""
MVN_HOME_RESOLVED=""
EXISTING_ENV_READY=0
APPENV_STATUS="unknown"
APPENV_MESSAGE=""
PROFILE_SNIPPET_START="# >>> hotel-trade-backend-env >>>"
PROFILE_SNIPPET_END="# <<< hotel-trade-backend-env <<<"
LOG_PREFIX="[hotel-trade-env]"

usage() {
  cat <<'EOF'
Usage:
  apic_local_start.sh doctor [--repo PATH] [--target-home PATH] [--host-env ENV]
  apic_local_start.sh setup [--repo PATH] [--target-home PATH] [--install-root PATH] [--shell-rc PATH] [--write-shell-rc] [--force-install]
  apic_local_start.sh prepare --repo PATH [--target-home PATH] [--host-env ENV] [--write-shell-rc]
  apic_local_start.sh start --repo PATH [--target-home PATH] [--host-env ENV] [--skip-build] [--foreground] [--write-shell-rc]

Modes:
  doctor   Inspect machine-level dependencies and repo metadata.
  setup    Prepare a reusable user-level hotel-trade backend environment.
  prepare  Generate a project-level env file under the user install root.
  start    Build and launch the target backend project locally.

Notes:
  - This skill only depends on Java 8 and Maven for local startup. No JDK 17 installation needed.
  - By default tools are installed under ~/.hotel-trade/backend-env only when required tools are missing.
  - If the machine already has a usable Java 8 / Maven environment, setup respects it and does not modify shell startup files by default.
  - JDK 8 download priority on macOS: internal s3plus DMG first, then Azul Zulu API fallback, then legacy public tarball.
  - The backend service depends on /data/webapps/appenv for host environment config (env, swimlane, etc.).
  - Maven local repository defaults to ~/.m2/repository.
  - Use --target-home only for testing the skill in a temporary home directory.
  - setup without --repo installs the generic hotel-trade backend environment (Java 8 + Maven).
  - Use --write-shell-rc only when you explicitly want the skill to modify ~/.zshrc or a custom shell rc.
EOF
}

log() {
  printf '%s %s\n' "$LOG_PREFIX" "$*"
}

warn() {
  printf '%s WARN: %s\n' "$LOG_PREFIX" "$*" >&2
}

fail() {
  printf '%s ERROR: %s\n' "$LOG_PREFIX" "$*" >&2
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

abs_path() {
  python3 - <<'PY' "$1"
import os,sys
print(os.path.abspath(os.path.expanduser(sys.argv[1])))
PY
}

trim() {
  local value="$1"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
}

java_major_version() {
  local java_bin="$1"
  local version_line version_text
  version_line=$({ "$java_bin" -version 2>&1 || true; } | head -n 1)
  version_text=$(printf '%s' "$version_line" | sed -nE 's/.*version "([^"]+)".*/\1/p')
  if [[ "$version_text" == 1.8* ]]; then
    printf '8\n'
  elif [[ "$version_text" == 17* ]]; then
    printf '17\n'
  else
    printf '%s\n' "$version_text"
  fi
}

normalize_jdk_version() {
  # Always use JDK 8 for hotel-trade backend
  printf '8'
}

parse_args() {
  if [[ $# -gt 0 ]]; then
    MODE="$1"
    shift
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --repo)
        REPO_ROOT="$2"
        shift 2
        ;;
      --host-env)
        HOST_ENV_VALUE="$2"
        shift 2
        ;;
      --target-home)
        TARGET_HOME="$2"
        shift 2
        ;;
      --install-root)
        INSTALL_ROOT="$2"
        shift 2
        ;;
      --shell-rc)
        SHELL_RC="$2"
        shift 2
        ;;
      --write-shell-rc)
        WRITE_SHELL_RC=1
        shift
        ;;
      --force-install)
        FORCE_INSTALL=1
        shift
        ;;
      --skip-build)
        SKIP_BUILD=1
        shift
        ;;
      --foreground)
        FOREGROUND=1
        shift
        ;;
      --no-download)
        DOWNLOAD_MISSING=0
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "Unknown argument: $1"
        ;;
    esac
  done

  case "$MODE" in
    doctor|setup|prepare|start)
      ;;
    *)
      fail "Unsupported mode: $MODE"
      ;;
  esac
}

ensure_repo_exists() {
  [[ -n "$REPO_ROOT" ]] || fail "This mode requires --repo PATH"
  REPO_ROOT=$(abs_path "$REPO_ROOT")
  [[ -d "$REPO_ROOT" ]] || fail "Repo root not found: $REPO_ROOT"
  [[ -f "$REPO_ROOT/pom.xml" ]] || fail "Missing pom.xml in repo root: $REPO_ROOT"
}

setup_paths() {
  TARGET_HOME_ABS=$(abs_path "$TARGET_HOME")
  INSTALL_ROOT_DEFAULT="$TARGET_HOME_ABS/.hotel-trade/backend-env"

  if [[ -z "$INSTALL_ROOT" ]]; then
    INSTALL_ROOT="$INSTALL_ROOT_DEFAULT"
  else
    INSTALL_ROOT=$(abs_path "$INSTALL_ROOT")
  fi

  if [[ -z "$SHELL_RC" ]]; then
    SHELL_RC="$TARGET_HOME_ABS/.zshrc"
  else
    SHELL_RC=$(abs_path "$SHELL_RC")
  fi

  TOOLS_ROOT="$INSTALL_ROOT/tools"
  DOWNLOAD_ROOT="$INSTALL_ROOT/downloads"
  PROFILE_FILE="$INSTALL_ROOT/profile.sh"
  PROJECT_ENV_DIR="$INSTALL_ROOT/projects"
  M2_REPO_LOCAL="$TARGET_HOME_ABS/.m2/repository"
  M2_SETTINGS="$TARGET_HOME_ABS/.m2/settings.xml"
}

ensure_managed_dirs() {
  mkdir -p "$TOOLS_ROOT" "$DOWNLOAD_ROOT" "$PROJECT_ENV_DIR" "$TARGET_HOME_ABS/.m2"
}

find_first_pom_with_spring_boot_plugin() {
  local path="$1"
  find "$path" -name pom.xml -print0 2>/dev/null | while IFS= read -r -d '' pom; do
    if grep -q '<artifactId>spring-boot-maven-plugin</artifactId>' "$pom"; then
      printf '%s\n' "$pom"
      break
    fi
  done
}

find_main_class_from_java() {
  local repo="$1"
  local loader_file package_name
  loader_file=$(find "$repo" -path '*/src/main/java/*ApplicationLoader.java' | head -n 1 || true)
  if [[ -z "$loader_file" ]]; then
    loader_file=$(find "$repo" -path '*/src/main/java/*' -name '*.java' -print0 2>/dev/null | while IFS= read -r -d '' f; do
      if grep -q 'public static void main' "$f"; then
        printf '%s\n' "$f"
        break
      fi
    done)
  fi

  if [[ -n "$loader_file" ]]; then
    package_name=$(sed -nE 's/^package[[:space:]]+([^;]+);/\1/p' "$loader_file" | head -n 1)
    if [[ -n "$package_name" ]]; then
      printf '%s.%s\n' "$package_name" "$(basename "$loader_file" .java)"
    fi
  fi
}

extract_repo_metadata() {
  local plusboot_file jdk_tools maven_ver first_pom port_line port_value app_props remote_url repo_path repo_group repo_name

  if [[ -z "$REPO_ROOT" ]]; then
    PROJECT_NAME="hotel-trade-backend"
    REQUIRED_JDK_VERSION="8"
    REQUIRED_MAVEN_VERSION="3.9.5"
    PUB_MODULE=""
    MAIN_CLASS=""
    APPKEY=""
    TEST_URL=""
    HEALTH_URL=""
    MODULE_POM=""
    REPO_PERMISSION_URL="https://dev.sankuai.com/code/home"
    return
  fi

  ensure_repo_exists
  PROJECT_NAME=$(basename "$REPO_ROOT")
  plusboot_file="$REPO_ROOT/plusboot.yaml"

  if [[ -f "$plusboot_file" ]]; then
    PUB_MODULE=$(sed -nE 's/^[[:space:]]*PUB_MODULE:[[:space:]]*([^[:space:]#]+).*$/\1/p' "$plusboot_file" | head -n 1)
    TEST_URL=$(sed -nE 's/^[[:space:]]*TEST_URL:[[:space:]]*(.+)$/\1/p' "$plusboot_file" | head -n 1)
    TEST_URL=$(trim "$TEST_URL")
    jdk_tools=$(sed -nE 's/^[[:space:]]*JDKTools:[[:space:]]*(.+)$/\1/p' "$plusboot_file" | head -n 1)
    maven_ver=$(sed -nE 's/^[[:space:]]*MavenVersion:[[:space:]]*(.+)$/\1/p' "$plusboot_file" | head -n 1)
    # Always use JDK 8; ignore plusboot.yaml JDKTools
   REQUIRED_JDK_VERSION="8"
    [[ -n "$maven_ver" ]] && REQUIRED_MAVEN_VERSION=$(trim "$maven_ver")
  fi

  if [[ -z "$PUB_MODULE" ]]; then
    first_pom=$(find_first_pom_with_spring_boot_plugin "$REPO_ROOT")
    if [[ -n "$first_pom" ]]; then
      if [[ "$first_pom" == "$REPO_ROOT/pom.xml" ]]; then
        PUB_MODULE=""
      else
        PUB_MODULE="${first_pom#"$REPO_ROOT/"}"
        PUB_MODULE="${PUB_MODULE%/pom.xml}"
      fi
    fi
  fi

  if [[ -n "$PUB_MODULE" && -f "$REPO_ROOT/$PUB_MODULE/pom.xml" ]]; then
    MODULE_POM="$REPO_ROOT/$PUB_MODULE/pom.xml"
  else
    MODULE_POM=$(find_first_pom_with_spring_boot_plugin "$REPO_ROOT")
  fi

  if [[ -n "$MODULE_POM" && -f "$MODULE_POM" ]]; then
    MAIN_CLASS=$(sed -nE 's@.*<mainClass>([^<]+)</mainClass>.*@\1@p' "$MODULE_POM" | head -n 1)
  fi

  if [[ -z "$MAIN_CLASS" ]]; then
    MAIN_CLASS=$(find_main_class_from_java "$REPO_ROOT")
  fi

  if [[ -f "$REPO_ROOT/SERVICE.DESCRIPTION.xml" ]]; then
    APPKEY=$(sed -nE 's@.*<appkey>([^<]+)</appkey>.*@\1@p' "$REPO_ROOT/SERVICE.DESCRIPTION.xml" | head -n 1)
  fi

  if [[ -z "$APPKEY" ]]; then
    app_props=$(find "$REPO_ROOT" -path '*/src/main/resources/META-INF/app.properties' | head -n 1 || true)
    if [[ -n "$app_props" ]]; then
      APPKEY=$(sed -nE 's/^[[:space:]]*app.name[[:space:]]*=[[:space:]]*(.+)$/\1/p' "$app_props" | head -n 1)
      APPKEY=$(trim "$APPKEY")
    fi
  fi

  if [[ -z "$TEST_URL" ]]; then
    port_line=$(grep -R -m1 '^server\.port[[:space:]]*=' "$REPO_ROOT" --include='application*.properties' 2>/dev/null || true)
    port_value=$(printf '%s' "$port_line" | sed -nE 's/.*server\.port[[:space:]]*=[[:space:]]*([0-9]+).*/\1/p' | head -n 1)
    if [[ -n "$port_value" ]]; then
      TEST_URL="http://127.0.0.1:${port_value}/monitor/alive"
    fi
  fi

  if [[ -z "$TEST_URL" ]]; then
    TEST_URL="http://127.0.0.1:8080/monitor/alive"
  fi

  remote_url=$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || true)
  if [[ "$remote_url" =~ git\.sankuai\.com[:/]([^/]+)/([^/.]+)(\.git)?$ ]]; then
    repo_group="${BASH_REMATCH[1]}"
    repo_name="${BASH_REMATCH[2]}"
    REPO_PERMISSION_URL="https://dev.sankuai.com/code/repo-detail/${repo_group}/${repo_name}/file/list"
  else
    REPO_PERMISSION_URL="https://dev.sankuai.com/code/home"
  fi

  HEALTH_URL="$TEST_URL"
}

detect_java_home_for_version() {
  local version="$1"
  local current_link env_var_name env_var_value desired_mac_version candidate common_dir java_bin major

  current_link="$TOOLS_ROOT/jdk${version}/current"
  if [[ -x "$current_link/bin/java" ]]; then
    major=$(java_major_version "$current_link/bin/java")
    if [[ "$major" == "$version" ]]; then
      printf '%s\n' "$current_link"
      return 0
    fi
  fi

  env_var_name="JAVA${version}_HOME"
  env_var_value="${!env_var_name:-}"
  if [[ -n "$env_var_value" && -x "$env_var_value/bin/java" ]]; then
    major=$(java_major_version "$env_var_value/bin/java")
    if [[ "$major" == "$version" ]]; then
      printf '%s\n' "$env_var_value"
      return 0
    fi
  fi

  if [[ -n "${JAVA_HOME:-}" && -x "${JAVA_HOME}/bin/java" ]]; then
    major=$(java_major_version "${JAVA_HOME}/bin/java")
    if [[ "$major" == "$version" ]]; then
      printf '%s\n' "$JAVA_HOME"
      return 0
    fi
  fi

  if [[ "$(uname -s)" == "Darwin" && -x /usr/libexec/java_home ]]; then
    if [[ "$version" == "8" ]]; then
      desired_mac_version="1.8"
    else
      desired_mac_version="$version"
    fi
    candidate=$(/usr/libexec/java_home -v "$desired_mac_version" 2>/dev/null || true)
    if [[ -n "$candidate" && -x "$candidate/bin/java" ]]; then
      major=$(java_major_version "$candidate/bin/java")
      if [[ "$major" == "$version" ]]; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  fi

  for common_dir in \
    "$HOME/Library/Java/JavaVirtualMachines" \
    "/Library/Java/JavaVirtualMachines" \
    "/usr/lib/jvm" \
    "$TOOLS_ROOT"; do
    if [[ -d "$common_dir" ]]; then
      candidate=$(find "$common_dir" -maxdepth 4 -type f -path '*/bin/java' 2>/dev/null | while IFS= read -r java_bin; do
        major=$(java_major_version "$java_bin")
        if [[ "$major" == "$version" ]]; then
          dirname "$(dirname "$java_bin")"
          break
        fi
      done)
      if [[ -n "$candidate" ]]; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done

  return 1
}

find_java_home_in_dir() {
  local base_dir="$1"
  find "$base_dir" -maxdepth 8 -type f -path '*/bin/java' 2>/dev/null | while IFS= read -r java_bin; do
    dirname "$(dirname "$java_bin")"
    break
  done
}

resolve_azul_jdk_download_url() {
  local version="$1"
  local os_name="$2"
  local arch_name="$3"

  python3 - <<'PY' "$version" "$os_name" "$arch_name" "$AZUL_METADATA_API"
import json
import sys
import urllib.parse
import urllib.request

version, os_name, arch_name, api_base = sys.argv[1:5]
params = {
    'java_version': version,
    'os': os_name,
    'arch': arch_name,
    'archive_type': 'tar.gz',
    'java_package_type': 'jdk',
    'release_status': 'ga',
    'availability_types': 'ca',
    'latest': 'true',
}
url = api_base + '?' + urllib.parse.urlencode(params)
try:
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.load(resp)
except Exception:
    print('')
    raise SystemExit(0)

items = data if isinstance(data, list) else []
preferred = None
fallback = None
for item in items:
    download_url = item.get('download_url', '')
    if not download_url:
        continue
    if fallback is None:
        fallback = download_url
    if '-fx-' not in download_url:
        preferred = download_url
        break

print(preferred or fallback or '')
PY
}

extract_java_archive() {
  local archive_path="$1"
  local archive_kind="$2"
  local extract_root="$3"
  local real_home=""
  local attach_output=""
  local mount_point=""
  local direct_bundle=""
  local pkg_path=""
  local pkg_expand=""
  local payload_root=""

  rm -rf "$extract_root"
  mkdir -p "$extract_root"

  case "$archive_kind" in
    tar.gz)
      tar -xzf "$archive_path" -C "$extract_root" >/dev/null 2>&1 || return 1
      ;;
    dmg)
      attach_output=$(hdiutil attach -nobrowse -readonly "$archive_path" 2>/dev/null || true)
      mount_point=$(printf '%s\n' "$attach_output" | awk '{for (i = 1; i <= NF; i++) if ($i ~ /^\/Volumes\//) {print $i; exit}}')
      [[ -n "$mount_point" ]] || return 1

      direct_bundle=$(find "$mount_point" -maxdepth 4 -type d -name '*.jdk' 2>/dev/null | head -n 1 || true)
      if [[ -n "$direct_bundle" && -d "$direct_bundle/Contents/Home" ]]; then
        cp -R "$direct_bundle" "$extract_root/" >/dev/null 2>&1 || true
      else
        pkg_path=$(find "$mount_point" -maxdepth 4 -type f -name '*.pkg' 2>/dev/null | head -n 1 || true)
        if [[ -z "$pkg_path" ]]; then
          hdiutil detach "$mount_point" >/dev/null 2>&1 || true
          return 1
        fi

        pkg_expand="$extract_root/pkg-expanded"
        payload_root="$extract_root/payload-root"
        mkdir -p "$payload_root"
        pkgutil --expand-full "$pkg_path" "$pkg_expand" >/dev/null 2>&1 || {
          hdiutil detach "$mount_point" >/dev/null 2>&1 || true
          return 1
        }

        while IFS= read -r payload; do
          local payload_type payload_dest
          payload_type=$(file -b "$payload" 2>/dev/null || true)
          payload_dest="$payload_root/$(basename "$(dirname "$payload")")"
          mkdir -p "$payload_dest"
          if [[ "$payload_type" == *"gzip compressed"* ]]; then
            gzip -dc "$payload" | (cd "$payload_dest" && cpio -idm --quiet) >/dev/null 2>&1 || true
          elif [[ "$payload_type" == *"XZ compressed"* ]] && command_exists xz; then
            xz -dc "$payload" | (cd "$payload_dest" && cpio -idm --quiet) >/dev/null 2>&1 || true
          elif [[ "$payload_type" == *"cpio archive"* ]]; then
            (cd "$payload_dest" && cpio -idm --quiet < "$payload") >/dev/null 2>&1 || true
          fi
        done < <(find "$pkg_expand" -type f -name Payload 2>/dev/null)
      fi

      hdiutil detach "$mount_point" >/dev/null 2>&1 || true
      ;;
    *)
      return 1
      ;;
  esac

  real_home=$(find_java_home_in_dir "$extract_root" || true)
  [[ -n "$real_home" ]] || return 1
  printf '%s\n' "$real_home"
}

download_java_version() {
  local version="$1"
  local os arch legacy_url azul_os azul_arch azul_url extract_root
  local -a candidate_urls=()
  local -a candidate_kinds=()
  os=$(uname -s)
  arch=$(uname -m)

  case "$version:$os:$arch" in
    8:Darwin:arm64)
      legacy_url="https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u452-b09/OpenJDK8U-jdk_aarch64_mac_hotspot_8u452b09.tar.gz"
      azul_os="macos"
      azul_arch="aarch64"
      candidate_urls+=("$JDK8_MAC_INTERNAL_DMG_URL")
      candidate_kinds+=("dmg")
      ;;
    8:Darwin:x86_64)
      legacy_url="https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u452-b09/OpenJDK8U-jdk_x64_mac_hotspot_8u452b09.tar.gz"
      azul_os="macos"
      azul_arch="x86_64"
      candidate_urls+=("$JDK8_MAC_INTERNAL_DMG_URL")
      candidate_kinds+=("dmg")
      ;;
    8:Linux:x86_64)
      legacy_url="https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u452-b09/OpenJDK8U-jdk_x64_linux_hotspot_8u452b09.tar.gz"
      azul_os="linux"
      azul_arch="x86_64"
      ;;
    8:Linux:aarch64)
      legacy_url="https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u452-b09/OpenJDK8U-jdk_aarch64_linux_hotspot_8u452b09.tar.gz"
      azul_os="linux"
      azul_arch="aarch64"
      ;;
    *)
      fail "Unsupported platform for Java ${version} download: ${os}/${arch}"
      ;;
  esac

  azul_url=$(resolve_azul_jdk_download_url "$version" "$azul_os" "$azul_arch" || true)
  if [[ -n "$azul_url" ]]; then
    candidate_urls+=("$azul_url")
    candidate_kinds+=("tar.gz")
  fi
  candidate_urls+=("$legacy_url")
  candidate_kinds+=("tar.gz")

  extract_root="$TOOLS_ROOT/jdk${version}"

  local idx url archive_kind archive_name archive_path real_home detected_version
  for idx in "${!candidate_urls[@]}"; do
    url="${candidate_urls[$idx]}"
    archive_kind="${candidate_kinds[$idx]}"
    archive_name=$(basename "${url%%\?*}")
    archive_path="$DOWNLOAD_ROOT/$archive_name"

    if [[ ! -f "$archive_path" ]]; then
      log "Downloading Java ${version} from $url"
      if ! curl -L --fail --retry 1 --retry-delay 1 -o "$archive_path" "$url"; then
        warn "Java ${version} download failed from $url"
        rm -f "$archive_path"
        continue
      fi
    fi

    if ! real_home=$(extract_java_archive "$archive_path" "$archive_kind" "$extract_root"); then
      warn "Java ${version} extraction failed for $archive_path"
      rm -rf "$extract_root"
      rm -f "$archive_path"
      continue
    fi

    detected_version=$(java_major_version "$real_home/bin/java")
    if [[ "$detected_version" != "$version" ]]; then
      warn "Downloaded Java from $url but detected version '$detected_version'; trying next candidate"
      rm -rf "$extract_root"
      rm -f "$archive_path"
      continue
    fi

    ln -sfn "$real_home" "$extract_root/current"
    printf '%s\n' "$extract_root/current"
    return 0
  done

  fail "Failed to download a usable Java ${version} for ${os}/${arch}. Tried internal mirror, Azul API fallback, and legacy public tarball."
}

ensure_java_version() {
  local version="$1"
  local resolved_home
  resolved_home=$(detect_java_home_for_version "$version" || true)
  if [[ -z "$resolved_home" ]]; then
    [[ "$DOWNLOAD_MISSING" == "1" ]] || fail "Java ${version} not found and downloads are disabled"
    ensure_managed_dirs
    resolved_home=$(download_java_version "$version")
  fi

  JAVA8_HOME_RESOLVED="$resolved_home"
}

detect_maven() {
  local local_mvn
  if command_exists mvn; then
    MVN_BIN=$(command -v mvn)
    MVN_HOME_RESOLVED=$(cd "$(dirname "$MVN_BIN")/.." && pwd)
    return 0
  fi

  local_mvn=$(find "$TOOLS_ROOT" -maxdepth 4 -type f -path '*/bin/mvn' | head -n 1 || true)
  if [[ -n "$local_mvn" ]]; then
    MVN_BIN="$local_mvn"
    MVN_HOME_RESOLVED=$(cd "$(dirname "$MVN_BIN")/.." && pwd)
    return 0
  fi

  return 1
}

download_maven() {
  local version archive_name archive_path url extract_root
  version="$REQUIRED_MAVEN_VERSION"
  archive_name="apache-maven-${version}-bin.tar.gz"
  archive_path="$DOWNLOAD_ROOT/$archive_name"
  url="https://archive.apache.org/dist/maven/maven-3/${version}/binaries/${archive_name}"
  extract_root="$TOOLS_ROOT/maven"

  ensure_managed_dirs
  if [[ ! -f "$archive_path" ]]; then
    log "Downloading Maven ${version} to $archive_path"
    curl -L --fail --retry 2 --retry-delay 2 -o "$archive_path" "$url"
  fi

  rm -rf "$extract_root"
  mkdir -p "$extract_root"
  tar -xzf "$archive_path" -C "$extract_root"
  MVN_HOME_RESOLVED="$extract_root/apache-maven-${version}"
  MVN_BIN="$MVN_HOME_RESOLVED/bin/mvn"
  [[ -x "$MVN_BIN" ]] || fail "Failed to locate Maven after extraction"
}

ensure_maven() {
  if ! detect_maven; then
    [[ "$DOWNLOAD_MISSING" == "1" ]] || fail "Maven not found and downloads are disabled"
    download_maven
  fi
}

profile_source_line() {
  printf '[ -f "%s" ] && source "%s"\n' "$PROFILE_FILE" "$PROFILE_FILE"
}

profile_file_needed() {
  [[ "$WRITE_SHELL_RC" == "1" || "$EXISTING_ENV_READY" != "1" || "$FORCE_INSTALL" == "1" ]]
}

write_profile_file() {
  cat > "$PROFILE_FILE" <<EOF
export HOTEL_TRADE_BACKEND_ENV_ROOT="$INSTALL_ROOT"
export JAVA8_HOME="$JAVA8_HOME_RESOLVED"
export M2_HOME="$MVN_HOME_RESOLVED"
export HOTEL_TRADE_M2_REPO="$M2_REPO_LOCAL"

if [[ -z "\${JAVA_HOME:-}" && -n "\${JAVA8_HOME:-}" ]]; then
  export JAVA_HOME="\$JAVA8_HOME"
fi

case ":\$PATH:" in
  *":\$M2_HOME/bin:"*) ;;
  *) export PATH="\$M2_HOME/bin:\$PATH" ;;
esac

if [[ -n "\${JAVA_HOME:-}" ]]; then
  case ":\$PATH:" in
    *":\$JAVA_HOME/bin:"*) ;;
    *) export PATH="\$JAVA_HOME/bin:\$PATH" ;;
  esac
fi
EOF
}

update_shell_rc() {
  local tmp_file rc_dir
  rc_dir=$(dirname "$SHELL_RC")
  mkdir -p "$rc_dir"
  touch "$SHELL_RC"
  tmp_file=$(mktemp)

  awk -v start="$PROFILE_SNIPPET_START" -v end="$PROFILE_SNIPPET_END" '
    BEGIN {skip=0}
    index($0,start)==1 {skip=1; next}
    index($0,end)==1 {skip=0; next}
    skip==0 {print}
  ' "$SHELL_RC" > "$tmp_file"

  {
    cat "$tmp_file"
    printf '\n%s\n' "$PROFILE_SNIPPET_START"
    profile_source_line
    printf '%s\n' "$PROFILE_SNIPPET_END"
  } > "$SHELL_RC"

  rm -f "$tmp_file"
}

write_project_env_file() {
  local java_home_for_project env_file_name
  java_home_for_project="$JAVA8_HOME_RESOLVED"

  env_file_name="$PROJECT_NAME.env.sh"
  PROJECT_ENV_FILE="$PROJECT_ENV_DIR/$env_file_name"

  cat > "$PROJECT_ENV_FILE" <<EOF
export HOTEL_TRADE_BACKEND_ENV_ROOT="$INSTALL_ROOT"
export REPO_ROOT="$REPO_ROOT"
export PROJECT_NAME="$PROJECT_NAME"
export JAVA_HOME="$java_home_for_project"
export JAVA8_HOME="$JAVA8_HOME_RESOLVED"
export M2_HOME="$MVN_HOME_RESOLVED"
export PATH="$java_home_for_project/bin:$MVN_HOME_RESOLVED/bin:\$PATH"
export HOST_ENV="$HOST_ENV_VALUE"
export SPRING_PROFILES_ACTIVE="$HOST_ENV_VALUE"
export HOTEL_TRADE_M2_REPO="$M2_REPO_LOCAL"
export PUB_MODULE="$PUB_MODULE"
export MAIN_CLASS="$MAIN_CLASS"
export APPKEY="$APPKEY"
export HEALTH_URL="$HEALTH_URL"
export REQUIRED_JDK_VERSION="$REQUIRED_JDK_VERSION"
EOF
}

print_summary() {
  log "project_name=$PROJECT_NAME"
  if [[ -n "$REPO_ROOT" ]]; then
    log "repo=$REPO_ROOT"
  else
    log "repo=<generic-env>"
  fi
  log "required_jdk=$REQUIRED_JDK_VERSION"
  log "required_maven=$REQUIRED_MAVEN_VERSION"
  log "java8_home=$JAVA8_HOME_RESOLVED"
  log "active_java_home=$JAVA_HOME_RESOLVED"
  log "maven_bin=$MVN_BIN"
  log "maven_home=$MVN_HOME_RESOLVED"
  log "host_env=$HOST_ENV_VALUE"
  log "pub_module=${PUB_MODULE:-<root-project>}"
  log "main_class=${MAIN_CLASS:-<auto-detect-failed>}"
  log "appkey=${APPKEY:-<not-found>}"
  log "health_url=$HEALTH_URL"
  log "install_root=$INSTALL_ROOT"
  log "profile_file=$PROFILE_FILE"
  log "shell_rc=$SHELL_RC"
  log "maven_repo_local=$M2_REPO_LOCAL"
  log "appenv_status=$APPENV_STATUS"
  if [[ "$APPENV_STATUS" == "ok" ]]; then
    log "appenv_detail=$APPENV_MESSAGE"
  else
    warn "appenv_detail=$APPENV_MESSAGE"
    warn "appenv_doc=$APPENV_DOC_URL"
  fi
  if [[ -f "$M2_SETTINGS" ]]; then
    log "maven_settings=$M2_SETTINGS"
  else
    warn "maven_settings_missing=$M2_SETTINGS"
  fi
  if [[ -n "$PROJECT_ENV_FILE" ]]; then
    log "project_env_file=$PROJECT_ENV_FILE"
  fi
  if [[ -n "$REPO_PERMISSION_URL" ]]; then
    log "repo_permission_url=$REPO_PERMISSION_URL"
  fi
}

check_appenv() {
  if [[ -f "$APPENV_FILE" ]]; then
    local env_value
    env_value=$(grep -E '^env=' "$APPENV_FILE" 2>/dev/null | head -n 1 | cut -d'=' -f2 || true)
    if [[ -n "$env_value" ]]; then
      APPENV_STATUS="ok"
      APPENV_MESSAGE="appenv configured: env=$env_value"
    else
      APPENV_STATUS="misconfigured"
      APPENV_MESSAGE="appenv exists at $APPENV_FILE but 'env=' line is missing or commented out. Please add 'env=test' (or your desired env)."
    fi
  else
    APPENV_STATUS="missing"
    APPENV_MESSAGE="appenv not found at $APPENV_FILE. The backend service reads /data/webapps/appenv for host environment config (env, swimlane, zkserver, etc.). Without it, local startup will fail. Please refer to: $APPENV_DOC_URL"
  fi
}

ensure_global_env() {
  setup_paths
  ensure_java_version 8
  ensure_maven
  check_appenv

  EXISTING_ENV_READY=0
  if [[ -n "$JAVA8_HOME_RESOLVED" && -n "$MVN_BIN" ]]; then
    if [[ "$JAVA8_HOME_RESOLVED" != "$TOOLS_ROOT"/* && "$MVN_BIN" != "$TOOLS_ROOT"/* ]]; then
      EXISTING_ENV_READY=1
    fi
  fi

  JAVA_HOME_RESOLVED="$JAVA8_HOME_RESOLVED"
}

health_port() {
  if [[ -z "$HEALTH_URL" ]]; then
    return 0
  fi
  python3 - <<'PY' "$HEALTH_URL"
from urllib.parse import urlparse
import sys
u = urlparse(sys.argv[1])
if u.port:
    print(u.port)
elif u.scheme == 'https':
    print(443)
elif u.scheme == 'http':
    print(80)
PY
}

is_port_in_use() {
  local port="$1"
  [[ -n "$port" ]] || return 1
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

preflight_start_checks() {
  local port
  port=$(health_port || true)

  if [[ -z "$PUB_MODULE" && -z "$MODULE_POM" ]]; then
    fail "Unable to determine spring-boot publish module for $PROJECT_NAME"
  fi

  if [[ -z "$MAIN_CLASS" ]]; then
    warn "main_class_missing_for=$PROJECT_NAME; spring-boot plugin default discovery will be used"
  fi

  if [[ -f "$M2_SETTINGS" ]]; then
    log "maven_settings_ready=$M2_SETTINGS"
  else
    warn "maven_settings_missing=$M2_SETTINGS; private Maven dependencies may fail to resolve"
  fi

  if [[ -n "$port" ]]; then
    log "health_port=$port"
    if is_port_in_use "$port"; then
      fail "Port $port is already in use. Please stop the existing process before starting $PROJECT_NAME"
    fi
  fi
}

wait_for_health() {
  local pid="$1"
  local url="$2"
  local timeout_seconds="${3:-150}"
  local elapsed=0

  [[ -n "$url" ]] || return 0

  while (( elapsed < timeout_seconds )); do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 1
    fi

    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      log "health_check_passed=$url"
      return 0
    fi

    sleep 3
    elapsed=$((elapsed + 3))
  done

  return 1
}

run_setup() {
  ensure_global_env

  if [[ "$EXISTING_ENV_READY" == "1" && "$FORCE_INSTALL" != "1" ]]; then
    log "existing_env_ready=true"
    log "Existing JDK and Maven environment already satisfies hotel-trade backend requirements"
    if [[ "$WRITE_SHELL_RC" == "1" ]]; then
      ensure_managed_dirs
      write_profile_file
      update_shell_rc
      log "shell_rc_updated=$SHELL_RC"
    else
      log "shell_rc_unchanged=true"
    fi
    print_summary
    return
  fi

  ensure_managed_dirs
  write_profile_file
  if [[ "$WRITE_SHELL_RC" == "1" ]]; then
    update_shell_rc
    log "shell_rc_updated=$SHELL_RC"
  else
    log "shell_rc_unchanged=true"
  fi
  print_summary
  log "User-level hotel-trade backend environment is ready"
}

run_doctor() {
  extract_repo_metadata
  ensure_global_env
  if [[ -n "$REPO_ROOT" ]]; then
    PROJECT_ENV_FILE="$PROJECT_ENV_DIR/$PROJECT_NAME.env.sh"
  fi
  print_summary
}

run_prepare() {
  extract_repo_metadata
  ensure_global_env
  ensure_managed_dirs
  write_project_env_file

  if profile_file_needed; then
    write_profile_file
    if [[ "$WRITE_SHELL_RC" == "1" ]]; then
      update_shell_rc
      log "shell_rc_updated=$SHELL_RC"
    else
      log "shell_rc_unchanged=true"
    fi
  else
    log "shell_rc_unchanged=true"
    log "profile_file_skipped=true"
  fi

  print_summary
  log "Project env prepared successfully"
}

build_project() {
  local mvn_args=()
  [[ -n "$PUB_MODULE" ]] && mvn_args+=( -pl "$PUB_MODULE" -am )

  log "Building $PROJECT_NAME with shared Maven repo $M2_REPO_LOCAL"
  (
    cd "$REPO_ROOT"
    export JAVA_HOME="$JAVA_HOME_RESOLVED"
    export PATH="$JAVA_HOME/bin:$MVN_HOME_RESOLVED/bin:$PATH"
    export HOST_ENV="$HOST_ENV_VALUE"
    export SPRING_PROFILES_ACTIVE="$HOST_ENV_VALUE"
    "$MVN_BIN" "${mvn_args[@]}" -Dmaven.repo.local="$M2_REPO_LOCAL" -Dmaven.test.skip=true -DskipTests install
  )
}

start_project() {
  local mvn_args=() jvm_args run_cmd app_pid
  [[ -n "$PUB_MODULE" ]] && mvn_args+=( -pl "$PUB_MODULE" )
  jvm_args="-DhostEnv=${HOST_ENV_VALUE} -DHOST_ENV=${HOST_ENV_VALUE} -Dspring.profiles.active=${HOST_ENV_VALUE}"
  run_cmd=("$MVN_BIN" "${mvn_args[@]}" -Dmaven.repo.local="$M2_REPO_LOCAL" -Dmaven.test.skip=true -DskipTests "-Dspring-boot.run.jvmArguments=${jvm_args}" spring-boot:run)

  log "Starting $PROJECT_NAME"
  log "Command: ${run_cmd[*]}"

  cd "$REPO_ROOT"
  export JAVA_HOME="$JAVA_HOME_RESOLVED"
  export PATH="$JAVA_HOME/bin:$MVN_HOME_RESOLVED/bin:$PATH"
  export HOST_ENV="$HOST_ENV_VALUE"
  export SPRING_PROFILES_ACTIVE="$HOST_ENV_VALUE"
  export APPKEY="$APPKEY"

  if [[ "$FOREGROUND" == "1" ]]; then
    exec "${run_cmd[@]}"
  fi

  "${run_cmd[@]}" &
  app_pid=$!
  log "spawned_pid=$app_pid"

  if ! wait_for_health "$app_pid" "$HEALTH_URL"; then
    kill "$app_pid" 2>/dev/null || true
    wait "$app_pid" 2>/dev/null || true
    fail "Health check did not pass for $PROJECT_NAME: $HEALTH_URL"
  fi

  wait "$app_pid"
}

run_start() {
  extract_repo_metadata
  ensure_global_env
  ensure_managed_dirs
  write_project_env_file

  if profile_file_needed; then
    write_profile_file
    if [[ "$WRITE_SHELL_RC" == "1" ]]; then
      update_shell_rc
      log "shell_rc_updated=$SHELL_RC"
    else
      log "shell_rc_unchanged=true"
    fi
  else
    log "shell_rc_unchanged=true"
    log "profile_file_skipped=true"
  fi

  preflight_start_checks
  print_summary
  if [[ "$SKIP_BUILD" != "1" ]]; then
    build_project
  else
    log "Skipping build as requested"
  fi
  start_project
}

main() {
  parse_args "$@"

  case "$MODE" in
    doctor)
      run_doctor
      ;;
    setup)
      extract_repo_metadata
      run_setup
      ;;
    prepare)
      ensure_repo_exists
      run_prepare
      ;;
    start)
      ensure_repo_exists
      run_start
      ;;
  esac
}

main "$@"
