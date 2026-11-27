#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="${HOME}/.config/autostart"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "${AUTOSTART_DIR}" "${BIN_DIR}"
ln -sfn "${SCRIPT_DIR}/baslat.sh" "${BIN_DIR}/wp9-baslat"
install -m 0644 "${SCRIPT_DIR}/wp9-dokunmatik.desktop" \
  "${AUTOSTART_DIR}/wp9-dokunmatik.desktop"

echo "Dokunmatik acilis baglantisi kuruldu."
echo "Simdi baslatmak icin: ${BIN_DIR}/wp9-baslat"
echo "Sonraki masaustu oturumunda arayuz otomatik acilacak."
