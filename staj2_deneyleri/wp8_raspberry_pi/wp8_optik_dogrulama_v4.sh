#!/usr/bin/env bash
set -euo pipefail

SURUM="WP8-OPTIK-DOGRULAMA-V4-20260822"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python3"
[[ -x "${PYTHON_BIN}" ]] || PYTHON_BIN="python3"
RUN_DIR="${HOME}/WP8_OPTIK_V4/$(date +%Y%m%d_%H%M%S)"
mkdir -p "${RUN_DIR}/odak" "${RUN_DIR}/pozlama" "${RUN_DIR}/dogrulama"

cek() {
    local cikti="$1" odak="$2" shutter="$3"
    rpicam-still --nopreview --timeout 1800 --width 2304 --height 1296 \
        --shutter "${shutter}" --gain 1 --awb daylight \
        --autofocus-mode manual --lens-position "${odak}" \
        --metadata-format json --output "${cikti}.jpg" --metadata "${cikti}.json"
}

ciftleri_cek() {
    local onek="$1" odak="$2" shutter="$3"
    echo "Lazeri KAPATIN."
    read -r -p "Hazırsa Enter'a basın... "
    for i in 01 02 03; do cek "${onek}_K_${i}" "${odak}" "${shutter}"; done
    echo "Yüzeye dokunmadan lazeri AÇIN."
    read -r -p "Lazer açıksa Enter'a basın... "
    for i in 01 02 03; do cek "${onek}_A_${i}" "${odak}" "${shutter}"; done
    echo "Lazeri KAPATIN."
}

echo "============================================================"
echo "${SURUM}"
echo "Bu test makine öğrenmesi kullanmaz. Önce ölçüm donanımını doğrular."
echo "============================================================"
echo "1/3 ODAK TESTİ"
echo "Üzerinde küçük ve net yazılar bulunan basılı bir sayfayı görüntünün"
echo "merkezine yerleştirin. Boş A4 kullanmayın. Lazeri KAPATIN."
read -r -p "Hazırsa Enter'a basın... "
for odak in 2.50 2.80 3.10 3.40 3.70 4.00; do
    cek "${RUN_DIR}/odak/odak_${odak}" "${odak}" 5000
done
ODAK_CIKTISI="$("${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_optik_dogrulama_v4.py" \
    odak-sec --klasor "${RUN_DIR}/odak" --cikti "${RUN_DIR}/odak_sonucu.json")"
echo "${ODAK_CIKTISI}"
ODAK="$(printf '%s\n' "${ODAK_CIKTISI}" | sed -n 's/^SECILEN_ODAK=//p')"
[[ -n "${ODAK}" ]] || { echo "HATA: Odak seçilemedi."; exit 2; }

echo
echo "2/3 LAZER POZLAMA TESTİ"
echo "Basılı sayfayı kaldırıp düz beyaz A4 koyun. Kameraya dokunmayın."
read -r -p "Düz beyaz A4 hazırsa Enter'a basın... "
for shutter in 2500 5000 7500; do
    echo "Pozlama ${shutter} us: Lazeri KAPATIN."
    read -r -p "Hazırsa Enter'a basın... "
    cek "${RUN_DIR}/pozlama/pozlama_${shutter}_K" "${ODAK}" "${shutter}"
    echo "Lazeri AÇIN."
    read -r -p "Hazırsa Enter'a basın... "
    cek "${RUN_DIR}/pozlama/pozlama_${shutter}_A" "${ODAK}" "${shutter}"
done
echo "Lazeri KAPATIN."
POZLAMA_CIKTISI="$("${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_optik_dogrulama_v4.py" \
    pozlama-sec --klasor "${RUN_DIR}/pozlama" --cikti "${RUN_DIR}/pozlama_sonucu.json")"
echo "${POZLAMA_CIKTISI}"
SHUTTER="$(printf '%s\n' "${POZLAMA_CIKTISI}" | sed -n 's/^SECILEN_POZLAMA=//p')"
[[ -n "${SHUTTER}" ]] || { echo "HATA: Pozlama seçilemedi."; exit 2; }

echo
echo "3/3 BİLİNEN 5 mm BASAMAK TESTİ"
echo "Önce yalnızca düz beyaz A4 çekilecek."
ciftleri_cek "${RUN_DIR}/dogrulama/DUZ" "${ODAK}" "${SHUTTER}"

echo
echo "Şimdi yaklaşık 5 mm kalınlığında, 20 mm genişliğinde ve en az 80 mm"
echo "uzunluğunda sert bir A4/karton basamak hazırlayın."
echo "Basamağı görüntünün ORTASINA ve kırmızı lazer çizgisine DİK yerleştirin."
echo "Bu ilk doğrulamada basamağın üstünü kumaşla ÖRTMEYİN."
ciftleri_cek "${RUN_DIR}/dogrulama/BASAMAK5MM" "${ODAK}" "${SHUTTER}"

"${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_optik_dogrulama_v4.py" \
    dogrula --klasor "${RUN_DIR}/dogrulama" \
    --cikti "${RUN_DIR}/optik_dogrulama_sonucu.json"

echo "Deney klasörü: ${RUN_DIR}"
