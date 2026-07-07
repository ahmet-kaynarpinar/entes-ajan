"""
filtrele.py için deterministik ZORLAYICI grounding testleri (LLM yok, hızlı, bedava).
Gerçek veri/ CSV'lerine dayanır. Beklenen model listesi UYDURULMAZ; her test bir
DAVRANIŞ ÖZELLİĞİNİ doğrular (tolerans, Belirsiz sızmaması, olmayan kolon atlanması vb.).

Çalıştır: python3 test_filtrele.py
"""
from pathlib import Path
import pandas as pd
from filtrele import filtrele

BASE = Path(__file__).parent
VERI = BASE / "veri"


def yukle(kategori: str) -> pd.DataFrame:
    return pd.read_csv(VERI / f"{kategori}.csv")


def model_seti(sonuc_df: pd.DataFrame) -> set[str]:
    return set(sonuc_df["Model"].astype(str))


testler = []


def test(ad):
    def dekor(fn):
        testler.append((ad, fn))
        return fn
    return dekor


# 1) Türkçe ondalık virgüllü KOLON ADI ("Sınıf 0,5") filtreyi bozmamalı
@test("Türkçe virgüllü kolon adı (Sınıf 0,5) çalışıyor")
def _():
    df = yukle("sebeke_analizorleri")
    sonuc, atlanan = filtrele({"Sınıf 0,5": "Var"}, df)
    assert "Sınıf 0,5" not in atlanan, "kolon çözülemedi (atlandı)"
    # dönen her satırın gerçekten Var olması gerekir
    assert all(v == "Var" for v in sonuc["Sınıf 0,5"].astype(str)), "Var olmayan satır sızdı"
    # kolon adı toleransı: alt çizgili varyant aynı sonucu vermeli
    sonuc2, _ = filtrele({"Sınıf_0_5": "Var"}, df)
    assert model_seti(sonuc) == model_seti(sonuc2), "kolon adı toleransı tutmadı"


# 2) Boyut "içerir" + × / " mm" eki normalize: "96x96" düz x ile × ve ekli değerleri yakalamalı
@test("Boyut 'içerir' + × normalize (96x96 -> 96×96 ve 96×96×45 mm)")
def _():
    df = yukle("sebeke_analizorleri")
    sonuc, _ = filtrele({"Boyut": "96x96"}, df)
    donen_boyutlar = set(sonuc["Boyut"].astype(str))
    assert len(sonuc) > 0, "hiç eşleşme yok"
    assert donen_boyutlar <= {"96×96", "96×96×45 mm"}, f"yanlış boyut sızdı: {donen_boyutlar}"
    # 72'li ve DIN'li satırlar KESİNLİKLE gelmemeli
    assert "72×72×50 mm" not in donen_boyutlar and "DIN4 ray" not in donen_boyutlar


# 3) x / × / X / boşluk toleransı: farklı yazımlar AYNI sonucu vermeli
@test("Boyut yazım toleransı (72x72 = 72X72 = '72 x 72' = 72×72)")
def _():
    a = yukle("ampermetreler")
    setler = [model_seti(filtrele({"Boyut": v}, a)[0])
              for v in ["72x72", "72X72", "72 x 72", "72×72"]]
    assert all(s == setler[0] for s in setler), "yazım varyantları farklı sonuç verdi"
    assert len(setler[0]) > 0, "72x72 hiç model döndürmedi"


# 4) Belirsiz SIZMAMALI: tam eşleşme kolonunda "Var" filtresi Belirsiz'i almamalı
@test("Belirsiz sızmıyor (Ethernet=Var -> yalnız gerçek Var, 2 model)")
def _():
    df = yukle("sebeke_analizorleri")
    sonuc, _ = filtrele({"Ethernet": "Var"}, df)
    assert all(v == "Var" for v in sonuc["Ethernet"].astype(str)), "Belirsiz/Yok sızdı"
    assert len(sonuc) == 2, f"beklenen 2 (veride Var=2), dönen {len(sonuc)}"


# 5) İmkansız kombinasyon -> boş sonuç, çökme yok
@test("İmkansız kombinasyon boş liste döner, çökmez")
def _():
    a = yukle("ampermetreler")
    sonuc, atlanan = filtrele({"Çıkış Kontağı": "Var", "Boyut": "999x999"}, a)
    assert len(sonuc) == 0, "olmayan boyut için sonuç dönmemeli"
    assert atlanan == [], "iki kolon da var, atlanan olmamalı"


# 6) Olmayan kolon ATLANMALI (uydurmadan), kalan filtre uygulanmalı
@test("Olmayan kolon (Ethernet@ampermetre) atlanır, kalan filtre uygulanır")
def _():
    a = yukle("ampermetreler")
    sonuc, atlanan = filtrele({"Ethernet": "Var", "Boyut": "96x96"}, a)
    assert "Ethernet" in atlanan, "olmayan kolon atlanmadı"
    # sonuç, sadece Boyut=96x96 ile aynı olmalı (Ethernet uygulanmamış olmalı)
    yalniz_boyut, _ = filtrele({"Boyut": "96x96"}, a)
    assert model_seti(sonuc) == model_seti(yalniz_boyut), "atlanan filtre yanlışlıkla uygulandı"


# 7) Belirsiz sorgusu simetrik: "Belirsiz" istenince yalnız Belirsiz gelmeli
@test("Belirsiz sorgusu yalnız Belirsiz döndürür (Ethernet=Belirsiz -> 5)")
def _():
    df = yukle("sebeke_analizorleri")
    sonuc, _ = filtrele({"Ethernet": "Belirsiz"}, df)
    assert all(v == "Belirsiz" for v in sonuc["Ethernet"].astype(str)), "Belirsiz dışı sızdı"
    assert len(sonuc) == 5, f"beklenen 5 (veride Belirsiz=5), dönen {len(sonuc)}"


def main():
    gecti = 0
    for ad, fn in testler:
        try:
            fn()
            print(f"[GEÇTİ] {ad}")
            gecti += 1
        except AssertionError as e:
            print(f"[KALDI] {ad}\n         -> {e}")
        except Exception as e:
            print(f"[HATA ] {ad}\n         -> {type(e).__name__}: {e}")
    print(f"\n{gecti}/{len(testler)} geçti")


if __name__ == "__main__":
    main()
