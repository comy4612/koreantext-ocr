#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전처리 전 기준선(baseline) OCR: 원본 스캔면 전체를 EasyOCR로 인식.

run_local_ocr.py와 동일한 정책(ko/ja 리더 각각 실행 → 신뢰도+문자 유형으로
채택, 박스 y좌표 정렬)을 전처리 없이 원본 이미지 전체에 적용한다.
전/후 비교에서 달라지는 것은 오직 전처리 유무가 되도록 설계한 것.

사용 예:
  python run_baseline_ocr.py ./images ./results_before
  python run_baseline_ocr.py ./images ./results_before --gpu

출력:
  <출력폴더>/easyocr/<이미지이름>.txt / .json / params.json
"""

import argparse
import json
import time
from pathlib import Path

from run_local_ocr import read_column


def main():
    ap = argparse.ArgumentParser(description="원본 이미지 전체 EasyOCR(기준선)")
    ap.add_argument("input", help="원본 이미지 폴더")
    ap.add_argument("output", help="결과 저장 폴더")
    ap.add_argument("--gpu", action="store_true")
    args = ap.parse_args()

    import easyocr

    print("EasyOCR 리더 초기화 중...")
    readers = {
        "ko": easyocr.Reader(["ko", "en"], gpu=args.gpu),
        "ja": easyocr.Reader(["ja", "en"], gpu=args.gpu),
    }

    out_dir = Path(args.output) / "easyocr"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "params.json", "w", encoding="utf-8") as f:
        json.dump({
            "engine": "EasyOCR", "version": getattr(easyocr, "__version__", "?"),
            "mode": "baseline(전처리 없음, 원본 스캔면 전체)",
            "policy": "ko/ja 리더 개별 실행 → 신뢰도+문자유형 채택, y좌표 정렬",
            "gpu": args.gpu, "date": time.strftime("%Y-%m-%d"),
        }, f, ensure_ascii=False, indent=2)

    exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
    files = sorted(f for f in Path(args.input).iterdir()
                   if f.suffix.lower() in exts)
    if not files:
        raise SystemExit("입력 이미지가 없습니다.")

    for f in files:
        t0 = time.time()
        # 원본 스캔면 전체에 동일 정책(박스 단위 ko/ja 앙상블) 적용.
        # 전/후 비교에서 달라지는 것은 전처리 유무뿐.
        # (원본은 이미 대형 이미지이므로 확대 없이 인식)
        lang, info = read_column(readers, f, upscale=1.0)
        (out_dir / f"{f.stem}.txt").write_text(info["text"], encoding="utf-8")
        with open(out_dir / f"{f.stem}.json", "w", encoding="utf-8") as jf:
            json.dump({"source": f.name, "lang": lang,
                       "conf": round(info["conf"], 4),
                       "by_lang": info["by_lang"],
                       "n_boxes": info["n_boxes"]},
                      jf, ensure_ascii=False, indent=2)
        print(f"[OK] {f.name}: 대표 언어={lang}, 박스 {info['n_boxes']}개, "
              f"{time.time() - t0:.1f}초")


if __name__ == "__main__":
    main()
