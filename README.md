# BitcoinWallet.Guide

> The Bitcoin onboarding toolkit for meetup organizers and educators.

A free, no-signup, no-tracking tool that lets you curate a personalized list of recommended Bitcoin wallets and share it as a single link. Built for the people teaching Bitcoin to newcomers.

🔗 **Live site:** [bitcoinwallet.guide](https://bitcoinwallet.guide/)

## What it does today

- Browse 40+ Bitcoin wallets, filtered by category (Lightning, on-chain, hardware, multi-sig, exchange, eCash), custody (self vs. custodial), and platform (iOS, Android, desktop, web).
- Select the wallets you recommend, add a personal welcome message (Markdown links supported), and generate a shareable link.
- Recipients land on a clean, curated page with direct App Store / Google Play / website / "buy hardware" links per wallet — plus a built-in QR code to scan onto another device.
- Selection and message are encoded entirely in the URL fragment. **No server. No accounts. No tracking. No analytics.**

## On the roadmap

- **Printable flyers** — curated wallet recommendations as a one-page handout, designed to print.
- **Bitcoin stickers** — meetup-ready sticker sheets.
- **Resource printables** — beginner-friendly cheat sheets and reference cards.
- All output customizable with your meetup's name, logo, and contact info — so you can hand out something that's actually *yours*.

## Run it locally

It's a single static file. Any HTTP server works:

```bash
git clone https://github.com/BitcoinCharlotte/bitcoinwallet.guide.git
cd bitcoinwallet.guide
python3 -m http.server 8000
# open http://localhost:8000
```

No build step, no dependencies, no toolchain.

## Project layout

```
.
├── index.html        # The entire app — HTML, CSS, JS, and embedded wallet data
├── icons/            # PNG icons for each wallet
├── CNAME             # GitHub Pages custom domain
├── .nojekyll         # Tells GitHub Pages to skip Jekyll processing
├── 404.html          # Graceful redirect for unknown URLs
├── LICENSE           # MIT
└── README.md
```

## Contributing

PRs welcome — especially for:

- Wallet additions, corrections, or descriptions getting stale (the space moves fast)
- Icon updates when a wallet rebrands
- Accessibility improvements
- New languages (i18n is on the roadmap but not yet implemented)

To add or edit a wallet, look for the `const WALLETS = [` block inside `index.html`. Each entry follows the same shape — keep descriptions short, accurate, and useful for someone who has never owned Bitcoin before.

## Why we built it

Bitcoin Charlotte runs in-person meetups in Charlotte, NC. Every meetup, someone new shows up and asks *"OK, but which wallet should I actually download?"* Pointing them at the right one depends on what they want to do — pay for coffee on Lightning, stack sats with hardware, run a self-custodial node. There was no good single answer to text them later. So we built one.

If your community needs the same thing — fork it, customize it, run with it. The MIT license means it's yours.

## License

MIT — see [LICENSE](./LICENSE). Built with care by [Bitcoin Charlotte](https://bitcoincharlotte.org).
