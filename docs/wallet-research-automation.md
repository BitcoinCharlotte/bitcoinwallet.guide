# Wallet Research Automation

BitcoinWallet.Guide is intentionally static and privacy-preserving. The weekly wallet research workflow keeps the wallet list current without adding visitor tracking, analytics, accounts, server code, or public clutter to the picker UI.

The short version: the script gathers evidence, stages review artifacts, and optionally applies a reviewed patch to `index.html`. It never publishes the live GitHub Pages site.

## Goals

- Catch dead or redirected wallet links.
- Notice stale App Store / Google Play / desktop / hardware purchase links.
- Track official wallet blogs, release pages, and source repositories without rendering those maintenance URLs on the public site.
- Watch a small set of high-signal discovery resources for new wallet candidates and broader wallet ecosystem changes.
- Generate objective review artifacts before changing public recommendations.

## Source model

There are two layers of maintenance sources.

### 1. Per-wallet sources

File: [`data/wallet-research-sources.json`](../data/wallet-research-sources.json)

Each wallet id can define hidden maintenance links grouped as:

- `news` — official blog, announcement feed, project site, or best available project update channel.
- `releases` — GitHub releases, app-store version history, changelog, or release page.
- `source` — official source repository or organization.

These links are scanned as evidence only. They are **not** rendered on the website.

The site currently tracks hidden maintenance sources for every wallet in `index.html`: 49 wallet entries, 53 news/blog links, 57 release links, and 40 source links.

### 2. Global discovery / cross-check resources

File: [`data/wallet-discovery-resources.json`](../data/wallet-discovery-resources.json)

These are not tied to one wallet. They are used to discover new wallet candidates or cross-check ecosystem changes:

- No Bullshit Bitcoin releases and sitemap.
- Bitcoin Optech newsletters.
- F-Droid, Apple, and Google Play wallet searches.
- GitHub topic pages: `bitcoin-wallet`, `lightning-wallet`, `ecash-wallet`, `nostr-wallet`.
- Nostr notes search via Primal.
- Stacker News wallet search.
- OpenSats and Spiral blog feeds.

Deliberately excluded from global discovery:

- Broad wallet directories and comparison indexes. They are too noisy for weekly discovery.
- Bitcoin Magazine wallet tags. Also too noisy.
- WalletScrutiny as a global feed. WalletScrutiny belongs on future individual wallet pages as per-wallet legitimacy / reproducibility context, not as a weekly discovery source.

## Main script

Script: [`scripts/wallet_weekly_research.py`](../scripts/wallet_weekly_research.py)

What it does by default:

1. Parses `const WALLETS = [...]` from `index.html` using Node's `vm` module instead of brittle regex parsing.
2. Fetches visible wallet URLs from the wallet data:
   - `url`
   - `appStore`
   - `playStore`
   - `desktop`
   - `buyUrl`
3. Fetches hidden per-wallet maintenance sources from `data/wallet-research-sources.json`.
4. Fetches global discovery resources from `data/wallet-discovery-resources.json`, unless `--skip-discovery` is passed.
5. Records objective metadata:
   - HTTP status
   - final URL after redirects
   - content type
   - page `<title>` when available
   - meta description when available
   - timeout / DNS / fetch errors
6. Writes review artifacts under `reports/weekly/<stamp>/`.

The script uses only Python standard-library networking plus local Node for wallet-array extraction. There is no package install step.

## Output artifacts

Generated reports are ignored by git via `reports/weekly/`.

Each run writes:

- `wallet-research.json` — raw machine-readable snapshot.
- `snapshot-summary.md` — readable link and discovery-resource summary.
- `source-inventory.md` — full hidden source and global discovery URL list for audit.
- `stage-proposal.prompt.md` — self-contained prompt for generating a proposed website patch.

When `--run-hermes` is used, the run should also produce:

- `proposal-summary.md` — human review table of proposed changes.
- `staged-wallet-updates.patch` — non-applied patch targeting `index.html` only.
- `hermes-response.txt` — captured Hermes stdout/stderr for debugging.

When `--apply-staged-patch` is also used, the run can additionally produce:

- `website-change-summary.md` — before/after summary intended for maintainer chat delivery.

## Manual commands

Smoke test first. This catches parser/runtime failures without scanning every source.

```bash
python3 scripts/wallet_weekly_research.py \
  --limit 3 \
  --skip-discovery \
  --timeout 5 \
  --workers 3
```

Full snapshot:

```bash
python3 scripts/wallet_weekly_research.py \
  --timeout 10 \
  --workers 10
```

Full snapshot plus staged Hermes proposal:

```bash
python3 scripts/wallet_weekly_research.py \
  --run-hermes \
  --timeout 10 \
  --workers 10
```

Automated review/apply mode, intended only for maintainer infrastructure:

```bash
python3 scripts/wallet_weekly_research.py \
  --git-sync \
  --run-hermes \
  --apply-staged-patch \
  --commit-and-push \
  --timeout 15 \
  --workers 10
```

That mode requires a clean working tree, a working `hermes` CLI, valid git credentials for the existing Gitea `origin/main`, and a staged patch that passes `git apply --check`.

## Maintainer automation wrapper

Script: [`scripts/wallet_weekly_ttmf_runner.sh`](../scripts/wallet_weekly_ttmf_runner.sh)

The wrapper is a thin shell entry point for a weekly systemd timer on the maintainer server. It runs the automated review/apply command above with environment-variable overrides:

| Variable | Default | Purpose |
|---|---|---|
| `BWG_REPO_DIR` | `/srv/www/bitcoin-wallet-guide` | Repo path to run from |
| `BWG_WEEKLY_STAMP` | UTC timestamp | Report folder name |
| `BWG_WEEKLY_TIMEOUT` | `15` | Per-request timeout in seconds |
| `BWG_WEEKLY_WORKERS` | `10` | Concurrent wallet scan workers |

Important guardrails:

- It syncs from `origin/main` before scanning.
- It aborts if the working tree is dirty before the run.
- It applies a generated patch only after `git apply --check` succeeds.
- It parses `WALLETS` after patch application to catch JavaScript syntax breakage.
- It commits and pushes only `index.html` changes to the existing Gitea `origin/main`.
- It does **not** run `scripts/publish.sh`.
- It does **not** push to GitHub Pages.
- Public live publish remains a separate maintainer action after preview review.

## Review policy

The script can collect evidence and stage changes. It should not become a blind recommendation machine.

Use conservative rules:

- Prefer official project sources over third-party claims.
- Do not add a wallet automatically just because it appears in a discovery source.
- Do not remove or archive a wallet from one failed link check; confirm with official sources.
- Keep descriptions short, neutral, and newcomer-oriented.
- Avoid marketing phrases copied from wallet homepages.
- Treat custody, `notBitcoinOnly`, and `archived` changes as high-impact; they need strong evidence.
- Add F-Droid links only when the wallet officially publishes or clearly endorses that package. Do not link unofficial mirrors.
- WalletScrutiny evidence belongs on future individual wallet pages, not the global weekly discovery scan.

## Failure behavior

Expected rough edges:

- GitHub topic pages may rate-limit or bot-check (`429`). That is a source availability problem, not evidence that the source is bad.
- App stores may block, redirect, geo-filter, or return noisy HTML. Record the result and review manually.
- A timeout is a signal to investigate, not proof that a wallet is dead.
- Generated reports are evidence snapshots, not canonical history.

If automation fails, fix the cause before rerunning. Do not just keep restarting it and hoping the smoke clears; that's how automation turns into a haunted lawn sprinkler.
