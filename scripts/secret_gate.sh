#!/usr/bin/env bash
# Secret gate — freaktown. Prints nothing on success; exits 1 with the
# offending lines if a key-shaped string is in the tracked content.
# Used by .git/hooks/pre-commit + pre-push (installed locally, never committed).
#
#   scripts/secret_gate.sh tree    # scan tracked files at HEAD
#   scripts/secret_gate.sh index   # scan what is staged right now
#   scripts/secret_gate.sh sha REV # scan the tracked tree at a commit (pre-push)
#
# Allowlist: documentation lines that name the patterns themselves, and
# vendor placeholders. Everything else blocks.
set -u

PAT='sk-ws-|sk-fish-|fal_sk_|msy_|sk-or-v1-|wl_live_|ghp_[A-Za-z0-9]{10,}|gho_[A-Za-z0-9]{10,}|cfat_[A-Za-z0-9]{10,}|sk-[A-Za-z0-9]{24,}'
ALLOW='replace_with_your_key|your_key_here|secret_gate|grep -rIlE|PASTE_YOUR|EXAMPLE_|redacted'

mode="${1:-tree}"
rev="${2:-}"
case "$mode" in
  tree)  scan() { git grep -I -nE "$PAT" HEAD -- . ; } ;;
  index) scan() { git grep --cached -I -nE "$PAT" -- . ; } ;;
  sha)
    [ -n "$rev" ] || { echo "secret_gate: sha mode needs a revision" >&2; exit 2; }
    scan() { git grep -I -nE "$PAT" "$rev" -- . ; } ;;
  *) echo "secret_gate: unknown mode '$mode' (use tree|index|sha REV)" >&2; exit 2 ;;
esac

hits=$(scan 2>/dev/null | grep -vE "$ALLOW" || true)
if [ -n "$hits" ]; then
  echo "secret_gate: BLOCKED — key-shaped string in tracked $mode content:" >&2
  echo "$hits" | sed 's/^/  /' >&2
  echo "Move it to .env (gitignored, mode 600). Nothing leaves this box." >&2
  exit 1
fi
exit 0
