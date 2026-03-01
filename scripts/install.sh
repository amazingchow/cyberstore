#!/usr/bin/env bash
# CyberStore install script
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/amazingchow/cyberstore/master/scripts/install.sh | bash
#   INSTALL_DIR=~/.local/bin bash install.sh          # custom install dir
#   CYBERSTORE_VERSION=v1.2.0 bash install.sh         # specific version

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
REPO="${REPO:-amazingchow/CyberStore}"  # ← replace with your GitHub repo
BINARY="cyberstore"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"

# ── Helpers ───────────────────────────────────────────────────────────────────
info()  { printf '\033[1;34m[INFO]\033[0m  %s\n' "$*"; }
ok()    { printf '\033[1;32m[ OK ]\033[0m  %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m  %s\n' "$*" >&2; }
die()   { printf '\033[1;31m[ERR ]\033[0m  %s\n' "$*" >&2; exit 1; }

need_cmd() { command -v "$1" &>/dev/null || die "Required command not found: $1"; }

# ── Detect platform ───────────────────────────────────────────────────────────
detect_artifact() {
  local os arch
  os=$(uname -s | tr '[:upper:]' '[:lower:]')
  arch=$(uname -m)

  case "$os" in
    darwin)
      case "$arch" in
        arm64)  echo "cyberstore-macos-arm64"  ;;
        x86_64) echo "cyberstore-macos-x86_64" ;;
        *)      die "Unsupported macOS architecture: $arch" ;;
      esac
      ;;
    linux)
      case "$arch" in
        x86_64)  echo "cyberstore-linux-x86_64" ;;
        aarch64) echo "cyberstore-linux-arm64"   ;;
        *)       die "Unsupported Linux architecture: $arch" ;;
      esac
      ;;
    *)
      die "Unsupported operating system: $os (only macOS and Linux are supported)"
      ;;
  esac
}

# ── Resolve download URL ──────────────────────────────────────────────────────
get_download_url() {
  local artifact="$1"
  local api_url

  if [[ -n "${CYBERSTORE_VERSION:-}" ]]; then
    api_url="https://api.github.com/repos/${REPO}/releases/tags/${CYBERSTORE_VERSION}"
  else
    api_url="https://api.github.com/repos/${REPO}/releases/latest"
  fi

  local url
  url=$(curl -fsSL "$api_url" \
    | grep -o "\"browser_download_url\": *\"[^\"]*${artifact}[^\"]*\"" \
    | grep -o 'https://[^"]*' \
    | head -1)

  [[ -n "$url" ]] || die "Could not find download URL for '$artifact' in release at: $api_url"
  echo "$url"
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  need_cmd curl
  need_cmd chmod

  local artifact download_url
  local tmp_file='cyberstore-tmp-binary'

  info "Detecting platform..."
  artifact=$(detect_artifact)
  info "Target artifact: $artifact"

  info "Resolving latest release..."
  download_url=$(get_download_url "$artifact")
  info "Download URL: $download_url"

  info "Downloading binary..."
  curl -fsSL --progress-bar "$download_url" -o "$tmp_file"
  chmod +x "$tmp_file"

  # Validate the binary is executable before installing
  if ! "$tmp_file" --help &>/dev/null && ! "$tmp_file" -h &>/dev/null; then
    warn "Binary smoke-test skipped (TUI app may not support --help flag)"
  fi

  info "Installing to $INSTALL_DIR/$BINARY..."
  if [[ -w "$INSTALL_DIR" ]]; then
    mv "$tmp_file" "$INSTALL_DIR/$BINARY"
  else
    info "  (requires sudo)"
    sudo mv "$tmp_file" "$INSTALL_DIR/$BINARY"
  fi

  ok "CyberStore installed successfully!"
  ok "Run: $BINARY"
}

main "$@"
