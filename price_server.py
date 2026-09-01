#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""주가 서버 — 평가앱이 직접 불러다 쓰는 작은 서버.

쓰는 법
    1) pip install pykrx yfinance
    2) python3 price_server.py
    3) 평가앱에서 종목코드를 넣고 '주가 자동 수집'을 누른다.

브라우저가 야후나 한국거래소를 직접 부르면 CORS 정책에 막힙니다.
이 서버는 내 컴퓨터에서 대신 받아 브라우저에 넘겨주는 역할만 합니다.
받아오는 것은 종가뿐이고 아무것도 저장하지 않습니다.

멈추려면 Ctrl+C 를 누르십시오.
"""
import datetime as dt, json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 8765

def via_pykrx(code, d1, d2):
    from pykrx import stock
    df = stock.get_market_ohlcv(d1.strftime("%Y%m%d"), d2.strftime("%Y%m%d"), code)
    if df is None or df.empty:
        raise RuntimeError("자료 없음")
    return [(i.strftime("%Y-%m-%d"), float(v)) for i, v in df["종가"].items() if v > 0], "한국거래소"

def via_yf(sym, d1, d2):
    import yfinance as yf
    df = yf.download(sym, start=d1, end=d2 + dt.timedelta(days=1),
                     progress=False, auto_adjust=True)
    if df is None or df.empty:
        raise RuntimeError("자료 없음")
    col = "Close" if "Close" in df else df.columns[0]
    s = df[col].dropna()
    return [(i.strftime("%Y-%m-%d"), float(v)) for i, v in s.items() if v > 0], f"야후 ({sym})"

def collect(code, days, market):
    d2 = dt.date.today()
    d1 = d2 - dt.timedelta(days=int(days * 1.7) + 20)
    errs = []
    if code.isdigit():
        try:
            return via_pykrx(code, d1, d2)
        except Exception as e:
            errs.append(f"한국거래소 {e}")
    sufs = [""] if not code.isdigit() else ([f".{market}"] if market else [".KQ", ".KS"])
    for suf in sufs:
        try:
            return via_yf(code + suf, d1, d2)
        except Exception as e:
            errs.append(f"야후{suf} {e}")
    raise RuntimeError(" / ".join(errs) or "수집 실패")

class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/ping":
            return self._send(200, {"ok": True, "name": "주가 서버"})
        if u.path != "/px":
            return self._send(404, {"error": "경로가 없습니다"})
        q = parse_qs(u.query)
        code = (q.get("code") or [""])[0].strip()
        days = int((q.get("days") or ["250"])[0])
        market = (q.get("market") or [""])[0].strip()
        if not code:
            return self._send(400, {"error": "종목코드가 없습니다"})
        try:
            px, src = collect(code, days, market)
            px = px[-days:]
            print(f"  {code} → {src} · {len(px)}개 · {px[0][0]} ~ {px[-1][0]}")
            return self._send(200, {"source": src,
                                    "rows": [{"d": d, "c": round(c, 4)} for d, c in px]})
        except Exception as e:
            print(f"  {code} 실패: {e}")
            return self._send(502, {"error": str(e)})

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    try:
        import pykrx  # noqa
    except ImportError:
        print("pykrx 가 없습니다. 국내 종목은 야후로만 받습니다. (pip install pykrx)")
    try:
        import yfinance  # noqa
    except ImportError:
        print("yfinance 가 없습니다. (pip install yfinance)")
    print(f"주가 서버 실행 중 · http://127.0.0.1:{PORT}")
    print("평가앱을 열고 '주가 자동 수집'을 누르십시오. 멈추려면 Ctrl+C.")
    try:
        HTTPServer(("127.0.0.1", PORT), H).serve_forever()
    except KeyboardInterrupt:
        print("\n종료했습니다.")
