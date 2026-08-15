# Mimari kararlar

## Değişmez ilkeler

- Canlı analiz ile backtest aynı indikatör ve sinyal motorunu kullanır.
- Sinyal yalnızca kapanmış mumdan üretilir; açık mum grafikte ayrı işaretlenir.
- MT5 ve kripto veri katmanları salt okunurdur ve emir fonksiyonu içermez.
- Her sinyal; zaman, veri sürümü, puan, gerekçe, uyarı, giriş, stop, hedef ve geçersizlik koşulu taşır.
- Veri yoksa sentetik/demo veri üretilmez. Sağlayıcı yoksa yalnızca daha önce doğrulanmış önbellek kullanılabilir.
- Grafik varsayılan olarak en fazla üç fiyat katmanı gösterir. Ayrıntılı ölçümler analiz ve dashboard'a taşınır.

## Katmanlar

```text
PySide6 UI + QSettings
  ├─ Canlı Grafik
  ├─ Analiz / Yorum / Sinyal + Rapor Defteri
  ├─ Piyasa Radarı + MTF ısı haritası
  └─ Backtest
        ↓
ApplicationService (iş akışı, çoklu zaman dilimi)
  ├─ AnalysisEngine (tek kaynaklı indikatör + sinyal + nedensel üst-TF projeksiyonu)
  ├─ BacktestEngine (kapalı mum, maliyet, parasal bakiye, MFE/MAE)
  ├─ BacktestDiagnostics (yön/kurulum/seans kanıtı; parametre değiştirmez)
  ├─ ReportJournal → SQLite rapor/not deposu
  └─ DataService → sağlayıcı yönlendirme
       ├─ Metal / FX / CFD → MT5ReadOnlyClient → izole MT5 yardımcı süreci
       ├─ BTC / ETH → BinancePublicClient (anahtarsız, salt okunur)
       └─ doğrulanmış kapanmış mum → SQLite BarCache
```

Veri sağlayıcıları `MarketDataClient` sözleşmesini uygular. Bu nedenle ileride başka bir kripto borsası veya veri terminali eklemek analiz, grafik ve backtest motorlarını değiştirmez. Benzer biçimde yerel LLM, hesap motorunun yerine geçmeden Rapor Defteri'ndeki yapılandırılmış sonuçları yorumlayan ayrı bir servis olarak eklenebilir.

## Hata sınırları

- Veri sağlayıcı hatası kullanıcıya açıkça gösterilir; sessizce başka sembole geçilmez.
- Sembol eşleme sonucu arayüzde görünür.
- NaN, sırasız zaman, kopya bar ve OHLC tutarsızlığı sinyal üretimini durdurur.
- Hafta sonu/seans boşlukları kalite uyarısıdır; OHLC bozukluğu kritik hatadır.
- Arka plan işleri GUI iş parçacığını bloke etmez.
- MetaTrader5 yerel IPC çağrısı Python GIL'ini kilitleyebildiği için ayrı süreçte çalışır; süre aşımında veya uygulama kapanırken süreç sonlandırılır.
- Arka plan görevi hataları hem kullanıcıya gösterilir hem `logs/aurum.log` dosyasına stack trace ile yazılır.
- Analiz raporları sembol, zaman dilimi ve kapanmış mum zamanıyla tekilleştirilir; otomatik yenileme aynı kaydı çoğaltmaz.
- Üst zaman dilimi bağlamı yalnızca eldeki kapanmış mumların tamamlanmış üst-TF kovalarından türetilir; henüz kapanmamış üst-TF mumu kullanılmaz.
