# BitcoinWallet.Guide

> The Bitcoin onboarding toolkit for meetup organizers and educators.

A free, no-signup, no-tracking tool that lets you curate a personalized list of recommended Bitcoin wallets and share it as a single link. Built for the people teaching Bitcoin to newcomers.

🔗 **Live site:** [bitcoinwallet.guide](https://bitcoinwallet.guide/)

## What it does today

- **Browse 49 Bitcoin wallet entries** with title search and dropdown filters for region, type, and platform.
  - Search matches wallet names only.
  - Region is scaffolded now and currently defaults to **All regions**.
  - Type includes Lightning, on-chain, hardware, multi-sig, exchange, eCash, and custody-style groupings.
  - Platform includes iOS, Android, desktop, web, and hardware.
- **Select the wallets you recommend**, add a personal welcome message (Markdown links supported), and generate a shareable link.
- **Recipients land on a clean curated page** with direct App Store / Google Play / website / "buy hardware" links per wallet — plus a saveable QR code to scan onto another device.
- **Visual safety signals** keep the list readable without over-explaining:
  - 🔴 **Not Bitcoin-only** wallets are marked with a red badge and red card treatment.
  - ⚪ **Archived** wallets are dimmed and marked with an archived badge.
  - Bitcoin-only is the default assumption; it is not separately badged.
- **Selection and message are encoded entirely in the URL fragment.** **No server. No accounts. No cookies. No tracking. No analytics.**

## On the roadmap

- **Region / availability metadata** — real country/region filtering once wallet availability is tracked.
- **Printable flyers** — curated wallet recommendations as a one-page handout, designed to print.
- **Bitcoin stickers** — meetup-ready sticker sheets.
- **Resource printables** — beginner-friendly cheat sheets and reference cards.
- **i18n** — translations for non-English meetups.
- All output customizable with your meetup's name, logo, and contact info — so you can hand out something that's actually *yours*.

## Run it locally

It's a static site. Any HTTP server works:

```bash
git clone https://github.com/BitcoinCharlotte/bitcoinwallet.guide.git
cd bitcoinwallet.guide
python3 -m http.server 8000
# open http://localhost:8000
```

No build step, no package install, no JavaScript toolchain. The app lives in `index.html` with static assets in `icons/`, `lib/`, and the root image files. Edit, refresh, ship.

## Development & publish workflow

This repo is mirrored across two remotes:

| Remote | URL | Purpose |
|---|---|---|
| `origin` | Internal Gitea | Source of truth. All commits land here first. |
| `github` | github.com/BitcoinCharlotte/bitcoinwallet.guide | Public mirror. Pushes here trigger a GitHub Pages deploy to https://bitcoinwallet.guide/ |

**The flow:**

1. Edit locally → `git add` → `git commit`.
2. `git push origin main` → goes to Gitea only.
3. Test the internal preview. Do not assume a Gitea push means the public site changed.
4. **STOP. Confirm visually that everything looks right on the preview.** Don't skip this step — it's the whole point of the split.
5. When Jacob explicitly approves a live publish, run `./scripts/publish.sh` → promotes the same commit to GitHub. Pages auto-deploys in ~30 seconds.

**🚨 Hard rule for agents: never run `publish.sh` in the same turn as the Gitea push.** Push to Gitea, then stop and surrender the turn to Jacob. He'll tell you when to publish. The two are deliberately separate actions — bundling them defeats the safety of the workflow.

The publish script has safety checks: it refuses to publish if the working tree isn't clean, if local `main` is ahead of Gitea (untested), or if the push would require a force-push (i.e. GitHub has commits Gitea doesn't — investigate first).

This setup keeps "iterate fast" (push to Gitea, no public exposure) separate from "publish to the world" (an explicit, deliberate action).

## Project layout

```
.
├── index.html             # The app — HTML, CSS, JS, embedded wallet data, inline icons
├── icons/                 # PNG wallet icons and source/icon variants
├── lib/                   # Third-party browser libraries, including QR generation
├── scripts/
│   ├── bump-version.sh    # Generates version.json from the current HEAD commit
│   └── publish.sh         # Promotes tested Gitea state to GitHub Pages
├── CNAME                  # GitHub Pages custom domain
├── .nojekyll              # Tells GitHub Pages to skip Jekyll processing
├── 404.html               # Branded "page not found" page
├── og-image.png           # Open Graph social-share image
├── og-image.svg           # Source/vector social-share image
├── LICENSE                # MIT
└── README.md
```

`version.json` is generated during publish and intentionally ignored by git.

## Contributing

PRs welcome — especially for:

- **Wallet additions, corrections, or stale descriptions** (the space moves fast)
- **Icon updates** when a wallet rebrands
- **Accessibility improvements**
- **Translations** (i18n is on the roadmap)
- **Bug fixes and polish**

To add or edit a wallet, look for the `const WALLETS = [` block inside `index.html`. Each entry follows the same shape — keep descriptions short, objective, and useful for someone who has never owned Bitcoin before.

### Wallet entry fields

| Field | Required | Notes |
|---|---|---|
| `id`, `name`, `description` | yes | Description should be plain language: what it is and what it does |
| `platforms` | yes | Array of `ios`, `android`, `desktop`, `web`, `hardware` |
| `categories` | yes | Array of `lightning`, `onchain`, `hardware`, `multisig`, `exchange`, `ecash` |
| `custody` | yes | One of `self-custodial`, `custodial`, `community` |
| `notBitcoinOnly` | optional | Flag for wallets/apps that support non-Bitcoin assets (red badge + red card treatment) |
| `archived` | optional | Flag for kept-for-reference wallets that should not appear as current recommendations |
| `url`, `icon` | yes | Canonical website + wallet icon |
| `appStore`, `playStore`, `desktop`, `buyUrl` | optional | Per-platform download or purchase links |

## Why we built it

Bitcoin Charlotte runs in-person meetups in Charlotte, NC. Every meetup, someone new shows up and asks *"OK, but which wallet should I actually download?"* Pointing them at the right one depends on what they want to do — pay for coffee on Lightning, stack sats with hardware, run a self-custodial node. There was no good single answer to text them later. So we built one.

If your community needs the same thing — fork it, customize it, run with it. The MIT license means it's yours.

## License

MIT — see [LICENSE](./LICENSE). Built with care by [Bitcoin Charlotte](https://bitcoincharlotte.org).
