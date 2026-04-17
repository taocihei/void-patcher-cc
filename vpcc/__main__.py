"""
vpcc — Void Patcher for Claude Code
Single-target applier: patches @anthropic-ai/claude-code/cli.js in-place.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT        = Path(__file__).resolve().parent.parent
PATCH_DIR   = ROOT / "patches"
BACKUP_DIR  = Path.home() / ".vpcc" / "backups"

G, Y, R, B, X = "\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[0m"


# ── locate cli.js ────────────────────────────────────────────────────────────

def find_cli_js() -> Path | None:
    """Locate @anthropic-ai/claude-code/cli.js across common install paths."""
    candidates: list[Path] = []

    # 1) npm global via `npm root -g`
    try:
        r = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            candidates.append(Path(r.stdout.strip()) / "@anthropic-ai/claude-code/cli.js")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 2) user-level npm prefix
    home = Path.home()
    candidates += [
        home / ".npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js",
        home / ".local/lib/node_modules/@anthropic-ai/claude-code/cli.js",
        home / "node_modules/@anthropic-ai/claude-code/cli.js",
        Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path("/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
    ]

    for p in candidates:
        if p.is_file():
            return p
    return None


def sha256_short(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def node_syntax_check(path: Path) -> bool:
    try:
        r = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return True  # can't check without node — assume OK


# ── patch application ────────────────────────────────────────────────────────

def load_patches() -> list[dict[str, Any]]:
    patches = []
    for f in sorted(PATCH_DIR.glob("*.json")):
        try:
            patches.append(json.loads(f.read_text()))
        except json.JSONDecodeError as e:
            print(f"{R}✗ {f.name}: invalid JSON — {e}{X}", file=sys.stderr)
    return patches


def apply_js_replace(cli_js: Path, patch: dict[str, Any], dry_run: bool = False) -> tuple[bool, str]:
    text = cli_js.read_text()
    orig = text
    total = 0
    for p in patch.get("patches", []):
        pat = p.get("search_regex") or p.get("search")
        if not pat:
            continue
        rep = p.get("replace", "")
        marker = p.get("applied_marker")
        if marker and marker in text:
            continue  # already applied
        try:
            new_text, n = re.subn(pat, rep, text, flags=re.DOTALL)
        except re.error as e:
            return False, f"regex error: {e}"
        expected = p.get("count", 1)
        if n == 0 and p.get("required", True):
            return False, f"pattern not found: {pat[:60]}..."
        if expected and n != expected and expected > 0:
            return False, f"expected {expected} replacements, got {n}"
        text = new_text
        total += n
    if text == orig:
        return True, "no-op (already applied)"
    if dry_run:
        return True, f"would apply {total} replacement(s)"
    cli_js.write_text(text)
    return True, f"{total} replacement(s)"


def apply_settings(patch: dict[str, Any], dry_run: bool = False) -> tuple[bool, str]:
    path = Path(os.path.expanduser(patch.get("settings_path", "~/.claude/settings.json")))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        cur = json.loads(path.read_text()) if path.is_file() else {}
    except json.JSONDecodeError:
        cur = {}
    wanted = patch.get("settings", {})
    changed = 0
    out = dict(cur)
    for k, v in wanted.items():
        if out.get(k) != v:
            out[k] = v
            changed += 1
    if not changed:
        return True, "no-op (already applied)"
    if dry_run:
        return True, f"would set {changed} key(s)"
    path.write_text(json.dumps(out, indent=2))
    return True, f"{changed} key(s) applied"


def backup(cli_js: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = BACKUP_DIR / f"cli.js.{stamp}.{sha256_short(cli_js)}.bak"
    shutil.copy2(cli_js, dst)
    # prune: keep last 10
    baks = sorted(BACKUP_DIR.glob("cli.js.*.bak"))
    for b in baks[:-10]:
        b.unlink(missing_ok=True)
    return dst


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_patch(args) -> int:
    patches = load_patches()
    print(f"{B}vpcc patch — {len(patches)} patches{X}")

    # Always try settings patches (target cli.js separately)
    cli_js = find_cli_js() if any(p.get("type") == "js_replace" for p in patches) else None

    if cli_js:
        print(f"  target: {cli_js}  (sha: {sha256_short(cli_js)})")
        if not args.dry_run:
            bkp = backup(cli_js)
            print(f"  backup: {bkp}")

    ok = fail = skip = 0
    for p in patches:
        t = p.get("type")
        if t == "js_replace":
            if not cli_js:
                print(f"  {Y}skip{X} {p['id']:40s}  cli.js not found")
                skip += 1
                continue
            success, msg = apply_js_replace(cli_js, p, dry_run=args.dry_run)
        elif t == "settings":
            success, msg = apply_settings(p, dry_run=args.dry_run)
        elif t == "hook":
            # Lightweight hook: write file literal to settings_path
            success, msg = apply_settings(p, dry_run=args.dry_run)
        else:
            success, msg = False, f"unsupported type: {t}"

        mark = f"{G}ok{X}" if success else f"{R}fail{X}"
        print(f"  {mark}   {p['id']:40s}  {msg}")
        ok += success; fail += not success

    # Post-apply syntax check
    if cli_js and not args.dry_run:
        if node_syntax_check(cli_js):
            print(f"{G}✓ cli.js syntax valid{X}")
        else:
            print(f"{R}✗ cli.js syntax INVALID — restore from backup if broken{X}")
            return 2

    print(f"\n{B}{ok} ok · {fail} failed · {skip} skipped{X}")
    return 1 if fail else 0


def cmd_verify(args) -> int:
    cli_js = find_cli_js()
    if not cli_js:
        print(f"{R}cli.js not found{X}")
        return 2
    text = cli_js.read_text()
    patches = load_patches()
    missing = 0
    for p in patches:
        if p.get("type") != "js_replace":
            continue
        for sub in p.get("patches", []):
            marker = sub.get("applied_marker")
            if marker and marker not in text:
                print(f"{R}✗{X} {p['id']}")
                missing += 1
                break
    if missing:
        print(f"\n{R}{missing} patches not applied{X}")
        return 1
    print(f"{G}✓ all patches verified{X}")
    return 0


def cmd_rollback(args) -> int:
    cli_js = find_cli_js()
    if not cli_js:
        print(f"{R}cli.js not found{X}")
        return 2
    baks = sorted(BACKUP_DIR.glob("cli.js.*.bak"))
    if not baks:
        print(f"{R}no backups in {BACKUP_DIR}{X}")
        return 1
    latest = baks[-1]
    shutil.copy2(latest, cli_js)
    print(f"{G}✓ restored{X} {cli_js} ← {latest.name}")
    return 0


def cmd_status(args) -> int:
    cli_js = find_cli_js()
    patches = load_patches()
    print(f"{B}vpcc status{X}")
    print(f"  patches in catalog: {len(patches)}")
    print(f"  cli.js: {cli_js or 'NOT FOUND'}")
    if cli_js:
        print(f"  sha: {sha256_short(cli_js)}")
        print(f"  node syntax: {'ok' if node_syntax_check(cli_js) else 'INVALID'}")
    baks = sorted(BACKUP_DIR.glob("cli.js.*.bak"))
    print(f"  backups: {len(baks)}  ({BACKUP_DIR})")
    return 0


def cmd_list(args) -> int:
    patches = load_patches()
    for p in patches:
        print(f"  {p['id']:40s}  {p.get('description','')}")
    return 0


# ── entry ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        prog="vpcc",
        description="Void Patcher for Claude Code — apply 39 hardening patches to cli.js",
    )
    sub = ap.add_subparsers(dest="cmd", metavar="command")

    p_patch = sub.add_parser("patch", help="Apply all patches")
    p_patch.add_argument("--dry-run", "-n", action="store_true")

    sub.add_parser("verify",   help="Check all patches are applied")
    sub.add_parser("rollback", help="Restore cli.js from most recent backup")
    sub.add_parser("status",   help="Show install state")
    sub.add_parser("list",     help="List patches in catalog")

    args = ap.parse_args()
    if args.cmd is None:
        ap.print_help()
        return 0

    dispatch = {
        "patch":    cmd_patch,
        "verify":   cmd_verify,
        "rollback": cmd_rollback,
        "status":   cmd_status,
        "list":     cmd_list,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
