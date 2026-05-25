#!/usr/bin/env bash
set -euo pipefail

# Weekly bitcoinwallet.guide maintenance runner for maintainer infrastructure.
# Intended TTMF systemd working directory: /srv/www/bitcoin-wallet-guide
# This updates Gitea/TTMF preview only. It does NOT publish to GitHub Pages/live.
# See docs/wallet-research-automation.md for source model, flags, outputs, and guardrails.

REPO_DIR="${BWG_REPO_DIR:-/srv/www/bitcoin-wallet-guide}"
STAMP="${BWG_WEEKLY_STAMP:-$(date -u +%Y%m%d-%H%M%S)}"
TIMEOUT="${BWG_WEEKLY_TIMEOUT:-15}"
WORKERS="${BWG_WEEKLY_WORKERS:-10}"

cd "$REPO_DIR"

python3 scripts/wallet_weekly_research.py \
  --stamp "$STAMP" \
  --timeout "$TIMEOUT" \
  --workers "$WORKERS" \
  --git-sync \
  --run-hermes \
  --apply-staged-patch \
  --commit-and-push
