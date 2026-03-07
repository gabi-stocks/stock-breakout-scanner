import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# פונקציה להשגת רשימת מניות (S&P 500 ו-Nasdaq 100)
def get_tickers():
    tickers =
    try:
        sp500 = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies").tolist()
        nasdaq = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")[1].tolist()
        tickers = list(set([t.replace('.', '-') for t in sp500 + nasdaq]))
    except:
        tickers = # גיבוי למקרה של שגיאה
    return tickers

# פונקציית הניתוח הטכני
def check_stock(ticker):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if len(df) < 100: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        # חישוב מדדים: RSI, ממוצעים, בולינגר
        df['MA50'] = ta.sma(df['Close'], length=50)
        df['MA200'] = ta.sma(df['Close'], length=200)
        df['VOL_MA20'] = ta.sma(df['Volume'], length=20)
        df = ta.rsi(df['Close'], length=14)
        bb = ta.bbands(df['Close'], length=20, std=2)
        df = pd.concat([df, bb], axis=1)

        curr = df.iloc[-1]
        local_high = df['High'].iloc[-11:-1].max() # שיא של 10 ימים
        
        # תנאי הפריצה: נפח חריג (>150%), RSI חזק (>60), פריצת שיא מקומי או בולינגר סקוויז
        vol_ok = curr['Volume'] > (curr['VOL_MA20'] * 1.5)
        rsi_ok = curr > 60
        price_ok = curr['Close'] > local_high
        trend_ok = curr['Close'] > curr['MA50'] > curr['MA200']
        is_squeeze = ((curr.iloc[:, -3] - curr.iloc[:, -5]) / curr['Close']) < 0.05

        if (vol_ok and rsi_ok and price_ok and trend_ok) or (is_squeeze and price_ok):
            return {"Ticker": ticker, "Price": round(float(curr['Close']), 2), "RSI": round(float(curr), 2), "Status": "BREAKOUT" if not is_squeeze else "SQUEEZE"}
    except: return None

def main():
    tickers = get_tickers()
    print(f"Scanning {len(tickers)} stocks...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        found = list(executor.map(check_stock, tickers))
    results = [f for f in found if f is not None]
    if results:
        df_final = pd.DataFrame(results)
        df_final.to_csv("scan_results.csv", index=False)
        print("Results saved to scan_results.csv")

if __name__ == "__main__":
    main()
