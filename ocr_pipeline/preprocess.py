#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""근대 한국어 학습서 전처리 스크립트 (v2.1: 기울기·노이즈 내성 강화).

스캔 이미지 1장 = 책 2페이지(스프레드) 구조를 전제로 다음을 수행한다.

  0) 스프레드 분리: 중앙의 북 크래들(검은 세로 막대)을 검출하여
     좌·우 페이지로 분리. 읽기 순서는 우철 제본에 따라 오른쪽 페이지 먼저.
  1) 아티팩트 제거: 테두리에 닿은 큰 검은 덩어리(스캐너 가장자리, 크래들,
     카운터), 키가 페이지 높이의 절반을 넘는 세로 띠(책배 음영), 미세 얼룩 제거.
  2) 콘텐츠 크롭: 인쇄된 테두리 상자(frame)가 있으면 상자 내부로,
     없으면 잉크 질량 분위수(0.5%~99.5%) 기반 경계 상자로 크롭.
  3) 페이지 영역 분할: 수평 구분선을 연결 성분(가로로 길고 얇은 덩어리)으로
     검출하여 N개 영역으로 분리. 스캔 기울기가 있어도 검출됨.
  4) 세로쓰기 컬럼 분리: 잉크 밀도 프로파일로 세로 열 분리(우→좌 순).
     잉크량이 너무 적은 컬럼(얼룩)은 제거.

사용 예:
  python preprocess.py ./images ./preprocessed --debug
  python preprocess.py ./images ./out --no-spread   # 이미지 1장 = 1페이지일 때

출력: out/<이름>/p1_r1_col01.png ..., meta.json, debug.png(--debug)
디버그 색상: 파랑=크래들 분리선, 주황=콘텐츠 크롭, 빨강=구분선, 초록=컬럼

의존성: pip install opencv-python numpy
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

DEFAULTS = dict(
    gutter_band=(0.35, 0.65),      # 크래들 탐색 가로 구간(폭 대비)
    gutter_min_ratio=0.30,         # 크래들로 인정할 최소 세로 잉크 점유율
    artifact_min_area=0.003,       # 제거할 테두리 접촉 덩어리 최소 면적(비율)
    strip_max_height=0.55,         # 이보다 키 큰 성분은 책배 띠로 보고 제거(높이 대비)
    speck_min_area=30,             # 이보다 작은 성분은 얼룩으로 제거(픽셀)
    frame_min_cover=0.50,          # 테두리 상자로 인정할 최소 페이지 점유율
    frame_inset_ratio=0.010,       # 상자 내부 크롭 시 선 두께 여유(폭 대비)
    bbox_quantile=0.005,           # 콘텐츠 박스 잉크 질량 분위수(양끝)
    bbox_pad=12,                   # 콘텐츠 박스 여유(픽셀)
    divider_min_width_ratio=0.55,  # 구분선으로 인정할 최소 가로 점유율(영역 폭 대비)
    divider_max_thickness=45,      # 구분선 성분의 최대 세로 두께(픽셀, 기울기 허용)
    divider_min_seg=80,            # 허프 변환 선분 최소 길이(픽셀)
    divider_max_gap=18,            # 허프 변환 선분 내 최대 끊김(픽셀)
    divider_bridge=40,             # 선분 연결용 가로 팽창 폭(픽셀)
    min_region_height=60,          # 영역 최소 높이(픽셀, 머리글 조각 배제)
    col_smooth_window=15,          # 컬럼 프로파일 이동평균 창(픽셀)
    col_ink_thresh_ratio=0.05,     # 텍스트로 인정할 최소 잉크 밀도(최댓값 대비)
    col_min_gap=10,                # 컬럼 사이 최소 여백 폭(픽셀)
    col_min_width=15,              # 컬럼 최소 폭(픽셀)
    col_pad=4,                     # 컬럼 절단 여유(픽셀)
    col_min_ink_ratio=0.04,        # 컬럼 최소 잉크량(중앙값 컬럼 대비)
    col_max_fill=0.45,             # 컬럼 최대 잉크 충전율(책배 음영 띠 배제)
)


def binarize(gray):
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return bw


def find_gutter(bw, p):
    """중앙 크래들(검은 세로 막대) 검출. 반환: 분리 기준 x 좌표."""
    h, w = bw.shape
    x0, x1 = int(w * p["gutter_band"][0]), int(w * p["gutter_band"][1])
    col_ink = (bw[:, x0:x1] > 0).sum(axis=0) / h
    peak = int(np.argmax(col_ink))
    if col_ink[peak] >= p["gutter_min_ratio"]:
        return x0 + peak
    return w // 2


def remove_border_artifacts(bw, p):
    """테두리에 닿은 큰 검은 덩어리 제거(스캐너 가장자리·크래들·카운터)."""
    h, w = bw.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    clean = bw.copy()
    for i in range(1, n):
        x, y, cw, ch, area = stats[i]
        touches = x <= 2 or y <= 2 or x + cw >= w - 2 or y + ch >= h - 2
        big = (area > p["artifact_min_area"] * h * w
               or ch > 0.7 * h or cw > 0.7 * w)
        if touches and big:
            clean[labels == i] = 0
    return clean


def find_frame(bw_page, p):
    """페이지에 인쇄된 테두리 상자 검출. 반환: (x,y,w,h) 또는 None."""
    h, w = bw_page.shape
    n, _, stats, _ = cv2.connectedComponentsWithStats(bw_page, connectivity=8)
    best = None
    for i in range(1, n):
        x, y, cw, ch, _ = stats[i]
        if cw > p["frame_min_cover"] * w and ch > p["frame_min_cover"] * h:
            if best is None or cw * ch > best[2] * best[3]:
                best = (int(x), int(y), int(cw), int(ch))
    return best


def clean_page_noise(bw_page, p):
    """상자 없는 페이지의 노이즈 제거: 키 큰 세로 띠(책배 음영)·미세 얼룩."""
    h, w = bw_page.shape
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw_page, connectivity=8)
    clean = bw_page.copy()
    for i in range(1, n):
        x, y, cw, ch, area = stats[i]
        if ch > p["strip_max_height"] * h or area < p["speck_min_area"]:
            clean[labels == i] = 0
    return clean


def quantile_bbox(bw_page, p):
    """잉크 질량 분위수 기반 콘텐츠 경계 상자(희소한 난외 요소·얼룩에 강함)."""
    h, w = bw_page.shape
    col_mass = (bw_page > 0).sum(axis=0).astype(float)
    row_mass = (bw_page > 0).sum(axis=1).astype(float)
    if col_mass.sum() == 0:
        return None
    q = p["bbox_quantile"]
    cx = np.cumsum(col_mass) / col_mass.sum()
    cy = np.cumsum(row_mass) / row_mass.sum()
    x0 = int(np.searchsorted(cx, q))
    x1 = int(np.searchsorted(cx, 1 - q))
    y0 = int(np.searchsorted(cy, q))
    y1 = int(np.searchsorted(cy, 1 - q))
    pad = p["bbox_pad"]
    return (max(0, x0 - pad), max(0, y0 - pad),
            min(w, x1 + pad), min(h, y1 + pad))


def find_divider_spans(bw_crop, p, gray_crop=None):
    """수평 구분선을 연결 성분으로 검출(기울기 허용).

    가로 팽창으로 끊긴 선을 이은 뒤, 폭이 넓고(≥ ratio·W) 세로로 얇은
    (≤ max_thickness) 성분을 구분선으로 본다.
    반환: [(y0, y1), ...] (선 성분의 세로 구간, 위→아래 정렬)
    """
    h, w = bw_crop.shape
    if h < 3 * p["min_region_height"]:
        return []
    # 흐린 선 대비: 전역 이진화(Otsu)에서 지워진 옅은 구분선을
    # 국소 적응 이진화로 되살려 합침 (구분선 검출에만 사용)
    line_src = bw_crop
    if gray_crop is not None and gray_crop.shape == bw_crop.shape:
        adaptive = cv2.adaptiveThreshold(
            gray_crop, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY_INV, 31, 10)
        line_src = cv2.max(bw_crop, adaptive)
    # 허프 변환으로 수평 근처의 긴 선분 검출
    # (얇거나 끊기거나 기울었거나 글자에 닿은 구분선도 잡힘.
    #  세로쓰기 컬럼 사이 여백이 max_gap보다 넓어서
    #  글자 획들이 가짜 선으로 이어지는 것은 방지됨)
    segs = cv2.HoughLinesP(line_src, 1, np.pi / 180, threshold=80,
                           minLineLength=p["divider_min_seg"],
                           maxLineGap=p["divider_max_gap"])
    if segs is None:
        return []
    mask = np.zeros_like(bw_crop)
    for x1, y1, x2, y2 in np.asarray(segs).reshape(-1, 4):
        if abs(y2 - y1) <= max(4, 0.02 * abs(x2 - x1)):  # 수평 ±약 1.1도
            cv2.line(mask, (int(x1), int(y1)), (int(x2), int(y2)), 255, 3)
    k_bridge = cv2.getStructuringElement(cv2.MORPH_RECT, (p["divider_bridge"], 1))
    bridged = cv2.dilate(mask, k_bridge)
    n, _, stats, _ = cv2.connectedComponentsWithStats(bridged, connectivity=8)
    spans = []
    for i in range(1, n):
        x, y, cw, ch, _ = stats[i]
        if (cw >= p["divider_min_width_ratio"] * w
                and ch <= p["divider_max_thickness"]
                and p["min_region_height"] < y
                and y + ch < h - p["min_region_height"]):
            spans.append((int(y), int(y + ch)))
    spans.sort()
    # 겹치거나 붙은 스팬 병합
    merged = []
    for s in spans:
        if merged and s[0] <= merged[-1][1] + 3:
            merged[-1] = (merged[-1][0], max(merged[-1][1], s[1]))
        else:
            merged.append(s)
    return merged


def moving_average(x, window):
    if window <= 1:
        return x.astype(float)
    return np.convolve(x, np.ones(window) / window, mode="same")


def split_columns(bw_crop, p):
    """세로쓰기 컬럼 분리 + 저잉크 컬럼(얼룩) 제거.

    반환: [(x0, x1), ...] (좌→우 오름차순)
    """
    col_ink = (bw_crop > 0).sum(axis=0).astype(float)
    smooth = moving_average(col_ink, p["col_smooth_window"])
    if smooth.max() <= 0:
        return []
    mask = smooth > smooth.max() * p["col_ink_thresh_ratio"]

    runs, x, n = [], 0, len(mask)
    while x < n:
        if mask[x]:
            s = x
            while x < n and mask[x]:
                x += 1
            runs.append([s, x])
        else:
            x += 1

    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < p["col_min_gap"]:
            merged[-1][1] = r[1]
        else:
            merged.append(r)

    cols = [(max(0, a - p["col_pad"]), min(n, b + p["col_pad"]))
            for a, b in merged if b - a >= p["col_min_width"]]
    if not cols:
        return []

    # 저잉크 컬럼(얼룩) 및 과충전 컬럼(책배 음영 띠) 제거
    h = bw_crop.shape[0]
    inks = [col_ink[a:b].sum() for a, b in cols]
    med = float(np.median(inks))
    kept = []
    for (a, b), ink in zip(cols, inks):
        if med > 0 and ink < med * p["col_min_ink_ratio"]:
            continue  # 얼룩: 잉크가 너무 적음
        if ink / max((b - a) * h, 1) > p["col_max_fill"]:
            continue  # 음영 띠: 면적 대비 잉크가 비정상적으로 빽빽함
        kept.append((a, b))
    return kept


def process_image(img_path, out_dir, p, no_spread=False, debug=False):
    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"이미지를 읽을 수 없습니다: {img_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    bw_raw = binarize(gray)

    gutter_x = None if no_spread else find_gutter(bw_raw, p)
    bw = remove_border_artifacts(bw_raw, p)

    if gutter_x is not None:
        halves = [("p1", gutter_x, W), ("p2", 0, gutter_x)]
    else:
        halves = [("p1", 0, W)]

    page_dir = out_dir / img_path.stem
    page_dir.mkdir(parents=True, exist_ok=True)
    meta = {"source": img_path.name, "image_size": [W, H],
            "gutter_x": gutter_x,
            "params": {k: list(v) if isinstance(v, tuple) else v
                       for k, v in p.items()},
            "regions": {}}

    dbg = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) if debug else None
    if debug and gutter_x is not None:
        cv2.line(dbg, (gutter_x, 0), (gutter_x, H), (255, 0, 0), 4)

    # 컬럼 크롭에 쓸 정제 이미지(아티팩트 제거분을 흰색으로)
    clean_gray = gray.copy()

    for pname, hx0, hx1 in halves:
        bw_page = bw[:, hx0:hx1]

        frame = find_frame(bw_page, p)
        if frame is not None:
            fx, fy, fw, fh = frame
            inset = int(p["frame_inset_ratio"] * fw) + 4
            cx0, cy0 = hx0 + fx + inset, fy + inset
            cx1, cy1 = hx0 + fx + fw - inset, fy + fh - inset
            crop_bw = bw[cy0:cy1, cx0:cx1]
        else:
            cleaned = clean_page_noise(bw_page, p)
            bb = quantile_bbox(cleaned, p)
            if bb is None:
                continue
            cx0, cy0, cx1, cy1 = bb[0] + hx0, bb[1], bb[2] + hx0, bb[3]
            crop_bw = cleaned[cy0:cy1, cx0 - hx0:cx1 - hx0]

        # 정제 결과를 clean_gray에 반영(제거된 잉크는 흰색)
        sub_raw = bw_raw[cy0:cy1, cx0:cx1]
        clean_gray[cy0:cy1, cx0:cx1][(sub_raw > 0) & (crop_bw == 0)] = 255

        if debug:
            cv2.rectangle(dbg, (cx0, cy0), (cx1, cy1), (0, 165, 255), 3)

        spans = find_divider_spans(crop_bw, p, gray[cy0:cy1, cx0:cx1])
        bounds = [(0, 0)] + spans + [(crop_bw.shape[0], crop_bw.shape[0])]
        if debug:
            for s0, s1 in spans:
                cv2.rectangle(dbg, (cx0, cy0 + s0), (cx1, cy0 + s1),
                              (0, 0, 255), 3)

        ri = 0
        for (a0, a1), (b0, b1) in zip(bounds[:-1], bounds[1:]):
            r0, r1 = a1 + 3, b0 - 3
            r0, r1 = max(0, r0), min(crop_bw.shape[0], r1)
            if r1 - r0 < p["min_region_height"]:
                continue
            ri += 1
            rname = f"{pname}_r{ri}"
            region_bw = crop_bw[r0:r1, :]

            cols = sorted(split_columns(region_bw, p), key=lambda c: -c[0])
            meta["regions"][rname] = []
            for i, (x0, x1) in enumerate(cols, start=1):
                gx0, gx1 = cx0 + x0, cx0 + x1
                gy0, gy1 = cy0 + r0, cy0 + r1
                crop = clean_gray[gy0:gy1, gx0:gx1]
                fname = f"{rname}_col{i:02d}.png"
                cv2.imwrite(str(page_dir / fname), crop)
                meta["regions"][rname].append(
                    {"file": fname, "order": i,
                     "x0": int(gx0), "x1": int(gx1),
                     "y0": int(gy0), "y1": int(gy1)})
                if debug:
                    cv2.rectangle(dbg, (gx0, gy0), (gx1, gy1), (0, 180, 0), 2)
                    cv2.putText(dbg, str(i), (gx0 + 2, gy0 + 32),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)

    if debug:
        cv2.imwrite(str(page_dir / "debug.png"), dbg)
    with open(page_dir / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


def main():
    ap = argparse.ArgumentParser(description="스프레드 분리 + 영역 분할 + 컬럼 분리")
    ap.add_argument("input", help="입력 이미지 폴더(또는 단일 파일)")
    ap.add_argument("output", help="출력 폴더")
    ap.add_argument("--no-spread", action="store_true",
                    help="이미지 1장 = 책 1페이지일 때(좌우 분리 생략)")
    ap.add_argument("--debug", action="store_true", help="검출 시각화 저장")
    for k, v in DEFAULTS.items():
        if isinstance(v, tuple):
            continue
        ap.add_argument(f"--{k.replace('_', '-')}", type=type(v), default=v)
    args = ap.parse_args()

    p = dict(DEFAULTS)
    for k in DEFAULTS:
        if hasattr(args, k):
            p[k] = getattr(args, k)

    in_path, out_dir = Path(args.input), Path(args.output)
    exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
    files = ([in_path] if in_path.is_file()
             else sorted(f for f in in_path.iterdir() if f.suffix.lower() in exts))
    if not files:
        raise SystemExit("입력 이미지가 없습니다.")

    for f in files:
        meta = process_image(f, out_dir, p, args.no_spread, args.debug)
        ncols = sum(len(v) for v in meta["regions"].values())
        nreg = len(meta["regions"])
        print(f"[OK] {f.name}: 페이지 {'2' if meta['gutter_x'] else '1'}면, "
              f"영역 {nreg}개, 컬럼 {ncols}개")


if __name__ == "__main__":
    main()
