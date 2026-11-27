#!/usr/bin/env bash
set -euo pipefail

SURUM="WP8-TARAMA-V3-20260822"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python3"
[[ -x "${PYTHON_BIN}" ]] || PYTHON_BIN="python3"

for gerekli in rpicam-still "${SCRIPT_DIR}/WP8_canli_tahmin.py" "${SCRIPT_DIR}/WP8_tarama_karar_v3.py"; do
    if [[ "${gerekli}" == "rpicam-still" ]]; then
        command -v rpicam-still >/dev/null 2>&1 || { echo "HATA: rpicam-still yok."; exit 1; }
    elif [[ ! -f "${gerekli}" ]]; then
        echo "HATA: Dosya bulunamadı: ${gerekli}"
        exit 1
    fi
done

RUN_DIR="${HOME}/WP8_TARAMA_V3/$(date +%Y%m%d_%H%M%S)"
CAL_DIR="${RUN_DIR}/kalibrasyon"
mkdir -p "${CAL_DIR}"

CAMERA_ARGS=(
    --nopreview --timeout 1500 --width 2304 --height 1296
    --shutter 2500 --gain 1 --awb daylight
    --autofocus-mode manual --lens-position 1.0 --metadata-format json
)

cek() {
    local temel="$1"
    rpicam-still "${CAMERA_ARGS[@]}" --output "${temel}.jpg" --metadata "${temel}.json"
}

uc_cift_cek() {
    local temel="$1"
    echo "Lazeri KAPATIN."
    read -r -p "Yüzey hazır ve lazer kapalıysa Enter'a basın... "
    for tekrar in 01 02 03; do cek "${temel}_K_${tekrar}"; done
    echo "Yüzeye dokunmadan lazeri AÇIN."
    read -r -p "Lazer açıksa Enter'a basın... "
    for tekrar in 01 02 03; do cek "${temel}_A_${tekrar}"; done
}

echo "============================================================"
echo "SÜRÜM: ${SURUM}"
echo "Amaç: 5 farklı konumda belirgin geometrik kusur taraması"
echo "Kat izi ve doğal dokusal kırışıklık KUSUR kapsamına alınmaz."
echo "============================================================"
echo "Düz ve kabul edilebilir kumaş bölgesini kameranın altına yerleştirin."
echo "Kalibrasyon boyunca kumaşa ve düzeneğe dokunmayın."
echo "Lazeri KAPATIN."
read -r -p "Kalibrasyona başlamak için Enter'a basın... "
for i in 01 02 03; do cek "${CAL_DIR}/D00_K_${i}"; done
echo "Lazeri AÇIN."
read -r -p "Lazer açıksa Enter'a basın... "
for i in 01 02 03; do cek "${CAL_DIR}/D00_A_${i}"; done
echo "Lazeri KAPATIN."

"${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_canli_tahmin.py" \
    --kalibrasyon "${CAL_DIR}" --kalibrasyon-kontrol

numune=1
while true; do
    echo
    read -r -p "Yeni yüzey taramak için Enter, bitirmek için q yazın: " cevap
    [[ "${cevap,,}" == "q" ]] && break

    echo "Kayıt etiketi (kararı etkilemez):"
    echo "  0=normal_duz  1=dikey_sirt  2=capraz_sirt"
    echo "  3=yumusak_kabariklik  4=kirisiklik"
    while true; do
        read -r -p "Kod [0-4]: " kod
        case "${kod}" in
            0) etiket="normal_duz"; break ;;
            1) etiket="dikey_sirt"; break ;;
            2) etiket="capraz_sirt"; break ;;
            3) etiket="yumusak_kabariklik"; break ;;
            4) etiket="kirisiklik"; break ;;
            *) echo "0 ile 4 arasında girin." ;;
        esac
    done

    printf -v numune_kodu "N%03d" "${numune}"
    NUMUNE_DIR="${RUN_DIR}/${numune_kodu}_${etiket}"
    mkdir -p "${NUMUNE_DIR}"
    KONUM_JSONLARI=()

    echo "İlk konumu hazırlayın. Sonraki konumlarda kumaşı lazere DİK yönde 10 mm kaydıracaksınız."
    for konum in 1 2 3 4 5; do
        printf -v konum_kodu "%02d" "${konum}"
        if (( konum > 1 )); then
            echo "Kumaşı lazere DİK yönde tam 10 mm kaydırın; yeni şerit taransın."
        fi
        read -r -p "Konum ${konum}/5 hazırsa Enter'a basın... "
        temel="${NUMUNE_DIR}/konum_${konum_kodu}"
        uc_cift_cek "${temel}"
        sonuc="${temel}_sonuc.json"
        "${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_canli_tahmin.py" \
            --kalibrasyon "${CAL_DIR}" \
            --lazer-kapali "${temel}_K_01.jpg" "${temel}_K_02.jpg" "${temel}_K_03.jpg" \
            --lazer-acik "${temel}_A_01.jpg" "${temel}_A_02.jpg" "${temel}_A_03.jpg" \
            --cikti "${sonuc}" --gercek-kod "${kod}" --gercek-etiket "${etiket}"
        KONUM_JSONLARI+=("${sonuc}")
        echo "Lazeri KAPATIN."
        read -r -p "Lazer kapalıysa Enter'a basın... "
    done

    "${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_tarama_karar_v3.py" \
        --konum-json "${KONUM_JSONLARI[@]}" \
        --cikti "${NUMUNE_DIR}/nihai_sonuc.json" \
        --gercek-etiket "${etiket}"
    numune=$((numune + 1))
done

echo "Deney tamamlandı: ${RUN_DIR}"
echo "Lazerin kapalı olduğunu kontrol edin."
