"""
ENTES SSS (destek makalesi) arama modülü.
sss_veri/ klasöründeki CSV'leri okur; müşterinin ürün + konu kelimelerine göre
makaleleri PUANLAR ve en yakınların ÇÖZÜM metnini AYNEN döndürür. Uydurma yok.
"""
import re
from pathlib import Path
import pandas as pd

SSS_DIR = Path(__file__).parent / "sss_veri"
BEKLENEN_KOLONLAR = ["urun_grubu", "urun", "baslik", "problem_tarifi", "cozum", "etiketler", "link"]


def load_sss() -> pd.DataFrame:
    frames = []
    for csv in sorted(SSS_DIR.glob("*.csv")):
        frames.append(pd.read_csv(csv, encoding="utf-8-sig"))
    if not frames:
        return pd.DataFrame(columns=BEKLENEN_KOLONLAR)
    return pd.concat(frames, ignore_index=True)


def _norm(s) -> str:
    s = str(s).lower().translate(str.maketrans("çğıöşüâî", "cgiosuai"))
    return s


def _terimler(*metinler) -> list[str]:
    ham = " ".join(str(m) for m in metinler if m)
    parcalar = re.split(r"[\s,;]+", ham)
    return [_norm(p) for p in parcalar if len(p) > 2]


def sss_ara(urun=None, anahtar_kelime=None, df=None, max_sonuc=3) -> str:
    if df is None:
        df = load_sss()
    if df.empty:
        return "SSS verisi yüklü değil."

    terimler = list(dict.fromkeys(_terimler(urun, anahtar_kelime)))
    if not terimler:
        return "Aramak için en az bir ürün adı ya da konu belirtilmeli."

    # Yüksek ağırlık: ürün+etiket+başlıkta geçen terim; düşük: problem+çözümde geçen
    ust = (df["urun"].astype(str) + " " + df["etiketler"].astype(str) + " " + df["baslik"].astype(str)).map(_norm)
    govde = (df["problem_tarifi"].astype(str) + " " + df["cozum"].astype(str)).map(_norm)

    def puanla(i):
        p = 0
        for t in terimler:
            if t in ust.iloc[i]:
                p += 3
            elif t in govde.iloc[i]:
                p += 1
        return p

    df = df.assign(_puan=[puanla(i) for i in range(len(df))])
    # Esik: en az bir GUCLU (urun/etiket/baslik) eslesme (>=3) olmali; zayif
    # (sadece genel kelime) eslesmeler grounding icin elenir.
    alt = df[df["_puan"] >= 3].sort_values("_puan", ascending=False)

    # Zayıf eşleşmeleri ele: lider puanının yarısından düşük makaleler
    # (genel kelimelerle tutunan alakasızlar) çıkarılır. Böylece sadece güçlü
    # eşleşenler ajana gider; alakasız makale gidip uydurmaya yol açmaz.
    if len(alt) >= 1:
        lider = alt.iloc[0]["_puan"]
        alt = alt[alt["_puan"] >= lider / 2 + 0.001]
    # Baskın lider: tek makale açık ara öndeyse yalnız onu döndür.
    if len(alt) >= 2:
        p1 = alt.iloc[0]["_puan"]; p2 = alt.iloc[1]["_puan"]
        if p1 >= 2 * p2:
            alt = alt.head(1)

    if len(alt) == 0:
        return ("Bu ürün/konuya uygun doğrulanmış bir destek makalesi bulunamadı. "
                "Ürün adını ve karşılaşılan sorunu netleştirmek faydalı olur.")

    parcalar = []
    for _, r in alt.head(max_sonuc).iterrows():
        parcalar.append(f"Başlık: {r['baslik']}\nÜrün: {r['urun']}\nÇözüm: {r['cozum']}\nKaynak: {r['link']}")
    return ("[ÖNEMLİ: Aşağıdaki makale(ler) anahtar kelime eşleşmesiyle bulundu, doğru olduğu garanti DEĞİLDİR. "
             "Makalenin başlığı/ürünü müşterinin sorduğu ürün ve konuyla gerçekten örtüşüyorsa çözümü aynen aktar. "
             "Örtüşmüyorsa kullanma, 'doğrulanmış makale bulamadım' de. Makalede yazmayan hiçbir şey ekleme.]\n\n"
            + "\n\n---\n\n".join(parcalar))


def referans_ara(sektor_veya_konu=None, df=None, max_sonuc=2) -> str:
    """Sadece "Çözümler" (referans/geçmiş proje) grubunda arar. Müşteri
    'bu alanda ne yaptınız / referanslarınız neler' diye sorduğunda kullanılır.
    Bulunan referans projenin metnini AYNEN döndürür; uydurma yok."""
    if df is None:
        df = load_sss()
    if df.empty or "urun_grubu" not in df.columns:
        return "Referans çözüm verisi yüklü değil."
    coz = df[df["urun_grubu"] == "Çözümler"].reset_index(drop=True)
    if coz.empty:
        return "Referans çözüm verisi bulunamadı."
    sonuc = sss_ara(anahtar_kelime=sektor_veya_konu, df=coz, max_sonuc=max_sonuc)
    return sonuc
