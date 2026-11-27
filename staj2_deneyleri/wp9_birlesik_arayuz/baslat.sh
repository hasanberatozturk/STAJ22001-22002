#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# SSH oturumunda DISPLAY degiskeni gelmeyebilir. Ayni kullanicinin acik
# dokunmatik masaustu varsa yerel XWayland/Wayland oturumunu otomatik bul.
KULLANICI_UID="$(id -u)"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${KULLANICI_UID}}"

if [[ -z "${WAYLAND_DISPLAY:-}" && -S "${XDG_RUNTIME_DIR}/wayland-0" ]]; then
  export WAYLAND_DISPLAY="wayland-0"
fi

if [[ -z "${DISPLAY:-}" ]]; then
  for X_SOKETI in /tmp/.X11-unix/X*; do
    [[ -S "${X_SOKETI}" ]] || continue
    export DISPLAY=":${X_SOKETI##*X}"
    break
  done
fi

if [[ -z "${XAUTHORITY:-}" ]]; then
  for YETKI_DOSYASI in "${HOME}/.Xauthority" "${XDG_RUNTIME_DIR}"/.mutter-Xwaylandauth.*; do
    [[ -f "${YETKI_DOSYASI}" ]] || continue
    export XAUTHORITY="${YETKI_DOSYASI}"
    break
  done
fi

if [[ -z "${DISPLAY:-}" ]]; then
  echo "HATA: Grafik masaustu bulunamadi."
  echo "Dokunmatik ekranda masaustu oturumu acin veya Pi'yi masaustu otomatik girisle yeniden baslatin."
  echo "SSH yalniz basina Tkinter penceresi gosteremez."
  exit 2
fi

source .venv/bin/activate
python3 wp9_arayuz.py
