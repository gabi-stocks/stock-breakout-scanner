import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

def get_tickers():
    tickers =
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # S&P 500
        sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        sp_tables = pd.read_html(requests.get(sp500_url, headers=headers).text)
        tickers.extend(sp_tables.tolist())
        # Nasdaq 100
        ndx_url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        ndx_tables = pd.read_html(requests.get(ndx_url, headers=headers).text)
        for table in ndx_tables:
            if 'Ticker' in table.columns:
                tickers.extend(table.tolist())
                break
        tickers = list(set([str(t).replace('.', '-') for t in tickers]))
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        tickers = # רשימת גיבוי
    return tickers

def check_stock(ticker):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty or len(df) < 100: return None
        
        # תיקון MultiIndex של yfinance החדש
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # חישוב מדדים טכניים לפי הפרופיל שזיהינו (כמו ב-QBTS ו-ASTS)
        df['MA50'] = ta.sma(df['Close'], length=50)
        df['MA200'] = ta.sma(df['Close'], length=200)
        df['VOL_MA20'] = ta.sma(df['Volume'], length=20)
        df = ta.rsi(df['Close'], length=14)
        
        bbands = ta.bbands(df['Close'], length=20, std=2)
        df = pd.concat([df, bbands], axis=1)

        curr = df.iloc[-1]
        local_high = df['High'].iloc[-11:-1].max() # שיא של 10 ימים
        
        # תנאים לפריצה (Breakout):
        # 1. נפח חריג (מעל 150% מהממוצע)
        vol_ok = curr['Volume'] > (curr['VOL_MA20'] * 1.5)
        # 2. מומנטום שורי (RSI מעל 60)
        rsi_ok = curr > 60
        # 3. מחיר מעל התנגדות (שיא מקומי)
        price_ok = curr['Close'] > local_high
        # 4. מגמה ארוכת טווח (מחיר > MA50 > MA200)
        trend_ok = curr['Close'] > curr['MA50'] and curr['MA50'] > curr['MA200']
        
        # זיהוי Squeeze (רצועות בולינגר צרות מ-5% - סימן לפני התפרצות)
        bb_width = (df.iloc[-1, -1] - df.iloc[-1, -3]) / curr['Close']
        is_squeeze = bb_width < 0.05

        if (vol_ok and rsi_ok and price_ok and trend_ok) or (is_squeeze and price_ok):
            return {
                "Ticker": ticker,
                "Price": round(float(curr['Close']), 2),
                "RSI": round(float(curr), 2),
                "Vol_Ratio": round(float(curr['Volume'] / curr['VOL_MA20']), 2),
                "Status": "STRONG_BREAKOUT" if not is_squeeze else "SQUEEZE_ALERT"
            }
    except: return None

def main():
    tickers = get_tickers()
    print(f"Scanning {len(tickers)} stocks...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        found = list(executor.map(check_stock, tickers))
    
    results = [f for f in found if f is not None]
    df_final = pd.DataFrame(results if results else)
    df_final.to_csv("scan_results.csv", index=False)
    print(f"Done. Found {len(results)} matches.")

if __name__ == "__main__":
    main()
