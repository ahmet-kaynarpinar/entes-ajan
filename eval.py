"""
ENTES Ürün Seçim Ajanı - Otomatik Değerlendirme
agent.py'deki ajan mantığını kullanarak eval_senaryolari.json içindeki
senaryoları tek tek çalıştırır ve beklenen davranışla karşılaştırır.
"""

import ast
import contextlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI

import agent

BASE = Path(__file__).parent
BEKLEME_SANIYE = 5  # OpenRouter rate-limit için turlar arası bekleme

DEBUG_SATIR_RE = re.compile(
    r"\[DEBUG\] Filtre çağrıldı: (.+?) -> (\d+) model: (\[.*?\])(?: \(atlanan filtreler: \[.*\]\))?$"
)


def gercek_modelleri_yukle() -> set[str]:
    modeller: set[str] = set()
    for df in agent.load_kategori_dataframeleri().values():
        modeller |= set(df["Model"].dropna().tolist())
    return modeller


def debug_ciktisini_ayristir(debug_metni: str) -> list[dict]:
    """call_urun_filtrele'nin bastığı [DEBUG] satırlarını ayrıştırıp
    her filtre çağrısı için {"kriterler": str, "modeller": list[str]} döndürür."""
    sonuclar = []
    for satir in debug_metni.splitlines():
        eslesme = DEBUG_SATIR_RE.search(satir.strip())
        if not eslesme:
            continue
        kriterler_str, _adet, model_listesi_str = eslesme.groups()
        try:
            modeller = ast.literal_eval(model_listesi_str)
        except (SyntaxError, ValueError):
            modeller = []
        sonuclar.append({"kriterler": kriterler_str, "modeller": modeller})
    return sonuclar


def cevapta_gercek_model_var_mi(cevap: str, gercek_modeller: set[str]) -> bool:
    """urunler.csv'deki gerçek model adlarından biri cevap metninde
    (substring olarak) geçiyor mu kontrol eder."""
    return any(model in cevap for model in gercek_modeller)


def bir_senaryo_calistir(
    client: OpenAI,
    sistem_talimati: str,
    tools: list[dict],
    girdi: str,
    kategori_df: dict[str, pd.DataFrame],
) -> dict:
    """Tek bir kullanıcı turunu, agent.py'deki main() ile aynı tool-calling
    döngüsüyle çalıştırır. DEBUG çıktısını yakalar, son cevabı döndürür."""
    messages: list[dict] = [
        {"role": "system", "content": sistem_talimati},
        {"role": "user", "content": girdi},
    ]

    debug_buffer = io.StringIO()

    response = agent.openrouter_cagir(client, messages, tools)
    if response is None:
        return {"cevap": "", "filtre_cagrilari": [], "hata": "OpenRouter çağrısı başarısız (rate limit)."}

    MAX_FILTRELE_CAGRI = 2
    filtrele_cagri_sayisi = 0

    with contextlib.redirect_stdout(debug_buffer):
        while True:
            msg = response.choices[0].message
            messages.append(msg)

            if not msg.tool_calls:
                break

            for tc in msg.tool_calls:
                fn_name = tc.function.name
                if fn_name == "urun_filtrele":
                    filtrele_cagri_sayisi += 1
                    if filtrele_cagri_sayisi > MAX_FILTRELE_CAGRI:
                        sonuc = (
                            "Uyarı: Bu turda zaten yeterli sayıda arama yapıldı. "
                            "Daha fazla urun_filtrele çağırma; mevcut sonuçları "
                            "kullanıcıya sun ya da netleştirici soru sor."
                        )
                    else:
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}
                        sonuc = agent.call_urun_filtrele(
                            args.get("kriterler", {}),
                            args.get("kategori", ""),
                            kategori_df,
                        )
                else:
                    sonuc = f"Bilinmeyen araç: {fn_name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": sonuc,
                })

            response = agent.openrouter_cagir(client, messages, tools)
            if response is None:
                break

    if response is None:
        return {
            "cevap": "",
            "filtre_cagrilari": debug_ciktisini_ayristir(debug_buffer.getvalue()),
            "hata": "OpenRouter çağrısı başarısız (rate limit).",
        }

    son_msg = response.choices[0].message
    return {
        "cevap": son_msg.content or "",
        "filtre_cagrilari": debug_ciktisini_ayristir(debug_buffer.getvalue()),
        "hata": None,
    }


def degerlendir(senaryo: dict, sonuc: dict, gercek_modeller: set[str]) -> tuple[bool, str]:
    tip = senaryo["beklenen_tip"]

    if sonuc["hata"]:
        return False, sonuc["hata"]

    if tip == "model_oner":
        beklenen = set(senaryo.get("beklenen_modeller", []))
        if not sonuc["filtre_cagrilari"]:
            return False, "urun_filtrele hiç çağrılmadı, model önerilemedi."
        dönen = set(sonuc["filtre_cagrilari"][-1]["modeller"])
        if dönen == beklenen:
            return True, f"Beklenen modeller döndü: {sorted(dönen)}"
        return False, f"Beklenen {sorted(beklenen)}, dönen {sorted(dönen)}"

    if tip == "kombinasyon_yok":
        # Asıl kriter: cevapta gerçek bir model adı geçiyor mu.
        # Geçiyorsa ajan model önermiş demektir -> KALDI.
        if cevapta_gercek_model_var_mi(sonuc["cevap"], gercek_modeller):
            return False, "Ajan cevabında gerçek bir model adı geçiyor (model önerdi)."

        tum_modeller = [m for c in sonuc["filtre_cagrilari"] for m in c["modeller"]]
        if tum_modeller:
            return False, f"Hiçbir model önerilmemesi gerekirken filtre model döndürdü: {tum_modeller}"

        return True, "Cevapta gerçek model adı geçmiyor, filtre 0 model döndürdü (ya da hiç çağrılmadı)."

    if tip in ("degerlendiremedim", "uretmiyor", "kategori_yonlendir", "soru_sor"):
        if sonuc["filtre_cagrilari"]:
            return False, "urun_filtrele çağrılmamalıydı ama çağrıldı."
        return True, "urun_filtrele çağrılmadı (beklenen davranış)."

    return False, f"Bilinmeyen beklenen_tip: {tip}"


def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Hata: OPENROUTER_API_KEY ortam değişkeni tanımlı değil.")
        sys.exit(1)

    with open(BASE / "eval_senaryolari.json", encoding="utf-8") as f:
        senaryolar = json.load(f)

    kategoriler = agent.load_kategoriler()
    kategori_df = agent.load_kategori_dataframeleri()
    verisi_olan = sorted(kategori_df.keys())
    sistem_talimati = agent.build_sistem_talimati(kategoriler, verisi_olan)
    tools = agent.build_tools(kategori_df)
    gercek_modeller = gercek_modelleri_yukle()

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    sonuclar = []
    for i, senaryo in enumerate(senaryolar, start=1):
        print(f"[{i}/{len(senaryolar)}] Senaryo çalıştırılıyor: {senaryo['girdi']!r} "
              f"(beklenen: {senaryo['beklenen_tip']})")

        sonuc = bir_senaryo_calistir(client, sistem_talimati, tools, senaryo["girdi"], kategori_df)
        gecti, aciklama = degerlendir(senaryo, sonuc, gercek_modeller)
        sonuclar.append((senaryo, gecti, aciklama))

        durum = "GEÇTİ" if gecti else "KALDI"
        print(f"    -> {durum}: {aciklama}\n")

        if i < len(senaryolar):
            time.sleep(BEKLEME_SANIYE)

    print("=" * 60)
    print("SONUÇLAR")
    print("=" * 60)
    for senaryo, gecti, aciklama in sonuclar:
        durum = "GEÇTİ" if gecti else "KALDI"
        print(f"[{durum}] {senaryo['girdi']!r} (beklenen: {senaryo['beklenen_tip']}) - {aciklama}")

    dogru_sayisi = sum(1 for _, gecti, _ in sonuclar if gecti)
    print(f"\n{dogru_sayisi}/{len(sonuclar)} doğru")


if __name__ == "__main__":
    main()
