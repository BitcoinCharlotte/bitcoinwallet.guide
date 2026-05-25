#!/usr/bin/env python3
"""Weekly wallet research + proposal staging for bitcoinwallet.guide.

Default mode is evidence-only:
1) Parse the WALLETS array from index.html without brittle regex edits.
2) Fetch objective signals from visible wallet links, hidden per-wallet
   maintenance sources, and curated global discovery resources.
3) Emit dated review artifacts under reports/weekly/<stamp>/.
4) Emit a self-contained Hermes prompt for producing a human-reviewable
   proposal summary and a non-applied index.html patch.

Maintainer automation can opt into the full review/apply flow with:
--git-sync --run-hermes --apply-staged-patch --commit-and-push

Even in automation mode this script pushes only to the existing Gitea
origin/main preview path. It does not publish the live GitHub Pages site.
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
DATA_ROOT = REPO_ROOT / "data"
WALLET_SOURCE_FILE = DATA_ROOT / "wallet-research-sources.json"
DISCOVERY_RESOURCE_FILE = DATA_ROOT / "wallet-discovery-resources.json"

URL_FIELDS = ["url", "appStore", "playStore", "desktop", "buyUrl"]
EXTRA_SOURCE_GROUPS = ["news", "releases", "source"]


def load_json_file(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Load a JSON config file, returning default when it does not exist."""
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_wallet_source_config(path: Path = WALLET_SOURCE_FILE) -> Dict[str, Any]:
    """Load hidden per-wallet research sources (not rendered on the site)."""
    return load_json_file(path, {"wallets": {}})


def load_discovery_resource_config(path: Path = DISCOVERY_RESOURCE_FILE) -> Dict[str, Any]:
    """Load global resources used to discover new wallets and cross-check existing ones."""
    return load_json_file(path, {"resources": []})


def iter_extra_wallet_links(wallet_id: str | None, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return hidden research links for a wallet id from data/wallet-research-sources.json."""
    if not wallet_id:
        return []

    wallet_sources = (source_config.get("wallets") or {}).get(wallet_id) or {}
    links: List[Dict[str, Any]] = []
    for group in EXTRA_SOURCE_GROUPS:
        for idx, entry in enumerate(wallet_sources.get(group) or [], start=1):
            url = entry.get("url")
            if not url or not isinstance(url, str):
                continue
            links.append(
                {
                    "field": group,
                    "source_group": group,
                    "label": entry.get("label") or f"{group} #{idx}",
                    "url": url,
                    "notes": entry.get("notes", ""),
                    "type": entry.get("type", ""),
                    "hidden": True,
                }
            )
    return links


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


def build_wallet_snapshot(wallet: Dict[str, Any], timeout: int, source_config: Dict[str, Any]) -> Dict[str, Any]:
    links = []
    for field in URL_FIELDS:
        val = wallet.get(field)
        if val and isinstance(val, str):
            links.append(
                {
                    "field": field,
                    "source_group": "site",
                    "label": field,
                    "url": val,
                    "hidden": False,
                }
            )

    links.extend(iter_extra_wallet_links(wallet.get("id"), source_config))

    sources = []
    for link in links:
        src = fetch_source(link["url"], timeout=timeout)
        src["field"] = link["field"]
        src["source_group"] = link.get("source_group", link["field"])
        src["label"] = link.get("label", link["field"])
        src["hidden"] = bool(link.get("hidden", False))
        if link.get("notes"):
            src["notes"] = link["notes"]
        if link.get("type"):
            src["type"] = link["type"]
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


def build_discovery_resource_snapshot(resource: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    """Fetch one global discovery/cross-check resource."""
    url = resource.get("url")
    if not url or not isinstance(url, str):
        return {
            "name": resource.get("name", "unnamed"),
            "kind": resource.get("kind", ""),
            "why": resource.get("why", ""),
            "url": url,
            "ok": False,
            "error": "missing url",
        }

    snap = fetch_source(url, timeout=timeout)
    snap["name"] = resource.get("name", "")
    snap["kind"] = resource.get("kind", "")
    snap["why"] = resource.get("why", "")
    return snap


def scan_discovery_resources(resources: List[Dict[str, Any]], timeout: int, workers: int) -> List[Dict[str, Any]]:
    """Fetch global discovery resources concurrently."""
    if not resources:
        return []

    snapshots_by_index: Dict[int, Dict[str, Any]] = {}
    resource_workers = max(1, min(workers, len(resources)))
    print(f"Scanning {len(resources)} discovery resource(s) with {resource_workers} worker(s)...")

    def scan_one(index: int, resource: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        return index, build_discovery_resource_snapshot(resource, timeout=timeout)

    with ThreadPoolExecutor(max_workers=resource_workers) as executor:
        futures = [executor.submit(scan_one, i, resource) for i, resource in enumerate(resources)]
        for done_count, future in enumerate(as_completed(futures), start=1):
            index, snapshot = future.result()
            snapshots_by_index[index] = snapshot
            print(f"[resource {done_count}/{len(resources)}] {snapshot.get('name') or snapshot.get('url')} scanned")

    return [snapshots_by_index[i] for i in range(len(resources))]


def write_source_inventory(
    path: Path,
    wallets: List[Dict[str, Any]],
    source_config: Dict[str, Any],
    discovery_resources: List[Dict[str, Any]],
) -> None:
    """Write a human-readable list of every hidden wallet source and global resource URL."""
    lines = [
        "# Wallet Research Source Inventory",
        "",
        "These maintenance URLs are scanned by `scripts/wallet_weekly_research.py` and are not rendered on the site.",
        "",
        "## Per-wallet hidden sources",
        "",
        "| Wallet | News/blog URL(s) | Release URL(s) | Source URL(s) |",
        "|---|---|---|---|",
    ]

    configured_wallets = source_config.get("wallets") or {}
    for wallet in wallets:
        wallet_id = wallet.get("id")
        wallet_name = wallet.get("name") or wallet_id
        entry = configured_wallets.get(wallet_id) or {}

        def urls_for(group: str) -> str:
            urls = []
            for item in entry.get(group) or []:
                label = item.get("label") or group
                url = item.get("url")
                if url:
                    urls.append(f"{label}: {url}")
            return "<br>".join(urls) if urls else "—"

        lines.append(
            f"| {wallet_name} (`{wallet_id}`) | {urls_for('news')} | {urls_for('releases')} | {urls_for('source')} |"
        )

    lines.extend([
        "",
        "## Global discovery / cross-check resources",
        "",
        "| Resource | Kind | URL | Why |",
        "|---|---|---|---|",
    ])
    for resource in discovery_resources:
        lines.append(
            f"| {resource.get('name', '')} | {resource.get('kind', '')} | {resource.get('url', '')} | {resource.get('why', '').replace('|', '/')} |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown_summary(path: Path, report: Dict[str, Any]) -> None:
    wallets = report["wallets"]
    resources = report.get("discovery_resources", [])
    total = len(wallets)

    bad_links = []
    hidden_count = 0
    for w in wallets:
        for s in w["sources"]:
            if s.get("hidden"):
                hidden_count += 1
            if not s.get("ok"):
                bad_links.append(
                    (
                        w["id"],
                        s.get("source_group") or s.get("field"),
                        s.get("label") or s.get("field"),
                        s["url"],
                        s.get("status_code"),
                        s.get("error"),
                    )
                )

    bad_resources = [r for r in resources if not r.get("ok")]

    lines = [
        "# Weekly Wallet Research Snapshot",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Wallets scanned: **{total}**",
        f"- Wallet link checks: **{sum(len(w['sources']) for w in wallets)}**",
        f"- Hidden research-source checks: **{hidden_count}**",
        f"- Global discovery resources checked: **{len(resources)}**",
        f"- Failing wallet link checks: **{len(bad_links)}**",
        f"- Failing discovery resource checks: **{len(bad_resources)}**",
        "",
        "## Failing wallet links",
        "",
    ]

    if not bad_links:
        lines.append("No failing wallet links in this run. ✅")
    else:
        lines.append("| Wallet | Group | Label | URL | Status | Error |")
        lines.append("|---|---|---|---|---:|---|")
        for wallet_id, group, label, url, status, error in bad_links:
            status_txt = "" if status is None else str(status)
            err_txt = (error or "").replace("|", "/")
            lines.append(f"| `{wallet_id}` | `{group}` | {label} | {url} | {status_txt} | {err_txt} |")

    lines.extend(["", "## Failing discovery resources", ""])
    if not bad_resources:
        lines.append("No failing discovery resources in this run. ✅")
    else:
        lines.append("| Resource | Kind | URL | Status | Error |")
        lines.append("|---|---|---|---:|---|")
        for resource in bad_resources:
            status_txt = "" if resource.get("status_code") is None else str(resource.get("status_code"))
            err_txt = (resource.get("error") or "").replace("|", "/")
            lines.append(
                f"| {resource.get('name', '')} | {resource.get('kind', '')} | {resource.get('url', '')} | {status_txt} | {err_txt} |"
            )

    lines.extend(
        [
            "",
            "## Next step",
            "",
            "Use `stage-proposal.prompt.md` in this same folder to generate objective description/tag proposals and a staged patch for review.",
            "Use `source-inventory.md` for the full hidden wallet-source and discovery-resource URL list.",
        ]
    )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_prompt(path: Path, report_dir: Path, report_json: Path, source_inventory: Path) -> None:
    rel_report_json = report_json.relative_to(REPO_ROOT)
    rel_source_inventory = source_inventory.relative_to(REPO_ROOT)
    rel_out_patch = (report_dir / "staged-wallet-updates.patch").relative_to(REPO_ROOT)
    rel_out_md = (report_dir / "proposal-summary.md").relative_to(REPO_ROOT)

    prompt = textwrap.dedent(
        f"""
        You are working inside the bitcoinwallet.guide repo.

        Inputs:
        - Current app data in `index.html` (`const WALLETS = [...]`)
        - Weekly objective source snapshot in `{rel_report_json}`
        - Full hidden research-source inventory in `{rel_source_inventory}`

        Task:
        1) Review each wallet objectively using the snapshot evidence (titles/meta descriptions/final URLs/statuses).
        2) Treat hidden `news`, `releases`, and `source` links as maintenance-only evidence. Do not add them to the visible website.
        3) Use global discovery resources only to flag new wallet candidates or cross-check existing wallets; do not auto-add a new wallet.
        4) Propose only high-confidence updates to:
           - `description`
           - `categories`
           - `platforms`
           - `custody`
           - `notBitcoinOnly`
           - `archived`
        5) Avoid marketing language. Keep descriptions concise, neutral, and useful to newcomers.
        6) If evidence is weak or ambiguous, keep the current value and note "needs manual review".
        7) Produce two artifacts:
           - A human review summary at `{rel_out_md}` with a table:
             wallet id | proposed change | reason | evidence URL(s) | confidence
           - A non-applied unified patch file at `{rel_out_patch}` that updates `index.html` only.
             Do NOT apply the patch. Stage for review only.

        Constraints:
        - No live publish.
        - No visible blog/news/release/source links on the site.
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


def run_cmd(cmd: List[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a repo-local command and return captured output."""
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def git_sync() -> None:
    """Pull the existing Gitea main branch before an automated run."""
    status = run_cmd(["git", "status", "--porcelain"], check=True).stdout.strip()
    if status:
        raise RuntimeError(f"Working tree is dirty before git sync; aborting automated run:\n{status}")
    run_cmd(["git", "pull", "--rebase", "origin", "main"], check=True)


def wallet_map(wallets: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(w.get("id")): w for w in wallets if w.get("id")}


def changed_wallet_rows(before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> List[str]:
    before_by_id = wallet_map(before)
    after_by_id = wallet_map(after)
    rows = []
    all_ids = sorted(set(before_by_id) | set(after_by_id))
    for wallet_id in all_ids:
        old = before_by_id.get(wallet_id)
        new = after_by_id.get(wallet_id)
        if old == new:
            continue
        if old is None:
            rows.append(f"| `{wallet_id}` | added | — | {new.get('name', '') if new else ''} |")
            continue
        if new is None:
            rows.append(f"| `{wallet_id}` | removed | {old.get('name', '')} | — |")
            continue
        changed_fields = []
        for key in sorted(set(old) | set(new)):
            if old.get(key) != new.get(key):
                changed_fields.append(key)
        rows.append(
            f"| `{wallet_id}` | {', '.join(changed_fields)} | {json.dumps({k: old.get(k) for k in changed_fields}, ensure_ascii=False)} | {json.dumps({k: new.get(k) for k in changed_fields}, ensure_ascii=False)} |"
        )
    return rows


def apply_staged_patch(report_dir: Path) -> bool:
    """Apply the staged wallet update patch after checking it cleanly applies."""
    patch_path = report_dir / "staged-wallet-updates.patch"
    if not patch_path.exists():
        raise FileNotFoundError(f"Missing staged patch: {patch_path}")
    patch_text = patch_path.read_text(encoding="utf-8").strip()
    if not patch_text:
        print("Staged patch is empty; no website update to apply.")
        return False
    run_cmd(["git", "apply", "--check", str(patch_path)], check=True)
    run_cmd(["git", "apply", str(patch_path)], check=True)
    extract_wallets_via_node(INDEX_HTML)  # syntax/parse verification
    print(f"Applied staged patch: {patch_path}")
    return True


def commit_and_push_index_changes() -> tuple[str, bool]:
    """Commit and push index.html changes to the existing Gitea main branch."""
    diff_check = run_cmd(["git", "diff", "--quiet", "--", "index.html"], check=False)
    if diff_check.returncode == 0:
        return "", False
    run_cmd(["git", "add", "index.html"], check=True)
    run_cmd(["git", "commit", "-m", "chore(wallets): apply weekly research updates"], check=True)
    run_cmd(["git", "pull", "--rebase", "origin", "main"], check=True)
    run_cmd(["git", "push", "origin", "main"], check=True)
    commit_hash = run_cmd(["git", "rev-parse", "--short", "HEAD"], check=True).stdout.strip()
    return commit_hash, True


def write_website_change_summary(
    path: Path,
    before_wallets: List[Dict[str, Any]],
    after_wallets: List[Dict[str, Any]],
    proposal_summary: Path,
    commit_hash: str = "",
    pushed: bool = False,
) -> None:
    """Write the before/after summary intended for Matrix chat delivery."""
    rows = changed_wallet_rows(before_wallets, after_wallets)
    if commit_hash:
        diff_stat = run_cmd(["git", "show", "--stat", "--oneline", "--no-renames", "HEAD", "--", "index.html"], check=False).stdout.strip()
    else:
        diff_stat = run_cmd(["git", "diff", "--stat", "--", "index.html"], check=False).stdout.strip()
    proposal_text = proposal_summary.read_text(encoding="utf-8") if proposal_summary.exists() else ""

    lines = [
        "# bitcoinwallet.guide Weekly Website Change Summary",
        "",
        f"- Generated: `{dt.datetime.now(dt.timezone.utc).isoformat()}`",
        f"- Changed wallets: **{len(rows)}**",
        f"- Gitea commit pushed: **{'yes' if pushed else 'no'}**" + (f" (`{commit_hash}`)" if commit_hash else ""),
        "- Live site published: **no** — this only touches Gitea/TTMF preview unless `publish.sh` is run separately.",
        "",
        "## Diff stat",
        "",
        "```",
        diff_stat or "No index.html diff remains in the working tree.",
        "```",
        "",
        "## Wallet before/after changes",
        "",
    ]
    if rows:
        lines.extend(["| Wallet | Fields | Before | After |", "|---|---|---|---|"])
        lines.extend(rows)
    else:
        lines.append("No wallet-visible data changed.")

    if proposal_text:
        lines.extend(["", "## Proposal summary", "", proposal_text.strip()])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run weekly wallet research snapshot + stage proposal prompt")
    parser.add_argument("--stamp", help="Override timestamp folder name (default: UTC yyyymmdd-HHMMSS)")
    parser.add_argument("--timeout", type=int, default=20, help="Per-request timeout seconds")
    parser.add_argument("--limit", type=int, help="Limit wallets scanned; useful for smoke tests")
    parser.add_argument("--workers", type=int, default=6, help="Concurrent wallet scan workers")
    parser.add_argument("--skip-discovery", action="store_true", help="Skip global discovery-resource scans.")
    parser.add_argument("--git-sync", action="store_true", help="Pull/rebase origin/main before scanning; intended for automation.")
    parser.add_argument(
        "--apply-staged-patch",
        action="store_true",
        help="After --run-hermes, apply staged-wallet-updates.patch if it cleanly applies.",
    )
    parser.add_argument(
        "--commit-and-push",
        action="store_true",
        help="After applying a staged patch, commit index.html and push to Gitea origin/main.",
    )
    parser.add_argument(
        "--run-hermes",
        action="store_true",
        help="Run the staged Hermes proposal prompt automatically after snapshot generation.",
    )
    args = parser.parse_args()

    if args.apply_staged_patch and not args.run_hermes:
        raise ValueError("--apply-staged-patch requires --run-hermes so the patch exists for this run")
    if args.commit_and_push and not args.apply_staged_patch:
        raise ValueError("--commit-and-push requires --apply-staged-patch")

    if not INDEX_HTML.exists():
        raise FileNotFoundError(f"index.html not found at {INDEX_HTML}")

    if args.git_sync:
        git_sync()

    before_wallets = extract_wallets_via_node(INDEX_HTML)
    source_config = load_wallet_source_config()
    discovery_config = load_discovery_resource_config()
    discovery_resources = discovery_config.get("resources") or []

    stamp = args.stamp or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_dir = REPORTS_ROOT / stamp
    report_dir.mkdir(parents=True, exist_ok=True)

    wallets = before_wallets
    if args.limit:
        wallets = wallets[: args.limit]

    snapshots_by_index: Dict[int, Dict[str, Any]] = {}
    workers = max(1, min(args.workers, len(wallets) or 1))
    print(f"Scanning {len(wallets)} wallet(s) with {workers} worker(s), timeout={args.timeout}s...")

    def scan_one(index: int, wallet: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        return index, build_wallet_snapshot(wallet, timeout=args.timeout, source_config=source_config)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(scan_one, i, wallet) for i, wallet in enumerate(wallets)]
        for done_count, future in enumerate(as_completed(futures), start=1):
            index, snapshot = future.result()
            snapshots_by_index[index] = snapshot
            print(f"[{done_count}/{len(wallets)}] {snapshot.get('id') or snapshot.get('name')} scanned")

    snapshot_wallets = [snapshots_by_index[i] for i in range(len(wallets))]
    resource_snapshots = [] if args.skip_discovery else scan_discovery_resources(
        discovery_resources,
        timeout=args.timeout,
        workers=args.workers,
    )

    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repo": "bitcoin-wallet-guide",
        "wallet_count": len(snapshot_wallets),
        "wallet_source_file": str(WALLET_SOURCE_FILE.relative_to(REPO_ROOT)),
        "discovery_resource_file": str(DISCOVERY_RESOURCE_FILE.relative_to(REPO_ROOT)),
        "wallets": snapshot_wallets,
        "discovery_resources": resource_snapshots,
    }

    report_json = report_dir / "wallet-research.json"
    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary_md = report_dir / "snapshot-summary.md"
    write_markdown_summary(summary_md, report)

    source_inventory_md = report_dir / "source-inventory.md"
    write_source_inventory(source_inventory_md, wallets, source_config, discovery_resources)

    prompt_md = report_dir / "stage-proposal.prompt.md"
    write_prompt(prompt_md, report_dir, report_json, source_inventory_md)

    print(f"Generated: {report_json}")
    print(f"Generated: {summary_md}")
    print(f"Generated: {source_inventory_md}")
    print(f"Generated: {prompt_md}")

    if args.run_hermes:
        run_hermes_proposal(prompt_md, report_dir)
        commit_hash = ""
        pushed = False
        if args.apply_staged_patch:
            patch_applied = apply_staged_patch(report_dir)
            after_wallets = extract_wallets_via_node(INDEX_HTML)
            if patch_applied and args.commit_and_push:
                commit_hash, pushed = commit_and_push_index_changes()
            change_summary_md = report_dir / "website-change-summary.md"
            write_website_change_summary(
                change_summary_md,
                before_wallets=before_wallets,
                after_wallets=after_wallets,
                proposal_summary=report_dir / "proposal-summary.md",
                commit_hash=commit_hash,
                pushed=pushed,
            )
            print(f"Generated: {change_summary_md}")
            print("\n--- BEGIN WEBSITE CHANGE SUMMARY ---")
            print(change_summary_md.read_text(encoding="utf-8"))
            print("--- END WEBSITE CHANGE SUMMARY ---")
    else:
        print("Next: run Hermes with the prompt to produce proposal-summary.md + staged-wallet-updates.patch")
        print(f"Example: hermes chat -q \"$(cat {prompt_md})\"")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
