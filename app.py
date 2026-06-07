from flask import Flask, jsonify
from flask_cors import CORS
import requests
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
import time

app = Flask(__name__)
CORS(app)

def fetch_twse_stock_list():
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.encoding = "big5"
        tables = pd.read_html(res.text)
        df = tables[0]
        df.columns = df.iloc[0]
        df = df.iloc[1:]
        stocks = []
        for _, row in df.iterrows():
            raw = str(row.iloc[0]).strip()
            parts = raw.split("\u3000")
            if len(parts) >= 2:
                code = parts[0].strip()
                name = parts[1].strip()
                if len(code) == 4 and code.isdigit():
                    stocks.append((code, name))
        return stocks
    except Exception as e:
        return []

def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_macd(closes, fast=10, slow=20, signal=10):
    dif = calc_ema(closes, fast) - calc_ema(closes, slow)
    dea = calc_ema(dif, signal)
    return dif - dea

def calc_sma(closes, period):
    return closes.rolling(window=period).mean()

def screen_stock(code, name):
    ticker = f"{code}.TW"
    try:
        end = datetime.today()
        start = end - timedelta(days=100)
        df = yf.download(ticker,
                         start=start.strftime("%Y-%m-%d"),
                         end=end.strftime("%Y-%m-%d"),
                         progress=False,
                         auto_adjust=True)
        if df.empty or len(df) < 22:
            return None
        closes = df["Close"].squeeze()
        last_price = round(float(closes.iloc[-1]), 2)
        ma5  = calc_sma(closes, 5)
        ma10 = calc_sma(closes, 10)
        ma18 = calc_sma(closes, 18)
        hist = calc_macd(closes, 10, 20, 10)
        m5_t,  m10_t,  m18_t = ma5.iloc[-1],  ma10.iloc[-1],  ma18.iloc[-1]
        m5_y,  m10_y,  m18_y = ma5.iloc[-2],  ma10.iloc[-2],  ma18.iloc[-2]
        h_today = hist.iloc[-1]
        h_prev  = hist.iloc[-2]
        h_prev2 = hist.iloc[-3]
        cond_align = bool(m5_t > m10_t > m18_t)
        cond_slope = bool((m5_t > m5_y) and (m10_t > m10_y) and (m18_t > m18_y))
        cond_macd  = bool((h_prev2 < 0) and (h_prev > 0) and (h_today > 0))
        if cond_align and cond_slope and cond_macd:
            return {"code": code, "name": name, "price": last_price}
        return None
    except Exception:
        return None

@app.route("/screen", methods=["GET"])
def screen():
    stock_list = fetch_twse_stock_list()
    if not stock_list:
        return jsonify({"error": "無法取得股票清單"}), 500
    results = []
    for code, name in stock_list:
        result = screen_stock(code, name)
        if result:
            results.append(result)
        time.sleep(0.3)
    return jsonify({"date": datetime.today().strftime("%Y-%m-%d"), "results": results})

@app.route("/")
def index():
    return "台股篩選器 API 運行中"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
