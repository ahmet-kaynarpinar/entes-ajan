# Sonek ve Hücre-Değer Sözlüğü (MPR Şebeke Analizörleri)

> Kaynak: ENTES karşılaştırma tabloları lejantı + ürün sayfası adlandırması.
> Amaç: ajan filtreleme kodunun (Aşama 4) bu kodları doğru yorumlaması.

## Model adı sonekleri
| Sonek | Anlam | Filtre etkisi |
|---|---|---|
| **S** | Standart — RS-485 haberleşmeli | RS-485 = Var *(⚠ uygulama mühendisine 1 soruyla teyit ettir)* |
| **E** | Ethernet'li | Ethernet = Var |
| **0,5** | Doğruluk Sınıf 0,5 | Sınıf 0,5 = Var, Sınıf 1 = Yok |
| **D** | 24-60 VDC besleme | 24-60 VDC = Var (50-270 = Yok) |
| **OG / OGT** | Orta gerilim, sabit akım klemensi | OG = Var |
| **PM** | Plug & Meter | plug&meter = Var |
| **C** (MPR-53**C**S) | Sayım/kombine varyant *(⚠ anlamı teyit edilmeli)* | belirsiz |

## Hücre içindeki değer kodları
| Değer | Anlam |
|---|---|
| **Var / Yok** | Özellik mevcut / yok |
| **H** | Özellik VAR ama **yalnızca haberleşme üzerinden** erişilir (yerel ekranda yok) |
| **M** | Modüler — sonradan eklenen modülle gelir (MPR-4 I/O) |
| **Ops** | Opsiyonel |
| **Belirsiz** | Kaynakta yazmıyor — ajan bunu "bilmiyorum, sorarım/yönlendiririm" diye ele almalı, ASLA Var/Yok varsaymaz |
| **51 / 31** | Ayrı harmonik mertebe derinliği |
| **16MB / 4MB / 1MB** | Hafıza kapasitesi |
| **1 / 2** | Adet (giriş/çıkış/röle sayısı) |

## Filtre için karar gereken nokta
- **"H" değeri:** Müşteri sadece "ölçsün" diyorsa H = Var sayılabilir. "Cihaz ekranında göreyim/yerelde kontrol" diyorsa H yeterli DEĞİL → o modeli eleme. Bu ayrımı Aşama 4 filtre kodunda netleştir.
