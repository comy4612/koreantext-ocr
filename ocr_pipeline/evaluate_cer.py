#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CER 산출 + 오류 유형 분해(삽입/대체/삭제).

논문 3.2절 지표 보강 및 심사자 C-3에 대한 답변 근거.

CER = (i + s + d) / n  (Neudecker et al. 2021)
  i: 삽입(insertion)  - 레이아웃 인식 실패(컬럼 미분리, 루비 혼입) 시 폭증
  s: 대체(substitution) - 순수 문자 인식 실패
  d: 삭제(deletion)   - 영역 누락
오류 유형을 분해하여 제시함으로써 레이아웃 인식 실패와 순수 문자 인식
실패를 구조적으로 구별한다.

사용 예:
  # 단일 파일 쌍
  python evaluate_cer.py --ref gt/page01.txt --hyp ocr/page01.txt

  # 폴더 일괄 (같은 이름의 .txt끼리 대조)
  python evaluate_cer.py --ref-dir gt/ --hyp-dir ocr_results/google/ --csv result.csv

  # 전처리 전후 비교 (두 결과 폴더를 같은 정답지와 대조)
  python evaluate_cer.py --ref-dir gt/ --hyp-dir before/ --hyp-dir2 after/ --csv compare.csv

정규화 옵션:
  --keep-space   공백을 오류 계산에 포함(기본: 공백·개행 제거 후 비교)
  --nfc          유니코드 NFC 정규화 적용(기본: 적용)

의존성: 표준 라이브러리만 사용.
"""

import argparse
import csv
import sys
import unicodedata
from pathlib import Path


def normalize(text, keep_space=False, nfc=True):
    if nfc:
        text = unicodedata.normalize("NFC", text)
    if not keep_space:
        text = "".join(text.split())
    return text


def cer_decompose(ref, hyp):
    """편집 거리 역추적으로 삽입·대체·삭제 횟수를 분해.

    반환: dict(n, i, s, d, cer)
      n: 정답지 문자 수, i/s/d: 삽입/대체/삭제 횟수
    """
    R, H = len(ref), len(hyp)
    # dp[r][h] = ref[:r] -> hyp[:h] 최소 편집 비용
    # 메모리 절약 없이 역추적을 위해 전체 표 유지 (파일럿 규모에서 충분)
    dp = [[0] * (H + 1) for _ in range(R + 1)]
    for r in range(1, R + 1):
        dp[r][0] = r
    for h in range(1, H + 1):
        dp[0][h] = h
    for r in range(1, R + 1):
        for h in range(1, H + 1):
            cost = 0 if ref[r - 1] == hyp[h - 1] else 1
            dp[r][h] = min(dp[r - 1][h] + 1,      # 삭제
                           dp[r][h - 1] + 1,      # 삽입
                           dp[r - 1][h - 1] + cost)  # 일치/대체

    # 역추적
    i = s = d = 0
    r, h = R, H
    while r > 0 or h > 0:
        if r > 0 and h > 0 and dp[r][h] == dp[r - 1][h - 1] and ref[r - 1] == hyp[h - 1]:
            r, h = r - 1, h - 1
        elif r > 0 and h > 0 and dp[r][h] == dp[r - 1][h - 1] + 1:
            s += 1
            r, h = r - 1, h - 1
        elif h > 0 and dp[r][h] == dp[r][h - 1] + 1:
            i += 1
            h -= 1
        else:
            d += 1
            r -= 1

    n = max(R, 1)
    return add_prf({"n": R, "i": i, "s": s, "d": d,
                    "cer": (i + s + d) / n})


def add_prf(m):
    """문자 단위 정밀도·재현율·F1을 계산해 덧붙인다.

      일치(correct) = 정답 문자 수 − 대체 − 삭제
      출력(hyp_len) = 정답 문자 수 − 삭제 + 삽입
      재현율 = 일치 / 정답 문자 수   → 검출 누락(삭제)에 대응
      정밀도 = 일치 / 출력 문자 수   → 잡음 혼입(삽입)에 대응
      F1     = 2PR / (P+R)

    CER는 삽입이 많으면 100%를 넘어 해석이 어렵지만 F1은 0~1에 한정되므로
    조건 간 비교에 적합하다(심사 의견 C-3 대응).
    """
    n, i, s, d = m["n"], m["i"], m["s"], m["d"]
    c = n - s - d              # 정답과 일치한 문자 수
    h = n - d + i              # 인식 결과의 문자 수
    p = c / h if h > 0 else 0.0
    r = c / n if n > 0 else 0.0
    f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    m.update({"correct": c, "hyp_len": h,
              "precision": p, "recall": r, "f1": f})
    return m


def eval_pair(ref_path, hyp_path, keep_space, nfc):
    ref = normalize(Path(ref_path).read_text(encoding="utf-8"), keep_space, nfc)
    hyp = normalize(Path(hyp_path).read_text(encoding="utf-8"), keep_space, nfc)
    return cer_decompose(ref, hyp)


def eval_dir(ref_dir, hyp_dir, keep_space, nfc):
    """같은 이름의 .txt 파일끼리 대조."""
    rows = []
    for ref_file in sorted(Path(ref_dir).glob("*.txt")):
        hyp_file = Path(hyp_dir) / ref_file.name
        if not hyp_file.exists():
            print(f"[경고] 대응 파일 없음: {hyp_file}", file=sys.stderr)
            continue
        m = eval_pair(ref_file, hyp_file, keep_space, nfc)
        m["file"] = ref_file.name
        rows.append(m)
    return rows


def aggregate(rows):
    """마이크로 평균(전체 문자 수 기준) 집계."""
    N = sum(r["n"] for r in rows)
    I = sum(r["i"] for r in rows)
    S = sum(r["s"] for r in rows)
    D = sum(r["d"] for r in rows)
    return add_prf({"n": N, "i": I, "s": S, "d": D,
                    "cer": (I + S + D) / max(N, 1)})


def fmt(m, label=""):
    return (f"{label:<24} n={m['n']:>6}  ins={m['i']:>6}  sub={m['s']:>6}  "
            f"del={m['d']:>6}  CER={m['cer']*100:7.2f}%  "
            f"P={m['precision']*100:5.1f}%  R={m['recall']*100:5.1f}%  "
            f"F1={m['f1']*100:6.2f}%")


def main():
    ap = argparse.ArgumentParser(description="CER 산출 + 삽입/대체/삭제 분해")
    ap.add_argument("--ref", help="정답지 txt (단일 쌍 모드)")
    ap.add_argument("--hyp", help="OCR 결과 txt (단일 쌍 모드)")
    ap.add_argument("--ref-dir", help="정답지 폴더 (일괄 모드)")
    ap.add_argument("--hyp-dir", help="OCR 결과 폴더 (일괄 모드)")
    ap.add_argument("--hyp-dir2", help="비교할 두 번째 결과 폴더 (전/후 비교)")
    ap.add_argument("--csv", help="파일별 결과를 저장할 CSV 경로")
    ap.add_argument("--keep-space", action="store_true")
    ap.add_argument("--no-nfc", dest="nfc", action="store_false")
    args = ap.parse_args()

    if args.ref and args.hyp:
        m = eval_pair(args.ref, args.hyp, args.keep_space, args.nfc)
        print(fmt(m, Path(args.hyp).name))
        return

    if not (args.ref_dir and args.hyp_dir):
        ap.error("--ref/--hyp 또는 --ref-dir/--hyp-dir을 지정하세요.")

    rows1 = eval_dir(args.ref_dir, args.hyp_dir, args.keep_space, args.nfc)
    if not rows1:
        raise SystemExit("평가할 파일 쌍이 없습니다.")

    label1 = Path(args.hyp_dir).name or "hyp1"
    print(f"\n=== {label1} ===")
    for r in rows1:
        print(fmt(r, r["file"]))
    agg1 = aggregate(rows1)
    print("-" * 78)
    print(fmt(agg1, "전체(micro avg)"))

    rows2 = None
    if args.hyp_dir2:
        rows2 = eval_dir(args.ref_dir, args.hyp_dir2, args.keep_space, args.nfc)
        label2 = Path(args.hyp_dir2).name or "hyp2"
        print(f"\n=== {label2} ===")
        for r in rows2:
            print(fmt(r, r["file"]))
        agg2 = aggregate(rows2)
        print("-" * 78)
        print(fmt(agg2, "전체(micro avg)"))
        d_cer = (agg1["cer"] - agg2["cer"]) * 100
        d_f1 = (agg2["f1"] - agg1["f1"]) * 100
        print(f"\n[전/후 비교] CER {agg1['cer']*100:.2f}% -> {agg2['cer']*100:.2f}% "
              f"({d_cer:+.2f}%p, 낮을수록 좋음)")
        print(f"[전/후 비교] F1  {agg1['f1']*100:.2f}% -> {agg2['f1']*100:.2f}% "
              f"({d_f1:+.2f}%p, 높을수록 좋음)")
        print(f"             정밀도 {agg1['precision']*100:.1f}% -> "
              f"{agg2['precision']*100:.1f}%  |  "
              f"재현율 {agg1['recall']*100:.1f}% -> {agg2['recall']*100:.1f}%")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            base = ["n", "ins", "sub", "del", "CER(%)", "정답일치",
                    "정밀도(%)", "재현율(%)", "F1(%)"]
            header = ["file"] + base
            if rows2:
                header += [c + "_2" for c in base[1:]] + ["CER차(%p)", "F1차(%p)"]
            w.writerow(header)

            def vals(r):
                return [r["i"], r["s"], r["d"], round(r["cer"] * 100, 2),
                        r["correct"], round(r["precision"] * 100, 2),
                        round(r["recall"] * 100, 2), round(r["f1"] * 100, 2)]

            idx2 = {r["file"]: r for r in (rows2 or [])}
            for r in rows1:
                row = [r["file"], r["n"]] + vals(r)
                if rows2 and r["file"] in idx2:
                    r2 = idx2[r["file"]]
                    row += vals(r2) + [round((r["cer"] - r2["cer"]) * 100, 2),
                                       round((r2["f1"] - r["f1"]) * 100, 2)]
                w.writerow(row)

            # 마지막 행에 전체(micro avg) 추가
            row = ["__전체(micro avg)__", agg1["n"]] + vals(agg1)
            if rows2:
                row += vals(agg2) + [round((agg1["cer"] - agg2["cer"]) * 100, 2),
                                     round((agg2["f1"] - agg1["f1"]) * 100, 2)]
            w.writerow(row)
        print(f"\nCSV 저장: {args.csv}")


if __name__ == "__main__":
    main()
