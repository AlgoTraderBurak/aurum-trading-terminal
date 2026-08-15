# AURUM Terminal

AURUM; MT5 ve halka açık kripto sağlayıcısından salt-okunur piyasa verisi alan, aynı hesap motorunu canlı analiz ve backtest için kullanan dört sekmeli Türkçe masaüstü analiz uygulamasıdır.

## Sekmeler

1. **Canlı Grafik** — seans, yapı, likidite, bölge, trend ve işlem planı katmanlarına sahip etkileşimli mum grafiği.
2. **Analiz / Yorum / Sinyal** — piyasa rejimi, yapı, momentum, likidite, risk planı, karar gerekçeleri ve kalıcı Rapor Defteri.
3. **Dashboard** — BTC, ETH, XAU, XAG ve isteğe bağlı FX/CFD ürünleri için fırsat sıralamalı piyasa radarı ve MTF ısı haritası.
4. **Backtest** — aynı sinyal motoruyla maliyet, muhafazakâr mum içi dolum, parasal bakiye ve işlem dökümü.

## Hızlı başlangıç

1. Metal/FX/CFD kullanacaksanız MetaTrader 5 terminalini açın ve hesabınıza giriş yapın; yalnızca BTC/ETH için MT5 gerekmez.
2. `KURULUM.bat` dosyasını bir kez çalıştırın.
3. `AURUM.bat` dosyasını çalıştırın.

Uygulama hiçbir emir göndermez. MT5 entegrasyonu yalnızca piyasa verisi ve sembol özelliklerini; kripto entegrasyonu yalnızca halka açık mum verisini okur.

## Geliştirici komutları

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m app.main
```

Mimari ve gösterge seçimlerinin gerekçesi `docs/` klasöründedir.
