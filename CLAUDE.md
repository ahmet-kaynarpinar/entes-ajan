# ENTES Ürün Seçim ve Destek Ajanı

## Proje Amacı
ENTES müşterilerine üç konuda yardım eden bir yapay zeka ajanı:
1. **Ürün seçimi** — teknik kriterlere göre doğru modeli bulma
2. **Teknik destek** — kurulum/ayar/sorun sorularına destek makalelerinden cevap
3. **Referans projeler** — sektöre göre ENTES'in geçmiş uygulamalarını anlatma

## ÇEKİRDEK İLKE (tavizsiz)
Ajan cihaz adı, özellik ve değerleri **yalnızca** doğrulanmış veri kaynaklarından alır, **ASLA uydurmaz**.
- Kesin değer (model adı, Var/Yok, sayı, çözüm adımı) sadece araç çıktısından gelir.
- Katalogda yazmayan hücre = `Belirsiz`.
- Veri bulunamazsa uydurmak yerine "bulamadım" der ve netleştirme ister.
- Dönen makalede olmayan hiçbir bilgi (sayı, menü adı, adım) eklenmez.
- Ürün sunarken CSV'de olmayan işlev/fayda yorumu yapılmaz.

## Kapsam
**TÜM ENTES ürün gamı** — sadece şebeke analizörleri değil.
- **42 ürün kategorisi**, 706 model (analizörler, ampermetreler, voltmetreler, akım trafoları, röleler, kompanzasyon, güç kaynakları, zaman röleleri vb.)
- **416 destek makalesi** (5 ürün grubu: Enerji Verimliliği, Enerji Yönetimi, Kompanzasyon, Koruma & Kontrol, Çözümler)
- **21 sektör bazlı referans proje** (boya/tekstil fabrikası, hastane, banka, üniversite vb.)

## Mimari
- **Model:** OpenRouter üzerinden `google/gemini-3-flash-preview`, `temperature=0`
- **Yaklaşım:** Tool-calling. Model eğitimi YOK; talimat + araç + veri veriliyor.
- **Grounding garantisi:** Model veriyi hatırlamaz, her değeri araç üzerinden CSV/makaleden çeker.

## Üç Araç
| Araç | Ne zaman | Veri kaynağı |
|---|---|---|
| `urun_filtrele(kriterler, kategori)` | Müşteri ürün seçmek istiyor | `veri/*.csv` (42 kategori) |
| `sss_ara(urun, anahtar_kelime)` | Kurulum/ayar/sorun sorusu | `sss_veri/*.csv` (416 makale) |
| `referans_ara(sektor_veya_konu)` | "Bu alanda ne yaptınız?" | `sss_veri/` içindeki "Çözümler" grubu |

## Dosya Yapısı

## Veri Formatları

**Ürün CSV (`veri/<kategori>.csv`):**
- İlk kolonlar: `Kategori, Seri, Model` — sonra kategoriye özgü kolonlar
- Değerler sade: `Var` / `Yok` / sayı / `Belirsiz`
- Boyut: `96x96`, `72x72`, `DIN ray` (birim/parantez yok)

**SSS CSV (`sss_veri/*.csv`):**
- Kolonlar: `urun_grubu, urun, baslik, problem_tarifi, cozum, etiketler, link`
- `cozum` = destek makalesinin birebir metni (özetlenmemiş)

## SSS Arama Mantığı (sss.py)
Puanlama tabanlı (anlamsal arama değil, kelime eşleşmesi):
- Ürün adı / etiket / başlıkta eşleşme → **3 puan**
- Problem tarifi / çözüm gövdesinde eşleşme → **1 puan**
- Minimum eşik: 3 puan (en az bir güçlü eşleşme)
- **Zayıf eleme:** lider puanının yarısından düşük makaleler atılır
- **Baskın lider:** bir makale 2 kat öndeyse yalnız o döndürülür
- Bu eleme, alakasız makale gidip ajanın uydurmasını önler.

## Test Durumu
- **`test_grounding_auto.py`: 2515/2515 geçti** — 42 kategori × her kolon × her değer; motor hiçbir yerde model uydurmuyor/kaçırmıyor.
- **`test_filtrele.py`: 7/7** — Türkçe virgül, ×/x normalize, Belirsiz sızmaması, olmayan kolon atlama.
- **`eval.py`: 33/37** — LLM davranış senaryoları (kalanlar test cümlesi yapaylığı, uydurma değil).

## Çalıştırma
```bash
python3 agent.py                              # Terminal ajanı
python3 -m streamlit run arayuz_agent.py      # Streamlit arayüzü
python3 test_grounding_auto.py                # Deterministik grounding testi
python3 eval.py                               # LLM eval
python3 whatsapp_bot.py                       # WhatsApp webhook (+ ayrı terminalde: ngrok http 5000)
```

## Canlı Ortam
- **GitHub:** `ahmet-kaynarpinar/entes-ajan` (push → Streamlit Cloud otomatik günceller)
- **Canlı demo:** https://entes-ajan-jehkys5ytggsgecepgtigb.streamlit.app/
- **Anahtar:** `OPENROUTER_API_KEY` — ortam değişkeni (yerelde `.zshrc`, canlıda Streamlit Secrets). Koda ASLA yazılmaz.

## Sesli Etkileşim
Web Speech API (tarayıcı yerleşik, ek paket/anahtar yok):
- Konuşma → yazı: `webkitSpeechRecognition`, `tr-TR`
- Yazı → ses: `SpeechSynthesis`, ses seçimi + hız ayarı
- **Chrome gerekir** (Safari'de kısıtlı). Ses sadece giriş/çıkışta; ajanın beyni ve grounding değişmez.

## Ortam
- Mac, Python 3.9, zsh, proje: `~/entes-ajan`
- Kod düzenleme: Antigravity (Gemini 3.1 Pro High) veya Claude Code
- CSV oluştururken `nano`/heredoc boş dosya üretebiliyor → `cat > dosya` → yapıştır → Ctrl+D

## Bilinen Durum / Kalanlar
- **WhatsApp: çalışıyor (test edildi, 13 Temmuz 2026).** Twilio sandbox + `whatsapp_bot.py` + ngrok (statik domain: `kinetic-denatured-mossy.ngrok-free.dev`) uçtan uca doğrulandı — gerçek mesaj gidip geldi, ajan doğru cevap üretti.
  - Sınırlama: Sandbox modu — sadece `join <kod>` mesajı gönderen numaralar bağlanabiliyor, üyelik 72 saatte düşüyor, sunumdan önce yenilenmeli.
  - Sunum günü checklist: `whatsapp_bot.py` + `ngrok http 5000` ayakta olmalı, Mac uykuya girmemeli, sandbox üyeliği güncel olmalı.
  - Sonraki adım (production): Twilio production WhatsApp Sender başvurusu → Meta Business doğrulaması gerekiyor (birkaç gün-2 hafta sürebilir, idari bir iş, kod değişikliği gerektirmiyor). Maliyet düşük (Twilio ~$0.005-0.01/mesaj + Meta ücreti, ülkeye göre).
  - Alternatif BSP: 360dialog (aylık sabit ~49€, mesaj başı komisyon yok) — hacim artarsa değerlendirilebilir.
- Kullanım talimatları verisi (seri bazlı) henüz çekilmedi.
- Sunum provası + ekran kaydı yedeği yapılmadı.
- **Planlanan ek özellikler (kapsam dahilinde, MPR sonrası ele alınacak):**
  - Lead/talep yakalama: kullanıcı ürün talep ederse isim/telefon/firma toplayıp satışa iletme.
  - Datasheet/PDF linki: model → resmi ürün sayfası eşleşmesi için ayrı doğrulanmış kaynak (`urun_linkleri.csv`) gerekiyor — `urunler.csv`'de link kolonu yok, uydurma link verilemez.
  - Konuşma logu/analiz: en çok sorulan sorular için basit kayıt.
  - Kalıcı hosting (Railway/Render/Fly.io gibi) — şu an localhost+ngrok'a bağımlı.

## Kurallar (bu projede çalışırken)
- Türkçe konuş. Gereksiz övme; bir şey yanlışsa açıkça söyle.
- Tek seferde tek adım ver.
- Test ederken ham çıktı (terminal/DEBUG) iste, özet değil.
- Grounding'i bozan bir tasarım önerilirse uyar.
- Yeni kategori/veri eklemek kapsam aşımı DEĞİL, planın parçasıdır.