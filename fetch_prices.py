#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""주가 수집 — 평가앱에 붙여넣을 종가 자료를 만든다.

사용법
    python3 fetch_prices.py 057680 --days 250
    python3 fetch_prices.py 057680 --from 2024-04-01 --to 2025-03-31
    python3 fetch_prices.py AAPL --source yfinance

수집 순서
    1) pykrx    국내 종목. 한국거래소 공식 자료라 배당·액면분할 수정이 반영된 종가를 준다.
    2) yfinance 국내외 공통. 국내는 코스피 .KS, 코스닥 .KQ를 자동으로 시도한다.

설치
    pip install pykrx yfinance

산출
    화면에 「날짜  종가」를 출력하고 prices_<종목>.txt 로 저장한다.
    파일을 열어 전체 복사한 뒤 평가앱의 주가 칸에 붙여넣으면 된다.
"""
import argparse, datetime as dt, sys, math

def log(*a): print(*a, file=sys.stderr)

def via_pykrx(code, d1, d2):
    from pykrx import stock
    df = stock.get_market_ohlcv(d1.strftime("%Y%m%d"), d2.strftime("%Y%m%d"), code)
    if df is None or df.empty: raise RuntimeError("자료 없음")
    return [(i.strftime("%Y-%m-%d"), float(v)) for i, v in df["종가"].items() if v > 0]

def via_yf(sym, d1, d2):
    import yfinance as yf
    df = yf.download(sym, start=d1, end=d2 + dt.timedelta(days=1),
                     progress=False, auto_adjust=True)
    if df is None or df.empty: raise RuntimeError("자료 없음")
    col = "Close" if "Close" in df else df.columns[0]
    ser = df[col].dropna()
    return [(i.strftime("%Y-%m-%d"), float(v)) for i, v in ser.items() if v > 0]

def collect(code, d1, d2, source):
    order = []
    if source in ("auto", "pykrx") and code.isdigit(): order.append("pykrx")
    if source in ("auto", "yfinance"): order.append("yfinance")
    if not order: order = ["yfinance"]
    for s in order:
        try:
            if s == "pykrx":
                log(f"[pykrx] {code} 조회")
                return via_pykrx(code, d1, d2), "pykrx"
            for suf in (["", ".KQ", ".KS"] if code.isdigit() else [""]):
                sym = code + suf
                try:
                    log(f"[yfinance] {sym} 조회")
                    return via_yf(sym, d1, d2), f"yfinance ({sym})"
                except Exception as e:
                    log(f"  실패: {e}")
        except ImportError:
            log(f"  {s} 미설치 — 건너뜀")
        except Exception as e:
            log(f"  실패: {e}")
    raise SystemExit("수집 실패. 종목코드와 설치 상태를 확인하십시오.")

def stats(px, days=250, drop_outlier=True):
    """평가앱과 같은 방식으로 변동성을 계산해 대조용으로 보여준다."""
    r = [math.log(px[i][1] / px[i-1][1]) for i in range(1, len(px))]
    if len(r) < 10: return None
    def med(a):
        b = sorted(a); h = len(b) // 2
        return b[h] if len(b) % 2 else (b[h-1] + b[h]) / 2
    use, removed, lo, hi = r, 0, None, None
    if drop_outlier:
        M = med(r); mad = med([abs(x - M) for x in r]) * 1.4826
        lo, hi = M - 3*mad, M + 3*mad
        use = [x for x in r if lo <= x <= hi]; removed = len(r) - len(use)
    m = sum(use) / len(use)
    sd = math.sqrt(sum((x - m) ** 2 for x in use) / (len(use) - 1))
    return dict(n=len(r), removed=removed, lo=lo, hi=hi,
                daily=sd, annual=sd * math.sqrt(days))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code", help="종목코드 (국내 6자리) 또는 티커")
    ap.add_argument("--days", type=int, default=250, help="영업일 기준 조회 일수")
    ap.add_argument("--from", dest="d1", help="시작일 YYYY-MM-DD")
    ap.add_argument("--to", dest="d2", help="종료일 YYYY-MM-DD")
    ap.add_argument("--source", choices=["auto", "pykrx", "yfinance"], default="auto")
    ap.add_argument("--trading-days", type=int, default=250, help="연환산 거래일수")
    ap.add_argument("--keep-outlier", action="store_true", help="이상치를 제거하지 않는다")
    a = ap.parse_args()

    d2 = dt.date.fromisoformat(a.d2) if a.d2 else dt.date.today()
    d1 = dt.date.fromisoformat(a.d1) if a.d1 else d2 - dt.timedelta(days=int(a.days * 1.6))

    px, src = collect(a.code, d1, d2, a.source)
    px = px[-a.days:] if not a.d1 else px

    fn = f"prices_{a.code}.txt"
    with open(fn, "w", encoding="utf-8") as f:
        for d, v in px: f.write(f"{d}\t{v:.2f}\n")

    print(f"\n출처 {src} · 기간 {px[0][0]} ~ {px[-1][0]} · {len(px)}개")
    print(f"저장 {fn}  — 파일을 열어 전체 복사한 뒤 평가앱 주가 칸에 붙여넣으십시오.\n")

    s = stats(px, a.trading_days, not a.keep_outlier)
    if s:
        print("참고 — 평가앱과 같은 방식으로 계산한 변동성")
        print(f"  연 변동성   {s['annual']*100:.2f}%")
        print(f"  일 변동성   {s['daily']*100:.2f}%")
        print(f"  관측        {s['n']}개" +
              (f" · 이상치 {s['removed']}개 제거" if s['removed'] else ""))
        if s['lo'] is not None:
            print(f"  정상범위    {s['lo']*100:.2f}% ~ {s['hi']*100:.2f}%")
    print("\n앞 5줄")
    for d, v in px[:5]: print(f"  {d}\t{v:,.2f}")

if __name__ == "__main__":
    main()
