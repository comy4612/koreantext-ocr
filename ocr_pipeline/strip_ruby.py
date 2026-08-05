#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""본문 문자와 루비(주석) 문자 분리 — 워크플로우 4.4단계의 간이 구현. (v2)

v2 변경점:
  - 글자 크기 기준을 컬럼 내부가 아니라 영역(region) 단위로 산출.
    (루비만으로 이루어진 컬럼에서는 컬럼 내부 중앙값이 곧 루비 크기라서
     아무것도 제거되지 않던 문제 해결)
  - 컬럼 전체가 루비인 경우(본문 열 옆에 별도 열로 분리된 루비)를
    통째로 제거: 컬럼의 글자 높이 중앙값이 영역 본문 크기에 크게
    못 미치면 루비 컬럼으로 판정.
  - "一"처럼 높이는 낮지만 폭이 넓은 본문 글자 보호(폭 조건 추가).

판정 규칙:
  main_h  = 영역 내 모든 글자 덩어리 높이의 75분위수(본문 글자 크기)
  루비 컬럼: 컬럼 덩어리 높이 중앙값 < main_h * ruby_size_ratio
  루비 덩어리(잔존): 높이 < main_h * ruby_size_ratio
                     AND 폭 < main_h (세장형 본문 글자 보호)
                     AND 중심이 컬럼 중앙선(right_bias) 오른쪽

사용 예:
  python strip_ruby.py ./preprocessed ./preprocessed_noruby
  python strip_ruby.py ./preprocessed ./out --debug

출력: 입력과 동일 구조(meta.json 복사, 같은 파일명). 루비 컬럼은 백지로 저장.
"""

import argparse
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

DEFAULTS = dict(
    close_kernel=5,        # 글자 획 병합용 닫힘 커널 크기(픽셀)
    close_iter=2,          # 닫힘 반복 횟수
    ruby_size_ratio=0.62,  # 본문 크기 대비 이 비율 미만이면 루비
    min_blob_area=40,      # 크기 통계에 포함할 최소 덩어리 면적
    right_bias=0.55,       # 잔존 루비 판정 위치 기준(컬럼 폭 대비)
)


def blobs_of(gray, p):
    """이진화+닫힘 후 글자 덩어리 목록 [(x,y,w,h,area), ...]와 라벨 반환."""
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, bw = cv2.threshold(blur, 0, 255,
                          cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    k = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (p["close_kernel"], p["close_kernel"]))
    closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, k,
                              iterations=p["close_iter"])
    n, labels, stats, _ = cv2.connectedComponentsWithStats(closed, 8)
    blobs = [tuple(stats[i]) + (i,) for i in range(1, n)
             if stats[i][4] >= p["min_blob_area"]]
    return blobs, labels


def process_region(page_dir, out_dir, cols, p, debug):
    """한 영역의 컬럼들을 함께 처리(본문 크기를 영역 단위로 산출)."""
    data = []  # (col, gray, blobs, labels)
    all_heights = []
    for col in cols:
        gray = cv2.imread(str(page_dir / col["file"]), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        blobs, labels = blobs_of(gray, p)
        data.append((col, gray, blobs, labels))
        all_heights.extend(b[3] for b in blobs)

    if not all_heights:
        for col, gray, _, _ in data:
            cv2.imwrite(str(out_dir / col["file"]), gray)
        return 0, 0

    main_h = float(np.percentile(all_heights, 75))
    thresh_h = main_h * p["ruby_size_ratio"]
    n_ruby_cols = n_ruby_blobs = 0

    for col, gray, blobs, labels in data:
        col_w = gray.shape[1]
        dbg = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) if debug else None

        # 루비 컬럼 판정: 본문 크기의 글자가 사실상 없는 컬럼
        # (중앙값 기준은 루비 글자 수가 본문보다 많은 혼합 컬럼을
        #  오판하므로, 90분위 높이로 "큰 글자의 존재 여부"를 본다)
        col_p90 = float(np.percentile([b[3] for b in blobs], 90)) if blobs else 0.0
        if blobs and col_p90 < thresh_h:
            # 컬럼 전체가 루비(본문 열 옆에 분리된 루비 열) → 백지 처리
            out = np.full_like(gray, 255)
            n_ruby_cols += 1
            if debug:
                cv2.rectangle(dbg, (0, 0), (col_w - 1, gray.shape[0] - 1),
                              (0, 0, 255), 4)
        else:
            out = gray.copy()
            for x, y, cw, ch, area, lab in blobs:
                cx = x + cw / 2
                is_ruby = (ch < thresh_h and cw < main_h
                           and cx > col_w * p["right_bias"])
                if is_ruby:
                    out[labels == lab] = 255
                    n_ruby_blobs += 1
                    if debug:
                        cv2.rectangle(dbg, (x, y), (x + cw, y + ch),
                                      (0, 0, 255), 1)
                elif debug:
                    cv2.rectangle(dbg, (x, y), (x + cw, y + ch),
                                  (0, 180, 0), 1)

        cv2.imwrite(str(out_dir / col["file"]), out)
        if debug:
            cv2.imwrite(str(out_dir / f"dbg_{col['file']}"), dbg)

    return n_ruby_cols, n_ruby_blobs


def main():
    ap = argparse.ArgumentParser(description="루비(주석) 문자 분리 - 4.4단계 간이 구현 v2")
    ap.add_argument("input", help="preprocess.py 출력 폴더")
    ap.add_argument("output", help="루비 제거본 저장 폴더")
    ap.add_argument("--debug", action="store_true", help="판정 시각화 저장")
    for kname, v in DEFAULTS.items():
        ap.add_argument(f"--{kname.replace('_', '-')}", type=type(v), default=v)
    args = ap.parse_args()
    p = {kname: getattr(args, kname) for kname in DEFAULTS}

    in_dir, out_dir = Path(args.input), Path(args.output)
    page_dirs = sorted(d for d in in_dir.iterdir()
                       if d.is_dir() and (d / "meta.json").exists())
    if not page_dirs:
        raise SystemExit("meta.json이 있는 페이지 폴더가 없습니다.")

    for pd in page_dirs:
        od = out_dir / pd.name
        od.mkdir(parents=True, exist_ok=True)
        shutil.copy(pd / "meta.json", od / "meta.json")
        with open(pd / "meta.json", encoding="utf-8") as f:
            meta = json.load(f)
        rc = rb = 0
        for cols in meta["regions"].values():
            a, b = process_region(pd, od, cols, p, args.debug)
            rc += a
            rb += b
        print(f"[OK] {pd.name}: 루비 컬럼 {rc}개 제거, 잔존 루비 덩어리 {rb}개 제거")

    with open(out_dir / "strip_ruby_params.json", "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
