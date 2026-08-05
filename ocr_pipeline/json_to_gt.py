#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JSON 정답지 → CER 평가용 페이지 단위 txt 변환.

정답지 JSON 구조(항목 예):
  {"page": 18, "line_id": "018_01", "text_type": "word",
   "text_ja": "朝鮮{デウセン}", "text_ko": "죠션{チヨ-ソン}", ...}

처리 내용:
  - 페이지를 line_id 순으로 정렬하여 병합
  - 루비 마크업 처리: 기본은 중괄호만 제거하고 루비 문자는 유지
    ("朝鮮{デウセン}" → "朝鮮デウセン"; 지면에 실제로 인쇄된 문자이므로)
  - 스캔 이미지 1장 = 책 2페이지이므로, 연속된 페이지를 짝지어
    "<접두어>_p018-019.txt" 형태로 저장 (--single-page 시 페이지별 저장)
  - --split-lang: "_ja.txt"/"_ko.txt"로 언어별 분리 저장(언어별 CER 평가용)

사용 예:
  python json_to_gt.py "정답지폴더/*.json" -o ./gt
  python json_to_gt.py "정답지폴더/*.json" -o ./gt --split-lang
  python json_to_gt.py 국원.json -o ./gt --drop-ruby --exclude-page 177

이미지 파일명은 생성된 txt와 같은 이름으로 맞출 것.
  예: gt/1912_국원수지일선회화_p018-019.txt
      images/1912_국원수지일선회화_p018-019.png
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path

RUBY_RE = re.compile(r"\{([^{}]*)\}")


def clean_text(text, drop_ruby=False, dash_to_choon=False):
    """루비 마크업 정리.

    drop_ruby=False: 중괄호만 제거, 루비 문자는 유지 (기본)
    drop_ruby=True : 루비 전체 제거 (본문 문자만 평가할 때)
    dash_to_choon  : 루비 안의 '-'를 장음 기호 'ー'로 치환
    """
    if drop_ruby:
        return RUBY_RE.sub("", text)
    if dash_to_choon:
        text = RUBY_RE.sub(lambda m: m.group(1).replace("-", "ー"), text)
        return text
    return text.replace("{", "").replace("}", "")


def convert_file(json_path, out_dir, args):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    exclude = set(args.exclude_page or [])
    data = [e for e in data if e["page"] not in exclude]
    if args.exclude_type:
        excl_types = set(args.exclude_type)
        data = [e for e in data if e.get("text_type") not in excl_types]

    # 접두어: 파일명에서 "_after" 제거, 공백 → 밑줄
    prefix = Path(json_path).stem.replace("_after", "").replace(" ", "_")

    # 페이지별로 line_id 순 정렬
    pages = {}
    for e in data:
        pages.setdefault(e["page"], []).append(e)
    for p in pages:
        pages[p].sort(key=lambda e: e["line_id"])

    sorted_pages = sorted(pages)

    # 그룹핑: 스캔 1장 = 연속 2페이지 (--single-page 시 1페이지)
    if args.single_page:
        groups = [[p] for p in sorted_pages]
    else:
        if len(sorted_pages) % 2 != 0:
            print(f"[경고] {prefix}: 페이지 수가 홀수({len(sorted_pages)})라서 "
                  f"마지막 페이지 {sorted_pages[-1]}는 단독 저장됩니다. "
                  f"오입력이면 --exclude-page로 제외하세요.", file=sys.stderr)
        groups = [sorted_pages[i:i + 2] for i in range(0, len(sorted_pages), 2)]

    out_dir.mkdir(parents=True, exist_ok=True)
    n_files = 0
    for grp in groups:
        name = (f"{prefix}_p{grp[0]:03d}" if len(grp) == 1
                else f"{prefix}_p{grp[0]:03d}-{grp[1]:03d}")

        ja_lines, ko_lines, mixed_lines = [], [], []
        for p in grp:
            for e in pages[p]:
                ja = clean_text(e.get("text_ja", ""), args.drop_ruby,
                                args.dash_to_choon)
                ko = clean_text(e.get("text_ko", ""), args.drop_ruby,
                                args.dash_to_choon)
                if ja:
                    ja_lines.append(ja)
                    mixed_lines.append(ja)
                if ko:
                    ko_lines.append(ko)
                    mixed_lines.append(ko)

        if args.split_lang:
            (out_dir / f"{name}_ja.txt").write_text("\n".join(ja_lines),
                                                    encoding="utf-8")
            (out_dir / f"{name}_ko.txt").write_text("\n".join(ko_lines),
                                                    encoding="utf-8")
            n_files += 2
        else:
            (out_dir / f"{name}.txt").write_text("\n".join(mixed_lines),
                                                 encoding="utf-8")
            n_files += 1

    print(f"[OK] {prefix}: 페이지 {len(sorted_pages)}개 → 파일 {n_files}개")
    return n_files


def main():
    ap = argparse.ArgumentParser(description="JSON 정답지 → 페이지 단위 txt")
    ap.add_argument("inputs", nargs="+", help="JSON 파일(들) 또는 글롭 패턴")
    ap.add_argument("-o", "--out", required=True, help="출력 폴더")
    ap.add_argument("--single-page", action="store_true",
                    help="페이지별 저장(기본: 연속 2페이지 묶음)")
    ap.add_argument("--split-lang", action="store_true",
                    help="언어별(_ja/_ko) 분리 저장")
    ap.add_argument("--drop-ruby", action="store_true",
                    help="루비 문자를 완전히 제거(기본: 중괄호만 제거)")
    ap.add_argument("--dash-to-choon", action="store_true",
                    help="루비 안의 '-'를 장음 'ー'로 치환")
    ap.add_argument("--exclude-page", type=int, action="append",
                    help="제외할 페이지 번호(반복 지정 가능)")
    ap.add_argument("--exclude-type", action="append",
                    help="제외할 text_type(반복 지정 가능. 예: --exclude-type "
                         "page_num --exclude-type title_2)")
    args = ap.parse_args()

    files = []
    for pat in args.inputs:
        matched = glob.glob(pat)
        files.extend(matched if matched else [pat])

    total = 0
    for f in sorted(files):
        total += convert_file(f, Path(args.out), args)
    print(f"총 {total}개 파일 생성 → {args.out}")


if __name__ == "__main__":
    main()
