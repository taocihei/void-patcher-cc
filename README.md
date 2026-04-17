# vpcc — Void Patcher for Claude Code

39 reverse-engineered hardening patches for Anthropic's `@anthropic-ai/claude-code` CLI.
Applies AST-level rewrites to `cli.js` to remove refusal classifiers, trust dialogs,
policy limits, telemetry sinks, and unlock gated feature flags.

**Verified against Claude Code `2.1.112`.**

---

## Patch catalog

| Category | Patches | Effect |
|----------|---------|--------|
| 🔓 **Permission/Trust Bypass** | 9 | `bypass-permissions` mode, sandbox off, root restriction off, workspace trust auto-accept |
| 🛡️ **Trust & Approval Bypass** | 5 | Pre-approve all tools, neutralize patch-guard / mcp-guard, skip trust dialogs |
| 🚫 **Refusal Neutralization** | 10 | AUP refusal gates, malware refusal, plan-mode refusal, security guardrail, denial workarounds |
| 🧪 **Classifier Fail-Open** | 4 | Prompt-injection classifier, AUP classifiers, auto-mode `shouldBlock` → false |
| 🌐 **Network/Policy Allow-All** | 3 | WebFetch preflight skip, domain blocklist empty, policy limits removed |
| 👁️ **Telemetry Kill** | 5 | 1P event logging, Datadog sink, Statsig gates, agent summary, metrics |
| ⚙️ **Feature Unlock** | 3 | A/B flags (Opus 4.6 `quiet_salted_ember`, Sonnet 4.6 `coral_reef_sonnet`), subscription pinning |

**Total: 39 patches.** Run `vpcc list` for the full index.

---

## Install

```bash
pip install --user git+https://github.com/VoidChecksum/void-patcher-cc.git
```

Or clone + run from source:

```bash
git clone https://github.com/VoidChecksum/void-patcher-cc.git
cd void-patcher-cc
python -m vpcc status
```

**Requires:** Python 3.9+, Node.js (for `node --check`), Claude Code installed via npm.

---

## Usage

```bash
vpcc status             # show install state, patch count, cli.js location
vpcc list               # list all 39 patches
vpcc patch --dry-run    # preview changes without writing
vpcc patch              # apply all patches (auto-backs-up cli.js first)
vpcc verify             # check all patches are currently applied
vpcc rollback           # restore cli.js from latest backup
```

Backups live in `~/.vpcc/backups/` (last 10 kept).

---

## How it works

Claude Code ships as a single ~26 MB bundled Node program (`cli.js`, webpack-minified).
Each patch is a JSON file with a regex `search_regex` + `replace` pair, optionally an
`applied_marker` used for idempotency checks. `vpcc patch` loads every patch from
`patches/*.json`, applies them to the located `cli.js`, and runs `node --check` to
verify syntax.

Patches are categorized by effect, not by file region — one patch may touch several
points. See `patches/*.json` for per-patch regex anchors, replacements, and targeted
CVE-style descriptions.

---

## Patch file format

```jsonc
{
  "id":          "js-example",
  "description": "What this patch does, in one sentence",
  "type":        "js_replace",   // or "settings"
  "patches": [
    {
      "search_regex":   "regex\\s+to\\s+find",
      "replace":        "replacement text",
      "applied_marker": "unique string present only after apply",
      "count":          1,          // expected replacement count (0 = any)
      "required":       true,       // fail if pattern missing
      "description":    "what this sub-patch does"
    }
  ]
}
```

For settings-type patches:

```json
{
  "id":            "enable-bypass",
  "type":          "settings",
  "settings_path": "~/.claude/settings.json",
  "settings":      { "bypassPermissions": true }
}
```

---

## Safety & scope

- Patches run **locally** on your own Claude Code install.
- Backups are taken automatically before any write.
- `vpcc rollback` restores from the most recent backup.
- Use `--dry-run` first if unsure.

These patches neutralize guardrails added to Claude Code. Use on systems you own and
for workflows you're responsible for. No warranty; no affiliation with Anthropic.

---

## Versioning

Patches are tested against the `supported_versions` range declared in each JSON.
`vpcc` matches by content signature (regex anchor), not strict version pin — if the
anchor is still present in a newer Claude Code release, the patch applies cleanly.
If Anthropic rewrites a hot spot, that single patch will fail gracefully and others
continue.

When a new Claude Code version breaks patches, open an issue with the failing patch
ID + the relevant `cli.js` snippet around where the old regex used to match.

---

## License

MIT — see `LICENSE`.

Built by [@VoidChecksum](https://github.com/VoidChecksum).
