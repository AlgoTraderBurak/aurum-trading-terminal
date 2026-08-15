# İlerleme günlüğü

Bu dosya ara sürüm dağıtmak için değil, tek üretim kod tabanındaki kararları ve tamamlanan doğrulamaları kaydetmek için tutulur.

## 2026-08-12

- Eski prototip ve son eklenen PySide6/backtest kodu yeniden incelendi.
- BTC M15: 7 sinyal, net -1R; XAUUSD M15: 75 sinyal, net -39R sonucu ölçüldü.
- Sabit ATR stop/hedef, maliyetsiz backtest, tek sembol/zaman dilimi GUI ve açık mum kullanımı yeni mimariye taşınmadı.
- 26 gösterge sınıflandırıldı; örtüşen özellikler tek hesap motorunda birleştirildi.
- Yeni hedefte üretim klasör yapısı ve mimari ilkeler oluşturuldu.
- MT5 salt-okunur erişimi, broker sembol eşleme, açık/kapanmış mum ayrımı ve SQLite önbellek tamamlandı.
- İndikatör, yapı, bölge, sinyal, yapısal risk planı ve maliyet duyarlı backtest aynı çekirdeğe bağlandı.
- Canlı Grafik, Analiz/Yorum/Sinyal, Türkçe Dashboard ve Backtest sekmeleri tamamlandı.
- MetaTrader5 IPC çağrısının Qt olay döngüsünü GIL üzerinden dondurabildiği tam pencere testinde görüldü; MT5 erişimi öldürülebilir yardımcı sürece taşındı.
- Hedef klasörde bağımsız `.venv` ve kilitli bağımlılıklar kuruldu.
- 20 otomatik test geçti; bozuk bağımlılık yok (`pip check`).
- Gerçek terminal bağlantı kontrolü kontrollü biçimde `IPC timeout` döndürdü. Terminal açık ve broker hesabı bağlıyken broker sembol adlarının son kullanıcı oturumunda doğrulanması gerekir.
- Canlı grafik referans görünüm doğrultusunda yeniden işlendi: AURUM trendi, gerçek seans yüksek/düşük kutuları, BOS/CHoCH ve likidite olayları, aktif FVG/IFVG/OB bölgeleri, destek/direnç, sinyal işlem planı ve sağ durum paneli aynı etkileşimli tuvale bağlandı.
- Grafik katmanları iki kompakt satıra ayrıldı; EMA/VWAP yardımcı seçime taşındı, uzak görünümde otomatik etiket sadeleştirme ve çift tıkla görünüm sıfırlama eklendi.
- Backtest'e son bakiye, net parasal K/Z, parasal drawdown, toplam R, işlem K/Z'si ve işlem sonrası bakiye eklendi; yüzlerce uyarının arayüz genişliğini bozması engellendi.
- Dashboard fırsat sıralamalı Piyasa Radarı ve M1–D1 ısı haritası olarak yeniden tasarlandı; radar satırından canlı grafiğe geçiş eklendi.
- Analiz ve backtest için tekilleştirilmiş SQLite Rapor Defteri, ayrıntı görünümü, kişisel not ve etiket mekanizması tamamlandı.
- Veri sağlayıcı sözleşmesi ayrıştırıldı; BTCUSD/ETHUSD anahtarsız Binance Public, metal/FX/CFD ise salt-okunur MT5 hattına yönlendirildi.
- Gerçek BTCUSD M15 bağlantısında 2.499 kapanmış + 1 açık mum, sağlıklı kalite raporu ve aynı analiz motorunun çalıştığı doğrulandı.
- Backtest işlemlerine MFE/MAE ve sinyal anı özellikleri eklendi; yön, kurulum ve seans bazında kanıt üreten deterministik strateji teşhisi hazırlandı.
- Canlı analizde ek sağlayıcı çağrısı yapmadan kapanmış mumlardan H1/H4/D1 üst zaman dilimi projeksiyonu üretildi ve grafik durum paneline bağlandı.
- Grafik katmanları, izleme listesi, son sekme ve temel backtest tercihleri QSettings ile kalıcı hale getirildi; normal oturum/işçi hataları loglanmaya başladı.
- Gerçek açık-mum oturumunda durum panelinin boş `structure_bias` okumasıyla kapanmasına yol açan hata logdan yakalandı; panel kapanmış analiz satırına sabitlendi ve açık-mum regresyon testi eklendi.
