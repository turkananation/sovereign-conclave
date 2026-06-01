#!/usr/bin/env bash
# Sovereign Conclave installer for Claude Code, Codex, and Antigravity.
# Independent project. Design-inspired by the public-domain "conclave" pattern; shares no code with it.
set -euo pipefail

CLAUDE_DIR="${HOME}/.claude"
CODEX_DIR="${HOME}/.codex"
ANTIGRAVITY_DIR="${HOME}/.gemini/antigravity"
DRY_RUN=0
TARGETS=("claude")

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

Options:
  --target NAME[,NAME]       Install target(s): claude, codex, antigravity, all
                             (default: claude)
  --claude-dir PATH          Claude config dir (default: ~/.claude)
  --codex-dir PATH           Codex config dir (default: ~/.codex)
  --antigravity-dir PATH     Antigravity config dir (default: ~/.gemini/antigravity)
  --dry-run                  Print actions without touching the filesystem
  -h, --help                 Show this help

Examples:
  ./install.sh
  ./install.sh --target codex
  ./install.sh --target antigravity
  ./install.sh --target all --dry-run
EOF
}

parse_targets() {
  local raw="$1"
  TARGETS=()

  if [[ "${raw}" == "all" ]]; then
    TARGETS=("claude" "codex" "antigravity")
    return
  fi

  IFS=',' read -r -a TARGETS <<<"${raw}"
  for target in "${TARGETS[@]}"; do
    case "${target}" in
      claude|codex|antigravity) ;;
      *)
        echo "Unknown target: ${target}" >&2
        usage
        exit 2
        ;;
    esac
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)           parse_targets "$2"; shift 2 ;;
    --claude-dir)       CLAUDE_DIR="$2"; shift 2 ;;
    --codex-dir)        CODEX_DIR="$2"; shift 2 ;;
    --antigravity-dir)  ANTIGRAVITY_DIR="$2"; shift 2 ;;
    --dry-run)          DRY_RUN=1; shift ;;
    -h|--help)          usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_SRC="${SCRIPT_DIR}/agents"

run() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    printf 'DRY-RUN:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

copy_common_skill_files() {
  local skill_dst="$1"

  run mkdir -p "${skill_dst}"
  run cp "${SCRIPT_DIR}/SKILL.md" "${skill_dst}/SKILL.md"

  for doc in directives.md roster.md; do
    [[ -f "${SCRIPT_DIR}/${doc}" ]] && run cp "${SCRIPT_DIR}/${doc}" "${skill_dst}/"
  done

  [[ -d "${SCRIPT_DIR}/demos" ]] && run cp -R "${SCRIPT_DIR}/demos" "${skill_dst}/"
  [[ -d "${SCRIPT_DIR}/configs" ]] && run cp -R "${SCRIPT_DIR}/configs" "${skill_dst}/"
  [[ -d "${SCRIPT_DIR}/docs" ]] && run cp -R "${SCRIPT_DIR}/docs" "${skill_dst}/"
  [[ -d "${SCRIPT_DIR}/schemas" ]] && run cp -R "${SCRIPT_DIR}/schemas" "${skill_dst}/"
}

copy_agents_into() {
  local agents_dst="$1"

  run mkdir -p "${agents_dst}"
  shopt -s nullglob
  for agent in "${AGENTS_SRC}"/conclave-*.md; do
    run cp "${agent}" "${agents_dst}/"
  done
}

install_claude() {
  local agents_dst="${CLAUDE_DIR}/agents"
  local skill_dst="${CLAUDE_DIR}/skills/conclave"

  echo "Installing Sovereign Conclave for Claude Code into ${CLAUDE_DIR}"
  copy_agents_into "${agents_dst}"
  copy_common_skill_files "${skill_dst}"
}

install_codex() {
  local skill_dst="${CODEX_DIR}/skills/conclave"

  echo "Installing Sovereign Conclave for Codex into ${skill_dst}"
  copy_common_skill_files "${skill_dst}"
  copy_agents_into "${skill_dst}/agents"
}

install_antigravity() {
  local skill_dst="${ANTIGRAVITY_DIR}/skills/conclave"

  echo "Installing Sovereign Conclave for Antigravity into ${skill_dst}"
  copy_common_skill_files "${skill_dst}"
  copy_agents_into "${skill_dst}/agents"
}

for target in "${TARGETS[@]}"; do
  case "${target}" in
    claude) install_claude ;;
    codex) install_codex ;;
    antigravity) install_antigravity ;;
  esac
done

echo "Done. Restart the target tool so it can discover the /conclave skill."
