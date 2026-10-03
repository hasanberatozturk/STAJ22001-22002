#!/usr/bin/env bash
set -euo pipefail

# Düz yüzey ve yerel yükselti için lazer açık/kapalı görüntü çiftleri kaydeder.
# Üst A4 dört köşesinden sabitlenir. Yaklaşık 5 x 10 cm boyutundaki 10 kat
# kâğıt parçası, üst A4 kaldırılmadan kenardan altına yerleştirilir.
# Kamera, lazer ve aydınlatma deney boyunca sabit tutulmalıdır.

if ! command -v rpicam-still >/dev/null 2>&1; then
    echo "HATA: rpicam-still bulunamadi."
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# İlk argüman verilirse görüntüler belirtilen çıktı klasörü altında saklanır.
OUTPUT_ROOT="${1:-${SCRIPT_DIR}/../output/staj1/yukselti}"
mkdir -p "${OUTPUT_ROOT}"
# Önceki kayıtları korumak için her çalıştırmada yeni bir klasör oluşturulur.
OUTPUT_DIR="$(mktemp -d "${OUTPUT_ROOT}/$(date +%Y%m%d_%H%M%S)_XXXXXX")"

CAMERA_ARGS=(
    --nopreview
    --timeout 1500
    --width 2304
    --height 1296
    --shutter 2500
    --gain 1
    --awbgains 1.427003,3.087750
    --autofocus-mode manual
    --lens-position 0.971509
    --metadata-format json
)

capture_group() {
    local label="$1"
    local i

    for i in 01 02 03; do
        echo "${label}_${i} kaydediliyor..."
        rpicam-still \
            "${CAMERA_ARGS[@]}" \
            --output "${OUTPUT_DIR}/${label}_${i}.jpg" \
            --metadata "${OUTPUT_DIR}/${label}_${i}.json"
    done
}

echo
echo "Deney klasoru: ${OUTPUT_DIR}"
echo "ON KONTROL:"
echo "- Ust A4 dort kosesinden masaya sabitlenmis olmali."
echo "- Lazer cizgisi A4'un orta bolgesinden gecmeli."
echo "- Kamera, lazer ve aydinlatma deney boyunca sabit kalmali."
echo "- 10 katlik yerel parca yaklasik 5 x 10 cm olmali."
read -r -p "On kontrol tamamsa Enter'a basin... "

echo
echo "KOSUL 1/4: Ust A4 duz, yerel parca disarida ve lazer KAPALI."
read -r -p "Hazirsa Enter'a basin... "
capture_group "duz_lazer_kapali"

echo
echo "KOSUL 2/4: Hicbir seyi oynatmadan lazeri ACIN."
read -r -p "Lazer aciksa Enter'a basin... "
capture_group "duz_lazer_acik"

echo
echo "Simdi lazeri KAPATIN."
echo "Ust A4'u kaldirmayin, cekmeyin veya yeniden konumlandirmayin."
echo "10 katlik yerel parcayi kenardan, lazer cizgisinin orta bolgesinin altina surun."
echo "Parcanin iki yaninda duz yuzey gorunmeli; boylece iki gecis noktasi olusmalidir."
read -r -p "Yerel parca yerlesti ve lazer kapaliysa Enter'a basin... "
capture_group "yukselti_10kat_lazer_kapali"

echo
echo "KOSUL 4/4: Kagida ve standa dokunmadan lazeri ACIN."
read -r -p "Lazer aciksa Enter'a basin... "
capture_group "yukselti_10kat_lazer_acik"

echo
echo "Deney tamamlandi. Simdi lazeri KAPATIN."
echo "Kayitlar: ${OUTPUT_DIR}"
ls -1 "${OUTPUT_DIR}"
