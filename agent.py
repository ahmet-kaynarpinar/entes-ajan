"""
ENTES Ürün Seçim Ajanı
Çok turlu konuşma, OpenRouter tool-calling (OpenAI-uyumlu API), tüm davranış dosyalardan okunur.
"""

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI

import filtrele as filtrele_module

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
    )


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
        }
    ]


def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Hata: OPENROUTER_API_KEY ortam değişkeni tanımlı değil.")
        sys.exit(1)

    kategoriler = load_kategoriler()
    kategori_df = load_kategori_dataframeleri()
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
            print(f"\nAjan: {''.join(tam_cevap_parcalari).strip()}\n")
        else:
            print("\nAjan: (sonuçları işledim ama bir metin üretemedim, lütfen tekrar sorun.)\n")


if __name__ == "__main__":
    main()
