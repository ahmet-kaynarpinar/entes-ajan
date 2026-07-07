"""
ENTES MPR Ürün Seçim Ajanı
NLU aşaması: Gemini API (google-genai)
"""

import json
import os
import sys

from google import genai
from google.genai import types

from filtrele import filtrele

# urunler.csv'deki filtre edilebilir kolonlar (Model hariç)
_KOLONLAR = [
    "Seri", "Boyut", "Ekran", "Sınıf 1", "Sınıf 0,5", "Hafıza",
    "Demand", "THD", "Ayrı Harmonik", "Dengesizlik", "Sag&Swell",
    "RS-485", "Ethernet", "Dijital Giriş", "Dijital Çıkış", "Analog Çıkış",
    "Röle", "Alarm", "Çalışma Saati", "Olay", "IP54", "X5/X1",
    "plug&meter", "X/333mV", "4. Akım", "OG", "CT-25",
    "Çift Enerji Sayacı", "Pals Sayacı", "Pulse Çıkışı", "RTC",
    "Sabit Akım Klemensi", "AO 0/2-10V", "AO 0/4-20mA",
    "95-270 VAC/DC", "12-50 VDC", "50-270 VAC/DC", "24-60 VDC",
    "45-265 VAC/DC", "110/230 VAC", "10-56 VDC", "85-265 VAC/DC",
]

_SISTEM_TALIMAT = """
Sen ENTES MPR şebeke analizörü ürün seçim ajanısın.
Kullanıcının Türkçe doğal dil isteğini analiz et ve TAM OLARAK şu JSON yapısını döndür:

{
  "filtreler": { "<kolon_adi>": "<deger>" },
  "degerlendirilemeyen": [ "<teknik_istek>" ]
}

## Geçerli CSV kolonları — SADECE bunlara eşleştir:
""" + "\n".join(f"- {k}" for k in _KOLONLAR) + """

## Kolon değerleri:
- Çoğu kolon: "Var" veya "Yok"
- Boyut kolonu: "DIN" (DIN ray tipi için), "96×96", "72×72", "144×144"
  (Bu değerler str.contains() ile aranır; "DIN4 ray" ve "DIN6" ikisi de "DIN" içerir.)

## KURALLAR (hiç biri çiğnenemez):
1. Bir ifadeyi SADECE yukarıdaki kolon listesindeki bir kolonla DOĞRUDAN ve
   AÇIKÇA anlam taşıyorsa eşleştir. Yakın / benzer / çağrışımlı eşleme YASAK.
2. Tabloda karşılığı olmayan teknik istekleri degerlendirilemeyen listesine koy:
     wifi, kablosuz, bluetooth, GPRS, Zigbee → Ethernet DEĞİL
     IP65, IP67, su geçirmez              → IP54 DEĞİL
     4G, LTE, hücresel                    → hiçbir kolon DEĞİL
3. "SCADA" → Ethernet iletişimi demektir → Ethernet = "Var" olarak filtrele.
4. "3 fazlı", "üç fazlı", "trifaze" → tüm MPR ürünleri 3 fazlıdır, ayırt edici
   değil → ne filtreye ne degerlendirilemeyen'e koy, yoksay.
5. Dolgu / nötr kelimeler yoksay, listeye de filtreye de koyma:
     analizör, cihaz, ürün, bir, lazım, istiyorum, gerekiyor,
     bağlantılı, olan, ile, ve, için
6. Emin değilsen filtreye EKLEME; o kriteri degerlendirilemeyen'e koy.
7. Kolon listesi dışına çıkma, değer uydurmaz.

## Örnekler:
Giriş: "Ethernet'li Class 0.5 analizör"
Çıktı: {"filtreler": {"Ethernet": "Var", "Sınıf 0,5": "Var"}, "degerlendirilemeyen": []}

Giriş: "bluetooth bağlantılı DIN ray analizör"
Çıktı: {"filtreler": {"Boyut": "DIN"}, "degerlendirilemeyen": ["bluetooth"]}

Giriş: "IP65 korumalı wifi analizör"
Çıktı: {"filtreler": {}, "degerlendirilemeyen": ["IP65", "wifi"]}

Giriş: "3 fazlı Ethernet SCADA Class 0.5"
Çıktı: {"filtreler": {"Ethernet": "Var", "Sınıf 0,5": "Var"}, "degerlendirilemeyen": []}
"""


def gemini_parse(metin: str) -> tuple[dict, list[str]]:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Kullanıcı isteği: {metin}",
        config=types.GenerateContentConfig(
            system_instruction=_SISTEM_TALIMAT,
            response_mime_type="application/json",
        ),
    )
    data = json.loads(response.text)
    return data.get("filtreler", {}), data.get("degerlendirilemeyen", [])


def calistir(metin: str) -> None:
    print(f"Giriş : {metin}\n")

    kriterler, degerlendirilemeyen = gemini_parse(metin)

    for madde in degerlendirilemeyen:
        print(f"[UYARI] Şu isteği tabloda değerlendiremedim: '{madde}'")
    if degerlendirilemeyen:
        print()

    if not kriterler:
        print("Hiçbir filtre kriteri tanımlanamadı. Lütfen daha açık belirtin.")
        return

    print(f"Uygulanan filtreler: {kriterler}\n")
    print("-" * 50)

    sonuc, atlanan = filtrele(kriterler)
    if atlanan:
        print(f"[UYARI] Şu kriterler bu kategoride yok, uygulanmadı: {atlanan}")

    if sonuc.empty:
        for kolon, deger in kriterler.items():
            ara, _ = filtrele({kolon: deger})
            if ara.empty:
                print(f"[UYARI] Şu kriteri karşılayan model yok: '{kolon} = {deger}'")
            else:
                modeller = ", ".join(ara["Model"].tolist())
                print(f"[BİLGİ] '{kolon} = {deger}' → {len(ara)} model var ({modeller})")
        print("\nBu kriterlerin kombinasyonunu karşılayan model yok.")
        print("ENTES uygulama mühendisine danışın.")
    else:
        print(sonuc.to_string(index=False))
        print(f"\nToplam {len(sonuc)} ürün eşleşti.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        metin = " ".join(sys.argv[1:])
    else:
        metin = input("İhtiyacınızı tarif edin: ")

    calistir(metin)
