#!/usr/bin/env bash
# Read-only guard for worktrees that may predate the canonical Ghar Sajag context.
set -u

CANONICAL_REPO='/home/udaybhan/projects/Ghar_sajag_r1'
CANONICAL_REF='feature/r1-commercial-baseline'

# Overrides exist only for isolated temporary-fixture validation.
if [[ "${GHAR_SAJAG_PREFLIGHT_TESTING:-0}" == '1' ]]; then
  CANONICAL_REPO="${GHAR_SAJAG_TEST_CANONICAL_REPO:-$CANONICAL_REPO}"
  CANONICAL_REF="${GHAR_SAJAG_TEST_CANONICAL_REF:-$CANONICAL_REF}"
fi

REQUIRED_FILES=(
  'AGENTS.md'
  'docs/product/CONTEXT_VERSION'
  'docs/product/GHAR_SAJAG_PROJECT_CONTEXT.md'
  'docs/product/R1_RELEASE_CONTRACT.md'
  'docs/product/R1_WORK_STATE.md'
  'docs/product/CANONICAL_REQUIREMENTS_INDEX.md'
  'docs/product/DECISION_LOG.md'
  'docs/product/P0_PRODUCT_REQUIREMENTS.md'
  'docs/architecture/STORAGE_SYNC_ROUTINE_LEARNING.md'
)

status='INCOMPLETE'
action='STOP_BEFORE_SUBSTANTIVE_IMPLEMENTATION'
worktree='UNKNOWN'
branch='UNKNOWN'
head='UNKNOWN'
local_version='MISSING'
canonical_version='MISSING'
reason=''

if ! worktree="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  reason='LOCAL_GIT_WORKTREE_NOT_FOUND'
else
  branch="$(git -C "$worktree" branch --show-current 2>/dev/null || true)"
  [[ -n "$branch" ]] || branch='DETACHED'
  head="$(git -C "$worktree" rev-parse HEAD 2>/dev/null || printf UNKNOWN)"
fi

missing_local=()
if [[ "$worktree" != 'UNKNOWN' ]]; then
  for file in "${REQUIRED_FILES[@]}"; do
    [[ -f "$worktree/$file" ]] || missing_local+=("$file")
  done
  if [[ -f "$worktree/docs/product/CONTEXT_VERSION" ]]; then
    local_version="$(sed -n 's/^GHAR_SAJAG_CONTEXT_VERSION=//p' "$worktree/docs/product/CONTEXT_VERSION" | head -n 1)"
    [[ -n "$local_version" ]] || local_version='INVALID'
  fi
fi

canonical_root=''
canonical_branch=''
if [[ -d "$CANONICAL_REPO" ]] && git -C "$CANONICAL_REPO" rev-parse --show-toplevel >/dev/null 2>&1; then
  canonical_root="$(cd "$CANONICAL_REPO" && pwd -P)"
  canonical_branch="$(git -C "$canonical_root" branch --show-current 2>/dev/null || true)"
  if [[ "$canonical_branch" == "$CANONICAL_REF" ]] && \
     git -C "$canonical_root" rev-parse --verify --quiet "refs/heads/$CANONICAL_REF" >/dev/null; then
    if [[ -f "$canonical_root/docs/product/CONTEXT_VERSION" ]]; then
      canonical_version="$(sed -n 's/^GHAR_SAJAG_CONTEXT_VERSION=//p' "$canonical_root/docs/product/CONTEXT_VERSION" | head -n 1)"
      [[ -n "$canonical_version" ]] || canonical_version='INVALID'
    fi
  else
    reason='CANONICAL_REPOSITORY_NOT_ON_DESIGNATED_REF'
  fi
else
  reason='CANONICAL_REPOSITORY_OR_GIT_REF_NOT_FOUND'
fi

missing_canonical=()
if [[ -n "$canonical_root" && "$canonical_branch" == "$CANONICAL_REF" ]]; then
  for file in "${REQUIRED_FILES[@]}"; do
    [[ -f "$canonical_root/$file" ]] || missing_canonical+=("$file")
  done
fi

if [[ "$worktree" != 'UNKNOWN' && -n "$canonical_root" && "$canonical_branch" == "$CANONICAL_REF" && \
      ${#missing_local[@]} -eq 0 && ${#missing_canonical[@]} -eq 0 && \
      "$local_version" != 'INVALID' && "$canonical_version" != 'INVALID' && \
      "$local_version" != 'MISSING' && "$canonical_version" != 'MISSING' ]]; then
  if [[ "$local_version" == "$canonical_version" ]]; then
    status='PASS'
    action='FOLLOW_REPOSITORY_AGENTS_AND_CANONICAL_REQUIREMENTS'
    reason=''
  else
    status='STALE'
    reason='CONTEXT_VERSION_MISMATCH'
  fi
fi

printf 'GHAR_SAJAG_CONTEXT_PREFLIGHT=%s\n' "$status"
printf 'LOCAL_CONTEXT_VERSION=%s\n' "$local_version"
printf 'CANONICAL_CONTEXT_VERSION=%s\n' "$canonical_version"
printf 'CANONICAL_SOURCE=%s@%s\n' "$CANONICAL_REPO" "$CANONICAL_REF"
printf 'WORKTREE=%s\n' "$worktree"
printf 'BRANCH=%s\n' "$branch"
printf 'HEAD=%s\n' "$head"
[[ -z "$reason" ]] || printf 'REASON=%s\n' "$reason"
[[ ${#missing_local[@]} -eq 0 ]] || printf 'MISSING_LOCAL_FILES=%s\n' "${missing_local[*]}"
[[ ${#missing_canonical[@]} -eq 0 ]] || printf 'MISSING_CANONICAL_FILES=%s\n' "${missing_canonical[*]}"
[[ "$status" == 'PASS' ]] || printf 'ACTION=%s\n' "$action"

[[ "$status" == 'PASS' ]]
