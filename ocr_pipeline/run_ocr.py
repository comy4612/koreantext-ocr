#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전처리된 컬럼 이미지에 대한 상용 OCR 호출 + 언어 영역 판별.

논문 4.2(언어 영역 판별)의 구현 및 심사자 B-1, B-2에 대한 답변 근거.

동작 흐름:
  1) preprocess.py 출력 폴더의 컬럼 이미지를 읽기 순서대로 OCR 호출
  2) 1차 인식 결과의 유니코드 문자 유형 분포로 영역 언어를 판별 (4.2절)
  3) (--two-pass 시) 판별된 언어를 힌트로 지정하여 2차 호출
  4) 결과를 페이지 단위 txt로 병합하고, 재현성을 위해 호출 파라미터를
     params.json에 기록

사용 예:
  export GOOGLE_API_KEY=...      # 또는 CLOVA_SECRET/CLOVA_URL, UPSTAGE_API_KEY
  python run_ocr.py ./out ./ocr_results --engine google
  python run_ocr.py ./out ./ocr_results --engine google --two-pass

출력:
  ocr_results/<엔진>/<페이지이름>.txt        # 읽기 순서로 병합된 전체 텍스트
  ocr_results/<엔진>/<페이지이름>.json       # 컬럼별 텍스트·판별 언어·원시 응답
  ocr_results/<엔진>/params.json             # 엔진·엔드포인트·언어 힌트 등 기록

의존성: pip install requests
"""

import argparse
import base64
import json
import os
import time
import unicodedata
import uuid
from pathlib import Path

try:
    import requests  # API 호출 시에만 필요 (run_local_ocr.py는 불필요)
except ImportError:
    requests = None

# ---------------------------------------------------------------------------
# 언어 영역 판별 (4.2절): 유니코드 블록 기반 문자 유형 분포 분석
# ---------------------------------------------------------------------------

def char_type(ch):
    """문자 1개를 hangul / hanja / kana / other로 분류."""
    o = ord(ch)
    if 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
        return "hangul"
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0xF900 <= o <= 0xFAFF:
        return "hanja"
    if 0x3040 <= o <= 0x309F or 0x30A0 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF:
        return "kana"
    return "other"


def classify_language(text):
    """텍스트의 문자 유형 분포로 언어 영역을 판별.

    한글 비율이 높으면 한국어 영역(ko), 가나·한자 비율이 높으면
    일본어 영역(ja)으로 판별한다. 판별 근거(비율)를 함께 반환.
    """
    counts = {"hangul": 0, "hanja": 0, "kana": 0, "other": 0}
    for ch in text:
        if ch.isspace():
            continue
        counts[char_type(ch)] += 1
    total = counts["hangul"] + counts["hanja"] + counts["kana"]
    if total == 0:
        return "unknown", counts
    ko_score = counts["hangul"] / total
    ja_score = (counts["kana"] + counts["hanja"]) / total
    # 한글이 유의미하게 존재하면 한국어 영역으로 우선 판별
    # (한국어 영역에도 대응 한자가 병기되는 경우가 있기 때문)
    lang = "ko" if ko_score >= 0.3 else ("ja" if ja_score > ko_score else "ko")
    return lang, counts


# ---------------------------------------------------------------------------
# OCR 엔진별 호출 함수 (REST API)
# ---------------------------------------------------------------------------

def ocr_google(image_bytes, lang_hints=None):
    """Google Cloud Vision - DOCUMENT_TEXT_DETECTION.

    필요 환경변수: GOOGLE_API_KEY
    lang_hints 예: ["ko"], ["ja"], ["ko", "ja"]
    """
    key = os.environ["GOOGLE_API_KEY"]
    url = f"https://vision.googleapis.com/v1/images:annotate?key={key}"
    req = {
        "requests": [{
            "image": {"content": base64.b64encode(image_bytes).decode()},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }]
    }
    if lang_hints:
        req["requests"][0]["imageContext"] = {"languageHints": lang_hints}
    r = requests.post(url, json=req, timeout=60)
    r.raise_for_status()
    resp = r.json()["responses"][0]
    text = resp.get("fullTextAnnotation", {}).get("text", "")
    return text, resp


def ocr_clova(image_bytes, lang_hints=None):
    """NAVER CLOVA OCR (General).

    필요 환경변수: CLOVA_URL(Invoke URL), CLOVA_SECRET
    CLOVA는 요청 단위 언어 힌트 파라미터가 없으므로 lang_hints는 무시되며,
    도메인 생성 시 언어를 설정한다(파라미터 기록용으로 남김).
    """
    url = os.environ["CLOVA_URL"]
    secret = os.environ["CLOVA_SECRET"]
    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
        "images": [{"format": "png", "name": "col",
                    "data": base64.b64encode(image_bytes).decode()}],
    }
    r = requests.post(url, json=payload,
                      headers={"X-OCR-SECRET": secret}, timeout=60)
    r.raise_for_status()
    resp = r.json()
    fields = resp.get("images", [{}])[0].get("fields", [])
    text = "\n".join(f.get("inferText", "") for f in fields)
    return text, resp


def ocr_upstage(image_bytes, lang_hints=None):
    """Upstage Document AI - Document OCR.

    필요 환경변수: UPSTAGE_API_KEY
    """
    key = os.environ["UPSTAGE_API_KEY"]
    url = "https://api.upstage.ai/v1/document-ai/ocr"
    r = requests.post(url, headers={"Authorization": f"Bearer {key}"},
                      files={"document": ("col.png", image_bytes, "image/png")},
                      timeout=60)
    r.raise_for_status()
    resp = r.json()
    text = resp.get("text", "")
    if not text and "pages" in resp:
        text = "\n".join(pg.get("text", "") for pg in resp["pages"])
    return text, resp


ENGINES = {"google": ocr_google, "clova": ocr_clova, "upstage": ocr_upstage}


# ---------------------------------------------------------------------------
# 파이프라인
# ---------------------------------------------------------------------------

def process_page(page_dir, engine_fn, two_pass, sleep):
    """페이지 폴더(preprocess.py 출력) 하나를 처리."""
    with open(page_dir / "meta.json", encoding="utf-8") as f:
        meta = json.load(f)

    page_result = {"source": meta["source"], "columns": []}
    merged_lines = []

    for rname, cols in meta["regions"].items():
        for col in sorted(cols, key=lambda c: c["order"]):
            img_bytes = (page_dir / col["file"]).read_bytes()

            # 1차 호출 (언어 힌트 없음)
            text, raw = engine_fn(img_bytes, None)
            lang, counts = classify_language(text)

            # 2차 호출 (판별된 언어를 힌트로 지정)
            if two_pass and lang in ("ko", "ja"):
                time.sleep(sleep)
                text2, raw2 = engine_fn(img_bytes, [lang])
                text, raw = text2, raw2

            page_result["columns"].append({
                "region": rname, "order": col["order"], "file": col["file"],
                "lang": lang, "char_counts": counts,
                "text": text,
            })
            merged_lines.append(text)
            time.sleep(sleep)

    return page_result, "\n".join(merged_lines)


def main():
    ap = argparse.ArgumentParser(description="컬럼 이미지 OCR 호출 + 언어 판별")
    ap.add_argument("input", help="preprocess.py 출력 폴더")
    ap.add_argument("output", help="OCR 결과 저장 폴더")
    ap.add_argument("--engine", choices=ENGINES, required=True)
    ap.add_argument("--two-pass", action="store_true",
                    help="언어 판별 후 언어 힌트를 지정하여 재호출")
    ap.add_argument("--sleep", type=float, default=0.5,
                    help="API 호출 간 대기(초). 호출 제한(rate limit) 대비")
    args = ap.parse_args()

    engine_fn = ENGINES[args.engine]
    out_dir = Path(args.output) / args.engine
    out_dir.mkdir(parents=True, exist_ok=True)

    # 재현성 기록 (논문 3.2절 파라미터 서술 및 심사자 C-1 대응)
    params = {
        "engine": args.engine,
        "two_pass": args.two_pass,
        "language_hint_policy": "1차 호출 무힌트 → 문자 유형 분포로 판별 → 2차 호출 시 판별 언어 지정" if args.two_pass else "무힌트 단일 호출",
        "google": {"endpoint": "v1/images:annotate", "feature": "DOCUMENT_TEXT_DETECTION"},
        "clova": {"version": "V2", "note": "언어는 도메인 생성 시 설정"},
        "upstage": {"endpoint": "v1/document-ai/ocr"},
        "date": time.strftime("%Y-%m-%d"),
    }
    with open(out_dir / "params.json", "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

    page_dirs = sorted(d for d in Path(args.input).iterdir()
                       if d.is_dir() and (d / "meta.json").exists())
    if not page_dirs:
        raise SystemExit("meta.json이 있는 페이지 폴더가 없습니다. preprocess.py를 먼저 실행하세요.")

    for pd in page_dirs:
        result, merged = process_page(pd, engine_fn, args.two_pass, args.sleep)
        (out_dir / f"{pd.name}.txt").write_text(merged, encoding="utf-8")
        with open(out_dir / f"{pd.name}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        langs = [c["lang"] for c in result["columns"]]
        print(f"[OK] {pd.name}: 컬럼 {len(langs)}개, 언어 판별 {langs}")


if __name__ == "__main__":
    main()
