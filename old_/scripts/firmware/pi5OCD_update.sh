#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Build & install OpenOCD with linuxgpiod support (Raspberry Pi 5)
#
# Why:
#   - Raspberry Pi 5 routes the 40-pin header GPIO through the RP1 chip.
#   - OpenOCD must be built with the `linuxgpiod` adapter driver to use SWD.
#
# This script:
#   1) Removes the distro OpenOCD (optional but recommended)
#   2) Installs build dependencies (incl. libgpiod + jimtcl)
#   3) Clones Raspberry Pi's OpenOCD fork
#   4) Configures with --enable-linuxgpiod
#   5) Builds and installs to /usr/local/bin/openocd
#   6) Prints a quick sanity check (adapter list)
# ------------------------------------------------------------

REPO_URL="https://github.com/raspberrypi/openocd.git"
WORKDIR="${HOME}/openocd-rpi"

log() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
err() { echo "[ERROR] $*" >&2; }

die() { err "$*"; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

run() {
  log "$*"
  "$@"
}

main() {
    # ------------------------------------------------------------
  # Safety check: Raspberry Pi 5 only
  # ------------------------------------------------------------
  if ! grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
    err "This script is intended for Raspberry Pi 5 only."
    err "Detected model:"
    cat /proc/device-tree/model 2>/dev/null || echo "Unknown"
    exit 1
  fi

  need_cmd sudo
  need_cmd git

  log "Removing distro OpenOCD (if present) to avoid PATH confusion..."
  # Not strictly required, but helps ensure we use /usr/local/bin/openocd
  run sudo apt remove -y openocd || true
  if command -v openocd >/dev/null 2>&1; then
    warn "openocd is still found at: $(command -v openocd)"
  else
    log "openocd not found in PATH (expected after removal)."
  fi

  log "Installing build dependencies..."
  run sudo apt update

  # JimTcl is required by OpenOCD (configure will fail without it)
  # Package name can differ by distro; we install libjim-dev which is common.
  run sudo apt install -y libjim-dev

  run sudo apt install -y \
    autoconf automake libtool pkg-config make \
    libusb-1.0-0-dev libgpiod-dev \
    libhidapi-dev libjaylink-dev

  log "Preparing source directory: ${WORKDIR}"
  if [[ -d "${WORKDIR}/.git" ]]; then
    log "Repo already exists. Updating..."
    run git -C "${WORKDIR}" fetch --all --prune
    run git -C "${WORKDIR}" pull --ff-only
  else
    run git clone "${REPO_URL}" "${WORKDIR}"
  fi

  run cd "${WORKDIR}"

  log "Cleaning previous build artifacts (if any)..."
  run make distclean 2>/dev/null || true

  log "Bootstrapping (autotools)..."
  run ./bootstrap

  log "Configuring OpenOCD with linuxgpiod support (Pi 5 RP1 GPIO)..."
  run ./configure \
    --enable-linuxgpiod \
    --enable-bcm2835gpio \
    --enable-sysfsgpio

  log "Building OpenOCD..."
  run make -j"$(nproc)"

  log "Installing to /usr/local..."
  run sudo make install
  run sudo ldconfig

  log "Installed openocd location:"
  if [[ -x /usr/local/bin/openocd ]]; then
    echo "  /usr/local/bin/openocd"
  else
    warn "Expected /usr/local/bin/openocd was not found. Check install output."
  fi

  log "Sanity check: adapter list (should include linuxgpiod)"
  /usr/local/bin/openocd -c "adapter list" | sed 's/^/  /'

  log "Done. If you still see the old openocd being used, check PATH order (which openocd)."
}

main "$@"