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
        # השגת מניות S&P 500
        sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        sp_tables = pd.read_html(requests.get(sp500_url, headers=headers).text)
        tickers.extend(sp_tables.tolist())
        
        # השגת מניות Nasdaq 100
        ndx_url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        ndx_tables = pd.read_html(requests.get(ndx_url, headers=headers).text)
        for table in ndx_tables:
            if 'Ticker' in table.columns:
                tickers.extend(table.tolist())
                break
            if 'Symbol' in table.columns:
                tickers.extend(table.tolist())
                break
        
        # ניקוי כפילויות ותיקון פורמט (נקודה במקום מקף עבור Yahoo)
        tickers = list(set([str(t).replace('.', '-') for t in tickers]))
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        # רשימת גיבוי של מניות מובילות במקרה שויקיפדיה חסומה
        tickers =
    return tickers

def check_stock(ticker):
    try:
        # הורדת נתונים - שנה אחורה לטובת ממוצעים ארוכים
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty or len(df) < 100: return None
        
        # טיפול במבנה נתונים MultiIndex של yfinance החדש
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # חישוב מדדים: RSI, ממוצעים, בולינגר
        df['MA50'] = ta.sma(df['Close'], length=50)
        df['MA200'] = ta.sma(df['Close'], length=200)
        df['VOL_MA20'] = ta.sma(df['Volume'], length=20)
        df = ta.rsi(df['Close'], length=14)
        
        # רצועות בולינגר לזיהוי Squeeze (דחיסה)
        bbands = ta.bbands(df['Close'], length=20, std=2)
        if bbands is None: return None
        df = pd.concat([df, bbands], axis=1)

        curr = df.iloc[-1]
        local_high = df['High'].iloc[-11:-1].max() # שיא של 10 ימים אחרונים
        
        # תנאי פריצה (מבוסס על המניות QBTS, ASTS ו-DE שניתחנו):
        # 1. מחיר מעל התנגדות (שיא מקומי)
        price_ok = curr['Close'] > local_high
        # 2. נפח חריג (מעל 150% מהממוצע) - אישור כסף מוסדי
        vol_ok = curr['Volume'] > (curr['VOL_MA20'] * 1.5)
        # 3. מומנטום שורי (RSI מעל 60)
        rsi_ok = curr > 60
        # 4. יישור מגמה (מחיר > MA50 > MA200)
        trend_ok = curr['Close'] > curr['MA50'] and curr['MA50'] > curr['MA200']
        
        # זיהוי Squeeze (רוחב רצועות בולינגר צר מ-5% - שקט לפני סערה)
        # שמות העמודות ב-pandas_ta הם בד"כ BBL_20_2.0 ו-BBU_20_2.0
        is_squeeze = ((df.iloc[-1, -1] - df.iloc[-1, -3]) / curr['Close']) < 0.05

        if (price_ok and vol_ok and rsi_ok and trend_ok) or (is_squeeze and price_ok):
            return {
                "Ticker": ticker,
                "Price": round(float(curr['Close']), 2),
                "RSI": round(float(curr), 2),
                "Vol_Ratio": round(float(curr['Volume'] / curr['VOL_MA20']), 2),
                "Status": "BREAKOUT" if not is_squeeze else "SQUEEZE_ALERT"
            }
    except:
        return None

def main():
    tickers = get_tickers()
    print(f"Starting scan on {len(tickers)} stocks...")
    
    # שימוש ב-Threadpool להאצת הסריקה
    with ThreadPoolExecutor(max_workers=5) as executor:
        found = list(executor.map(check_stock, tickers))
    
    results = [f for f in found if f is not None]
    df_final = pd.DataFrame(results if results else)
    
    # שמירה לקובץ
    df_final.to_csv("scan_results.csv", index=False)
    print(f"Success! Found {len(results)} potential breakouts.")
    if not df_final.empty:
        print(df_final.to_string())

if __name__ == "__main__":
    main()
