#!/usr/bin/env bash
# publish.sh — promote the current Gitea state to the live GitHub Pages site.
#
# Workflow:
#   1. Edit locally, commit, `git push` (or `git push origin main`) → goes to Gitea ONLY.
#      Test at http://127.0.0.1:8766/ (local preview server).
#   2. When happy, run `./scripts/publish.sh` → pushes the same Gitea commit to GitHub.
#      GitHub Pages auto-deploys to https://bitcoinwallet.guide/ in ~30 seconds.
#
# Safety: refuses to push if local main has commits not on origin/main (i.e. not yet
# tested against Gitea), or if origin/main and github/main would diverge in a way
# that requires a force-push.

set -euo pipefail

cd "$(dirname "$0")/.."

GITEA_REMOTE="origin"
GITHUB_REMOTE="github"
BRANCH="main"

# Helper for colored output
c_green='\033[0;32m'
c_yellow='\033[0;33m'
c_red='\033[0;31m'
c_reset='\033[0m'

say()  { printf "${c_green}==>${c_reset} %s\n" "$1"; }
warn() { printf "${c_yellow}!!!${c_reset} %s\n" "$1"; }
die()  { printf "${c_red}xxx${c_reset} %s\n" "$1" >&2; exit 1; }

say "Fetching both remotes..."
git fetch "$GITEA_REMOTE" --quiet
git fetch "$GITHUB_REMOTE" --quiet

LOCAL=$(git rev-parse "$BRANCH")
GITEA=$(git rev-parse "$GITEA_REMOTE/$BRANCH")
GITHUB=$(git rev-parse "$GITHUB_REMOTE/$BRANCH" 2>/dev/null || echo "MISSING")

say "Local   $BRANCH:  $(git rev-parse --short $BRANCH)"
say "Gitea   $BRANCH:  $(git rev-parse --short $GITEA_REMOTE/$BRANCH)"
if [ "$GITHUB" = "MISSING" ]; then
  say "GitHub  $BRANCH:  (no remote tracking ref — first publish)"
else
  say "GitHub  $BRANCH:  $(git rev-parse --short $GITHUB_REMOTE/$BRANCH)"
fi
echo

# Safety check 1: working tree clean
if ! git diff --quiet || ! git diff --cached --quiet; then
  die "Working tree has uncommitted changes. Commit or stash before publishing."
fi

# Safety check 2: local must match Gitea (test loop has been completed)
if [ "$LOCAL" != "$GITEA" ]; then
  die "Local $BRANCH ($LOCAL) does not match $GITEA_REMOTE/$BRANCH ($GITEA). Push to Gitea first: git push $GITEA_REMOTE $BRANCH"
fi

# If already in sync, nothing to do
if [ "$GITEA" = "$GITHUB" ]; then
  say "GitHub is already at $(git rev-parse --short $BRANCH) — nothing to publish."
  exit 0
fi

# Safety check 3: would the push fast-forward, or require force?
if [ "$GITHUB" != "MISSING" ] && ! git merge-base --is-ancestor "$GITHUB" "$LOCAL"; then
  warn "GitHub $BRANCH has commits NOT in your local $BRANCH:"
  git log --oneline "$LOCAL..$GITHUB"
  echo
  die "Refusing to publish — this would require a force-push and might drop commits made directly on GitHub. Investigate before retrying."
fi

# Show what's about to be published
echo
say "Commits to publish to https://bitcoinwallet.guide/ :"
if [ "$GITHUB" = "MISSING" ]; then
  git log --oneline "$LOCAL" | head -10
else
  git log --oneline "$GITHUB..$LOCAL"
fi
echo

# Confirm
read -p "$(printf "${c_yellow}?${c_reset} Publish to GitHub Pages (live)? [y/N] ")" -n 1 -r REPLY
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  warn "Aborted by user. Nothing pushed."
  exit 1
fi

say "Pushing to $GITHUB_REMOTE/$BRANCH..."
git push "$GITHUB_REMOTE" "$BRANCH"
echo

# Push tags too if any are local-only
LOCAL_TAGS=$(git tag --list)
if [ -n "$LOCAL_TAGS" ]; then
  say "Syncing tags to GitHub..."
  git push "$GITHUB_REMOTE" --tags --quiet || warn "Some tags failed to push (probably already exist on GitHub) — that's fine."
fi

# Bump version.json so the footer hash reflects the live deploy
if [ -x scripts/bump-version.sh ]; then
  ./scripts/bump-version.sh > /dev/null
  say "Bumped version.json to $(git rev-parse --short HEAD)"
fi

echo
say "Published. GitHub Pages will redeploy in ~30 seconds."
say "Live: https://bitcoinwallet.guide/"
