#!/bin/sh
# Installs waywatch: clones/updates the repo into ~/.local/share/waywatch,
# syncs its dependencies with uv, and drops a `waywatch` launcher into
# ~/.local/bin.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Mohamed-Rirash/waywatch/main/install.sh | sh
set -eu

REPO_URL="https://github.com/Mohamed-Rirash/waywatch.git"
INSTALL_DIR="${WAYWATCH_INSTALL_DIR:-$HOME/.local/share/waywatch}"
BIN_DIR="${WAYWATCH_BIN_DIR:-$HOME/.local/bin}"

info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33mnote:\033[0m %s\n' "$1"; }
error() { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }

command -v git >/dev/null 2>&1 || error "git is required but not found in PATH"
command -v uv >/dev/null 2>&1 || error "uv is required but not found in PATH (see https://docs.astral.sh/uv/getting-started/installation/)"

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing install at $INSTALL_DIR"
    git -C "$INSTALL_DIR" pull --ff-only
else
    info "Cloning waywatch into $INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

info "Installing dependencies"
uv sync --project "$INSTALL_DIR"

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/waywatch" <<EOF
#!/bin/sh
exec uv run --project "$INSTALL_DIR" python "$INSTALL_DIR/main.py" "\$@"
EOF
chmod +x "$BIN_DIR/waywatch"

info "Installed waywatch to $BIN_DIR/waywatch"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        warn "$BIN_DIR is not on your PATH. Add this to your shell rc file:"
        printf '  export PATH="%s:$PATH"\n' "$BIN_DIR"
        ;;
esac

info "Run 'waywatch' to launch the dashboard, or 'waywatch report' for a quick summary."
info "Config: ~/.config/waywatch/config.toml"
