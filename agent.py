"""
ENTES Ürün Seçim Ajanı
Çok turlu konuşma, OpenRouter tool-calling (OpenAI-uyumlu API), tüm davranış dosyalardan okunur.
"""

import json
import os
import sys
import time
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from openai import OpenAI

import filtrele as filtrele_module
import sss

BASE = Path(__file__).parent
VERI_DIR = BASE / "veri"
OPENROUTER_MODEL = "google/gemini-3-flash-preview"


def load_kategoriler() -> list[dict]:
    with open(BASE / "kategoriler.json", encoding="utf-8") as f:
        return json.load(f)


def load_kategori_dataframeleri() -> dict[str, pd.DataFrame]:
    """veri/ klasöründeki her CSV'yi okur ve "Kategori" kolonundaki değere göre
    kategori -> dataframe eşlemesi çıkarır. Kolonlar her CSV'den dinamik okunur,
    hiçbir kategori/kolon adı burada sabitlenmez (hardcode yok)."""
    kategori_df: dict[str, pd.DataFrame] = {}
    for csv_yolu in sorted(VERI_DIR.glob("*.csv")):
        df = pd.read_csv(csv_yolu, encoding="utf-8-sig")
        if "Kategori" not in df.columns:
            raise ValueError(f"{csv_yolu.name}: 'Kategori' kolonu yok, atlanamaz.")
        for kategori, alt_df in df.groupby("Kategori"):
            alt_df = alt_df.reset_index(drop=True)
            if kategori in kategori_df:
                kategori_df[kategori] = pd.concat(
                    [kategori_df[kategori], alt_df], ignore_index=True
                )
            else:
                kategori_df[kategori] = alt_df
    return kategori_df


def load_filtre_kolonlari(df: pd.DataFrame) -> list[str]:
    """Verilen kategori dataframe'indeki gerçek kriter kolonlarını döndürür
    (Model ve Kategori hariç, Kategori ayrı bir araç parametresi olduğu için
    burada tekrarlanmaz)."""
    return [k for k in df.columns if k not in ("Model", "Kategori")]


def build_sistem_talimati(kategoriler: list[dict], verisi_olan: list[str]) -> str:
    with open(BASE / "sistem_talimati.txt", encoding="utf-8") as f:
        template = f.read()

    tum_str = "\n".join(
        f"- {k['kategori']}: {k['aciklama']}" for k in kategoriler
    )
    olan_str = "\n".join(f"- {k}" for k in verisi_olan)

    return (
        template
        .replace("{TUM_KATEGORILER}", tum_str)
        .replace("{VERISI_OLAN_KATEGORILER}", olan_str)
        + "\n\nKonuşmanın sonunda müşteriyle bir ürün üzerinde netleşildiğinde (müşteri belirli bir modele karar verdiğinde), satın alma niyetini AÇIKÇA belirtmesini beklemeden şunu sor: 'Sizinle iletişime geçmemizi ister misiniz?' Müşteri 'evet' derse: tercih ettiği iletişim biçimini sor (telefon/e-posta/WhatsApp), sonra sırasıyla isim, firma, e-posta, telefon bilgilerini iste. Müşteri bir bilgiyi vermek istemezse veya atlarsa o alanı boş bırak, ISRAR ETME. Müşteri 'hayır, istemiyorum' derse hiçbir şey kaydetme, konuşmaya normal devam et. Tüm bilgiler toplandıktan (veya müşteri atladıktan) sonra lead_kaydet aracını çağır."
    )


def call_model_ara(model_adi: str, kategori_df: dict[str, pd.DataFrame]) -> str:
    """Tüm kategorilerin Model kolonunda büyük/küçük harf duyarsız, kısmi eşleşme arar."""
    if not model_adi or not model_adi.strip():
        return "Model adı belirtilmedi."
    aranan = model_adi.strip().lower()
    sonuclar = []
    for kategori, df in kategori_df.items():
        eslesen = df[df["Model"].astype(str).str.lower().str.contains(aranan, na=False, regex=False)]
        if not eslesen.empty:
            sonuclar.append(eslesen)
    if not sonuclar:
        return f"'{model_adi}' adında/kodunda bir model doğrulanmış veri tabanında bulunamadı. Farklı bir isimlendirme deneyebilir veya teknik kriterlerinizi belirtebilirsiniz."
    import pandas as pd
    tumu = pd.concat(sonuclar, ignore_index=True)
    return f"{len(tumu)} eşleşme bulundu:\n{tumu.to_string(index=False)}"


def call_urun_filtrele(kriterler, kategori: str, kategori_df: dict[str, pd.DataFrame]) -> str:
    """kriterler bir dict (model artık böyle gönderiyor) ya da geriye dönük
    uyumluluk için JSON string olabilir; her iki durumu da güvenle işler."""
    if kriterler is None:
        kriterler = {}
    elif isinstance(kriterler, str):
        try:
            kriterler = json.loads(kriterler) if kriterler.strip() else {}
        except json.JSONDecodeError as e:
            return f"Hata: kriterler geçerli JSON değil: {e}"

    if not isinstance(kriterler, dict):
        return "Hata: kriterler bir JSON nesnesi (object) olmalı."

    if kategori not in kategori_df:
        return (
            f"Hata: '{kategori}' için doğrulanmış ürün verisi yok. "
            f"Veri olan kategoriler: {', '.join(sorted(kategori_df.keys()))}."
        )
    df = kategori_df[kategori]

    kriterler = dict(kriterler)
    kriterler["Kategori"] = kategori

    anlamli_kriterler = {k: v for k, v in kriterler.items() if k != "Kategori"}
    if not anlamli_kriterler:
        return (
            "Uyarı: Kriter belirtilmeden sadece kategoriyle arama yapılmadı. "
            "En az bir teknik kriter (örn. \"Ethernet\": \"Var\") belirtmeden "
            "urun_filtrele çağırma; tüm kategoriyi amaçsızca tarama."
        )

    try:
        sonuc, atlanan_filtreler = filtrele_module.filtrele(kriterler, df=df)
    except ValueError as e:
        print(f"[DEBUG] Filtre çağrıldı: {kriterler} -> Hata: {e}")
        return f"Hata: {e}"

    modeller = sonuc["Model"].tolist() if "Model" in sonuc.columns else []
    print(
        f"[DEBUG] Filtre çağrıldı: {kriterler} -> {len(sonuc)} model: {modeller} "
        f"(atlanan filtreler: {atlanan_filtreler})"
    )

    atlanan_uyarisi = ""
    if atlanan_filtreler:
        atlanan_uyarisi = (
            f"\nUYARI: Şu kriterler '{kategori}' kategorisinde bu ismiyle bir "
            f"kolon olmadığı için UYGULANMADI, sonuçlara dahil edilmedi: "
            f"{atlanan_filtreler}. Bu özellikler için sonuçları yorumlarken "
            f"varmış/yokmuş gibi konuşma; kullanıcıya bu kategoride bu veri "
            f"olmadığını açıkça söyle."
        )

    if sonuc.empty:
        return "Eşleşen ürün bulunamadı." + atlanan_uyarisi

    goster = sonuc.drop(columns=["Kategori"], errors="ignore")
    return f"{len(sonuc)} ürün bulundu:\n{goster.to_string(index=False)}" + atlanan_uyarisi


def call_lead_kaydet(isim: str, firma: str, email: str, telefon: str, tercih_iletisim: str, ilgilenilen_urun: str, not_: str, whatsapp_no: str, dosya="leads.csv") -> str:
    dosya_yolu = BASE / dosya
    dosya_yok = not dosya_yolu.exists()
    
    tarih = datetime.now().isoformat()
    if not isim: isim = ""
    if not firma: firma = ""
    if not email: email = ""
    if not telefon: telefon = ""
    if not tercih_iletisim: tercih_iletisim = ""
    if not not_: not_ = ""
        
    import csv
    import os
    print(f"[LEAD_KAYDET] Calisma dizini: {os.getcwd()}")
    print(f"[LEAD_KAYDET] Hedef dosya (mutlak yol): {os.path.abspath(dosya_yolu)}")
    try:
        with open(dosya_yolu, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if dosya_yok:
                writer.writerow(["tarih", "whatsapp_no", "isim", "firma", "email", "telefon", "tercih_iletisim", "ilgilenilen_urun", "not"])
            writer.writerow([tarih, whatsapp_no, isim, firma, email, telefon, tercih_iletisim, ilgilenilen_urun, not_])
        print(f"[LEAD_KAYDET] BASARILI: satir yazildi -> {os.path.abspath(dosya_yolu)}")
    except Exception as e:
        print(f"[LEAD_KAYDET] HATA: yazilamadi -> {e}")

    return "Talep kaydedildi, satış ekibimiz en kısa sürede sizinle iletişime geçecek."


def clean_content(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    # XML tag'leri ile gelen düşünce bloklarını at
    text = re.sub(r'^<(thought|thinking|reasoning)>.*?</\1>\s*', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Sadece etiket sızmalarını baştan temizle ("thought\n" vb.)
    text = re.sub(r'^(thought|thinking|reasoning):?\s+', '', text, flags=re.IGNORECASE)
    return text.strip()


MAX_TOKENS = 1500


def _hata_yaniti_mi(response) -> bool:
    """choices[0].finish_reason == "error" ya da native_finish_reason
    "MALFORMED" içeriyorsa True döner. response None ise ya da choices
    boş/None ise de True döner (hatalı yanıt sayılır)."""
    if response is None or not getattr(response, "choices", None):
        return True

    try:
        secim = response.choices[0]
    except (IndexError, AttributeError, TypeError):
        return True

    if secim.finish_reason == "error":
        return True

    native = getattr(secim, "native_finish_reason", None)
    if native and "MALFORMED" in str(native):
        return True

    return False


def openrouter_cagir(client: OpenAI, messages: list[dict], tools: list[dict]):
    """OpenRouter API çağrısını 429 rate-limit yönetimiyle çalıştırır.
    Başarıda response döndürür; kalıcı rate-limit'te None döndürür, çökmez."""
    MAX_DENEME = 3
    BEKLEME = 3  # saniye

    MAX_HATA_DENEME = 2
    HATA_BEKLEME = 1  # saniye

    for deneme in range(1, MAX_DENEME + 1):
        try:
            response = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=MAX_TOKENS,
                temperature=0,
            )
        except Exception as e:
            hata_str = str(e)
            is_rate_limit = "429" in hata_str or "rate_limit" in hata_str.lower()
            if not is_rate_limit:
                raise

            if deneme == MAX_DENEME:
                print("\n[Ajan] Kota limiti aşıldı, lütfen bir dakika sonra tekrar deneyin.\n")
                return None

            print(f"Kota limiti nedeniyle {BEKLEME} saniye bekleniyor... (Deneme {deneme}/{MAX_DENEME})")
            time.sleep(BEKLEME)
            continue

        if not _hata_yaniti_mi(response):
            return response

        for hata_deneme in range(1, MAX_HATA_DENEME + 1):
            print(
                f"[Ajan] Modelden hatalı yanıt geldi, yeniden deneniyor... "
                f"(Deneme {hata_deneme}/{MAX_HATA_DENEME})"
            )
            time.sleep(HATA_BEKLEME)
            response = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=MAX_TOKENS,
                temperature=0,
            )
            if not _hata_yaniti_mi(response):
                return response

        print("\n[Ajan] Modelden tekrar tekrar hatalı yanıt geldi, isteği tamamlayamadım.\n")
        return None

    return None


def build_tools(kategori_df: dict[str, pd.DataFrame]) -> list[dict]:
    """urun_filtrele aracının şemasını her kategorinin KENDİ CSV'sindeki gerçek
    kolon adlarından dinamik olarak üretir; böylece model kriter anahtarı olarak
    var olmayan ya da başka kategoriye ait bir kolon adı uyduramaz. Her
    kategorinin kolon listesi ayrı ayrı açıklamaya yazılır ki model kategori
    seçtikten sonra sadece o kategoride GERÇEKTEN var olan kolonları kullansın."""
    kategori_kolonlari = {
        kategori: load_filtre_kolonlari(df) for kategori, df in kategori_df.items()
    }

    kategori_aciklama = "\n".join(
        f"- {kategori}: {', '.join(kolonlar)}"
        for kategori, kolonlar in sorted(kategori_kolonlari.items())
    )

    return [
        {
            "type": "function",
            "function": {
                "name": "urun_filtrele",
                "description": (
                    "Belirtilen teknik kriterlere ve ürün kategorisine göre SEÇİLEN "
                    "kategorinin kendi doğrulanmış ürün tablosunu filtreler; eşleşen "
                    "model listesini döndürür. Her kategorinin GEÇERLİ kriter kolonları "
                    "farklıdır ve aşağıda kategori bazında listelenmiştir. kriterler "
                    "nesnesinin anahtarları YALNIZCA seçtiğin kategorinin kendi kolon "
                    "listesinden biri olabilir, başka kategoriden ya da uydurma kolon "
                    f"adı kullanma:\n{kategori_aciklama}\n"
                    "Kategoride olmayan bir kolon gönderirsen araç hata döndürür, uydurma yerine kolon listesine bak."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "kriterler": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                            "description": (
                                "Anahtar = seçilen kategorinin kolon adı (sistem "
                                "talimatındaki listeden birebir), değer = aranan "
                                "değer (Var/Yok vb.)."
                            ),
                        },
                        "kategori": {
                            "type": "string",
                            "description": (
                                'Filtrelenecek ürün kategorisi. Örnek: "Şebeke Analizörleri".'
                            ),
                            "enum": sorted(kategori_df.keys()),
                        },
                    },
                    "required": ["kriterler", "kategori"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sss_ara",
                "description": (
                    "Müşteri bir ürünün kullanımı, kurulumu, ayarı veya bir sorunuyla "
                    "ilgili DESTEK sorusu sorduğunda çağrılır (ürün SEÇİMİ değil). "
                    "ENTES destek makalelerinden en uygun olanın çözümünü döndürür."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "urun": {
                            "type": "string",
                            "description": (
                                'Müşterinin bahsettiği ürün/seri adı (örn. "MPR-53", '
                                '"DCA", "EPM-4").'
                            ),
                        },
                        "anahtar_kelime": {
                            "type": "string",
                            "description": (
                                'Sorunun konusu/anahtar kelimeleri (örn. "kurulum", '
                                '"C/T oranı", "yanlış akım gösteriyor").'
                            ),
                        },
                    },
                    "required": ["urun", "anahtar_kelime"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "referans_ara",
                "description": (
                    "Müşteri ENTES'in geçmiş projelerini/referanslarını sorduğunda çağrılır (örn. 'boya fabrikam var, bu alanda ne çözümler geliştirdiniz?', 'fabrikamda enerji tasarrufu için bugüne kadar neler yaptınız?'). Bir ürün ya da teknik sorun sorusu DEĞİL, geçmiş uygulama/referans sorusudur. İlgili referans projenin gerçek metnini döndürür."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sektor_veya_konu": {
                            "type": "string",
                            "description": (
                                "Müşterinin bahsettiği sektör/tesis türü veya konu (örn. \"boya fabrikası\", \"hastane\", \"tekstil\", \"enerji tasarrufu fabrika\")."
                            ),
                        },
                    },
                    "required": ["sektor_veya_konu"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lead_kaydet",
                "description": "Müşteriyle bir ürün üzerinde netleşildiğinde (müşteri belirli bir modele karar verdiğinde) çağrılır — müşterinin satın alma niyetini açıkça belirtmesini BEKLEME. Önce 'Sizinle iletişime geçmemizi ister misiniz?' diye sor. 'Evet' derse tercih ettiği iletişim biçimini, sonra isim/firma/e-posta/telefon bilgilerini sırayla iste, ısrar etme. 'Hayır' derse bu aracı ÇAĞIRMA. Müşterinin söylemediği hiçbir bilgiyi uydurma, boş bırak.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "isim": {
                            "type": "string",
                            "description": "Müşterinin adı soyadı."
                        },
                        "firma": {
                            "type": "string",
                            "description": "Müşterinin firma adı (boş olabilir)."
                        },
                        "email": {
                            "type": "string",
                            "description": "Müşterinin e-posta adresi."
                        },
                        "telefon": {
                            "type": "string",
                            "description": "Müşterinin tercih ettiği iletişim numarası (whatsapp numarasından farklı olabilir)."
                        },
                        "tercih_iletisim": {
                            "type": "string",
                            "description": "Tercih edilen iletişim yöntemi ('telefon' / 'e-posta' / 'whatsapp' / 'Belirsiz')."
                        },
                        "ilgilenilen_urun": {
                            "type": "string",
                            "description": "Konuşmadan çıkan ürün veya kategori adı."
                        },
                        "not": {
                            "type": "string",
                            "description": "Müşterinin ek talebi veya notu."
                        }
                    },
                    "required": ["ilgilenilen_urun"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "model_ara",
                "description": "Müşteri doğrudan bir model kodu veya adı söylediğinde (örn. 'MPR-47SE istiyorum') çağrılır — netleştirici soru sormadan ÖNCE bunu dene. Tüm kategorilerde Model kolonunda arama yapar. Tek bir net eşleşme bulunursa dönen TÜM özellikleri doğrudan sun, soru sorma. Birden fazla/karışık kategoriden eşleşme dönerse müşteriden netleştirme iste. Hiç eşleşme yoksa bunu söyle, teknik kriter sorup urun_filtrele'ye geç.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "model_adi": {
                            "type": "string",
                            "description": "Müşterinin söylediği model kodu/adı, örn. 'MPR-47SE'."
                        }
                    },
                    "required": ["model_adi"]
                }
            }
        }
    ]


def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Hata: OPENROUTER_API_KEY ortam değişkeni tanımlı değil.")
        sys.exit(1)

    kategoriler = load_kategoriler()
    kategori_df = load_kategori_dataframeleri()
    sss_df = sss.load_sss()
    verisi_olan = sorted(kategori_df.keys())
    sistem_talimati = build_sistem_talimati(kategoriler, verisi_olan)
    tools = build_tools(kategori_df)

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    messages: list[dict] = [{"role": "system", "content": sistem_talimati}]

    print("ENTES Ürün Seçim Ajanı hazır. Çıkmak için 'çıkış' yazın.\n")

    while True:
        try:
            kullanici = input("Siz: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nÇıkılıyor...")
            break

        if not kullanici:
            continue

        if kullanici.lower() in ("çıkış", "cikis", "exit", "quit"):
            print("Görüşmek üzere!")
            break

        messages.append({"role": "user", "content": kullanici})

        response = openrouter_cagir(client, messages, tools)
        if response is None:
            continue

        # Bir kullanıcı turunda urun_filtrele en fazla bu kadar kez çağrılabilir;
        # amaçsız ardışık (kategori tarama) çağrıları engeller.
        MAX_FILTRELE_CAGRI = 2
        filtrele_cagri_sayisi = 0

        # finish_reason "length" nedeniyle metin kesilirse en fazla bu kadar
        # kez "devam et" ile tamamlatılır.
        MAX_UZATMA_DENEME = 3
        uzatma_sayisi = 0

        # Son cevap bundan kısaysa (boş/bozuk sayılır) bir kez daha denenir.
        MIN_GECERLI_UZUNLUK = 10
        bozuk_deneme_yapildi = False

        tam_cevap_parcalari: list[str] = []

        # Tool-calling döngüsü: model "stop" ile tam bir metin üretene kadar sürer
        while True:
            secim = response.choices[0]
            msg = secim.message
            finish_reason = secim.finish_reason

            # Asistan mesajını geçmişe ekle
            messages.append(msg)

            if msg.tool_calls:
                # Model, araç çağrısıyla birlikte ara metin de üretmiş olabilir
                # (örn. "filtreliyorum"); bu metni de biriktir, yoksa kaybolur.
                if msg.content:
                    tam_cevap_parcalari.append(msg.content)

                # Her araç çağrısını işle ve sonuçları geçmişe ekle
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
                            sonuc = call_urun_filtrele(
                                args.get("kriterler", {}),
                                args.get("kategori", ""),
                                kategori_df,
                            )
                    elif fn_name == "sss_ara":
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}
                        sonuc = sss.sss_ara(
                            args.get("urun"),
                            args.get("anahtar_kelime"),
                            df=sss_df,
                        )
                    elif fn_name == "referans_ara":
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}
                        sonuc = sss.referans_ara(
                            args.get("sektor_veya_konu", ""),
                            df=sss_df,
                        )
                    elif fn_name == "model_ara":
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}
                        sonuc = call_model_ara(args.get("model_adi", ""), kategori_df)
                    elif fn_name == "lead_kaydet":
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}
                        sonuc = call_lead_kaydet(
                            isim=args.get("isim", ""),
                            firma=args.get("firma", ""),
                            email=args.get("email", ""),
                            telefon=args.get("telefon", ""),
                            tercih_iletisim=args.get("tercih_iletisim", ""),
                            ilgilenilen_urun=args.get("ilgilenilen_urun", ""),
                            not_=args.get("not", ""),
                            whatsapp_no="CLI-terminal",
                        )
                    else:
                        sonuc = f"Bilinmeyen araç: {fn_name}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": sonuc,
                    })

                response = openrouter_cagir(client, messages, tools)
                if response is None:
                    break
                continue

            # Araç çağrısı yok: bu bir metin cevabı (tam ya da kesilmiş olabilir)
            if msg.content:
                tam_cevap_parcalari.append(msg.content)

            if finish_reason == "length" and uzatma_sayisi < MAX_UZATMA_DENEME:
                uzatma_sayisi += 1
                messages.append({
                    "role": "user",
                    "content": "Cevabın kesildi, kaldığın yerden aynen devam et.",
                })
                response = openrouter_cagir(client, messages, tools)
                if response is None:
                    break
                continue

            # finish_reason "stop" (ya da uzatma hakkı tükendi): cevap tamamlanmış sayılır
            birlesik = "".join(tam_cevap_parcalari).strip()
            if len(birlesik) < MIN_GECERLI_UZUNLUK and not bozuk_deneme_yapildi:
                bozuk_deneme_yapildi = True
                tam_cevap_parcalari = []
                messages.pop()  # boş/bozuk asistan mesajını geçmişten çıkar
                response = openrouter_cagir(client, messages, tools)
                if response is None:
                    break
                continue

            break

        if tam_cevap_parcalari:
            final_cevap = "".join(tam_cevap_parcalari)
            final_cevap = clean_content(final_cevap)
            print(f"\nAjan: {final_cevap}\n")
        else:
            print("\nAjan: (sonuçları işledim ama bir metin üretemedim, lütfen tekrar sorun.)\n")


if __name__ == "__main__":
    main()
