#!/usr/bin/env bash
set -euo pipefail

# Lazer çizgisinin görünürlüğünü farklı pozlama sürelerinde karşılaştırır.
# Stand, A4 ve kamera sabit tutulur; lazer kullanıcı tarafından açılıp kapatılır.

if ! command -v rpicam-still >/dev/null 2>&1; then
    echo "HATA: rpicam-still bulunamadi."
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# İlk argüman verilirse görüntüler belirtilen çıktı klasörü altında saklanır.
OUTPUT_ROOT="${1:-${SCRIPT_DIR}/../output/staj1/pozlama}"
mkdir -p "${OUTPUT_ROOT}"
# Önceki kayıtları korumak için her çalıştırmada yeni bir klasör oluşturulur.
OUTPUT_DIR="$(mktemp -d "${OUTPUT_ROOT}/$(date +%Y%m%d_%H%M%S)_XXXXXX")"

# Pozlama süreleri mikrosaniye cinsindendir; diğer kamera ayarları sabit kalır.
EXPOSURES=(1000 2500 5000 10000 20000)

capture_sweep() {
    local label="$1"
    local exposure

    for exposure in "${EXPOSURES[@]}"; do
        echo "${label} - ${exposure} us kaydediliyor..."
        rpicam-still \
            --nopreview \
            --timeout 1500 \
            --width 2304 \
            --height 1296 \
            --shutter "${exposure}" \
            --gain 1 \
            --awbgains 1.427003,3.087750 \
            --autofocus-mode manual \
            --lens-position 0.971509 \
            --metadata-format json \
            --output "${OUTPUT_DIR}/${label}_${exposure}us.jpg" \
            --metadata "${OUTPUT_DIR}/${label}_${exposure}us.json"
    done
}

echo
echo "Gun isiginda pozlama tarama klasoru: ${OUTPUT_DIR}"
echo "Kosul: Dolayli ve homojen gun isigi; masa lambasi ve sari oda isigi kapali."
echo "A4 uzerinde parlak gunes lekesi veya pencere golgesi olmamali."
echo "Lazer KAPALI olmali."
read -r -p "Kosullar uygunsa Enter'a basin... "
capture_sweep "lazer_kapali"

echo
echo "Stand, A4 ve kameraya dokunmadan lazeri ACIN."
echo "Lazer isinina ve parlak yansimalara dogrudan bakmayin."
read -r -p "Lazer aciksa Enter'a basin... "
capture_sweep "lazer_acik"

echo
echo "Tarama tamamlandi. Simdi lazeri KAPATIN."
echo "Kayitlar: ${OUTPUT_DIR}"
ls -1 "${OUTPUT_DIR}"
