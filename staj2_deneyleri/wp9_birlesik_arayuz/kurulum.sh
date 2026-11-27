#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"
sudo apt-get update
sudo apt-get install -y \
  python3-picamera2 \
  python3-tk \
  python3-pil \
  python3-pil.imagetk
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
python3 -m pip install --upgrade pip

# Raspberry Pi 5 aarch64 icin yalniz CPU PyTorch kurulumu.
# PyPI'daki yeni varsayilan paketlerin NVIDIA/CUDA arsivlerini indirmesini onler.
python3 -m pip install \
  --index-url https://download.pytorch.org/whl/cpu \
  torch==2.6.0 torchvision==0.21.0

python3 -m pip install --upgrade-strategy only-if-needed \
  ultralytics==8.4.129 pillow numpy

python3 - <<'PY'
import torch
from PIL import Image, ImageTk
from ultralytics import YOLO

print("Kurulum dogrulandi:", "torch", torch.__version__, "CUDA", torch.cuda.is_available())
print("Pillow ImageTk ve Ultralytics hazir.")
PY
chmod +x baslat.sh dokunmatik_kur.sh wp8_kabariklik_modulu/wp8_cizgi_test_final.sh
echo "Kurulum tamam. Kamerayi baglayin ve baslatmak icin: ./baslat.sh"
