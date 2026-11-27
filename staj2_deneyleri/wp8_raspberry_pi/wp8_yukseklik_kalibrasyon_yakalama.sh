#!/usr/bin/env bash
set -euo pipefail

if ! command -v rpicam-still >/dev/null 2>&1; then
    echo "HATA: rpicam-still bulunamadi."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python3"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="python3"
fi

RUN_DIR="${HOME}/WP8_YUKSEKLIK_KALIBRASYON/$(date +%Y%m%d_%H%M%S)"
CAL_DIR="${RUN_DIR}/kalibrasyon"
OLCUM_DIR="${RUN_DIR}/olcumler"
MANIFEST="${RUN_DIR}/yukseklik_manifest.csv"
mkdir -p "${CAL_DIR}" "${OLCUM_DIR}"
printf 'numune_id,yukseklik_mm,genislik_mm,yon\n' > "${MANIFEST}"

CAMERA_ARGS=(
    --nopreview
    --timeout 1500
    --width 2304
    --height 1296
    --shutter 2500
    --gain 1
    --awb daylight
    --autofocus-mode manual
    --lens-position 1.0
    --metadata-format json
)

cek() {
    local temel="$1"
    rpicam-still "${CAMERA_ARGS[@]}" \
        --output "${temel}.jpg" \
        --metadata "${temel}.json"
}

echo "WP8 gercek yukseklik kalibrasyonu: ${RUN_DIR}"
echo "Bu turda kumas KULLANILMAYACAK; rijit A4 basamak kalibre edilecek."
echo "Masaya duz bir beyaz A4 taban yerlestirin ve deney boyunca oynatmayin."
echo "20 mm genisligindeki A4 seritlerini tabanin ustune, goruntu ortasina"
echo "ve lazer cizgisine DIK yerlestirin. Seritlerin ustunu kumasla ortmeyin."
echo "Ilk olarak yalnizca duz A4 tabandan 3 kalibrasyon cifti alinacak."
echo "Lazeri KAPATIN."
read -r -p "Duz A4 taban hazirsa Enter'a basin... "

for i in 01 02 03; do
    cek "${CAL_DIR}/D00_K_${i}"
done

echo "Kumasa dokunmadan lazeri ACIN."
read -r -p "Lazer aciksa Enter'a basin... "
for i in 01 02 03; do
    cek "${CAL_DIR}/D00_A_${i}"
done

echo "Lazeri KAPATIN. Kalibrasyon kontrol ediliyor..."
if ! "${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_canli_tahmin.py" \
    --kalibrasyon "${CAL_DIR}" \
    --kalibrasyon-kontrol; then
    echo "HATA: Duz yuzey kalibrasyonu gecersiz."
    exit 2
fi

YUKSEKLIKLER=(0.5 0.5 0.5 1 1 1 2 2 2 3 3 3)
KAT_SAYILARI=(5 5 5 10 10 10 20 20 20 30 30 30)
genislik=20
sayac=1
hedef_indeksi=0

while (( hedef_indeksi < ${#YUKSEKLIKLER[@]} )); do
    yukseklik="${YUKSEKLIKLER[hedef_indeksi]}"
    kat_sayisi="${KAT_SAYILARI[hedef_indeksi]}"
    tekrar_no=$((hedef_indeksi % 3 + 1))

    echo
    echo "Siradaki hedef: ${yukseklik} mm, tekrar ${tekrar_no}/3."
    echo "20 mm genisliginde, yaklasik ${kat_sayisi} kat A4 serit kullanin."
    echo "Her tekrarda seridi kaldirip yeniden ortalayarak yerlestirin."

    printf -v kod "H%03d" "${sayac}"
    NUMUNE_DIR="${OLCUM_DIR}/${kod}"
    mkdir -p "${NUMUNE_DIR}"
    echo "${kod},${yukseklik},${genislik},lazere_dik" >> "${MANIFEST}"

    echo "${yukseklik} mm A4 serit basamagini taban A4'un USTUNE yerlestirin."
    echo "Basamak acikta, lazer cizgisine dik, ortalanmis ve ${genislik} mm genislikte olmali."
    echo "Lazeri KAPATIN."
    read -r -p "Yuzey hazirsa Enter'a basin... "
    for tekrar in 01 02 03; do
        cek "${NUMUNE_DIR}/${kod}_K_${tekrar}"
    done

    echo "Yuzeye dokunmadan lazeri ACIN."
    read -r -p "Lazer aciksa Enter'a basin... "
    for tekrar in 01 02 03; do
        cek "${NUMUNE_DIR}/${kod}_A_${tekrar}"
    done
    echo "Lazeri KAPATIN."
    read -r -p "Lazer kapaliysa Enter'a basin... "
    if ! "${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_yukseklik_kalibrasyon_analiz.py" \
        --deney "${RUN_DIR}" \
        --son-numuneyi-kontrol-et; then
        echo "UYARI: Bu numune gecersiz; hedef tekrar sayisina katilmadi."
        echo "Ayni yuksekligi orta konumda yeniden cekin."
    else
        hedef_indeksi=$((hedef_indeksi + 1))
    fi
    sayac=$((sayac + 1))
done

"${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_yukseklik_kalibrasyon_analiz.py" \
    --deney "${RUN_DIR}"

echo "Yukseklik kalibrasyonu tamamlandi: ${RUN_DIR}"
echo "Lazerin kapali oldugunu kontrol edin."
