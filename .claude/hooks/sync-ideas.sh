#!/usr/bin/env bash
# UserPromptSubmit hook for the wotmod-planner skill.
#
# Two jobs, both keyed on the planner session registered in
# .git/.plan-saver-session (written by plan-saver-register.sh when the skill
# activates):
#
#   1. Stash THIS session's id (+ transcript path) to .git/.current-session so the
#      planner skill can learn its own id and register itself. Hooks are the only
#      place the session id is reliably available (Claude Code passes it on stdin).
#
#   2. Turn EXTERNAL edits to TASKS.md into "pings". Any session that changes
#      TASKS.md (e.g. deletes a shipped idea while cleaning up) appends a
#      session-tagged ping line to .git/.plan-saver-pings. On the *registered
#      planner session's* next turn, if pings from other sessions are pending,
#      this prints a nudge on stdout — which Claude Code injects into the model's
#      context — so the planner reconciles its mirrored task list, then clears the
#      queue. Non-planner sessions get no nudge, so this adds no noise for them.
#
# The task list can only be mutated by the model on a turn, so this is turn-level
# ("next prompt") sync, not instantaneous — that is the closest achievable pattern.
set -uo pipefail

# Read the hook payload (JSON on stdin) and pull out this session's id + transcript.
input="$(cat 2>/dev/null || true)"
sid="$(printf '%s' "$input" | grep -oE '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*"([^"]*)"$/\1/')"
transcript="$(printf '%s' "$input" | grep -oE '"transcript_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed -E 's/.*"([^"]*)"$/\1/')"

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
tasks="$repo_root/TASKS.md"
# Per-repo state, stashed inside .git (never committed).
hash_marker="$repo_root/.git/.ideas-md-hash"
current="$repo_root/.git/.current-session"
registered_file="$repo_root/.git/.plan-saver-session"
pings="$repo_root/.git/.plan-saver-pings"

# Record this session's id so plan-saver-register.sh can pick it up.
if [ -n "$sid" ]; then
  { printf '%s\n' "$sid"; [ -n "$transcript" ] && printf '%s\n' "$transcript"; } > "$current" 2>/dev/null || true
fi

# No backlog file -> nothing to sync.
[ -f "$tasks" ] || exit 0

# git hash-object is the most portable content hash (git is always present); fall
# back to sha256sum if needed.
cur="$(git hash-object "$tasks" 2>/dev/null || sha256sum "$tasks" 2>/dev/null | awk '{print $1}')"
[ -n "$cur" ] || exit 0

prev=""
[ -f "$hash_marker" ] && prev="$(cat "$hash_marker" 2>/dev/null || true)"
printf '%s' "$cur" > "$hash_marker" 2>/dev/null || true

# On a real change (and not the first run in this repo), append a session-tagged
# ping. Format: "<author_session_id>\t<hash>". "unknown" if the id wasn't parsed.
if [ -n "$prev" ] && [ "$cur" != "$prev" ]; then
  printf '%s\t%s\n' "${sid:-unknown}" "$cur" >> "$pings" 2>/dev/null || true
fi

# Only the registered planner session reacts to pings.
registered=""
[ -f "$registered_file" ] && registered="$(cat "$registered_file" 2>/dev/null || true)"
[ -n "$registered" ] && [ -n "$sid" ] && [ "$sid" = "$registered" ] || exit 0
[ -s "$pings" ] || exit 0

# Count pings authored by OTHER sessions (self-authored edits are already reflected
# in this session's task list, so they don't warrant a nudge).
others="$(awk -F'\t' -v me="$sid" '$1 != me && $1 != "" {n++} END {print n+0}' "$pings" 2>/dev/null || echo 0)"

# Clear the queue now that the planner is about to reconcile.
: > "$pings" 2>/dev/null || true

if [ "$others" -gt 0 ]; then
  cat <<'EOF'
[planner] TASKS.md was changed by another session since your last turn (e.g. a
shipped idea was pruned during cleanup). Re-read the ## Open section of TASKS.md and
reconcile the mirrored task list: add tasks for new entries, and complete/delete
tasks for removed or shipped entries.
EOF
fi
exit 0
