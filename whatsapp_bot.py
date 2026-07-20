"""
ENTES Ürün Seçim Ajanı - WhatsApp Entegrasyonu (Twilio Webhook).
Twilio'dan gelen WhatsApp mesajını agent.py'nin mantığıyla işler,
cevabı WhatsApp'a döndürür. Grounding korunur.

Çalıştır: python3 whatsapp_bot.py
Gereksinimler: pip3 install flask twilio --break-system-packages
"""

import contextlib
import io
import json
import os
import sys

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

import agent
import sss

app = Flask(__name__)

# ── Kaynakları bir kez yükle ───────────────────────────────────────────────
print("Kaynaklar yükleniyor...")
api_key = os.environ.get("OPENROUTER_API_KEY")
if not api_key:
    print("HATA: OPENROUTER_API_KEY ortam değişkeni tanımlı değil.")
    sys.exit(1)

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
kategoriler = agent.load_kategoriler()
kategori_df = agent.load_kategori_dataframeleri()
verisi_olan = sorted(kategori_df.keys())
sistem_talimati = agent.build_sistem_talimati(kategoriler, verisi_olan)
tools = agent.build_tools(kategori_df)
sss_df = sss.load_sss()
print(f"Hazır: {len(kategori_df)} kategori, {len(sss_df)} SSS makalesi.")

# ── Kullanıcı bazlı konuşma geçmişi (basit, bellekte) ─────────────────────
konusmalar: dict[str, list[dict]] = {}

MAX_GECMIS = 20  # son N mesaj tutulur (token tasarrufu)


def gecmis_al(telefon: str) -> list[dict]:
    if telefon not in konusmalar:
        konusmalar[telefon] = [{"role": "system", "content": sistem_talimati}]
    return konusmalar[telefon]


# ── Bir mesajı agent.py'nin tool-calling döngüsüyle işle ──────────────────
def mesaj_isle(telefon: str, mesaj: str) -> str:
    gecmis = gecmis_al(telefon)
    gecmis.append({"role": "user", "content": mesaj})

    # Geçmişi kırp (sistem talimatı + son MAX_GECMIS mesaj)
    if len(gecmis) > MAX_GECMIS + 1:
        gecmis[:] = [gecmis[0]] + gecmis[-(MAX_GECMIS):]

    try:
        response = agent.openrouter_cagir(client, gecmis, tools)
        if response is None:
            return "Şu anda bir bağlantı sorunu yaşanıyor, lütfen tekrar deneyin."

        MAX_TOOL_CAGRI = 3
        tool_sayisi = 0

        while True:
            msg = response.choices[0].message
            gecmis.append(msg)

            if not msg.tool_calls:
                break

            for tc in msg.tool_calls:
                fn_name = tc.function.name
                tool_sayisi += 1

                if tool_sayisi > MAX_TOOL_CAGRI:
                    sonuc = "Uyarı: Bu turda yeterli arama yapıldı. Mevcut sonuçları kullanıcıya sun."
                else:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    if fn_name == "urun_filtrele":
                        call_buf = io.StringIO()
                        with contextlib.redirect_stdout(call_buf):
                            sonuc = agent.call_urun_filtrele(
                                args.get("kriterler", {}),
                                args.get("kategori", ""),
                                kategori_df,
                            )
                    elif fn_name == "sss_ara":
                        sonuc = sss.sss_ara(
                            urun=args.get("urun", ""),
                            anahtar_kelime=args.get("anahtar_kelime", ""),
                            df=sss_df,
                        )
                    elif fn_name == "referans_ara":
                        sonuc = sss.referans_ara(
                            sektor_veya_konu=args.get("sektor_veya_konu", ""),
                            df=sss_df,
                        )
                    elif fn_name == "lead_kaydet":
                        sonuc = agent.call_lead_kaydet(
                            isim=args.get("isim", ""),
                            firma=args.get("firma", ""),
                            email=args.get("email", ""),
                            telefon=args.get("telefon", ""),
                            tercih_iletisim=args.get("tercih_iletisim", ""),
                            ilgilenilen_urun=args.get("ilgilenilen_urun", ""),
                            not_=args.get("not", ""),
                            whatsapp_no=telefon,
                        )
                    elif fn_name == "model_ara":
                        sonuc = agent.call_model_ara(args.get("model_adi", ""), kategori_df)
                    else:
                        sonuc = f"Bilinmeyen araç: {fn_name}"

                gecmis.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": sonuc,
                })

            response = agent.openrouter_cagir(client, gecmis, tools)
            if response is None:
                return "Bağlantı sorunu, lütfen tekrar deneyin."

        son_msg = response.choices[0].message
        cevap = son_msg.content or "Bir cevap üretilemedi."

        # thought/thinking temizliği (agent.py'deki gibi)
        import re
        cevap = re.sub(r'^<(thought|thinking|reasoning)>.*?</\1>\s*', '', cevap, flags=re.DOTALL | re.IGNORECASE)
        cevap = re.sub(r'^(thought|thinking|reasoning):?\s+', '', cevap, flags=re.IGNORECASE)
        cevap = cevap.strip()

        # WhatsApp mesaj limiti (~1600 karakter güvenli)
        if len(cevap) > 1500:
            cevap = cevap[:1500] + "\n\n(Devamı için lütfen tekrar sorun.)"

        gecmis.append({"role": "assistant", "content": cevap})
        return cevap

    except Exception as e:
        print(f"HATA: {e}")
        return "Bir hata oluştu, lütfen tekrar deneyin."


# ── Twilio Webhook ─────────────────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    gelen_mesaj = request.values.get("Body", "").strip()
    gonderen = request.values.get("From", "")

    print(f"[WhatsApp] {gonderen}: {gelen_mesaj}")

    if not gelen_mesaj:
        cevap = "Lütfen bir mesaj yazın."
    else:
        cevap = mesaj_isle(gonderen, gelen_mesaj)

    print(f"[Cevap] {cevap[:100]}...")

    resp = MessagingResponse()
    resp.message(cevap)
    return str(resp)


# ── Sağlık kontrolü ───────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def saglik():
    return "ENTES WhatsApp Ajanı çalışıyor."


if __name__ == "__main__":
    print("WhatsApp webhook başlatılıyor (port 5000)...")
    app.run(host="0.0.0.0", port=5000, debug=False)
