# 26 gösterge incelemesi ve seçim

Arşivdeki 26 Pine Script toplam 8.081 satırdır. Kodlar doğrudan kopyalanmaz; kavramlar tek, test edilebilir ve kapanmış-mum semantiğine sahip Python hesaplarına dönüştürülür.

## Çekirdek olarak kullanılacaklar

- **Market Structure CHoCH/BOS + Smart Money Concepts + ICT Concepts:** tek bir yapı motorunda pivot, internal/swing BOS ve CHoCH.
- **Buyside & Sellside Liquidity + Liquidity Swings/Pools:** eşit tepe/dip, önceki gün ve seans seviyeleri, sweep/break ayrımı.
- **FVG Sessions + IFVG:** ATR filtresi olan FVG yaşam döngüsü, mitigation ve tersine dönen FVG.
- **Order Block Detector + Breaker Blocks:** yapı kırılımına bağlı son karşıt mum bölgesi; yalnızca güncel ve yakın bölgeler.
- **Sessions:** Tokyo/Londra/New York aralıkları, günlük ve seans VWAP, seans yüksek/düşükleri.
- **Range Detector + Predictive Ranges:** ATR tabanlı sıkışma/rejim ve uyarlanan fiyat aralığı.
- **Ultimate RSI:** momentum bağlamı; tek başına sinyal değildir.
- **Support/Resistance + Pivot/Missed Reversal:** hedef, stop ve geçersizlik seviyeleri.
- **Volume/Money Flow:** MT5 tick volume olduğu açıkça belirtilerek göreli hacim ve katılım puanı.

## İsteğe bağlı ve sade gösterilecekler

- **Three Bar Reversal:** sadece yapı/likidite yakınında teyit.
- **Nadaraya-Watson Envelope:** yalnızca geçmiş veriyi kullanan, repaint etmeyen sürüm.
- **LTF Activity Heatmap:** dashboard ayrıntısı; fiyat grafiği üzerine bindirilmez.
- **Money Flow Profile / Volume Heatmap:** seçili aralığın yan panel özeti; varsayılan grafikte kapalı.

## Varsayılan dışı bırakılanlar

- **McDonald's Pattern:** ana stratejiyle nedensel bağı zayıf ve ek görsel gürültü üretir.
- **FVG Instantaneous Mitigation Signals:** FVG yaşam döngüsüyle çakışır; ayrı sinyal üretmesi çift sayım yaratır.
- **Reversal Signals:** çok sayıda faz/işaret üretir; yapı ve likidite motoruyla örtüşür.
- **Swing Highs/Lows & Candle Patterns:** bağımsız katman yerine yapı motoruna veri sağlar.
- **Repainting Nadaraya seçeneği:** canlı/backtest eşitliğini bozar.
- **Volume Bubbles:** grafik kalabalığı nedeniyle varsayılan görünümde kullanılmaz.

## Grafik varsayılanı

Mumlar + EMA20/EMA50 + VWAP gösterilir. Son iki aktif FVG/OB bölgesi, en yakın destek/direnç ve en son geçerli sinyal dışında etiket basılmaz. RSI, ATR, ADX ve göreli hacim fiyat grafiği yerine analiz panelinde sunulur.
