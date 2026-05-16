import yfinance as yf
import pandas as pd
import datetime
import requests
import time
import warnings
warnings.filterwarnings("ignore")

def get_tickers():
    """משיכת מניות מדד נאסדק, S&P 500 ודאו ג'ונס תוך מניעת חסימה"""
    tickers = []
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        # S&P 500
        sp500 = pd.read_html(requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers).text)[0]['Symbol'].tolist()
        # Nasdaq 100
        nasdaq = pd.read_html(requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers).text)[4]['Ticker'].tolist()
        # Dow Jones
        dow = pd.read_html(requests.get('https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average', headers=headers).text)[1]['Symbol'].tolist()
        
        tickers = list(set(sp500 + nasdaq + dow))
        return [str(t).replace('.', '-') for t in tickers]
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        return ["AAPL", "MSFT", "NVDA", "TSLA", "META"] # Fallback

def check_insider_selling(ticker):
    """בדיקה האם הייתה מכירת אינסיידרים בחצי השנה האחרונה"""
    try:
        stock = yf.Ticker(ticker)
        insider = stock.insider_transactions
        if insider is not None and not insider.empty:
            # סינון לחצי שנה האחרונה
            six_months_ago = pd.Timestamp.now() - pd.DateOffset(months=6)
            # בחלק מגרסאות yfinance עמודת התאריך נקראת 'Start Date'
            date_col = 'Start Date' if 'Start Date' in insider.columns else insider.columns[0]
            recent_insider = insider[insider[date_col] > six_months_ago]
            
            sell_transactions = recent_insider[recent_insider['Text'].str.contains('Sale|Sell', case=False, na=False)]
            if not sell_transactions.empty:
                return "<span style='color:#e74c3c; font-weight:bold;'>⚠️ Yes</span>"
        return "<span style='color:#7f8c8d;'>No</span>"
    except:
        return "Unknown"

def run_pro_scanner():
    print("Starting Pro Breakout Scanner...")
    tickers = get_tickers()
    results = []
    print(f"Total unique tickers to scan: {len(tickers)}")

    # הורדת נתונים מרוכזת (Bulk) למניעת חסימות IP של Yahoo
    batch_size = 100
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}...")
        
        # מורידים נתונים ל-7 חודשים (כדי שיהיה מספיק לחישוב 150 ימי מסחר + 3 חודשים אחורה)
        data = yf.download(batch, period="7m", interval="1d", progress=False, threads=True)
        time.sleep(1) # השהייה למניעת חסימה
        
        if data.empty: continue

        for ticker in batch:
            try:
                # סידור הנתונים עבור מניה בודדת בתוך הורדת ה-Bulk
                if len(batch) > 1:
                    df = data.xs(ticker, level=1, axis=1).dropna()
                else:
                    df = data.dropna()

                if len(df) < 155: continue

                close_prices = df['Close']
                high_prices = df['High']
                low_prices = df['Low']
                volumes = df['Volume']
                
                current_price = float(close_prices.iloc[-1])
                
                # חישוב ממוצעים
                ma10 = close_prices.rolling(10).mean().iloc[-1]
                ma50 = close_prices.rolling(50).mean().iloc[-1]
                ma150 = close_prices.rolling(150).mean().iloc[-1]
                
                # 1. תנאי ירידה של 21% ב-3 חודשים (כ-63 ימי מסחר)
                price_3m_ago = float(close_prices.iloc[-63])
                drop_3m = ((current_price - price_3m_ago) / price_3m_ago) * 100
                drop_flag = "<b>+</b>" if drop_3m <= -21 else ""

                # 2. חישוב RVOL שבועיים (10 ימי מסחר)
                avg_vol_2w = volumes.rolling(10).mean().iloc[-1]
                rvol = float(volumes.iloc[-1] / avg_vol_2w) if avg_vol_2w > 0 else 0
                if rvol < 1.2: continue # סינון א: חובה RVOL > 1.2

                # 3. דשדוש של 4 שבועות (20 ימי מסחר) - טווח מקסימלי של 8%
                last_20_high = high_prices.tail(20).max()
                last_20_low = low_prices.tail(20).min()
                consolidation_range = ((last_20_high - last_20_low) / last_20_low) * 100
                if consolidation_range > 8: continue # סינון ב: לא זזה יותר מ-8%

                # 4. נגיעה ב-MA10 ו-MA50 וקירבה לפריצת MA150
                # נגיעה נגדיר כמרחק של עד 2% מהממוצע
                touch_ma10 = abs((current_price - ma10) / ma10) <= 0.02
                touch_ma50 = abs((current_price - ma50) / ma50) <= 0.02
                # קרובה לפריצת 150: נמצאת קצת מתחתיו או פרצה אותו הרגע (טווח -5% עד +2%)
                near_breakout_150 = -0.05 <= ((current_price - ma150) / ma150) <= 0.02
                
                if not (touch_ma10 and touch_ma50 and near_breakout_150): continue # סינון ג

                # 5. כסף מוסדי (Institutional Accumulation)
                # Proxy: ווליום בימי עליות ב-20 הימים האחרונים גבוה ב-20% מהווליום בימי ירידות
                recent_20_df = df.tail(20)
                up_volume = recent_20_df[recent_20_df['Close'] > recent_20_df['Open']]['Volume'].sum()
                down_volume = recent_20_df[recent_20_df['Close'] <= recent_20_df['Open']]['Volume'].sum()
                
                if up_volume <= down_volume * 1.2: continue # סינון ד: דורש איסוף מוסדי

                # רק אם המניה עברה את כל התנאים הקשוחים, נבדוק אינסיידרים (כדי לחסוך זמן ריצה)
                insider_sell = check_insider_selling(ticker)

                results.append({
                    "Ticker": f"<b><a href='https://finance.yahoo.com/quote/{ticker}' target='_blank' style='color:#1a73e8; text-decoration:none;'>{ticker}</a></b>",
                    "Price": f"${current_price:.2f}",
                    "Drop_21_Plus": drop_flag,
                    "Insider_Sell_6M": insider_sell,
                    "MA_10": f"${ma10:.2f}",
                    "MA_50": f"${ma50:.2f}",
                    "MA_150": f"${ma150:.2f}",
                    "RVOL": f"<span style='color:#27ae60; font-weight:bold;'>{rvol:.2f}</span>"
                })
            except Exception as e:
                continue

    # בניית HTML
    if results:
        df_res = pd.DataFrame(results)
        table_html = df_res.to_html(escape=False, index=False)
    else:
        table_html = "<h3 style='text-align:center;'>No stocks met the strict breakout criteria in this scan.</h3>"

    full_html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Pro Breakout Scanner</title>
        <style>
            body {{ font-family: 'Segoe UI', Arial; background: #121212; color: #ffffff; padding: 20px; }}
            .nav {{ margin-bottom: 20px; text-align: center; }}
            .nav a {{ color: #00bcd4; text-decoration: none; padding: 10px 20px; border: 1px solid #00bcd4; border-radius: 5px; margin: 0 10px; }}
            .nav a:hover {{ background: #00bcd4; color: #121212; }}
            .card {{ background: #1e1e1e; padding: 25px; border-radius: 15px; box-shadow: 0 10px 20px rgba(0,0,0,0.5); }}
            h1 {{ color: #00bcd4; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; color: #fff; }}
            th {{ background: #333; padding: 15px; text-align: left; border-bottom: 2px solid #00bcd4; }}
            td {{ padding: 15px; border-bottom: 1px solid #333; }}
            tr:hover {{ background: #2a2a2a; }}
        </style>
    </head>
    <body>
        <div class="nav">
            <a href="index.html">⬅ Back to General Scanner</a>
            <a href="breakout.html">🚀 Pro Breakout Scanner</a>
        </div>
        <div class="card">
            <h1>🚀 Institutional Breakout Scanner</h1>
            <p style="text-align:center; color:#aaa;">Searching Nasdaq, S&P 500, Dow Jones for VCP & Smart Money Accumulation<br>
            Last Scan: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
            {table_html}
        </div>
    </body>
    </html>
    """
    with open("breakout.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("Breakout scan completed!")

if __name__ == "__main__":
    run_pro_scanner()
