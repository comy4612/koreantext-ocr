#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tesseract 세로쓰기 전용 모델(kor_vert+jpn_vert)로 전/후 OCR 실행.

EasyOCR과 달리 Tesseract는 세로쓰기 텍스트로 학습된 전용 모델을
제공하므로 근대 세로쓰기 활자에 유리하다. 완전 로컬로 동작한다.

설치(WSL/Ubuntu):
  sudo apt install -y tesseract-ocr tesseract-ocr-kor tesseract-ocr-jpn \
      tesseract-ocr-jpn-vert
  pip install pytesseract
  # 설치 확인: tesseract --list-langs 에 kor_vert, jpn_vert가 보여야 함

사용 예:
  # 기준선(전처리 전): 원본 스캔면 전체
  python run_tesseract.py baseline ./images ./results_before

  # 전처리 후: 컬럼 단위 (--psm 5 = 세로 정렬 텍스트 블록)
  python run_tesseract.py after ./preprocessed ./results_after

출력:
  <출력폴더>/tesseract/<이름>.txt / params.json
"""

import argparse
import json
import time
from pathlib import Path

import cv2
import pytesseract


def ocr_image(img, langs, psm, upscale=1.0):
    if upscale and upscale != 1.0:
        img = cv2.resize(img, None, fx=upscale, fy=upscale,
                         interpolation=cv2.INTER_CUBIC)
    config = f"--psm {psm}"
    text = pytesseract.image_to_string(img, lang=langs, config=config)
    return text.strip()


def main():
    ap = argparse.ArgumentParser(description="Tesseract 세로쓰기 OCR(전/후)")
    ap.add_argument("mode", choices=["baseline", "after"],
                    help="baseline=원본 전체, after=전처리된 컬럼")
    ap.add_argument("input", help="입력 폴더(baseline=images, after=preprocessed)")
    ap.add_argument("output", help="결과 저장 폴더")
    ap.add_argument("--langs", default="kor_vert+jpn_vert",
                    help="Tesseract 언어 조합(기본 kor_vert+jpn_vert)")
    ap.add_argument("--psm-page", type=int, default=3,
                    help="baseline 페이지 psm(기본 3=자동)")
    ap.add_argument("--psm-col", type=int, default=5,
                    help="after 컬럼 psm(기본 5=세로 정렬 단일 블록)")
    ap.add_argument("--upscale", type=float, default=2.0,
                    help="after 컬럼 확대 배율(기본 2.0)")
    args = ap.parse_args()

    out_dir = Path(args.output) / "tesseract"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "params.json", "w", encoding="utf-8") as f:
        json.dump({
            "engine": "Tesseract",
            "version": str(pytesseract.get_tesseract_version()),
            "langs": args.langs, "mode": args.mode,
            "psm": args.psm_page if args.mode == "baseline" else args.psm_col,
            "upscale": 1.0 if args.mode == "baseline" else args.upscale,
            "date": time.strftime("%Y-%m-%d"),
        }, f, ensure_ascii=False, indent=2)

    if args.mode == "baseline":
        exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
        files = sorted(f for f in Path(args.input).iterdir()
                       if f.suffix.lower() in exts)
        if not files:
            raise SystemExit("입력 이미지가 없습니다.")
        for f in files:
            t0 = time.time()
            img = cv2.imread(str(f))
            text = ocr_image(img, args.langs, args.psm_page)
            (out_dir / f"{f.stem}.txt").write_text(text, encoding="utf-8")
            print(f"[OK] {f.name}: {len(text)}자, {time.time() - t0:.1f}초")
        return

    # after: preprocess.py 출력 폴더의 컬럼들을 읽기 순서대로
    page_dirs = sorted(d for d in Path(args.input).iterdir()
                       if d.is_dir() and (d / "meta.json").exists())
    if not page_dirs:
        raise SystemExit("meta.json이 있는 페이지 폴더가 없습니다.")
    for pd in page_dirs:
        with open(pd / "meta.json", encoding="utf-8") as f:
            meta = json.load(f)
        t0 = time.time()
        merged = []
        for rname, cols in meta["regions"].items():
            for col in sorted(cols, key=lambda c: c["order"]):
                img = cv2.imread(str(pd / col["file"]))
                if img is None:
                    continue
                text = ocr_image(img, args.langs, args.psm_col, args.upscale)
                if text:
                    merged.append(text)
        full = "\n".join(merged)
        (out_dir / f"{pd.name}.txt").write_text(full, encoding="utf-8")
        print(f"[OK] {pd.name}: 컬럼 {sum(len(c) for c in meta['regions'].values())}개, "
              f"{len(full)}자, {time.time() - t0:.1f}초")


if __name__ == "__main__":
    main()
