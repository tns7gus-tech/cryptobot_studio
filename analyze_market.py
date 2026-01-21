import pyupbit
import pandas as pd

# 5분봉 데이터 가져오기
df = pyupbit.get_ohlcv('KRW-ETH', interval='minute5', count=100)
prices = df['close']

# RSI 계산
delta = prices.diff()
gain = delta.where(delta > 0, 0.0)
loss = (-delta).where(delta < 0, 0.0)
avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))
current_rsi = float(rsi.iloc[-1])

# EMA 계산
ema9 = float(prices.ewm(span=9, adjust=False).mean().iloc[-1])
ema21 = float(prices.ewm(span=21, adjust=False).mean().iloc[-1])
current_price = float(prices.iloc[-1])

# 추세 확인
is_uptrend = current_price > ema21
is_downtrend = current_price < ema21

print('=' * 50)
print('ETH Market Analysis')
print('=' * 50)
print(f'Current Price: {current_price:,.0f} KRW')
print(f'RSI(14): {current_rsi:.1f}')
print(f'EMA9: {ema9:,.0f} KRW')
print(f'EMA21: {ema21:,.0f} KRW')
print(f'Trend: {"Uptrend" if is_uptrend else "Downtrend"}')
print()
print('Current Strategy Conditions:')
print(f'  Buy: RSI < 35 + Uptrend -> RSI={current_rsi:.1f}, Uptrend={is_uptrend}')
print(f'  Sell: RSI > 65 + Downtrend -> RSI={current_rsi:.1f}, Downtrend={is_downtrend}')
print()
if 35 <= current_rsi <= 65:
    print('WARNING: RSI is in neutral zone (35~65), no signal generated!')
    print('TIP: Relaxing conditions will generate more trades.')
elif current_rsi < 35:
    if is_uptrend:
        print('BUY SIGNAL should be generated!')
    else:
        print('RSI is oversold but not in uptrend, no buy signal.')
elif current_rsi > 65:
    if is_downtrend:
        print('SELL SIGNAL should be generated!')
    else:
        print('RSI is overbought but not in downtrend, no sell signal.')
