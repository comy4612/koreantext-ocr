#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전처리된 컬럼 이미지에 대한 로컬 OCR(EasyOCR) 실행. (v2: 박스 앙상블)

v2 변경점:
  - 컬럼 이미지를 확대(기본 2배)한 뒤 인식: 세로쓰기 소형 활자·루비 대응
  - ko/ja 리더를 모두 실행하고 검출 박스 단위로 앙상블:
    겹치는 박스(IoU 기준)는 신뢰도 높은 쪽을 채택.
    → 한 열 안에 한글과 한자·가나가 섞여 있어도 각 문자 체계를
      해당 언어 리더가 읽음 (언어 판별을 열 단위→박스 단위로 정밀화)
  - 박스는 y좌표 상→하 정렬로 세로쓰기 읽기 순서 복원

사용 예:
  python run_local_ocr.py ./preprocessed ./results_after --gpu

출력:
  <출력폴더>/easyocr/<페이지이름>.txt        # 읽기 순서 병합 텍스트
  <출력폴더>/easyocr/<페이지이름>_ja.txt     # ja 리더가 읽은 박스만
  <출력폴더>/easyocr/<페이지이름>_ko.txt     # ko 리더가 읽은 박스만
  <출력폴더>/easyocr/<페이지이름>.json       # 컬럼별 상세
  <출력폴더>/easyocr/params.json             # 설정 기록(재현성)

의존성: pip install easyocr opencv-python
"""

import argparse
import json
import time
from pathlib import Path

import cv2

from run_ocr import classify_language


def _iou(a, b):
    ix0, iy0 = max(a["x0"], b["x0"]), max(a["y0"], b["y0"])
    ix1, iy1 = min(a["x1"], b["x1"]), min(a["y1"], b["y1"])
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = (a["x1"] - a["x0"]) * (a["y1"] - a["y0"])
    area_b = (b["x1"] - b["x0"]) * (b["y1"] - b["y0"])
    return inter / max(area_a + area_b - inter, 1)


def read_column(readers, img_path, upscale=2.0, iou_thresh=0.45,
                min_conf=0.05):
    """컬럼 이미지 하나를 ko/ja 리더로 각각 인식하고 박스 단위 앙상블.

    반환: (lang, info)
      lang: 병합 텍스트의 문자 유형 분포로 판별한 대표 언어
      info: {"text", "conf", "n_boxes", "by_lang", "text_by_lang"}
    """
    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"이미지를 읽을 수 없습니다: {img_path}")
    if upscale and upscale != 1.0:
        img = cv2.resize(img, None, fx=upscale, fy=upscale,
                         interpolation=cv2.INTER_CUBIC)

    boxes = []
    for rlang, reader in readers.items():
        for bbox, text, conf in reader.readtext(img, detail=1,
                                                paragraph=False):
            if conf < min_conf or not text.strip():
                continue
            xs = [pt[0] for pt in bbox]
            ys = [pt[1] for pt in bbox]
            boxes.append({"x0": min(xs), "y0": min(ys),
                          "x1": max(xs), "y1": max(ys),
                          "text": text, "conf": float(conf), "rlang": rlang})

    # 앙상블: 신뢰도 내림차순 그리디, 겹치는 박스는 높은 쪽만 유지
    boxes.sort(key=lambda b: -b["conf"])
    kept = []
    for b in boxes:
        if all(_iou(b, k) < iou_thresh for k in kept):
            kept.append(b)
    kept.sort(key=lambda b: b["y0"])  # 세로쓰기 읽기 순서: 상→하

    text = "\n".join(b["text"] for b in kept)
    conf = sum(b["conf"] for b in kept) / len(kept) if kept else 0.0
    lang, counts = classify_language(text)
    info = {
        "text": text, "conf": conf, "n_boxes": len(kept),
        "char_counts": counts,
        "by_lang": {lg: sum(1 for b in kept if b["rlang"] == lg)
                    for lg in readers},
        "text_by_lang": {lg: "\n".join(b["text"] for b in kept
                                       if b["rlang"] == lg)
                         for lg in readers},
    }
    return lang, info


def main():
    ap = argparse.ArgumentParser(
        description="컬럼 이미지 EasyOCR 실행(박스 단위 ko/ja 앙상블)")
    ap.add_argument("input", help="preprocess.py 출력 폴더")
    ap.add_argument("output", help="결과 저장 폴더")
    ap.add_argument("--gpu", action="store_true", help="GPU 사용(기본: CPU)")
    ap.add_argument("--upscale", type=float, default=2.0,
                    help="인식 전 확대 배율(기본 2.0)")
    args = ap.parse_args()

    import easyocr

    print("EasyOCR 리더 초기화 중 (최초 실행 시 모델 다운로드)...")
    readers = {
        "ko": easyocr.Reader(["ko", "en"], gpu=args.gpu),
        "ja": easyocr.Reader(["ja", "en"], gpu=args.gpu),
    }

    out_dir = Path(args.output) / "easyocr"
    out_dir.mkdir(parents=True, exist_ok=True)

    params = {
        "engine": "EasyOCR",
        "version": getattr(easyocr, "__version__", "unknown"),
        "readers": {"ko": ["ko", "en"], "ja": ["ja", "en"]},
        "policy": "박스 단위 ko/ja 앙상블(IoU 0.45, 신뢰도 우선), 확대 배율 %s" % args.upscale,
        "box_order": "박스 y좌표 상→하 정렬(세로쓰기 읽기 순서)",
        "gpu": args.gpu,
        "date": time.strftime("%Y-%m-%d"),
    }
    with open(out_dir / "params.json", "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

    page_dirs = sorted(d for d in Path(args.input).iterdir()
                       if d.is_dir() and (d / "meta.json").exists())
    if not page_dirs:
        raise SystemExit("meta.json이 있는 페이지 폴더가 없습니다. preprocess.py를 먼저 실행하세요.")

    for pd in page_dirs:
        with open(pd / "meta.json", encoding="utf-8") as f:
            meta = json.load(f)

        page_result = {"source": meta["source"], "columns": []}
        merged, merged_ja, merged_ko = [], [], []
        t0 = time.time()

        for rname, cols in meta["regions"].items():
            for col in sorted(cols, key=lambda c: c["order"]):
                lang, info = read_column(readers, pd / col["file"],
                                         upscale=args.upscale)
                page_result["columns"].append({
                    "region": rname, "order": col["order"],
                    "file": col["file"], "lang": lang,
                    "conf": round(info["conf"], 4),
                    "n_boxes": info["n_boxes"],
                    "by_lang": info["by_lang"],
                    "text": info["text"],
                })
                merged.append(info["text"])
                merged_ja.append(info["text_by_lang"]["ja"])
                merged_ko.append(info["text_by_lang"]["ko"])

        (out_dir / f"{pd.name}.txt").write_text(
            "\n".join(t for t in merged if t), encoding="utf-8")
        (out_dir / f"{pd.name}_ja.txt").write_text(
            "\n".join(t for t in merged_ja if t), encoding="utf-8")
        (out_dir / f"{pd.name}_ko.txt").write_text(
            "\n".join(t for t in merged_ko if t), encoding="utf-8")
        with open(out_dir / f"{pd.name}.json", "w", encoding="utf-8") as f:
            json.dump(page_result, f, ensure_ascii=False, indent=2)

        nb = sum(c["n_boxes"] for c in page_result["columns"])
        print(f"[OK] {pd.name}: 컬럼 {len(page_result['columns'])}개, "
              f"박스 {nb}개, {time.time() - t0:.1f}초")


if __name__ == "__main__":
    main()
