"""
ENTES Ürün Seçim Ajanı - Streamlit sohbet arayüzü (ENTES sarısı tema).
agent.py'deki OpenRouter tool-calling ajan mantığını (grounding, sistem
talimatı, urun_filtrele) OLDUĞU GİBİ kullanır; yeniden yazmaz.
Çalıştır: python3 -m streamlit run arayuz_agent.py
"""

import ast
import contextlib
import io
import json
import os
import re

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

import agent
import sss

# ----------------------------------------------------------------------------
# Sayfa ayarı + ENTES teması
# ----------------------------------------------------------------------------
st.set_page_config(page_title="ENTES Ürün Seçim Ajanı", page_icon="⚡", layout="wide")

ENTES_SARI = "#FDC300"
ENTES_KOYU = "#333333"

COMMON_CSS = f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap');
html, body {{
font-family: 'Montserrat', sans-serif !important;
}}
.entes-utility *, .entes-header *, .entes-hero *, .homepage-container *, [data-testid="stChatMessage"] *, [data-testid="stMarkdownContainer"] * {{
font-family: 'Montserrat', sans-serif !important;
}}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
background-color: #FFFFFF !important;
color: #222222 !important;
}}
/* Sayfa üst boşluklarını sıfırlama */
[data-testid="stAppViewBlockContainer"] {{
padding-top: 0.5rem !important;
padding-bottom: 0.5rem !important;
}}
[data-testid="stMainBlockContainer"] {{
padding-top: 0.5rem !important;
max-width: 1200px !important;
margin: 0 auto !important;
padding-left: 20px !important;
padding-right: 20px !important;
}}
.entes-utility {{
background-color: #FFFFFF;
border-bottom: 1px solid #EAEAEA;
padding: 8px 20px;
display: flex;
justify-content: space-between;
align-items: center;
font-size: 11px;
color: #666666;
margin-bottom: 0px;
}}
.entes-utility-left {{
display: flex;
gap: 20px;
}}
.entes-utility-right {{
display: flex;
gap: 15px;
}}
.entes-utility-right a {{
color: #666666;
text-decoration: none;
transition: color 0.2s ease;
}}
.entes-utility-right a:hover {{
color: {ENTES_SARI};
}}
/* Ekmek Kırıntıları Satırı (Sarı Tablo Üstü) */
.entes-breadcrumbs-row {{
max-width: 1200px;
margin: 8px auto 4px auto;
padding: 0 20px;
font-size: 11px;
color: #777777 !important;
font-weight: 600;
}}
/* ENTES Sarı Ana Header */
.entes-header {{
background-color: {ENTES_SARI};
padding: 15px 30px;
display: flex;
justify-content: space-between;
align-items: center;
border-radius: 8px;
margin-top: 4px;
margin-bottom: 0px;
box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
}}
.entes-logo-box {{
display: flex;
align-items: center;
}}
.entes-logo-text {{
font-family: 'Montserrat', sans-serif !important;
font-weight: 900;
font-style: italic;
font-size: 30px;
color: #FFFFFF;
letter-spacing: -1.5px;
margin: 0;
line-height: 1;
}}
.entes-nav {{
display: flex;
gap: 20px;
}}
.entes-nav a {{
color: #333333 !important;
font-weight: 700;
font-size: 12px;
text-decoration: none;
text-transform: uppercase;
letter-spacing: 0.5px;
transition: opacity 0.2s ease;
}}
.entes-nav a:hover {{
opacity: 0.7;
}}
.entes-header-btn {{
background-color: #FFFFFF;
color: #333333 !important;
padding: 8px 20px;
border-radius: 20px;
font-weight: 700;
font-size: 12px;
text-decoration: none;
box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
transition: all 0.2s ease;
}}
.entes-header-btn:hover {{
background-color: #333333;
color: #FFFFFF !important;
}}
/* Nötr Hero Banner */
.entes-hero {{
background: linear-gradient(135deg, #F5F6F8 0%, #FFFDF0 100%);
background-image: radial-gradient(rgba(0,0,0,0.035) 1px, transparent 0), radial-gradient(rgba(0,0,0,0.035) 1px, transparent 0);
background-size: 20px 20px;
background-position: 0 0, 10px 10px;
padding: 25px 30px;
border-bottom: 4px solid {ENTES_SARI};
color: #222222;
margin-top: 12px;
margin-bottom: 12px;
border-radius: 8px;
}}
.entes-hero h2 {{
color: #222222 !important;
font-size: 24px !important;
font-weight: 800 !important;
margin: 0 !important;
}}
/* Sohbet Baloncukları */
[data-testid="stChatMessage"] {{
border-radius: 12px !important;
padding: 12px 14px !important;
margin-bottom: 12px !important;
max-width: 100% !important;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
background-color: #F0F0F0 !important;
color: #222222 !important;
border: 1px solid #E2E2E2 !important;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {{
background-color: #FFFFFF !important;
color: #222222 !important;
border: 1px solid #EAEAEA !important;
box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03) !important;
}}
[data-testid="stChatMessage"], [data-testid="stChatMessageContent"] {{
background-color: transparent !important;
color: #222222 !important;
}}
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] p,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] li,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] span,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h1,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h3,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h4,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h5,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] h6,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] strong,
[data-testid="stChatMessageContent"] [data-testid="stMarkdownContainer"] em {{
color: #222222 !important;
opacity: 1 !important;
font-size: 14px !important;
line-height: 1.5 !important;
}}
.streamlit-expanderHeader {{
background-color: #F8F9FA !important;
border: 1px solid #EAEAEA !important;
border-radius: 8px !important;
color: #333333 !important;
font-weight: 600 !important;
font-size: 12px !important;
}}
.streamlit-expanderContent {{
background-color: #FFFFFF !important;
border: 1px solid #EAEAEA !important;
border-top: none !important;
border-radius: 0 0 8px 8px !important;
}}
.kaynak-rozet {{
background-color: {ENTES_SARI};
color: {ENTES_KOYU};
padding: 3px 10px;
border-radius: 12px;
font-size: 10px;
font-weight: 700;
text-transform: uppercase;
letter-spacing: 0.5px;
display: inline-block;
margin-top: 8px;
}}
[data-testid="stChatInput"] {{
border: 1px solid #D0D0D0 !important;
border-radius: 10px !important;
background-color: #FFFFFF !important;
box-shadow: 0 2px 10px rgba(0,0,0,0.05);
max-width: 100% !important;
}}
.homepage-container {{
margin-top: 15px;
margin-bottom: 50px;
}}
.entes-slider {{
background: linear-gradient(135deg, #FDFDFD 0%, #F5F5F5 100%);
border-radius: 12px;
padding: 40px;
display: flex;
position: relative;
overflow: hidden;
min-height: 320px;
border: 1px solid #EAEAEA;
box-shadow: 0 4px 15px rgba(0,0,0,0.02);
}}
.slider-left {{
flex: 1.3;
display: flex;
flex-direction: column;
justify-content: center;
z-index: 2;
padding-right: 20px;
}}
.shield-badge {{
font-size: 40px;
margin-bottom: 15px;
}}
.slider-left h2 {{
color: #333333 !important;
font-size: 26px !important;
font-weight: 800 !important;
line-height: 1.3 !important;
margin-bottom: 25px !important;
}}
.detayli-bilgi-btn {{
background-color: {ENTES_SARI};
color: {ENTES_KOYU} !important;
padding: 12px 28px;
border-radius: 4px;
font-weight: 800;
font-size: 13px;
text-decoration: none;
align-self: flex-start;
box-shadow: 0 4px 12px rgba(253, 195, 0, 0.25);
transition: all 0.2s ease;
}}
.detayli-bilgi-btn:hover {{
background-color: #E2AE00;
transform: translateY(-1px);
}}
.slider-right {{
flex: 0.7;
display: flex;
align-items: center;
justify-content: center;
z-index: 1;
}}
.tech-graphic {{
background: rgba(51, 51, 51, 0.95);
border-radius: 8px;
padding: 20px;
width: 100%;
box-shadow: 0 10px 30px rgba(0,0,0,0.15);
}}
.slider-bottom-bar {{
position: absolute;
bottom: 0;
left: 0;
right: 0;
background-color: {ENTES_SARI};
padding: 10px 30px;
font-weight: 700;
font-size: 14px;
color: {ENTES_KOYU};
text-align: center;
}}
.section-title {{
text-align: center;
margin: 50px 0 30px 0;
}}
.section-title h3 {{
color: #444444 !important;
font-size: 20px !important;
font-weight: 800 !important;
letter-spacing: 1.5px;
}}
.services-row {{
display: flex;
gap: 24px;
margin-bottom: 50px;
}}
.service-card {{
flex: 1;
background-color: #FFFFFF;
border: 1px solid #EAEAEA;
border-radius: 8px;
padding: 25px;
text-align: center;
box-shadow: 0 4px 12px rgba(0,0,0,0.02);
transition: all 0.3s ease;
}}
.service-card:hover {{
transform: translateY(-4px);
box-shadow: 0 8px 20px rgba(0,0,0,0.08);
}}
.service-icon {{
font-size: 32px;
margin-bottom: 12px;
}}
.service-card h4 {{
color: #333333 !important;
font-size: 14px !important;
font-weight: 700 !important;
margin: 0 !important;
}}
.product-showcase {{
display: flex;
gap: 35px;
margin-top: 40px;
border-top: 1px solid #EEEEEE;
padding-top: 40px;
}}
.showcase-sidebar {{
flex: 0.75;
}}
.showcase-sidebar h4 {{
font-size: 15px !important;
font-weight: 800 !important;
color: #333333 !important;
margin-bottom: 20px !important;
border-bottom: 2px solid #333333;
padding-bottom: 6px;
}}
.category-list {{
list-style: none;
padding: 0;
margin: 0;
}}
.category-list li {{
padding: 12px 18px;
font-size: 13px;
font-weight: 700;
color: #333333;
background-color: #F8F9FA;
margin-bottom: 10px;
border-radius: 4px;
cursor: pointer;
transition: all 0.2s ease;
}}
.category-list li.active, .category-list li:hover {{
background-color: {ENTES_SARI};
color: {ENTES_KOYU};
}}
.showcase-grid {{
flex: 2.25;
display: flex;
gap: 24px;
}}
.mock-product-card {{
flex: 1;
background-color: #FFFFFF;
border: 1px solid #EAEAEA;
border-radius: 8px;
display: flex;
flex-direction: column;
overflow: hidden;
box-shadow: 0 4px 12px rgba(0,0,0,0.02);
transition: all 0.3s ease;
}}
.mock-product-card:hover {{
transform: translateY(-4px);
box-shadow: 0 8px 20px rgba(0,0,0,0.08);
}}
.product-img {{
flex: 1;
display: flex;
align-items: center;
justify-content: center;
padding: 30px 15px;
background-color: #FAFAFA;
}}
.product-title-bar {{
background-color: {ENTES_SARI};
color: {ENTES_KOYU};
padding: 12px;
font-size: 13px;
font-weight: 700;
text-align: center;
min-height: 50px;
display: flex;
align-items: center;
justify-content: center;
}}
/* Karşılama Kutusu ve Soru Sütunları Tasarımı (Net Koyu Renkler) */
.chat-welcome-box {{
background-color: #FDFDFD;
border: 1px solid #EAEAEA;
border-radius: 12px;
padding: 30px;
text-align: center;
margin: 20px auto;
max-width: 600px;
box-shadow: 0 4px 15px rgba(0,0,0,0.02);
}}
.chat-welcome-box h4 {{
color: #333333 !important;
font-size: 18px !important;
font-weight: 800 !important;
margin: 10px 0 8px 0 !important;
}}
.chat-welcome-box p {{
color: #666666 !important;
font-size: 13px !important;
margin: 0 !important;
line-height: 1.5 !important;
}}
.chat-welcome-icon {{
font-size: 36px;
display: inline-block;
padding: 8px;
background-color: #FFFDF0;
border-radius: 50%;
border: 1px solid #FEEFAD;
}}
/* Asistan Sayfası Scroll ve Sütun Yapıları */
.chat-scroll-container {{
height: calc(100vh - 350px) !important;
max-height: calc(100vh - 350px) !important;
overflow-y: auto !important;
padding-right: 15px !important;
padding-left: 5px !important;
}}
@media (max-width: 768px) {{
  [data-testid="stAppViewBlockContainer"], [data-testid="stMainBlockContainer"] {{
    max-width: 100% !important;
    padding-left: 10px !important;
    padding-right: 10px !important;
  }}
  [data-testid="stHorizontalBlock"] {{
    flex-direction: column !important;
  }}
  [data-testid="column"] {{
    width: 100% !important;
    min-width: 100% !important;
    flex: 1 1 100% !important;
  }}
  .entes-utility, .entes-header {{
    flex-wrap: wrap !important;
    padding: 10px !important;
    font-size: 10px !important;
  }}
  .entes-logo-text {{ font-size: 18px !important; }}
  .shield-badge {{ font-size: 22px !important; }}
  .slider-left h2 {{ font-size: 16px !important; }}
  .service-icon {{ font-size: 18px !important; }}
  .chat-welcome-icon {{ font-size: 20px !important; }}
  #entes-voice-select, #entes-rate-slider {{
    width: 100% !important;
    max-width: 100% !important;
  }}
  [data-testid="stPopoverBody"] div.stButton > button {{
    width: 100% !important;
    min-width: 100% !important;
    height: auto !important;
  }}
  [data-testid="stPopoverBody"] {{
    max-width: 92vw !important;
  }}
}}
"""

NAZIK_HATA_MESAJI = (
    "Şu anda isteğinizi işlerken bir sorun oluştu (kota limiti ya da bağlantı "
    "olabilir). Lütfen birkaç saniye sonra tekrar deneyin."
)


# ----------------------------------------------------------------------------
# Kaynakları yükle (güncel agent.py imzalarına göre)
# ----------------------------------------------------------------------------
@st.cache_resource
def kaynaklari_yukle():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None, None, None, None, None

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    kategoriler = agent.load_kategoriler()
    kategori_df = agent.load_kategori_dataframeleri()
    verisi_olan = sorted(kategori_df.keys())
    sistem_talimati = agent.build_sistem_talimati(kategoriler, verisi_olan)
    tools = agent.build_tools(kategori_df)
    sss_df = sss.load_sss()
    return client, sistem_talimati, tools, kategori_df, sss_df


client, sistem_talimati, tools, kategori_df, sss_df = kaynaklari_yukle()

if client is None:
    st.error(
        "OPENROUTER_API_KEY ortam değişkeni tanımlı değil. Terminalde "
        "ayarlayıp uygulamayı yeniden başlatın."
    )
    st.stop()

if "api_mesajlari" not in st.session_state:
    st.session_state.api_mesajlari = [{"role": "system", "content": sistem_talimati}]
if "gorunen_mesajlar" not in st.session_state:
    st.session_state.gorunen_mesajlar = []

KARSILAMA_MESAJI = (
    "Merhaba! Ben ENTES ürün seçim ve destek asistanınızım. "
    "Size nasıl yardımcı olabilirim?"
)
if not st.session_state.gorunen_mesajlar:
    st.session_state.gorunen_mesajlar.append(
        {"rol": "assistant", "icerik": KARSILAMA_MESAJI}
    )


# ----------------------------------------------------------------------------
# Bir konuşma turunu işle (agent.py döngüsüyle)
# ----------------------------------------------------------------------------
def bir_tur_isle(kullanici_metni: str) -> tuple[str, list[dict]]:
    snapshot = list(st.session_state.api_mesajlari)
    st.session_state.api_mesajlari.append({"role": "user", "content": kullanici_metni})
    filtre_kayitlari: list[dict] = []

    try:
        response = agent.openrouter_cagir(client, st.session_state.api_mesajlari, tools)
        if response is None:
            st.session_state.api_mesajlari = snapshot
            return NAZIK_HATA_MESAJI, filtre_kayitlari

        while True:
            msg = response.choices[0].message
            st.session_state.api_mesajlari.append(msg)

            if not msg.tool_calls:
                break

            for tc in msg.tool_calls:
                if tc.function.name == "urun_filtrele":
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    kriterler = args.get("kriterler", {})
                    kategori = args.get("kategori", "")

                    call_buffer = io.StringIO()
                    with contextlib.redirect_stdout(call_buffer):
                        sonuc = agent.call_urun_filtrele(kriterler, kategori, kategori_df)

                    filtre_kayitlari.append(
                        _filtre_kaydi_olustur(kriterler, kategori, call_buffer.getvalue())
                    )
                elif tc.function.name == "sss_ara":
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    sonuc = sss.sss_ara(
                        args.get("urun"),
                        args.get("anahtar_kelime"),
                        df=sss_df,
                    )
                elif tc.function.name == "referans_ara":
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    sonuc = sss.referans_ara(
                        args.get("sektor_veya_konu", ""),
                        df=sss_df,
                    )
                elif tc.function.name == "model_ara":
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    sonuc = agent.call_model_ara(args.get("model_adi", ""), kategori_df)
                elif tc.function.name == "lead_kaydet":
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    sonuc = agent.call_lead_kaydet(
                        isim=args.get("isim", ""),
                        firma=args.get("firma", ""),
                        email=args.get("email", ""),
                        telefon=args.get("telefon", ""),
                        tercih_iletisim=args.get("tercih_iletisim", ""),
                        ilgilenilen_urun=args.get("ilgilenilen_urun", ""),
                        not_=args.get("not", ""),
                        whatsapp_no="Streamlit-web",
                    )
                else:
                    sonuc = f"Bilinmeyen araç: {tc.function.name}"

                st.session_state.api_mesajlari.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": sonuc,
                })

            response = agent.openrouter_cagir(client, st.session_state.api_mesajlari, tools)
            if response is None:
                st.session_state.api_mesajlari = snapshot
                return NAZIK_HATA_MESAJI, filtre_kayitlari

        son_msg = response.choices[0].message
        final_content = son_msg.content or "Bir cevap üretilemedi."
        final_content = agent.clean_content(final_content)
        return final_content, filtre_kayitlari

    except Exception as e:
        import traceback
        print(f"HATA (bir_tur_isle): {e}")
        traceback.print_exc()
        st.session_state.api_mesajlari = snapshot
        return NAZIK_HATA_MESAJI, filtre_kayitlari


def _filtre_kaydi_olustur(kriterler, kategori: str, debug_metni: str) -> dict:
    """agent.call_urun_filtrele'nin [DEBUG] çıktısından model listesini çıkarır."""
    kayit = {"kriterler": dict(kriterler) if isinstance(kriterler, dict) else kriterler}
    if kategori:
        kayit["kategori"] = kategori
    model_eslesme = re.search(r"-> \d+ model: (\[.*?\])", debug_metni)
    if model_eslesme:
        try:
            kayit["modeller"] = ast.literal_eval(model_eslesme.group(1))
        except (ValueError, SyntaxError):
            kayit["modeller"] = []
    else:
        kayit["modeller"] = []
    return kayit


def filtre_ozeti_olustur(filtre_kayitlari: list[dict]) -> str:
    if not filtre_kayitlari:
        return "Bu adımda tablo sorgusu yapılmadı."
    parcalar = []
    for kayit in filtre_kayitlari:
        krit = dict(kayit["kriterler"]) if isinstance(kayit["kriterler"], dict) else kayit["kriterler"]
        if kayit.get("kategori") and isinstance(krit, dict):
            krit = {**krit, "Kategori": kayit["kategori"]}
        modeller = kayit.get("modeller", [])
        sonuc_str = f"Eşleşen modeller: {', '.join(modeller)}" if modeller else "Eşleşen ürün yok"
        parcalar.append(f"Uygulanan filtre: {krit}\n{sonuc_str}\nKaynak: veri/ CSV tabloları")
    return "\n\n".join(parcalar)


def asistan_mesaji_goster(mesaj: dict) -> None:
    st.markdown(mesaj["icerik"])


# ----------------------------------------------------------------------------
# Sesli etkileşim (Web Speech API — sadece tarayıcı, ek servis/API anahtarı yok)
# ----------------------------------------------------------------------------
def _ses_icin_metin_temizle(md_metni: str) -> str:
    """Sesli okuma için markdown işaretlerini basitçe temizler."""
    metin = re.sub(r"`{1,3}", "", md_metni)
    metin = re.sub(r"\*\*|__|\*|_", "", metin)
    metin = re.sub(r"^\s{0,3}#{1,6}\s*", "", metin, flags=re.MULTILINE)
    metin = re.sub(r"^\s*[-•]\s+", "", metin, flags=re.MULTILINE)
    metin = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", metin)
    return metin.strip()


_SES_PANELI_HTML_SABLONU = """
<div id="entes-ses-panel" style="font-family:'Montserrat',sans-serif; display:flex; flex-wrap:wrap;
     align-items:center; gap:10px; padding:6px 4px;">
  <button id="entes-mic-btn" type="button" style="background:#FDC300;color:#333333;border:none;
    border-radius:20px;padding:8px 16px;font-weight:700;font-size:12px;cursor:pointer;white-space:nowrap;">
    🎤 Konuş
  </button>
  <label style="font-size:11px;color:#666666;display:flex;align-items:center;gap:4px;cursor:pointer;">
    <input type="checkbox" id="entes-auto-read"> Cevapları otomatik oku
  </label>
  <button id="entes-stop-btn" type="button" style="background:#F0F0F0;color:#333333;
    border:1px solid #D0D0D0;border-radius:20px;padding:6px 14px;font-weight:700;font-size:11px;
    cursor:pointer;white-space:nowrap;">
    ⏹ Sesi durdur
  </button>
  <select id="entes-voice-select" style="font-size:11px;padding:5px 8px;border-radius:6px;
    border:1px solid #D0D0D0;max-width:220px;"></select>
  <label style="font-size:11px;color:#666666;display:flex;align-items:center;gap:6px;">
    Hız
    <input type="range" id="entes-rate-slider" min="0.5" max="1.5" step="0.1" value="1.0" style="width:80px;">
    <span id="entes-rate-val">1.0</span>
  </label>
  <span id="entes-ses-durum" style="font-size:11px;color:#999999;"></span>
</div>
<script>
(function () {
  var durum = document.getElementById('entes-ses-durum');
  var LAST_KEY = 'entes_last_spoken_text';
  var VOICE_KEY = 'entes_selected_voice';
  var RATE_KEY = 'entes_speech_rate';
  var AUTO_KEY = 'entes_auto_read';

  // ---------------- KONUŞMA -> YAZI ----------------
  var micBtn = document.getElementById('entes-mic-btn');
  var TanimaSinifi = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!TanimaSinifi) {
    micBtn.style.display = 'none';
  } else {
    var dinliyor = false;
    micBtn.addEventListener('click', function () {
      if (dinliyor) return;
      try {
        var tanima = new TanimaSinifi();
        tanima.lang = 'tr-TR';
        tanima.interimResults = false;
        tanima.maxAlternatives = 1;
        dinliyor = true;
        micBtn.textContent = '🔴 Dinleniyor...';
        tanima.onresult = function (event) {
          var metin = event.results[0][0].transcript;
          mesajGonder(metin);
        };
        tanima.onerror = function () {
          durum.textContent = 'Ses tanıma hatası.';
        };
        tanima.onend = function () {
          dinliyor = false;
          micBtn.textContent = '🎤 Konuş';
        };
        tanima.start();
      } catch (e) {
        durum.textContent = 'Ses tanıma bu tarayıcıda desteklenmiyor.';
        dinliyor = false;
        micBtn.textContent = '🎤 Konuş';
      }
    });
  }

  function nativeDegerAta(eleman, deger) {
    var proto = window.parent.HTMLTextAreaElement.prototype;
    var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(eleman, deger);
    eleman.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function mesajGonder(metin, deneme) {
    deneme = deneme || 0;
    try {
      var pdoc = window.parent.document;
      var textarea = pdoc.querySelector('[data-testid="stChatInputTextArea"]');
      if (!textarea) {
        durum.textContent = 'Sohbet kutusu bulunamadı.';
        return;
      }
      textarea.focus();
      nativeDegerAta(textarea, metin);
      setTimeout(function () {
        var gonderBtn = pdoc.querySelector('[data-testid="stChatInputSubmitButton"]');
        if (gonderBtn && !gonderBtn.disabled) {
          gonderBtn.click();
          durum.textContent = '';
        } else if (deneme < 5) {
          mesajGonder(metin, deneme + 1);
        } else {
          durum.textContent = 'Mesaj gönderilemedi, lütfen tekrar deneyin.';
        }
      }, 120);
    } catch (e) {
      durum.textContent = 'Mesaj gönderilemedi: ' + e.message;
    }
  }

  // ---------------- YAZI -> SES ----------------
  var synth = window.speechSynthesis;
  var autoCb = document.getElementById('entes-auto-read');
  var stopBtn = document.getElementById('entes-stop-btn');
  var voiceSelect = document.getElementById('entes-voice-select');
  var rateSlider = document.getElementById('entes-rate-slider');
  var rateVal = document.getElementById('entes-rate-val');

  if (!synth) {
    autoCb.disabled = true;
    stopBtn.style.display = 'none';
    voiceSelect.style.display = 'none';
    rateSlider.style.display = 'none';
  } else {
    autoCb.checked = localStorage.getItem(AUTO_KEY) === '1';
    var kayitliHiz = parseFloat(localStorage.getItem(RATE_KEY));
    if (!isNaN(kayitliHiz)) {
      rateSlider.value = kayitliHiz;
      rateVal.textContent = kayitliHiz.toFixed(1);
    }

    autoCb.addEventListener('change', function () {
      localStorage.setItem(AUTO_KEY, autoCb.checked ? '1' : '0');
    });
    rateSlider.addEventListener('input', function () {
      rateVal.textContent = parseFloat(rateSlider.value).toFixed(1);
      localStorage.setItem(RATE_KEY, rateSlider.value);
    });
    stopBtn.addEventListener('click', function () {
      synth.cancel();
    });

    function seslerDoldur() {
      var sesler = synth.getVoices();
      if (!sesler.length) return;
      var oncekiSecim = localStorage.getItem(VOICE_KEY);
      voiceSelect.innerHTML = '';
      sesler.forEach(function (ses) {
        var opt = document.createElement('option');
        opt.value = ses.name;
        opt.textContent = ses.name + ' (' + ses.lang + ')';
        voiceSelect.appendChild(opt);
      });
      if (oncekiSecim && sesler.some(function (s) { return s.name === oncekiSecim; })) {
        voiceSelect.value = oncekiSecim;
      } else {
        var trSes = sesler.find(function (s) {
          return s.lang && s.lang.toLowerCase().indexOf('tr') === 0;
        });
        if (trSes) voiceSelect.value = trSes.name;
      }
    }
    seslerDoldur();
    if (synth.onvoiceschanged !== undefined) {
      synth.onvoiceschanged = seslerDoldur;
    }
    voiceSelect.addEventListener('change', function () {
      localStorage.setItem(VOICE_KEY, voiceSelect.value);
    });

    function metniOku(metin) {
      if (!metin) return;
      synth.cancel();
      var utter = new SpeechSynthesisUtterance(metin);
      utter.lang = 'tr-TR';
      utter.rate = parseFloat(rateSlider.value) || 1.0;
      var secilenAd = voiceSelect.value;
      var eslesen = synth.getVoices().find(function (s) { return s.name === secilenAd; });
      if (eslesen) utter.voice = eslesen;
      synth.speak(utter);
    }

    var guncelMetin = __ENTES_SON_MESAJ_JSON__;
    var oncekiOkunan = localStorage.getItem(LAST_KEY);
    if (guncelMetin && oncekiOkunan !== guncelMetin) {
      localStorage.setItem(LAST_KEY, guncelMetin);
      if (autoCb.checked) {
        metniOku(guncelMetin);
      }
    }
  }
})();
</script>
"""


def ses_paneli_goster(son_asistan_metni: str) -> None:
    """Sesli giriş/çıkış kontrol panelini gömer (Web Speech API, Chrome hedefli)."""
    html = _SES_PANELI_HTML_SABLONU.replace(
        "__ENTES_SON_MESAJ_JSON__", json.dumps(son_asistan_metni)
    )
    components.html(html, height=90)


# ----------------------------------------------------------------------------
# ANASAYFA + YÜZEN SOHBET POPOVER
# ----------------------------------------------------------------------------
# 1. CSS Kurallarını Yükle (Popover Tetikleyici Butonu Dahil)
st.markdown(
    COMMON_CSS + f"""
    /* Popover tetikleyicisini sağ altta sabit yuvarlak bir butona çevir */
    [data-testid="stPopover"] {{
        position: fixed !important;
        bottom: 40px !important;
        right: 40px !important;
        z-index: 999999 !important;
        width: auto !important;
    }}
    [data-testid="stPopoverButton"] {{
        width: 65px !important;
        height: 65px !important;
        border-radius: 50% !important;
        background-color: {ENTES_SARI} !important;
        color: {ENTES_KOYU} !important;
        border: none !important;
        font-size: 28px !important;
        box-shadow: 0 6px 20px rgba(253, 195, 0, 0.4) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.2s ease !important;
        padding: 0 !important;
    }}
    [data-testid="stPopoverButton"]:hover {{
        transform: scale(1.08) !important;
        background-color: #E2AE00 !important;
    }}
    [data-testid="stPopoverBody"] {{
        width: 400px !important;
        max-width: 92vw !important;
        background-color: #FFFFFF !important;
        color: #222222 !important;
    }}
    [data-testid="stPopoverBody"] * {{
        color: #222222 !important;
    }}
    [data-testid="stPopoverBody"] [data-testid="stVerticalBlock"],
    [data-testid="stPopoverBody"] [data-testid="stMarkdownContainer"] {{
        background-color: #FFFFFF !important;
    }}
    .popover-chat-title {{
        font-size: 14px !important;
        font-weight: 800 !important;
        color: #333333 !important;
        margin-bottom: 8px;
    }}
    [data-testid="stPopoverBody"] [data-testid="stVerticalBlock"] {{
        overflow-y: auto !important;
        scrollbar-width: thin !important;
    }}
    [data-testid="stPopoverBody"] [data-testid="stVerticalBlock"]::-webkit-scrollbar {{
        width: 6px !important;
    }}
    [data-testid="stPopoverBody"] [data-testid="stVerticalBlock"]::-webkit-scrollbar-thumb {{
        background-color: #D6D6D6 !important;
        border-radius: 3px !important;
    }}
    [data-testid="stPopoverBody"] [data-testid="stVerticalBlock"]::-webkit-scrollbar-track {{
        background: transparent !important;
    }}
    [data-testid="stPopoverBody"] div.stButton > button {{
        background-color: #F8F9FA !important;
        color: #333333 !important;
        border: 1px solid #EAEAEA !important;
        border-radius: 8px !important;
        padding: 10px 12px !important;
        text-align: left !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        line-height: 1.4 !important;
        white-space: normal !important;
        width: 100% !important;
        display: block !important;
        margin-bottom: 6px !important;
        transition: all 0.2s ease !important;
    }}
    [data-testid="stPopoverBody"] div.stButton > button:hover {{
        background-color: {ENTES_SARI} !important;
        border-color: {ENTES_SARI} !important;
        color: #000000 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# 2. ENTES Anasayfa HTML Yapısını Çiz
st.markdown(
    """<div class="entes-utility">
<div class="entes-utility-left">
<span>🌐 Türkçe / English</span>
<span>📞 +90 (216) 313 0110</span>
<span>✉️ iletisim@entes.com.tr</span>
</div>
<div class="entes-utility-right">
<a href="#">Hakkımızda</a>
<a href="#">Neler Yapıyoruz?</a>
<a href="#">Katalog</a>
<a href="#">Teknik Destek</a>
</div>
</div>
<div class="entes-breadcrumbs-row">Anasayfa &gt; Ürün Seçimi &gt; Yapay Zeka Ajanı</div>
<div class="entes-header">
<div class="entes-logo-box">
<h1 class="entes-logo-text">ENTES</h1>
</div>
<div class="entes-nav">
<a href="#">Ürünler</a>
<a href="#">Çözümler</a>
<a href="#">Destek</a>
<a href="#">Doğrulama</a>
</div>
<div>
<a href="#" class="entes-header-btn">İletişim</a>
</div>
</div>
<div class="entes-hero">
<h2>Güç Kalitesi ve Enerji Ajanı</h2>
</div>
<div class="homepage-container">
<div class="entes-slider">
<div class="slider-left">
<div class="shield-badge">🛡️</div>
<h2>ENTES, ISO/IEC 27001:2022 Sertifikası ile Bilgi Güvenliğinde En Üst Seviyede</h2>
<a href="#" class="detayli-bilgi-btn">DETAYLI Bİ LOGİ</a>
</div>
<div class="slider-right">
<div class="tech-graphic">
<svg viewBox="0 0 200 120" width="100%">
<path d="M10 100 L50 70 L90 85 L130 40 L170 60" stroke="#FDC300" stroke-width="3" fill="none"/>
<circle cx="130" cy="40" r="5" fill="#FFFFFF" stroke="#FDC300" stroke-width="2"/>
<rect x="20" y="20" width="40" height="30" rx="3" fill="rgba(255,255,255,0.1)" stroke="rgba(255,255,255,0.2)"/>
<line x1="30" y1="35" x2="50" y2="35" stroke="#FFFFFF" stroke-width="2"/>
<line x1="30" y1="42" x2="45" y2="42" stroke="#FFFFFF" stroke-width="2"/>
</svg>
</div>
</div>
<div class="slider-bottom-bar">
<span>Daha İyi Bir Gelecek İçin Enerji Verimliliği</span>
</div>
</div>
<div class="section-title">
<h3>ENERJİNİN OLDUĞU HER YERDE</h3>
</div>
<div class="services-row">
<div class="service-card">
<div class="service-icon">☀️</div>
<h4>Solar / Enerji İzleme</h4>
</div>
<div class="service-card">
<div class="service-icon">🛠️</div>
<h4>Teknik Destek</h4>
</div>
<div class="service-card">
<div class="service-icon">💼</div>
<h4>Kariyer Merkezi</h4>
</div>
</div>
<div class="product-showcase">
<div class="showcase-sidebar">
<h4>KATEGORİLER</h4>
<ul class="category-list">
<li class="active">Tümü</li>
<li>Güç Kalitesi ve Enerji</li>
<li>Ölçme</li>
<li>Kompanzasyon Cihazları</li>
<li>Enerji Yönetimi Donanımları</li>
<li>Koruma & Kontrol</li>
<li>Akım Trafoları</li>
</ul>
</div>
<div class="showcase-grid">
<div class="mock-product-card">
<div class="product-img">
<svg viewBox="0 0 100 100" width="80" height="80">
<rect x="10" y="10" width="80" height="80" rx="8" fill="#333" stroke="#FDC300" stroke-width="2"/>
<rect x="20" y="20" width="60" height="40" rx="3" fill="#000" stroke="#666"/>
<text x="30" y="42" font-family="monospace" font-size="10" fill="#0F0">1.87 kW</text>
<circle cx="25" cy="75" r="3" fill="#FFF"/>
<circle cx="35" cy="75" r="3" fill="#FFF"/>
<circle cx="45" cy="75" r="3" fill="#FFF"/>
</svg>
</div>
<div class="product-title-bar">Şebeke Analizörleri</div>
</div>
<div class="mock-product-card">
<div class="product-img">
<svg viewBox="0 0 100 100" width="80" height="80">
<rect x="10" y="10" width="80" height="80" rx="8" fill="#222" stroke="#FDC300" stroke-width="2"/>
<rect x="20" y="20" width="60" height="40" rx="3" fill="#111" stroke="#444"/>
<text x="25" y="42" font-family="sans-serif" font-size="8" fill="#FFF">EMK SERİSİ</text>
<circle cx="25" cy="75" r="3" fill="#FFF"/>
<circle cx="35" cy="75" r="3" fill="#FFF"/>
</svg>
</div>
<div class="product-title-bar">EMK Serisi Class A Kalite Analizörü</div>
</div>
<div class="mock-product-card">
<div class="product-img">
<svg viewBox="0 0 100 100" width="80" height="80">
<rect x="15" y="10" width="70" height="80" rx="5" fill="#444" stroke="#CCC"/>
<rect x="25" y="20" width="50" height="30" fill="#000"/>
<circle cx="30" cy="65" r="4" fill="#FDC300"/>
<circle cx="45" cy="65" r="4" fill="#FFF"/>
</svg>
</div>
<div class="product-title-bar">Güç ve Enerji Ölçerler</div>
</div>
</div>
</div>
</div>""",
    unsafe_allow_html=True,
)
st.caption("Enerjinin olduğu her yerde • Cevaplar yalnızca ENTES 2023 kataloğundan gelir, uydurma yoktur.")

# ----------------------------------------------------------------------------
# Yüzen Sohbet Popovera: aynı sayfada, buton yakınında küçük bir pencere.
# Anasayfa arkada değişmeden kalır; popover kendi kendine açılıp kapanır.
# ----------------------------------------------------------------------------
with st.popover("💬"):
    st.markdown(
        "<div class='popover-chat-title'>ENTES Katalog Asistanı</div>",
        unsafe_allow_html=True,
    )

    # Mesajların kaydırılabilir alanı - st.container(height=...) ile.
    # Küçük tutuluyor ki popover ilk açıldığında giriş kutusu kaydırmadan görünsün;
    # içerik taştığında konteyner kendi içinde kaydırılabilir.
    chat_container = st.container(height=280)

    with chat_container:
        for gecmis in st.session_state.gorunen_mesajlar:
            with st.chat_message(gecmis["rol"], avatar="👤" if gecmis["rol"] == "user" else "🤖"):
                if gecmis["rol"] == "user":
                    st.markdown(gecmis["icerik"])
                else:
                    asistan_mesaji_goster(gecmis)

        # Yeni mesaj gönderme işlemi
        if "yeni_girdi" in st.session_state and st.session_state.yeni_girdi:
            girdi = st.session_state.yeni_girdi
            st.session_state.yeni_girdi = None

            with st.chat_message("user", avatar="👤"):
                st.markdown(girdi)

            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Katalog taranıyor..."):
                    cevap, filtre_kayitlari = bir_tur_isle(girdi)
                yeni_mesaj = {
                    "rol": "assistant",
                    "icerik": cevap,
                    "debug": filtre_ozeti_olustur(filtre_kayitlari),
                }
                asistan_mesaji_goster(yeni_mesaj)

            st.session_state.gorunen_mesajlar.append({"rol": "user", "icerik": girdi})
            st.session_state.gorunen_mesajlar.append(yeni_mesaj)

    # Sesli giriş/çıkış kontrol paneli (mikrofon, otomatik okuma, ses/hız seçimi)
    son_asistan_mesaji = next(
        (m for m in reversed(st.session_state.gorunen_mesajlar) if m["rol"] == "assistant"),
        None,
    )
    son_asistan_metni = (
        _ses_icin_metin_temizle(son_asistan_mesaji["icerik"]) if son_asistan_mesaji else ""
    )
    ses_paneli_goster(son_asistan_metni)

    if girdi := st.chat_input("İhtiyacınızı tarif edin...", key="main_chat_input"):
        st.session_state.yeni_girdi = girdi
        st.rerun()
