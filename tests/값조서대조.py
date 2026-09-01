#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""값 조서가 엔진과 같은 숫자를 싣는지 확인한다.

값 조서는 계산이 끝난 숫자를 받아 적는 스냅샷이다. 그래도 배분표·분개·결과 시트는
`build_xlsx` 안에서 다시 조립하므로 엔진과 어긋날 수 있다. 실제로 배분표와 분개가
같은 시트 안에서 13.5 만큼 어긋난 적이 있다.

수식 조서 쪽은 `조서대조.py` 가, 머리 행 배선은 `배선대조.py` 가 본다.
엑셀을 풀지 않으므로 몇 초면 끝난다.

    python3 tests/값조서대조.py
"""
import sys, os, io, types, warnings
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_app():
    stub = types.ModuleType("streamlit"); stub.cache_data = lambda **k: (lambda f: f)
    sys.modules["streamlit"] = stub
    m = types.ModuleType("cbapp"); sys.modules["cbapp"] = m
    src = open(os.path.join(ROOT, "cb_app.py"), encoding="utf-8").read()
    exec(compile(src.split("st.set_page_config")[0], "cb_app.py", "exec"), m.__dict__)
    return m.__dict__


CASES = [(cls, km, md)
         for cls in ("equity", "liability")
         for km in (0, 1, 2)
         for md in ("TF", "GS")]


def main():
    G = load_app()
    import openpyxl
    bad = []

    def chk(tag, a, b, tol=1e-6):
        ok = a is not None and abs(a - b) < tol
        print("   %-42s %12s %12.4f  %s"
              % (tag, f"{a:.4f}" if a is not None else "없음", b,
                 "OK" if ok else "★"))
        if not ok: bad.append(tag)

    for cls, km, md in CASES:
        t = G["Terms"]()
        t.rf_curve = [(1, .0226), (3, .0240), (5, .0252)]
        t.cr_curve = [(1, .1409), (3, .1740), (5, .1905)]
        t.conv_class, t.k_method, t.model = cls, km, md
        t.face_total = 9_000_000_000
        G["derive"](t)
        full, b0, b1, b2, ca, conv = G["decompose"](t)
        rows, _ = G["allocate"](t, full, b0, b1, b2, ca)
        wb = openpyxl.load_workbook(io.BytesIO(
            G["build_xlsx"](t, full, b0, b1, b2, ca, conv, G["eir_table"](t, b0))),
            data_only=True)
        E, R = wb["회계처리"], wb["결과"]
        print(f"\n[{cls} · 방법{km} · {md}]")
        # 결과 시트 · 순차 차감
        for i, (nm, v) in enumerate([("B0 주계약", b0), ("B1 부채요소", b1),
                                     ("B2 전체", b2), ("B3 매도청구 반영", b2-ca)]):
            chk("결과 " + nm, R.cell(6+i, 3).value, v)
        # 배분표 각 줄과 합계
        for i, (k, v) in enumerate(rows[:-1]):
            chk("배분표 " + k.split(" · ")[0], E.cell(7+i, 3).value, v)
        chk("배분표 합계", E.cell(7+len(rows)-1, 3).value, 100.0, 0.01)
        # 전액 기준 환산
        chk("전액 기준 · 주계약", E.cell(7, 4).value,
            rows[0][1]/100*t.face_total, 1.0)
        # 분개 대차
        dr = cr = None
        for r in range(13, E.max_row+1):
            if E.cell(r, 2).value == "합계" and isinstance(E.cell(r, 3).value, float):
                dr, cr = E.cell(r, 3).value, E.cell(r, 4).value
        chk("분개 차변", dr, 100+ca, 0.01)
        chk("분개 대변", cr, 100+ca, 0.01)
        # 상각표 마지막 줄 기말 = 만기상환금액
        M = wb["상각표"]
        r_eir, rows_eir, redm, nper = G["eir_table"](t, b0)
        chk("상각표 기말 = 만기상환금액", M.cell(12+len(rows_eir), 7).value, redm, 0.01)
        chk("상각표 유효이자율", M.cell(9, 3).value, r_eir)

    print("\n" + ("모든 항목 일치" if not bad else "★ %d건 불일치" % len(bad)))
    for b in bad: print("   ★ " + b)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
