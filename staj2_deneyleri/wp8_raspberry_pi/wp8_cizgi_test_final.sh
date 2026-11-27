#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python3"
[[ -x "${PYTHON_BIN}" ]] || PYTHON_BIN="python3"
RUN_KOKU="${HOME}/WP8_FINAL"
ODAK="2.50"
SHUTTER="5000"

echo "============================================================"
echo "WP8 FINAL - BASIT LAZER CIZGISI SAPMA TESTI"
echo "Kapsam: duz yuzeyli acik, koyu, desenli ve parlak kumas"
echo "Kusur: belirgin kirisiklik veya kabariklik cizgiyi bozarsa"
echo "Kapsam disi: kat izi ve kendinden kirisik/dokulu kumas"
echo "============================================================"

read -r -p "Kumas kodu (ornek K001): " KUMAS_KODU
read -r -p "Kumas adi ASCII (ornek sari_acik_mat): " KUMAS_ADI
KUMAS_KODU="$(printf '%s' "${KUMAS_KODU}" | tr -cd 'A-Za-z0-9_-')"
KUMAS_ADI="$(printf '%s' "${KUMAS_ADI}" | tr ' ' '_' | tr -cd 'A-Za-z0-9_-')"
[[ -n "${KUMAS_KODU}" && -n "${KUMAS_ADI}" ]] || {
    echo "HATA: Kumas kodu veya adi bos."; exit 2;
}

OTURUM="$(date +%Y%m%d_%H%M%S)_${KUMAS_KODU}_${KUMAS_ADI}"
RUN_DIR="${RUN_KOKU}/${OTURUM}"
mkdir -p "${RUN_DIR}/pozlama" "${RUN_DIR}/normal" "${RUN_DIR}/testler"

cek() {
    local cikti="$1"
    rpicam-still --nopreview --timeout 1800 --width 2304 --height 1296 \
        --shutter "${SHUTTER}" --gain 1 --awb daylight \
        --autofocus-mode manual --lens-position "${ODAK}" \
        --metadata-format json --output "${cikti}.jpg" --metadata "${cikti}.json"
}

uc_cift_cek() {
    local onek="$1"
    echo "Lazeri KAPATIN; kumasa dokunmayin."
    read -r -p "Hazirsa Enter: "
    for i in 01 02 03; do cek "${onek}_K_${i}"; done
    echo "Kumasa dokunmadan lazeri ACIN."
    read -r -p "Lazer aciksa Enter: "
    for i in 01 02 03; do cek "${onek}_A_${i}"; done
    echo "Lazeri KAPATIN."
}

echo ""
echo "POZLAMA SECIMI: Kumas duz ve sabit olsun."
for aday in 2500 5000 7500; do
    echo "Pozlama ${aday}: lazer KAPALI."
    read -r -p "Hazirsa Enter: "
    SHUTTER="${aday}" cek "${RUN_DIR}/pozlama/pozlama_${aday}_K"
    echo "Lazeri ACIN."
    read -r -p "Lazer aciksa Enter: "
    SHUTTER="${aday}" cek "${RUN_DIR}/pozlama/pozlama_${aday}_A"
done
echo "Lazeri KAPATIN."
POZLAMA_CIKTISI="$("${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_optik_dogrulama_v4.py" \
    pozlama-sec --klasor "${RUN_DIR}/pozlama" \
    --cikti "${RUN_DIR}/pozlama_sonucu.json")"
echo "${POZLAMA_CIKTISI}"
SHUTTER="$(printf '%s\n' "${POZLAMA_CIKTISI}" | sed -n 's/^SECILEN_POZLAMA=//p')"
[[ -n "${SHUTTER}" ]] || { echo "HATA: Pozlama secilemedi."; exit 2; }
echo "Bu kumas icin secilen pozlama: ${SHUTTER}"

echo ""
echo "NORMAL REFERANS: Kumasi duz ve dogal halinde sabitleyin."
echo "Uc farkli noktada olcum alinacak."
for sira in 1 2 3; do
    printf -v kk "%02d" "${sira}"
    (( sira > 1 )) && echo "Kumasi lazer cizgisine DIK yaklasik 10 mm kaydirin."
    uc_cift_cek "${RUN_DIR}/normal/normal_${kk}"
done

numune=1
while true; do
    read -r -p "Yeni test icin Enter, bitirmek icin q: " cevap
    [[ "${cevap,,}" == "q" ]] && break
    printf -v nk "N%03d" "${numune}"
    TEST_DIR="${RUN_DIR}/testler/${nk}"
    mkdir -p "${TEST_DIR}"
    echo "Test durumunu hazirlayin. Kusur varsa LAZER CIZGISINI KESMELI."
    echo "Uc taramada kusurun seklini bozmayin."
    for sira in 1 2 3; do
        printf -v kk "%02d" "${sira}"
        (( sira > 1 )) && echo "Kumas ve kusuru birlikte DIK yonde 10 mm kaydirin."
        uc_cift_cek "${TEST_DIR}/konum_${kk}"
    done
    "${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_cizgi_sapma_karar.py" \
        --normal "${RUN_DIR}/normal" --test "${TEST_DIR}" \
        --cikti "${TEST_DIR}/nihai_sonuc.json"
    numune=$((numune + 1))
done

echo "Deney tamamlandi: ${RUN_DIR}"
echo "Lazerin kapali oldugunu kontrol edin."
