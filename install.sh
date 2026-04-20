#!/usr/bin/env bash
# vpcc 1-liner installer — macOS · Linux · WSL
#
#   curl -fsSL https://raw.githubusercontent.com/VoidChecksum/void-patcher-cc/main/install.sh | bash
#
# Chains on top of Anthropic's official native installer
# (https://claude.ai/install.sh) → then deploys vpcc patches + preload hook.
# No hardcoded absolute paths — every path is $HOME/XDG derived.

set -euo pipefail

REPO="VoidChecksum/void-patcher-cc"
ANTHROPIC_INSTALL="https://claude.ai/install.sh"

BLUE='\033[1;34m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; NC='\033[0m'
log() { printf "${BLUE}[vpcc]${NC} %s\n" "$*"; }
ok()  { printf "${GREEN}[ ok ]${NC} %s\n" "$*"; }
warn(){ printf "${YELLOW}[warn]${NC} %s\n" "$*"; }
die() { printf "${RED}[fail]${NC} %s\n" "$*" >&2; exit 1; }

XDG_BIN="${XDG_BIN_HOME:-$HOME/.local/bin}"
XDG_DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CFG="${XDG_CONFIG_HOME:-$HOME/.config}"
export PATH="$XDG_BIN:$PATH"

# ── 1. Install Claude Code via the official installer (idempotent) ───────────
if ! command -v claude >/dev/null 2>&1; then
    log "installing Claude Code via $ANTHROPIC_INSTALL"
    curl -fsSL "$ANTHROPIC_INSTALL" | bash || die "Anthropic installer failed"
fi
ok "claude binary: $(command -v claude)"

# ── 2. Python + pipx ─────────────────────────────────────────────────────────
command -v python3 >/dev/null || die "python3 missing (brew install python / apt install python3)"
if ! command -v pipx >/dev/null; then
    log "installing pipx"
    python3 -m pip install --user pipx >/dev/null 2>&1 || die "pipx install failed"
    python3 -m pipx ensurepath >/dev/null 2>&1 || true
fi

# ── 3. vpcc package ──────────────────────────────────────────────────────────
log "installing vpcc from git+$REPO"
pipx install --force "git+https://github.com/$REPO" >/dev/null || die "pipx install vpcc failed"

# ── 4. Clone repo locally for contrib/ (preload, systemd units) ──────────────
REPO_DIR="$XDG_DATA/void-patcher-cc"
if [ ! -d "$REPO_DIR/.git" ]; then
    log "cloning $REPO to $REPO_DIR"
    git clone --depth=1 "https://github.com/$REPO" "$REPO_DIR" >/dev/null 2>&1 || \
        warn "clone failed — preload / systemd steps skipped"
else
    (cd "$REPO_DIR" && git pull --ff-only >/dev/null 2>&1) || true
fi

# ── 5. Apply patches + preload hook ──────────────────────────────────────────
log "applying signature patches"
vpcc patch || warn "patch returned non-zero — run 'vpcc doctor'"

log "installing runtime preload hook"
vpcc install-preload || warn "preload install failed"

# ── 6. Optional systemd --user autoheal timer (Linux only) ───────────────────
if command -v systemctl >/dev/null 2>&1 && [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -d "$REPO_DIR/contrib/systemd" ]; then
    UNIT_DIR="$XDG_CFG/systemd/user"
    mkdir -p "$UNIT_DIR"
    cp -f "$REPO_DIR/contrib/systemd/"*.service "$UNIT_DIR/" 2>/dev/null || true
    cp -f "$REPO_DIR/contrib/systemd/"*.timer   "$UNIT_DIR/" 2>/dev/null || true
    systemctl --user daemon-reload 2>/dev/null || true
    if systemctl --user enable --now vpcc-autoheal.timer 2>/dev/null; then
        ok "autoheal timer active — runs every 15 min"
    fi
fi

# ── 7. Verify ────────────────────────────────────────────────────────────────
printf "\n"
vpcc doctor || true
printf "\n"
ok "install complete"
ok "usage:  vpcc patch · vpcc scan · vpcc watch · vpcc doctor"
