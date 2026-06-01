#!/usr/bin/env bash
# Sovereign Conclave — installer for the Claude Code skill + conclave subagents.
# Independent project. Design-inspired by the public-domain "council" pattern; shares no code with it.
set -euo pipefail

CLAUDE_DIR="${HOME}/.claude"
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [--claude-dir PATH] [--dry-run]

  --claude-dir PATH   Install into a non-default Claude config dir (default: ~/.claude)
  --dry-run           Print actions without touching the filesystem
  -h, --help          Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --claude-dir) CLAUDE_DIR="$2"; shift 2 ;;
    --dry-run)    DRY_RUN=1; shift ;;
    -h|--help)    usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_SRC="${SCRIPT_DIR}/agents"
AGENTS_DST="${CLAUDE_DIR}/agents"
SKILL_DST="${CLAUDE_DIR}/skills/conclave"

run() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "DRY-RUN: $*"
  else
    eval "$@"
  fi
}

echo "Installing Sovereign Conclave into ${CLAUDE_DIR}"
run "mkdir -p '${AGENTS_DST}'"
run "mkdir -p '${SKILL_DST}'"

# Council subagents (skip the template).
shopt -s nullglob
for agent in "${AGENTS_SRC}"/conclave-*.md; do
  run "cp '${agent}' '${AGENTS_DST}/'"
done

# The skill itself, plus the docs it references at runtime.
run "cp '${SCRIPT_DIR}/SKILL.md' '${SKILL_DST}/SKILL.md'"
for doc in directives.md roster.md; do
  [[ -f "${SCRIPT_DIR}/${doc}" ]] && run "cp '${SCRIPT_DIR}/${doc}' '${SKILL_DST}/'"
done
[[ -d "${SCRIPT_DIR}/demos" ]] && run "cp -R '${SCRIPT_DIR}/demos' '${SKILL_DST}/'"

echo "Done. Restart Claude Code; the /conclave command will be available."
