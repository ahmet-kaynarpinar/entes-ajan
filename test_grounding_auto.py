"""
OTOMATİK GROUNDING TESTİ — tüm veri/ kategorilerinde, her kolon × her değer için:
"filtrele(kolon=V), CSV'de o değere sahip satırları TAM olarak döndürmeli
(ne eksik, ne fazla, ne uydurma)."

Beklenen sonuç, filtrele.py'nin iç fonksiyonları KULLANILMADAN, bağımsız bir
normalize ile hesaplanır; böylece test gerçek bir çapraz-kontrol olur.
Binlerce deterministik kontrol, saniyede koşar, LLM/maliyet yok.

Çalıştır: python3 test_grounding_auto.py
"""
import contextlib
import glob
import io
from pathlib import Path

import pandas as pd

from filtrele import filtrele, ICEREN_KOLONLAR

BASE = Path(__file__).parent
VERI = BASE / "veri"
SABIT_KOLONLAR = {"Kategori", "Seri", "Model"}


def bagimsiz_norm(deger) -> str:
    """filtrele.py'den BAĞIMSIZ normalize (çapraz-kontrol için)."""
    s = str(deger).strip().lower()
    for ch in ("×", "*", "✕", "✗"):  # 'X' zaten lower() ile 'x' oldu
        s = s.replace(ch, "x")
    return "".join(s.split())


def main():
    kontrol = 0
    kalan = 0
    kategori_sayisi = 0
    ornek_hatalar = []

    for yol in sorted(glob.glob(str(VERI / "*.csv"))):
        ad = Path(yol).name
        try:
            df = pd.read_csv(yol)
        except Exception as e:
            print(f"[HATA ] {ad} okunamadı: {e}")
            continue
        if "Model" not in df.columns:
            print(f"[ATLA ] {ad}: 'Model' kolonu yok")
            continue
        kategori_sayisi += 1
        gecerli_modeller = set(df["Model"].astype(str))

        for kol in df.columns:
            if kol in SABIT_KOLONLAR:
                continue
            iceren = kol in ICEREN_KOLONLAR
            for V in df[kol].dropna().astype(str).unique():
                if V.strip() == "" or V.lower() == "nan":
                    continue
                # Beklenen: bağımsız normalize ile eşleşen modeller
                vn = bagimsiz_norm(V)
                seri = df[kol].astype(str).map(bagimsiz_norm)
                if iceren:
                    maske = seri.str.contains(vn, na=False, regex=False)
                else:
                    maske = seri == vn
                beklenen = set(df[maske]["Model"].astype(str))

                # Gerçek: filtrele ne döndürüyor (DEBUG çıktısı susturulur)
                with contextlib.redirect_stdout(io.StringIO()):
                    sonuc, _ = filtrele({kol: V}, df)
                donen = set(sonuc["Model"].astype(str))

                kontrol += 1
                # 1) uydurma yok: dönen her model gerçekten CSV'de olmalı
                # 2) tam eşleşme: dönen == beklenen
                if donen != beklenen:
                    kalan += 1
                    if len(ornek_hatalar) < 10:
                        ornek_hatalar.append(
                            f"{ad} | {kol}={V!r} | beklenen {len(beklenen)}, dönen {len(donen)} "
                            f"| fazla={sorted(donen-beklenen)[:3]} eksik={sorted(beklenen-donen)[:3]}"
                        )
                elif not donen <= gecerli_modeller:
                    kalan += 1

    print(f"{kategori_sayisi} kategori tarandı.")
    print(f"{kontrol - kalan}/{kontrol} kontrol geçti.")
    if ornek_hatalar:
        print("\nÖrnek hatalar:")
        for h in ornek_hatalar:
            print("  -", h)
    else:
        print("Tüm kontroller geçti: filtreleme motoru hiçbir yerde model uydurmuyor/kaçırmıyor.")


if __name__ == "__main__":
    main()
