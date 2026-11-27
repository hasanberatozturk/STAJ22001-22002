"""Uc RGB resmi leke ve yirtik icin birlikte test eder."""

from __future__ import annotations

import argparse
from pathlib import Path

from wp9_ortak import KusurMotoru, json_kaydet


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("resimler", nargs=3, type=Path, help="Ayni fiziksel durumun 3 karesi")
    p.add_argument("--cikti", type=Path, default=Path("wp9_rgb_sonuc.json"))
    args = p.parse_args()
    motor = KusurMotoru()
    sonuc = motor.uclu_incele(args.resimler)
    json_kaydet(sonuc, args.cikti)
    print("NIHAI RGB KARARI:", sonuc["karar"])
    print("Leke oyu:", f"{sonuc['leke_oyu']}/3")
    print("Yirtik oyu:", f"{sonuc['yirtik_oyu']}/3")
    print("Kayit:", args.cikti.resolve())


if __name__ == "__main__":
    main()
