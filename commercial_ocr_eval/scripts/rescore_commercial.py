#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""상용 OCR 5종 재채점 — 3장과 5장의 비교축 통일.

1차 심사본의 채점 스크립트(commercial_ocr_eval/scripts/*_cer_result_*.py)는
엔진별 텍스트 추출과 세로 정렬 로직을 그대로 가져오되, 정답지 구성과
정규화 방식만 5장과 동일하게 맞춘다.

1차 산출과 달라지는 점:
  1) 정답지에서 구두점을 제거하지 않는다.
     1차 스크립트는 정답지에서만 「。、∘「」『』(),」를 지우고 OCR 출력에서는
     지우지 않아, 구두점을 읽어 낸 엔진이 그만큼 삽입 오류를 떠안았다.
     본 스크립트는 양쪽 모두 구두점을 유지한다(--strip-punct로 1차 재현 가능).
  2) 유니코드 NFC 정규화를 양쪽에 적용한다(5장과 동일).
  3) 오류를 삽입·대체·삭제로 분해하고 정밀도·재현율·F1을 함께 산출한다.

정답지 축 두 가지:
  --gt-mode full : 지면에 인쇄된 모든 문자(루비 포함). 5장의 '전체' 축.
  --gt-mode body : 루비를 제외한 본문 문자만. 5장의 '본문 계층' 축.
                   → 이 축이 3장과 5장을 한자리에 놓는다.

사용 예:
  python rescore_commercial.py --root .. --gt-mode body --csv rescore_body.csv
  python rescore_commercial.py --root .. --gt-mode full --csv rescore_full.csv
  python rescore_commercial.py --root .. --gt-mode full --strip-punct   # 1차 재현

의존성: 표준 라이브러리만 사용.
"""

import argparse
import csv
import glob
import json
import os
import re
import sys
import unicodedata as ud

# ---------------------------------------------------------------- 설정

# 약칭 → (정답지 JSON 파일명 패턴, OCR 출력 파일명에 쓰인 일본어 서명)
BOOKS = [
    ("국원", "*국원수지일선회화*.json", "1912 局員須知日鮮会話"),
    ("신선", "*신선정칙일선회화*.json", "1912 新撰正則日鮮会話"),
    ("국어", "*국어선어쌍*통해*.json", "1913 國語鮮語雙舌通解"),
    ("포켓", "*포켓조선어독학*.json", "1915 ポケット朝鮮語独学"),
]

ENGINES = ["google", "upstage", "naver", "easyocr", "acrobat"]

ENGINE_LABEL = {
    "google": "Google Cloud Vision",
    "upstage": "Upstage Document AI",
    "naver": "NAVER CLOVA",
    "easyocr": "EasyOCR",
    "acrobat": "Adobe Acrobat",
}

# 엔진별 결과 폴더와 파일명 패턴
ENGINE_FILES = {
    "google":  ("google_answer",  "OCR_TEST_{jp}_page{n}_google_result.json"),
    "upstage": ("upstage_answer", "OCR_TEST_{jp}_page{n}_upstage_result.json"),
    "naver":   ("naver_answer",   "OCR_TEST_{jp}_page{n}_ocr_result.json"),
    "easyocr": ("easyocr_answer", "OCR_TEST_{jp}_page{n}_easyocr_result.json"),
    "acrobat": ("acrobat_answer", "Acrobat_answer_{jp}.txt"),
}

RUBY_RE = re.compile(r"\{([^{}]*)\}")
PUNCT_RE = re.compile(r"[{}(),「」『』。、∘]")

# ---------------------------------------------------------- 정답지 구성


def gt_text(entry, mode, strip_punct):
    """정답지 항목 하나에서 평가 대상 문자열을 만든다."""
    out = []
    for key in ("text_ja", "text_ko"):
        t = entry.get(key, "") or ""
        if mode == "body":
            t = RUBY_RE.sub("", t)          # 루비 통째로 제거
        else:
            t = t.replace("{", "").replace("}", "")   # 중괄호만 제거
        if strip_punct:
            t = PUNCT_RE.sub("", t)
        out.append(t)
    return "".join(out)


def load_gt(path, mode, strip_punct):
    """책 하나의 정답지를 면(스캔 1장 = 책 2쪽) 단위로 묶어 반환."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    pages = {}
    for e in data:
        pages.setdefault(e["page"], []).append(e)
    for p in pages:
        pages[p].sort(key=lambda e: e["line_id"])

    ordered = sorted(pages)
    groups = [ordered[i:i + 2] for i in range(0, len(ordered), 2)]
    chunks = []
    for grp in groups:
        buf = []
        for p in grp:
            for e in pages[p]:
                buf.append(gt_text(e, mode, strip_punct))
        chunks.append(("".join(buf), grp))
    return chunks

# ------------------------------------------------- 엔진별 텍스트 추출
# 1차 심사본 스크립트의 로직을 그대로 옮긴다. 세로 정렬은
# X좌표 100픽셀 단위로 열을 묶어 우→좌, 상→하로 읽는 휴리스틱이다.


def sort_vertical(boxes):
    boxes.sort(key=lambda b: (-round(b["cx"] / 100), b["cy"]))
    return "".join(b["text"] for b in boxes)


def _center(xs, ys):
    return sum(xs) / len(xs), sum(ys) / len(ys)


def extract_google(obj):
    anns = obj.get("responses", [{}])[0].get("textAnnotations", [])
    if len(anns) < 2:
        return ""
    boxes = []
    for w in anns[1:]:
        verts = w.get("boundingPoly", {}).get("vertices", [])
        if not verts:
            continue
        cx, cy = _center([v.get("x", 0) for v in verts],
                         [v.get("y", 0) for v in verts])
        boxes.append({"text": w.get("description", ""), "cx": cx, "cy": cy})
    return sort_vertical(boxes)


def extract_naver(obj):
    fields = obj["images"][0].get("fields", [])
    boxes = []
    for f in fields:
        verts = f.get("boundingPoly", {}).get("vertices", [])
        if not verts:
            continue
        cx, cy = _center([v.get("x", 0) for v in verts],
                         [v.get("y", 0) for v in verts])
        boxes.append({"text": f.get("inferText", ""), "cx": cx, "cy": cy})
    return sort_vertical(boxes)


def extract_upstage(obj):
    pages = obj.get("pages", [])
    if not pages:
        return ""
    boxes = []
    for w in pages[0].get("words", []):
        verts = w.get("boundingBox", {}).get("vertices", [])
        if not verts:
            continue
        cx, cy = _center([v.get("x", 0) for v in verts],
                         [v.get("y", 0) for v in verts])
        boxes.append({"text": w.get("text", ""), "cx": cx, "cy": cy})
    return sort_vertical(boxes)


def extract_easyocr(obj):
    boxes = []
    for it in obj:
        bbox = it.get("boundingPoly", [])
        if not bbox or len(bbox) != 4:
            continue
        cx, cy = _center([p[0] for p in bbox], [p[1] for p in bbox])
        boxes.append({"text": it.get("text", ""), "cx": cx, "cy": cy})
    return sort_vertical(boxes)


EXTRACT = {
    "google": extract_google,
    "naver": extract_naver,
    "upstage": extract_upstage,
    "easyocr": extract_easyocr,
}

# ------------------------------------------------------------ 평가 지표


def normalize(s, strip_punct=False):
    s = ud.normalize("NFC", s)
    s = re.sub(r"\s+", "", s)
    if strip_punct:
        s = PUNCT_RE.sub("", s)
    return s


def cer_decompose(ref, hyp):
    """편집 거리 역추적으로 삽입·대체·삭제를 분해한다."""
    R, H = len(ref), len(hyp)
    dp = [[0] * (H + 1) for _ in range(R + 1)]
    for r in range(1, R + 1):
        dp[r][0] = r
    for h in range(1, H + 1):
        dp[0][h] = h
    for r in range(1, R + 1):
        rc = ref[r - 1]
        row, prev = dp[r], dp[r - 1]
        for h in range(1, H + 1):
            cost = 0 if rc == hyp[h - 1] else 1
            row[h] = min(prev[h] + 1, row[h - 1] + 1, prev[h - 1] + cost)

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
    return {"n": R, "i": i, "s": s, "d": d}


def add_metrics(m):
    n, i, s, d = m["n"], m["i"], m["s"], m["d"]
    c = n - s - d
    hyp_len = n - d + i
    p = c / hyp_len if hyp_len > 0 else 0.0
    rc = c / n if n > 0 else 0.0
    f1 = 2 * p * rc / (p + rc) if (p + rc) > 0 else 0.0
    m.update({"cer": (i + s + d) / max(n, 1), "correct": c,
              "precision": p, "recall": rc, "f1": f1})
    return m

# ---------------------------------------------------------------- 실행


def score_book(root, engine, jp_name, gt_chunks, strip_punct):
    """책 하나에 대해 오류 수와 정답 문자 수를 합산한다."""
    folder, pattern = ENGINE_FILES[engine]
    ocr_dir = os.path.join(root, "ocr_output", folder)
    agg = {"n": 0, "i": 0, "s": 0, "d": 0}

    if engine == "acrobat":
        path = os.path.join(ocr_dir, pattern.format(jp=jp_name))
        if not os.path.exists(path):
            return None
        hyp = normalize(open(path, encoding="utf-8").read(), strip_punct)
        ref = normalize("".join(c[0] for c in gt_chunks), strip_punct)
        m = cer_decompose(ref, hyp)
        return add_metrics(m)

    for idx, (chunk, _pages) in enumerate(gt_chunks, start=1):
        path = os.path.join(ocr_dir, pattern.format(jp=jp_name, n=idx))
        if not os.path.exists(path):
            print(f"  [경고] 없음: {os.path.basename(path)}", file=sys.stderr)
            continue
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
        hyp = normalize(EXTRACT[engine](obj), strip_punct)
        ref = normalize(chunk, strip_punct)
        m = cer_decompose(ref, hyp)
        for k in agg:
            agg[k] += m[k]
    return add_metrics(agg) if agg["n"] else None


def main():
    ap = argparse.ArgumentParser(description="상용 OCR 5종 재채점")
    ap.add_argument("--root", default="..",
                    help="commercial_ocr_eval 폴더 경로 (기본: ..)")
    ap.add_argument("--gt-dir", default=None,
                    help="정답지 JSON 폴더 (기본: <root>/../gt_json)")
    ap.add_argument("--gt-mode", choices=["full", "body"], default="body",
                    help="full=루비 포함, body=본문 문자만 (기본: body)")
    ap.add_argument("--strip-punct", action="store_true",
                    help="1차 심사본처럼 구두점을 양쪽에서 제거")
    ap.add_argument("--csv", help="결과를 저장할 CSV 경로")
    args = ap.parse_args()

    gt_dir = args.gt_dir or os.path.join(args.root, "..", "gt_json")

    # 책별 정답지 로드
    book_gt = {}
    for abbr, pat, jp in BOOKS:
        hits = glob.glob(os.path.join(gt_dir, pat))
        if not hits:
            raise SystemExit(f"정답지를 찾을 수 없습니다: {pat} (in {gt_dir})")
        book_gt[abbr] = load_gt(hits[0], args.gt_mode, args.strip_punct)

    mode_label = "본문 문자만(루비 제외)" if args.gt_mode == "body" else "전체(루비 포함)"
    print(f"\n정답지 축: {mode_label}"
          f"{' / 구두점 제거' if args.strip_punct else ' / 구두점 유지'}")
    print(f"정답 문자 수: " + "  ".join(
        f"{a}={sum(len(normalize(c[0], args.strip_punct)) for c in book_gt[a]):,}"
        for a, _, _ in BOOKS))

    header = f"\n{'엔진':<22}" + "".join(f"{a:>12}" for a, _, _ in BOOKS) + f"{'종합':>14}{'F1':>9}"
    print(header)
    print("-" * len(header))

    rows = []
    for eng in ENGINES:
        cells, total = [], {"n": 0, "i": 0, "s": 0, "d": 0}
        for abbr, _pat, jp in BOOKS:
            m = score_book(args.root, eng, jp, book_gt[abbr], args.strip_punct)
            if m is None:
                cells.append("—")
                continue
            cells.append(f"{m['cer']*100:.2f}%")
            for k in total:
                total[k] += m[k]
            rows.append({"engine": ENGINE_LABEL[eng], "book": abbr, **m})
        t = add_metrics(total)
        rows.append({"engine": ENGINE_LABEL[eng], "book": "종합", **t})
        print(f"{ENGINE_LABEL[eng]:<22}"
              + "".join(f"{c:>12}" for c in cells)
              + f"{t['cer']*100:>13.2f}%{t['f1']*100:>8.2f}%")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["엔진", "문헌", "정답(자)", "삽입", "대체", "삭제",
                        "CER(%)", "정답일치", "정밀도(%)", "재현율(%)", "F1(%)"])
            for r in rows:
                w.writerow([r["engine"], r["book"], r["n"], r["i"], r["s"], r["d"],
                            round(r["cer"] * 100, 2), r["correct"],
                            round(r["precision"] * 100, 2),
                            round(r["recall"] * 100, 2),
                            round(r["f1"] * 100, 2)])
        print(f"\nCSV 저장: {args.csv}")


if __name__ == "__main__":
    main()
