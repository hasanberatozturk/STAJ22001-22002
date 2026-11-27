"""WP8-TARAMA-V3: Birden fazla lazer konumundan nihai karar üretir.

Bu betik görüntü işlemez. Her tarama konumu için WP8_canli_tahmin.py
tarafından oluşturulan JSON dosyalarını birleştirir. Gerçek etiket yalnızca
kayıt içindir; karar hesabında kullanılmaz.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


SURUM = "WP8-TARAMA-V3-20260822"

# Bu iki güçlü kanıt kuralı, eldeki 132 geçerli geçmiş kayıtta normal
# örneklerde yanlış alarm üretmemiştir. Bu geriye dönük bir kontroldür;
# yeni kumaşlarda üretim doğruluğu garantisi değildir.
KURAL_A = {
    "sapma_aralik_px": 2.20,
    "sapma_p95_px": 1.10,
    "aktif_oran_0_5px": 0.30,
}
KURAL_B = {
    "sapma_aralik_px": 2.60,
    "sapma_p95_px": 0.90,
    "aktif_oran_0_5px": 0.20,
}


def json_oku(yol: Path) -> dict:
    return json.loads(yol.read_text(encoding="utf-8"))


def esit_ve_buyuk(ozellikler: dict, kural: dict) -> bool:
    return all(float(ozellikler.get(ad, 0.0)) >= esik for ad, esik in kural.items())


def konumu_degerlendir(yol: Path) -> dict:
    veri = json_oku(yol)
    ozellikler = veri.get("ozellikler") or {}
    gecerli = bool(veri.get("olcum_gecerli")) and bool(ozellikler)
    kural_a = gecerli and esit_ve_buyuk(ozellikler, KURAL_A)
    kural_b = gecerli and esit_ve_buyuk(ozellikler, KURAL_B)
    return {
        "dosya": str(yol),
        "olcum_gecerli": gecerli,
        "gecersizlik_nedeni": veri.get("gecersizlik_nedeni"),
        "guclu_kusur_kaniti": bool(kural_a or kural_b),
        "saglanan_kurallar": [
            ad for ad, saglandi in (("A", kural_a), ("B", kural_b)) if saglandi
        ],
        "sapma_aralik_px": float(ozellikler.get("sapma_aralik_px", 0.0)),
        "sapma_p95_px": float(ozellikler.get("sapma_p95_px", 0.0)),
        "aktif_oran_0_5px": float(ozellikler.get("aktif_oran_0_5px", 0.0)),
        "rf_ham_kusur_skoru": veri.get("rf_ham_kusur_skoru"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--konum-json", type=Path, nargs="+", required=True)
    parser.add_argument("--cikti", type=Path, required=True)
    parser.add_argument("--gercek-etiket", default="bilinmiyor")
    args = parser.parse_args()

    konumlar = [konumu_degerlendir(yol) for yol in args.konum_json]
    gecerli_sayisi = sum(k["olcum_gecerli"] for k in konumlar)
    guclu_konumlar = [k for k in konumlar if k["guclu_kusur_kaniti"]]

    if gecerli_sayisi < len(konumlar):
        karar = "OLCUM_YETERSIZ"
        gerekce = "En az bir tarama konumunda görüntü/lazer kalite kontrolü geçilemedi."
    elif len(konumlar) < 5:
        karar = "OLCUM_YETERSIZ"
        gerekce = "Nihai karar için beş farklı tarama konumu gereklidir."
    elif guclu_konumlar:
        karar = "KUSUR"
        gerekce = (
            f"{len(guclu_konumlar)} konumda güçlü ve tekrarlanabilir geometrik "
            "deformasyon kanıtı bulundu."
        )
    else:
        karar = "NORMAL"
        gerekce = (
            "Beş geçerli konumun hiçbirinde belirlenen güçlü geometrik kusur "
            "sınırı aşılmadı. Hafif kat izi ve doğal doku kapsam dışıdır."
        )

    sonuc = {
        "surum": SURUM,
        "zaman": datetime.now().astimezone().isoformat(),
        "gercek_etiket": args.gercek_etiket,
        "nihai_karar": karar,
        "karar_gerekcesi": gerekce,
        "tarama_konumu_sayisi": len(konumlar),
        "gecerli_konum_sayisi": gecerli_sayisi,
        "guclu_kusur_konumu_sayisi": len(guclu_konumlar),
        "kural_a": KURAL_A,
        "kural_b": KURAL_B,
        "konumlar": konumlar,
        "kapsam_notu": (
            "Bu sürüm belirgin kırışıklık, kabarıklık ve sırt gibi geometrik "
            "deformasyonları hedefler. Kat izi ve doğal dokusal kırışıklık kusur "
            "sınıfına dahil değildir."
        ),
    }
    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    args.cikti.write_text(
        json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("=" * 64)
    print("SÜRÜM:", SURUM)
    print("NİHAİ KARAR:", karar)
    print("GEREKÇE:", gerekce)
    print("Geçerli konum:", f"{gecerli_sayisi}/{len(konumlar)}")
    print("Güçlü kusur bulunan konum:", len(guclu_konumlar))
    for sira, konum in enumerate(konumlar, start=1):
        durum = "GÜÇLÜ KUSUR" if konum["guclu_kusur_kaniti"] else "sınır aşılmadı"
        if not konum["olcum_gecerli"]:
            durum = "GEÇERSİZ"
        print(
            f"Konum {sira}: {durum} | "
            f"aralık={konum['sapma_aralik_px']:.3f} px | "
            f"p95={konum['sapma_p95_px']:.3f} px | "
            f"aktif={konum['aktif_oran_0_5px']:.3f}"
        )
    print("Sonuç dosyası:", args.cikti)
    print("=" * 64)


if __name__ == "__main__":
    main()
