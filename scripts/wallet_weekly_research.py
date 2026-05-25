#!/usr/bin/env python3
"""Weekly wallet research + proposal staging for bitcoinwallet.guide.

What this script does:
1) Parses the WALLETS array from index.html (without brittle regex edits).
2) Fetches objective source signals from each wallet's official links:
   - HTTP status/final URL/content-type
   - <title> and meta description (when available)
3) Emits a dated research snapshot under reports/weekly/<stamp>/.
4) Emits a self-contained Hermes prompt that asks for objective
   description/tag proposals and a staged patch file for review.

This script does NOT modify index.html directly.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import textwrap
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = REPO_ROOT / "index.html"
REPORTS_ROOT = REPO_ROOT / "reports" / "weekly"

URL_FIELDS = ["url", "appStore", "playStore", "desktop", "buyUrl"]


def extract_wallets_via_node(index_path: Path) -> List[Dict[str, Any]]:
    """Use Node to evaluate `const WALLETS = [...]` safely in a sandbox.

    We avoid trying to hand-parse JS object literals in Python.
    """
    node_script = textwrap.dedent(
        r"""
        const fs = require('fs');
        const vm = require('vm');

        const file = process.argv[1];
        const src = fs.readFileSync(file, 'utf8');
        const marker = 'const WALLETS = [';
        const start = src.indexOf(marker);
        if (start === -1) {
          console.error('WALLETS marker not found');
          process.exit(2);
        }

        const open = src.indexOf('[', start);
        let depth = 0;
        let inSingle = false, inDouble = false, inTemplate = false;
        let escaped = false;
        let end = -1;

        for (let i = open; i < src.length; i++) {
          const ch = src[i];

          if (escaped) { escaped = false; continue; }
          if (ch === '\\') { escaped = true; continue; }

          if (!inDouble && !inTemplate && ch === "'") { inSingle = !inSingle; continue; }
          if (!inSingle && !inTemplate && ch === '"') { inDouble = !inDouble; continue; }
          if (!inSingle && !inDouble && ch === '`') { inTemplate = !inTemplate; continue; }

          if (inSingle || inDouble || inTemplate) continue;

          if (ch === '[') depth++;
          if (ch === ']') {
            depth--;
            if (depth === 0) {
              end = i;
              break;
            }
          }
        }

        if (end === -1) {
          console.error('Could not find end of WALLETS array');
          process.exit(3);
        }

        const arrayLiteral = src.slice(open, end + 1);
        const context = {};
        vm.createContext(context);
        vm.runInContext('WALLETS = ' + arrayLiteral, context, { timeout: 1000 });

        process.stdout.write(JSON.stringify(context.WALLETS));
        """
    )

    result = subprocess.run(
        ["node", "-e", node_script, str(index_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to parse WALLETS via Node (exit {result.returncode}): {result.stderr.strip()}"
        )

    wallets = json.loads(result.stdout)
    if not isinstance(wallets, list):
        raise RuntimeError("Parsed WALLETS is not a list")
    return wallets


def domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def extract_meta(html: str) -> Dict[str, str]:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not desc_match:
        # catch property-based patterns or different attr ordering
        desc_match = re.search(
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

    return {
        "title": normalize_ws(title_match.group(1)) if title_match else "",
        "meta_description": normalize_ws(desc_match.group(1)) if desc_match else "",
    }


def decode_response_body(resp: Any, max_bytes: int = 512_000) -> str:
    raw = resp.read(max_bytes)
    charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def capture_response(resp: Any, out: Dict[str, Any]) -> None:
    out["status_code"] = getattr(resp, "status", None) or getattr(resp, "code", None)
    out["final_url"] = resp.geturl()
    out["content_type"] = (resp.headers.get("content-type") or "").split(";")[0].strip()
    out["ok"] = 200 <= int(out["status_code"] or 0) < 400

    if "text/html" in (out["content_type"] or ""):
        meta = extract_meta(decode_response_body(resp))
        out.update(meta)


def fetch_source(url: str, timeout: int = 20) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "url": url,
        "domain": domain(url),
        "ok": False,
        "status_code": None,
        "final_url": None,
        "content_type": None,
        "title": "",
        "meta_description": "",
        "error": None,
    }
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; BWGWeeklyResearch/1.0; +https://bitcoinwallet.guide)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - URLs come from local wallet data.
            capture_response(resp, out)
    except urllib.error.HTTPError as e:
        # urllib raises for 4xx/5xx; keep the response metadata because those are useful review signals.
        capture_response(e, out)
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)
    return out


def build_wallet_snapshot(wallet: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    links = []
    for field in URL_FIELDS:
        val = wallet.get(field)
        if val and isinstance(val, str):
            links.append({"field": field, "url": val})

    sources = []
    for link in links:
        src = fetch_source(link["url"], timeout=timeout)
        src["field"] = link["field"]
        sources.append(src)

    return {
        "id": wallet.get("id"),
        "name": wallet.get("name"),
        "description": wallet.get("description"),
        "platforms": wallet.get("platforms", []),
        "categories": wallet.get("categories", []),
        "custody": wallet.get("custody"),
        "notBitcoinOnly": bool(wallet.get("notBitcoinOnly", False)),
        "archived": bool(wallet.get("archived", False)),
        "sources": sources,
    }


def write_markdown_summary(path: Path, report: Dict[str, Any]) -> None:
    wallets = report["wallets"]
    total = len(wallets)

    bad_links = []
    for w in wallets:
        for s in w["sources"]:
            if not s.get("ok"):
                bad_links.append((w["id"], s["field"], s["url"], s.get("status_code"), s.get("error")))

    lines = [
        "# Weekly Wallet Research Snapshot",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Wallets scanned: **{total}**",
        f"- Link checks: **{sum(len(w['sources']) for w in wallets)}**",
        f"- Failing link checks: **{len(bad_links)}**",
        "",
        "## Failing links",
        "",
    ]

    if not bad_links:
        lines.append("No failing links in this run. ✅")
    else:
        lines.append("| Wallet | Field | URL | Status | Error |")
        lines.append("|---|---|---|---:|---|")
        for wallet_id, field, url, status, error in bad_links:
            status_txt = "" if status is None else str(status)
            err_txt = (error or "").replace("|", "/")
            lines.append(f"| `{wallet_id}` | `{field}` | {url} | {status_txt} | {err_txt} |")

    lines.extend(
        [
            "",
            "## Next step",
            "",
            "Use `stage-proposal.prompt.md` in this same folder to generate objective description/tag proposals and a staged patch for review.",
        ]
    )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_prompt(path: Path, report_dir: Path, report_json: Path) -> None:
    rel_report_json = report_json.relative_to(REPO_ROOT)
    rel_out_patch = (report_dir / "staged-wallet-updates.patch").relative_to(REPO_ROOT)
    rel_out_md = (report_dir / "proposal-summary.md").relative_to(REPO_ROOT)

    prompt = textwrap.dedent(
        f"""
        You are working inside the bitcoinwallet.guide repo.

        Inputs:
        - Current app data in `index.html` (`const WALLETS = [...]`)
        - Weekly objective source snapshot in `{rel_report_json}`

        Task:
        1) Review each wallet objectively using the snapshot evidence (titles/meta descriptions/final URLs/statuses).
        2) Propose only high-confidence updates to:
           - `description`
           - `categories`
           - `platforms`
           - `custody`
           - `notBitcoinOnly`
           - `archived`
        3) Avoid marketing language. Keep descriptions concise, neutral, and useful to newcomers.
        4) If evidence is weak or ambiguous, keep the current value and note "needs manual review".
        5) Produce two artifacts:
           - A human review summary at `{rel_out_md}` with a table:
             wallet id | proposed change | reason | evidence URL(s) | confidence
           - A non-applied unified patch file at `{rel_out_patch}` that updates `index.html` only.
             Do NOT apply the patch. Stage for review only.

        Constraints:
        - No live publish.
        - No changes outside `index.html` in the patch.
        - Preserve JSON/JS syntax exactly.

        Final response format:
        - Short summary of how many wallets had proposed edits.
        - Absolute paths of both output artifacts.
        """
    ).strip() + "\n"

    path.write_text(prompt, encoding="utf-8")


def run_hermes_proposal(prompt_md: Path, report_dir: Path) -> None:
    prompt_text = prompt_md.read_text(encoding="utf-8")
    cmd = ["hermes", "chat", "-q", prompt_text]

    print("Running Hermes proposal stage...")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)

    response_path = report_dir / "hermes-response.txt"
    response_path.write_text(result.stdout + ("\nSTDERR:\n" + result.stderr if result.stderr else ""), encoding="utf-8")

    if result.returncode != 0:
        raise RuntimeError(
            "Hermes proposal stage failed. "
            f"See {response_path} for details. Exit code: {result.returncode}"
        )

    expected_md = report_dir / "proposal-summary.md"
    expected_patch = report_dir / "staged-wallet-updates.patch"

    missing = [p for p in (expected_md, expected_patch) if not p.exists()]
    if missing:
        missing_txt = ", ".join(str(p) for p in missing)
        raise RuntimeError(
            "Hermes completed but expected staged artifacts are missing: "
            f"{missing_txt}. See {response_path}."
        )

    print(f"Generated: {expected_md}")
    print(f"Generated: {expected_patch}")
    print(f"Log: {response_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run weekly wallet research snapshot + stage proposal prompt")
    parser.add_argument("--stamp", help="Override timestamp folder name (default: UTC yyyymmdd-HHMMSS)")
    parser.add_argument("--timeout", type=int, default=20, help="Per-request timeout seconds")
    parser.add_argument("--limit", type=int, help="Limit wallets scanned; useful for smoke tests")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent wallet scan workers")
    parser.add_argument(
        "--run-hermes",
        action="store_true",
        help="Run the staged Hermes proposal prompt automatically after snapshot generation.",
    )
    args = parser.parse_args()

    if not INDEX_HTML.exists():
        raise FileNotFoundError(f"index.html not found at {INDEX_HTML}")

    stamp = args.stamp or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_dir = REPORTS_ROOT / stamp
    report_dir.mkdir(parents=True, exist_ok=True)

    wallets = extract_wallets_via_node(INDEX_HTML)
    if args.limit:
        wallets = wallets[: args.limit]

    snapshots_by_index: Dict[int, Dict[str, Any]] = {}
    workers = max(1, min(args.workers, len(wallets) or 1))
    print(f"Scanning {len(wallets)} wallet(s) with {workers} worker(s), timeout={args.timeout}s...")

    def scan_one(index: int, wallet: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        return index, build_wallet_snapshot(wallet, timeout=args.timeout)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(scan_one, i, wallet) for i, wallet in enumerate(wallets)]
        for done_count, future in enumerate(as_completed(futures), start=1):
            index, snapshot = future.result()
            snapshots_by_index[index] = snapshot
            print(f"[{done_count}/{len(wallets)}] {snapshot.get('id') or snapshot.get('name')} scanned")

    snapshot_wallets = [snapshots_by_index[i] for i in range(len(wallets))]

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repo": "bitcoin-wallet-guide",
        "wallet_count": len(snapshot_wallets),
        "wallets": snapshot_wallets,
    }

    report_json = report_dir / "wallet-research.json"
    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary_md = report_dir / "snapshot-summary.md"
    write_markdown_summary(summary_md, report)

    prompt_md = report_dir / "stage-proposal.prompt.md"
    write_prompt(prompt_md, report_dir, report_json)

    print(f"Generated: {report_json}")
    print(f"Generated: {summary_md}")
    print(f"Generated: {prompt_md}")

    if args.run_hermes:
        run_hermes_proposal(prompt_md, report_dir)
    else:
        print("Next: run Hermes with the prompt to produce proposal-summary.md + staged-wallet-updates.patch")
        print(f"Example: hermes chat -q \"$(cat {prompt_md})\"")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
