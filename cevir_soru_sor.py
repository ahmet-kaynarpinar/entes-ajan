"""
Belirsiz analizör/cihaz senaryolarını 'soru_sor' tipine çevirir.
Artık 41 kategori olduğu için "analizör" tek başına belirsiz; ajan doğru
şekilde soru soruyor. Bu senaryolar da onu ölçsün.
Çalıştır: python3 cevir_soru_sor.py
"""
import json
from pathlib import Path

DOSYA = Path(__file__).parent / "eval_senaryolari.json"

# soru_sor'a çevrilecek girdiler (kategorisi belirsiz olanlar)
CEVRILECEK = {
    "Ethernet ve Class 0.5 olan 96x96 analizör",
    "Sadece Ethernet olan analizör",
    "Sag&Swell ve Class 0.5 olan analizör",
    "Çift enerji sayacı olan cihaz",
    "72x72 boyutunda analizör",
}

with open(DOSYA, encoding="utf-8") as f:
    senaryolar = json.load(f)

cevrilen = 0
for s in senaryolar:
    if s["girdi"] in CEVRILECEK:
        if s["beklenen_tip"] != "soru_sor":
            print(f"CEVRILDI: {s['girdi']!r}  ({s['beklenen_tip']} -> soru_sor)")
            s["beklenen_tip"] = "soru_sor"
            s["beklenen_modeller"] = []
            cevrilen += 1
        else:
            print(f"ATLA (zaten soru_sor): {s['girdi']!r}")

with open(DOSYA, "w", encoding="utf-8") as f:
    json.dump(senaryolar, f, ensure_ascii=False, indent=2)

print(f"\n{cevrilen} senaryo soru_sor'a çevrildi. Toplam {len(senaryolar)} senaryo.")
