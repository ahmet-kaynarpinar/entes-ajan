"""
20 kategoriden gerçek veriye dayalı LLM senaryosunu eval_senaryolari.json'a ekler.
Aynı girdi varsa atlar. Çalıştır: python3 ekle_llm_senaryolari.py
"""
import json
from pathlib import Path

DOSYA = Path(__file__).parent / "eval_senaryolari.json"
YENI_DOSYA = Path(__file__).parent / "yeni_llm_senaryolari.json"

YENI = json.load(open(YENI_DOSYA, encoding="utf-8"))

with open(DOSYA, encoding="utf-8") as f:
    mevcut = json.load(f)

var = {s["girdi"] for s in mevcut}
n = 0
for s in YENI:
    if s["girdi"] in var:
        print(f"ATLA (zaten var): {s['girdi'][:55]}...")
        continue
    mevcut.append(s)
    n += 1
    print(f"EKLENDI: {s['girdi'][:55]}...")

with open(DOSYA, "w", encoding="utf-8") as f:
    json.dump(mevcut, f, ensure_ascii=False, indent=2)

print(f"\n{n} yeni senaryo eklendi. Toplam {len(mevcut)} senaryo.")
