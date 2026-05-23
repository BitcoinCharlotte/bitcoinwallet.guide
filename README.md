# BitcoinWallet.Guide

> The Bitcoin onboarding toolkit for meetup organizers and educators.

A free, no-signup, no-tracking tool that lets you curate a personalized list of recommended Bitcoin wallets and share it as a single link. Built for the people teaching Bitcoin to newcomers.

🔗 **Live site:** [bitcoinwallet.guide](https://bitcoinwallet.guide/)

## What it does today

- **Browse 50 Bitcoin wallets**, filtered by category (Lightning, on-chain, hardware, multi-sig, exchange, eCash), custody (self / custodial / community), and platform (iOS, Android, desktop, web).
- **Select the wallets you recommend**, add a personal welcome message (Markdown links supported), and generate a shareable link.
- **Recipients land on a clean curated page** with direct App Store / Google Play / website / "buy hardware" links per wallet — plus a built-in QR code to scan onto another device.
- **Visual safety signals** so newcomers can see the trade-offs at a glance:
  - ₿ **Bitcoin-only** wallets are clearly badged
  - 🟡 **Yellow border** on wallets worth vetting carefully (Bitcoin-supporting but with caveats)
  - 🔴 **Red border** on wallets that aren't Bitcoin-only (still listed because newcomers will ask about them, but visually deprioritized and sorted to the bottom)
- **Selection and message are encoded entirely in the URL fragment.** **No server. No accounts. No cookies. No tracking. No analytics.**

## On the roadmap

- **Printable flyers** — curated wallet recommendations as a one-page handout, designed to print.
- **Bitcoin stickers** — meetup-ready sticker sheets.
- **Resource printables** — beginner-friendly cheat sheets and reference cards.
- **i18n** — translations for non-English meetups.
- All output customizable with your meetup's name, logo, and contact info — so you can hand out something that's actually *yours*.

## Run it locally

It's a single static file. Any HTTP server works:

```bash
git clone https://github.com/BitcoinCharlotte/bitcoinwallet.guide.git
cd bitcoinwallet.guide
python3 -m http.server 8000
# open http://localhost:8000
```

No build step, no dependencies, no toolchain. The whole app lives in `index.html` — HTML, CSS, JavaScript, the wallet database, and inline Lucide SVG icons. Edit, refresh, ship.

## Project layout

```
.
├── index.html        # The entire app — HTML, CSS, JS, embedded wallet data, inline icons
├── icons/            # PNG icons for each wallet
├── CNAME             # GitHub Pages custom domain
├── .nojekyll         # Tells GitHub Pages to skip Jekyll processing
├── 404.html          # Branded "page not found" page
├── og-image.png      # Open Graph social-share image
├── version.json      # Footer commit hash for "this site is from commit X" verification
├── LICENSE           # MIT
└── README.md
```

## Contributing

PRs welcome — especially for:

- **Wallet additions, corrections, or stale descriptions** (the space moves fast)
- **Icon updates** when a wallet rebrands
- **Accessibility improvements**
- **Translations** (i18n is on the roadmap)
- **Bug fixes and polish**

To add or edit a wallet, look for the `const WALLETS = [` block inside `index.html`. Each entry follows the same shape — keep descriptions short, accurate, and useful for someone who has never owned Bitcoin before.

### Wallet entry fields

| Field | Required | Notes |
|---|---|---|
| `id`, `name`, `description` | yes | Description should be one sentence, plain language |
| `platforms` | yes | Array of `ios`, `android`, `desktop`, `web`, `hardware` |
| `categories` | yes | Array of `lightning`, `onchain`, `hardware`, `multisig`, `exchange`, `ecash` |
| `custody` | yes | One of `self-custodial`, `custodial`, `community` |
| `bitcoinOnly` | optional | Flag for clearly Bitcoin-only wallets |
| `notBitcoinOnly` | optional | Flag for multi-asset wallets (red border + sort to bottom) |
| `caution` | optional | Middle tier — wallet supports Bitcoin well but has caveats worth vetting (yellow border) |
| `url`, `icon` | yes | Canonical website + 64×64 PNG icon |
| `appStore`, `playStore`, `desktop`, `buyUrl` | optional | Per-platform download links |

## Why we built it

Bitcoin Charlotte runs in-person meetups in Charlotte, NC. Every meetup, someone new shows up and asks *"OK, but which wallet should I actually download?"* Pointing them at the right one depends on what they want to do — pay for coffee on Lightning, stack sats with hardware, run a self-custodial node. There was no good single answer to text them later. So we built one.

If your community needs the same thing — fork it, customize it, run with it. The MIT license means it's yours.

## License

MIT — see [LICENSE](./LICENSE). Built with care by [Bitcoin Charlotte](https://bitcoincharlotte.org).
