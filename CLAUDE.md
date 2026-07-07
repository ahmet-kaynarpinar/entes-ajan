# ENTES MPR Ürün Seçim Ajanı — Proje Kuralları

## Ne yapıyoruz
Kullanıcının ihtiyacını anlayan, entes urunleri  kaynak göstererek öneren bir ajan kuruyoruz.

## EN KRİTİK KURAL (asla çiğnenmez)
Cihaz adı, özellik ve değerler YALNIZCA `urunler.csv` dosyasından gelir.
Hiçbir model adı, hiçbir özellik değeri uydurulmaz/tahmin edilmez.
`urunler.csv`'de "Belirsiz" yazan hücreler için ajan "bilmiyorum, mühendise
yönlendiriyorum" der — ASLA Var/Yok varsaymaz.

## Veri dosyaları
- `urunler.csv`: 52 model, 43 kolon, doğrulanmış kaynak tablo.
- `sonek_sozlugu.md`: model adı soneklerinin (S/E/D/OG/PM/0,5) ve hücre
  değerlerinin (Var/Yok/H/M/Ops/Belirsiz) ne anlama geldiğini tanımlar.
  Kod yazmadan önce bu dosyayı oku.

## Kapsam
- SADECE şebeke analizörü (MPR serisi). Başka ENTES ürün kategorisi YOK.
- Fiyat bilgisi yok, ajan fiyat söylemez.
- Kapsam genişletme isteği gelirse kullanıcıyı uyar, önce çekirdek bitsin.

## Çalışma tarzı
- Tek seferde tek adım. Büyük refactor/yeniden tasarım önerme, küçük adımlarla ilerle.
- Her yeni özellik/filtre kuralı eklerken `sonek_sozlugu.md`'deki tanıma sadık kal.
- "H" değeri = özellik var ama sadece haberleşme üzerinden erişilir, yerel ekranda yok.
  Filtre mantığında bunu Var ile aynı sayma (ayrı ele al).
