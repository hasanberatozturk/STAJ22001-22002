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

RUN_DIR="${HOME}/WP8_CANLI/$(date +%Y%m%d_%H%M%S)"
CAL_DIR="${RUN_DIR}/kalibrasyon"
OLCUM_DIR="${RUN_DIR}/olcumler"
mkdir -p "${CAL_DIR}" "${OLCUM_DIR}"

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

uc_cift_cek() {
    local temel="$1"
    echo "Lazeri KAPATIN."
    read -r -p "Yuzey hazir ve lazer kapaliysa Enter'a basin... "
    for tekrar in 01 02 03; do
        echo "${temel}_K_${tekrar} kaydediliyor..."
        cek "${temel}_K_${tekrar}"
    done
    echo "Yuzeye ve duzeneklere dokunmadan lazeri ACIN."
    read -r -p "Lazer aciksa Enter'a basin... "
    for tekrar in 01 02 03; do
        echo "${temel}_A_${tekrar} kaydediliyor..."
        cek "${temel}_A_${tekrar}"
    done
}

echo "WP8 canli tahmin deneyi: ${RUN_DIR}"
echo "Kamera 30 cm, lazer ayrimi 10 cm ve aci yaklasik 60 derece olmali."
echo "Ilk olarak ayni kumastan 3 duz NORMAL kalibrasyon cifti alinacak."
echo "Kumasi duz yerlestirin; dikis, dugme ve kenarlar goruntu disinda kalsin."
echo "ONEMLI: Lazerin analiz edilen orta bolumu ve iki yan referans bandi tamamen ayni kumasla kapli olmali."
echo "Lazeri KAPATIN."
read -r -p "Duzenek ve normal kumas hazirsa Enter'a basin... "

for i in 01 02 03; do
    echo "D00_K_${i} kaydediliyor..."
    cek "${CAL_DIR}/D00_K_${i}"
done

echo "Kumasa ve duzeneklere dokunmadan lazeri ACIN."
read -r -p "Lazer aciksa Enter'a basin... "
for i in 01 02 03; do
    echo "D00_A_${i} kaydediliyor..."
    cek "${CAL_DIR}/D00_A_${i}"
done

echo "Lazeri KAPATIN. Kalibrasyon tamamlandi."
echo "Kalibrasyon otomatik kontrol ediliyor..."
if ! "${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_canli_tahmin.py" \
    --kalibrasyon "${CAL_DIR}" \
    --kalibrasyon-kontrol; then
    echo "HATA: Kalibrasyon gecersiz. Hicbir olcum kaydedilmedi."
    echo "Lazeri kapatip betigi yeniden baslatin."
    exit 2
fi
echo "Her canli olcumde 3 kapali ve 3 acik goruntu medyanlanacak."
echo
echo "KUMASA OZEL NORMAL REFERANS ASAMASI"
echo "Simdi ayni kumasin 5 farkli, kabul edilebilir NORMAL bolgesi olculecek."
echo "Her olcumde kumasi biraz kaydirin veya dondurun. Dogal doku ve desen kalabilir."
echo "Dikis, dugme, kenar, kasitli sirt, kabariklik ve belirgin kirisiklik kullanmayin."
NORMAL_REFERANSLARI=()
sayac=1
for referans_no in 1 2 3 4 5; do
    printf -v kod "%03d" "${sayac}"
    echo
    echo "Normal referans ${referans_no}/5 hazirlaniyor."
    echo "Kumasta daha oncekinden farkli ve kabul edilebilir bir normal bolge secin."
    uc_cift_cek "${OLCUM_DIR}/olcum_${kod}"

    "${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_canli_tahmin.py" \
        --kalibrasyon "${CAL_DIR}" \
        --lazer-kapali \
            "${OLCUM_DIR}/olcum_${kod}_K_01.jpg" \
            "${OLCUM_DIR}/olcum_${kod}_K_02.jpg" \
            "${OLCUM_DIR}/olcum_${kod}_K_03.jpg" \
        --lazer-acik \
            "${OLCUM_DIR}/olcum_${kod}_A_01.jpg" \
            "${OLCUM_DIR}/olcum_${kod}_A_02.jpg" \
            "${OLCUM_DIR}/olcum_${kod}_A_03.jpg" \
        --cikti "${OLCUM_DIR}/olcum_${kod}_sonuc.json" \
        --gercek-kod "0" \
        --gercek-etiket "normal_referans" \
        --ozet-csv "${RUN_DIR}/olcum_ozeti.csv"

    NORMAL_REFERANSLARI+=("${OLCUM_DIR}/olcum_${kod}_sonuc.json")
    echo "Lazeri KAPATIN."
    read -r -p "Lazer kapaliysa Enter'a basin... "
    sayac=$((sayac + 1))
done

echo "Bes normal referans tamamlandi. Bundan sonraki kararlar bu kumasa ozel verilecek."
while true; do
    printf -v kod "%03d" "${sayac}"
    echo
    read -r -p "Yeni olcum icin Enter, bitirmek icin q yazin: " cevap
    if [[ "${cevap,,}" == "q" ]]; then
        break
    fi
    echo "Gercek yuzey durumu:"
    echo "  0 = normal_duz"
    echo "  1 = dikey_sirt"
    echo "  2 = capraz_sirt"
    echo "  3 = yumusak_kabariklik"
    echo "  4 = kirisiklik"
    while true; do
        read -r -p "Durum kodunu girin [0-4]: " gercek_kod
        case "${gercek_kod}" in
            0) gercek_etiket="normal_duz"; break ;;
            1) gercek_etiket="dikey_sirt"; break ;;
            2) gercek_etiket="capraz_sirt"; break ;;
            3) gercek_etiket="yumusak_kabariklik"; break ;;
            4) gercek_etiket="kirisiklik"; break ;;
            *) echo "Gecersiz kod; 0 ile 4 arasinda bir deger girin." ;;
        esac
    done
    echo "Test etmek istediginiz yuzeyi hazirlayin."
    uc_cift_cek "${OLCUM_DIR}/olcum_${kod}"

    "${PYTHON_BIN}" "${SCRIPT_DIR}/WP8_canli_tahmin.py" \
        --kalibrasyon "${CAL_DIR}" \
        --lazer-kapali \
            "${OLCUM_DIR}/olcum_${kod}_K_01.jpg" \
            "${OLCUM_DIR}/olcum_${kod}_K_02.jpg" \
            "${OLCUM_DIR}/olcum_${kod}_K_03.jpg" \
        --lazer-acik \
            "${OLCUM_DIR}/olcum_${kod}_A_01.jpg" \
            "${OLCUM_DIR}/olcum_${kod}_A_02.jpg" \
            "${OLCUM_DIR}/olcum_${kod}_A_03.jpg" \
        --cikti "${OLCUM_DIR}/olcum_${kod}_sonuc.json" \
        --gercek-kod "${gercek_kod}" \
        --gercek-etiket "${gercek_etiket}" \
        --normal-referans-json "${NORMAL_REFERANSLARI[@]}" \
        --ozet-csv "${RUN_DIR}/olcum_ozeti.csv"

    echo "Lazeri KAPATIN."
    read -r -p "Lazer kapaliysa Enter'a basin... "
    sayac=$((sayac + 1))
done

echo "Deney tamamlandi: ${RUN_DIR}"
echo "Lazerin kapali oldugunu kontrol edin."
