"""
eval_senaryolari.json'a yeni kategorilerden senaryo ekler.
Aynı 'girdi' zaten varsa atlar (idempotent). Mevcut senaryolara dokunmaz.
Çalıştır: python3 ekle_senaryolar.py
"""
import json
from pathlib import Path

DOSYA = Path(__file__).parent / "eval_senaryolari.json"

YENI = [
    {
        "girdi": "96x96 kontak çıkışlı voltmetre istiyorum",
        "beklenen_tip": "model_oner",
        "beklenen_modeller": ["EVM-3C-96"],
    },
    {
        "girdi": "LCD ekranlı 3 fazlı gerilim koruma rölesi arıyorum",
        "beklenen_tip": "model_oner",
        "beklenen_modeller": ["GKRC-31E LCD", "GKRC-21E LCD", "GKRC-32E LCD", "GKRC-22E LCD"],
    },
    {
        "girdi": "otomatik resetli toprak kaçak akım rölesi istiyorum",
        "beklenen_tip": "model_oner",
        "beklenen_modeller": ["ELR-30-A"],
    },
    {
        "girdi": "manuel resetli toprak kaçak akım rölesi istiyorum",
        "beklenen_tip": "model_oner",
        "beklenen_modeller": ["ELR-30-M"],
    },
    {
        "girdi": "LCD ekranlı tek fazlı gerilim koruma rölesi istiyorum",
        "beklenen_tip": "kombinasyon_yok",
    },
]

with open(DOSYA, encoding="utf-8") as f:
    mevcut = json.load(f)

var_olan_girdiler = {s["girdi"] for s in mevcut}
eklenen = 0
for s in YENI:
    if s["girdi"] in var_olan_girdiler:
        print(f"ATLA (zaten var): {s['girdi']!r}")
        continue
    mevcut.append(s)
    eklenen += 1
    print(f"EKLENDI: {s['girdi']!r}")

with open(DOSYA, "w", encoding="utf-8") as f:
    json.dump(mevcut, f, ensure_ascii=False, indent=2)

print(f"\nToplam {eklenen} yeni senaryo eklendi. Dosyada artık {len(mevcut)} senaryo var.")
