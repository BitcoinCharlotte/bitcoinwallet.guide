# Bitcoin Wallet Guide

**bitcoinwallet.guide** — URL-encoded wallet recommendation tool for meetups and educators.

## Source Code

**Gitea repo:** `btcknight21/bitcoin-wallet-guide` on Start9
- Source of truth: `/home/setup/sites/bitcoin-wallet-guide/`
- Served by Caddy on port 8082
- Backed up nightly to Gitea

## Architecture

- 100% static — no backend, no database, no accounts
- State in URL — wallet selections + custom text encoded in URL fragment
- QR-safe — URL kept under ~1,000 chars for reliable QR scanning
- Two modes: Builder (pick wallets + write welcome) and Landing (clean page for newbies)

## Wallet Database

44 Bitcoin-only wallets across categories:
- ⚡ Lightning (self-custodial & custodial)
- 🔗 On-chain
- 🔒 Hardware
- 🔐 Multi-sig
- 💰 Exchange / on-ramps
- 🫂 eCash (Fedimint & Cashu)

## Domain

- **bitcoinwallet.guide** — purchased 2026-03-24 (~$5K in BTC)
- Not yet pointed to hosting — currently served on Tailscale only

## Key Decisions

- No specific wallet names on flyers — the site handles recommendations via customizable links
- Welcome message supports markdown links `[text](url)` with anti-scam URL verification
- Filter pills for discovery, not category sections
- All wallet icons sourced and stored locally (128x128 PNG)

## TODO

- [ ] Add Bitcoin Keeper to the wallet database
