# Kullanım kılavuzu

## İlk açılış

1. Metal, FX ve CFD için MetaTrader 5 terminalini normal şekilde açın ve broker hesabına giriş yapın. BTC/ETH için MT5 gerekmez.
2. Market Watch içinde incelemek istediğiniz sembollerin görünür olduğundan emin olun.
3. `AURUM.bat` dosyasına çift tıklayın.

MT5 kapalıysa metal/FX/CFD ürünleri bağlantı hatası gösterir. BTCUSD ve ETHUSD, anahtar gerektirmeyen salt-okunur kripto sağlayıcısından alınır. Daha önce alınmış sağlıklı veri varsa “Önbellek” kaynağıyla okunabilir; uygulama asla demo veri üretmez.

## Canlı Grafik

- Sembol kutusu broker sembolünü doğrudan kabul eder; `XAUUSD.m` gibi özel isimler yazılabilir.
- BTCUSD ve ETHUSD halka açık kripto verisine; XAUUSD, XAGUSD ve diğer ürünler MT5'e yönlendirilir. Kullanılan gerçek sembol ve kaynak bağlantı satırında görünür.
- M1, M5, M15, H1, H4 ve D1 desteklenir.
- Açık mum yalnızca grafikte görünür ve sarı kesikli çerçeveyle ayrılır; sinyal hesabına katılmaz.
- Fare tekeri bar sayısını, sürükleme görüntülenen tarih aralığını değiştirir.
- AURUM trendi, seans yüksek/düşük kutuları, BOS/CHoCH, likidite süpürmeleri, aktif bölgeler, seviyeler ve sağ durum paneli ayrı ayrı açılıp kapatılabilir.
- EMA/VWAP yardımcı seçimi varsayılan görünümü kalabalıklaştırmadan açılır; çift tık görünümü sıfırlar.
- Sağ paneldeki üst zaman dilimi yönleri seçili verinin yalnızca tamamlanmış üst-TF mumlarından türetilir; gelecekteki veya açık üst-TF mumu kullanılmaz.

## Analiz / Yorum / Sinyal

Piyasa yapısı, EMA konumu, günlük VWAP, RSI, ADX, göreli tick hacmi, ATR rejimi, likidite zinciri ve aktif bölgeler tek yorumda birleştirilir. Her sinyalin puanı, kurulum türü, fiyat seviyeleri, gerekçeleri, uyarıları ve geçersizlik koşulu görülebilir.

`İZLE`, yön fikrinin oluştuğunu fakat risk/teyit şartlarının tamamlanmadığını belirtir. `AL` ve `SAT` yatırım garantisi değildir; yalnızca tanımlı ve test edilmiş koşulların kapanmış mumda birleşmesidir.

### Rapor Defteri

Analiz ekranındaki **Rapor Defteri**, her yeni kapanmış mum analizini ve çalıştırılan backtest'i kalıcı olarak saklar. Aynı kapanmış mum yeniden okunursa ikinci bir kayıt oluşmaz. Kayıt seçilerek hesap özeti görülebilir; kişisel not ve virgülle ayrılmış etiketler eklenebilir.

## Dashboard

Virgülle ayrılmış semboller girilebilir. Piyasa Radarı üst zaman dilimlerine daha fazla ağırlık vererek MTF yön, hizalanma, güncel sinyal, rejim, seans, volatilite ve veri zamanını tek satırda sıralar. Alt bölümde ayrıntılı M1–D1 ısı haritası korunur. Radar satırına çift tıklamak ilgili sembol ve zaman dilimini Canlı Grafik'te açar.

## Backtest

- Seçili canlı veri ve aynı AnalysisEngine kullanılır.
- Sinyal mumunun ardından gelen mumun açılışında işleme girilir.
- Aynı mum içinde stop ve hedefin ikisi de görülürse muhafazakâr biçimde stop kabul edilir.
- Spread, slippage ve komisyon kullanıcı tarafından broker değerlerine göre girilmelidir.
- MT5 tick value ve lot adımı bulunursa pozisyon büyüklüğü broker kurallarına göre hesaplanır. Bu bilgi yoksa sonuçta açık uyarı yer alır.
- Son bakiye, net parasal kâr/zarar, parasal/yüzdesel drawdown, toplam R ve her işlem sonrası bakiye birlikte gösterilir.
- Para birimi yalnızca rapor gösterimidir; kontrat ve tick değerlerinin doğruluğu yine veri sağlayıcısına bağlıdır.
- Strateji teşhisi; örneklem büyüklüğü, MFE/MAE, yön, kurulum ve seans gruplarını inceler. Bu bölüm otomatik parametre değiştirmez ve önerilerin out-of-sample doğrulanması gerektiğini açıkça belirtir.

## Güvenlik sınırı

Uygulamada emir gönderme, pozisyon açma/kapatma veya hesap değiştirme kodu yoktur. MT5 entegrasyonu yalnızca `initialize`, sembol bilgisi ve `copy_rates_from_pos` piyasa verisi çağrılarını kullanır.
