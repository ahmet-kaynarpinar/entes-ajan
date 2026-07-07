from __future__ import annotations

import pandas as pd
from pathlib import Path


CSV_PATH = Path(__file__).parent / "urunler.csv"


ICEREN_KOLONLAR = {"Boyut"}

# Karşılaştırmadan önce sadeleştirilecek, birbirinin yerine geçen semboller
# (ör. "96x96" ile "96×96" aynı sayılsın). Yeni benzer sembol farkları
# ortaya çıkarsa buraya eklemek yeterli.
ESDEGER_SEMBOLLER = {"×": "x", "X": "x", "*": "x", "✕": "x", "✗": "x"}


def _normalize(deger) -> str:
    """Karşılaştırma için bir değeri sadeleştirir: boşluk, harf büyüklüğü ve
    birbirinin yerine geçen semboller (x/×) farkını yok sayar."""
    s = str(deger).strip().lower()
    for sembol, karsilik in ESDEGER_SEMBOLLER.items():
        s = s.replace(sembol.lower(), karsilik)
    s = "".join(s.split())
    return s


# Kolon adı eşleştirirken birbirinin yerine geçen ayraçlar (hepsi yok sayılır).
KOLON_AYRAC_KARAKTERLERI = ("-", "_", " ", ",")


def _kolon_normalize(ad) -> str:
    """Kolon adı karşılaştırması için tire/alt çizgi/boşluk/virgül farkını yok
    sayar: "RS_485" ile "RS-485", "Sınıf_0_5" ile "Sınıf 0,5" aynı kabul edilir."""
    s = str(ad).strip().lower()
    for karakter in KOLON_AYRAC_KARAKTERLERI:
        s = s.replace(karakter, "")
    return s


def _kolonu_coz(kolon: str, df: pd.DataFrame) -> str | None:
    """Verilen kriter kolon adını df.columns içindeki gerçek kolon adına çözer.
    Önce tam eşleşmeye bakar, sonra tire/alt çizgi/boşluk/virgül farkını yok
    sayarak eşleşen kolonu arar. Bulamazsa None döner (bu kategoride kolon yok)."""
    if kolon in df.columns:
        return kolon
    hedef = _kolon_normalize(kolon)
    for gercek_kolon in df.columns:
        if _kolon_normalize(gercek_kolon) == hedef:
            return gercek_kolon
    return None


def filtrele(kriterler: dict, df: pd.DataFrame | None = None) -> tuple[pd.DataFrame, list[str]]:
    """
    kriterler: {"kolon_adi": "beklenen_deger", ...}
    df verilmezse geriye dönük uyumluluk için urunler.csv okunur (ajan.py tek
    kategori/tek dosya modeliyle böyle çağırır). agent.py çoklu kategori
    desteği için seçtiği kategorinin dataframe'ini df parametresiyle geçirir.
    Belirsiz dahil tam eşleşmeyen satırlar elenir.
    ICEREN_KOLONLAR listesindeki kolonlar için tam eşleşme yerine 'içerir' mantığı kullanılır.
    Karşılaştırma _normalize ile sadeleştirilmiş değerler üzerinden yapılır.
    Kriterdeki bir kolon bu kategorinin df'inde yoksa (ör. başka kategoriye
    özgü bir özellik), o filtre uydurulmadan atlanır; kalan filtrelerle devam
    edilir.

    Dönüş: (sonuç_df, atlanan_kolonlar). atlanan_kolonlar, bu kategoride
    bulunmadığı için uygulanamayan kriter kolonlarının adlarını taşır; çağıran
    taraf bu bilgiyi modele/kullanıcıya iletmelidir ki sonuçlar o özelliğe
    sahipmiş gibi yorumlanmasın.
    """
    if df is None:
        df = pd.read_csv(CSV_PATH)

    çözülmüş_kolonlar = []
    atlanan_kolonlar = []
    for kolon, deger in kriterler.items():
        gerçek_kolon = _kolonu_coz(kolon, df)
        if gerçek_kolon is None:
            atlanan_kolonlar.append(kolon)
            continue
        çözülmüş_kolonlar.append(gerçek_kolon)
        deger_norm = _normalize(deger)
        kolon_norm = df[gerçek_kolon].astype(str).map(_normalize)
        if gerçek_kolon in ICEREN_KOLONLAR:
            df = df[kolon_norm.str.contains(deger_norm, na=False, regex=False)]
        else:
            df = df[kolon_norm == deger_norm]

    if atlanan_kolonlar:
        print(f"DEBUG: Uygulanamayan filtreler: {atlanan_kolonlar} (bu kategoride veri yok)")

    görüntü_kolonları = ["Model"] + çözülmüş_kolonlar
    return df[görüntü_kolonları].reset_index(drop=True), atlanan_kolonlar


if __name__ == "__main__":
    örnek_kriterler = {"Ethernet": "Var", "Sınıf 0,5": "Var"}

    print(f"Filtre: {örnek_kriterler}\n")
    sonuç, atlanan = filtrele(örnek_kriterler)

    if atlanan:
        print(f"Atlanan filtreler (bu kategoride veri yok): {atlanan}\n")

    if sonuç.empty:
        print("Eşleşen ürün bulunamadı.")
    else:
        print(sonuç.to_string(index=False))
        print(f"\nToplam {len(sonuç)} ürün eşleşti.")
