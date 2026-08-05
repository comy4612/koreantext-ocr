# 근대 한국어 학습서 OCR 전처리 워크플로우 파일럿 검증

Preprocessing Workflow for OCR of Early Modern Korean Textbooks for Japanese
Learners: Pilot Validation Code and Data

근대(19세기 말~20세기 초) 일본인을 위한 한국어 학습서의 디지털화를 위한
전처리 워크플로우의 구현 코드, 평가 데이터(정답지), 실험 결과입니다.
세로쓰기, 일·한 병렬 배치, 루비 문자(후리가나·가타카나 발음 표기)라는
구조적 난제를 다루는 단계별 전처리(페이지 영역 분할, 언어 영역 판별,
컬럼 분리, 본문·주석 문자 분리)를 제공하고, 전처리 적용 전후의
CER(문자 단위 오류율)를 삽입/대체/삭제로 분해하여 비교합니다.

## 저장소 구조

```
├── ocr_pipeline/            # 전처리·OCR·평가 스크립트
│   ├── preprocess.py        #   4.1~4.3: 스프레드 분리, 아티팩트 제거,
│   │                        #   영역 분할(허프 변환), 컬럼 분리
│   ├── strip_ruby.py        #   4.4: 본문·주석(루비) 문자 분리
│   ├── run_baseline_ocr.py  #   기준선: 원본 스캔면 전체 EasyOCR
│   ├── run_local_ocr.py     #   전처리 후: 컬럼 단위 EasyOCR(ko/ja 박스 앙상블)
│   ├── run_tesseract.py     #   Tesseract(kor_vert+jpn_vert) 전/후 실행
│   ├── run_ocr.py           #   (선택) 클라우드 API 호출 + 언어 판별 함수
│   ├── json_to_gt.py        #   JSON 정답지 → 평가용 txt 변환
│   └── evaluate_cer.py      #   CER 산출 + 삽입/대체/삭제 분해
├── gt_json/                 # 정답지 원본(JSON, 문헌 4종 × 40페이지)
├── gt/                      # 평가용 정답지(루비 포함, 스캔면 단위 txt)
├── gt_noruby/               # 평가용 정답지(본문 문자만)
├── results/                 # 실험 결과(조건별 OCR 출력 txt, 비교 CSV)
├── requirements.txt
└── LICENSE
```

## 대상 문헌

| 약칭 | 서명 | 간행 연도 |
|---|---|---|
| 국원 | 局員須知日鮮会話 | 1912 |
| 신선 | 新選正則日鮮会話 | 1912 |
| 국어 | 國語鮮語双舌通解 | 1913 |
| 포켓 | ポケット朝鮮語独学 | 1915 |

## 원시 데이터(스캔 이미지) 취득 안내

네 문헌의 스캔 이미지는 모두 도쿄경제대학 도서관 사쿠라이 요시유키
문고(桜井義之文庫) 디지털 아카이브 소장 자료로, 아래 링크에서 로그인
없이 누구나 열람·다운로드할 수 있습니다. 원문 자체는 저작권 보호
기간이 만료된 자료이나, 스캔 파일의 재배포는 소장 기관의 이용 정책을
따르므로 본 저장소에는 이미지를 직접 포함하지 않고 취득 경로를
안내합니다(소장 기관의 게재 허가를 받는 대로 이미지를 추가할
예정입니다). 파일명 규칙은 `README`의 재현 절차와 `gt/`의 정답지
파일명을 따르십시오.

| 약칭 | 아카이브 URL | 사용 페이지 |
|---|---|---|
| 국원 | [문헌별 영구 링크 기입] | 18-21, 60-65 |
| 신선 | [문헌별 영구 링크 기입] | 76-79, 112-117 |
| 국어 | [문헌별 영구 링크 기입] | 46-49, 94-99 |
| 포켓 | [문헌별 영구 링크 기입] | 38-41, 152-157 |

## 설치

```bash
# Python 3.11 권장
pip install -r requirements.txt

# Tesseract (Ubuntu/WSL)
sudo apt install -y tesseract-ocr
sudo wget -P /usr/share/tesseract-ocr/5/tessdata \
    https://github.com/tesseract-ocr/tessdata_best/raw/main/kor_vert.traineddata
sudo wget -P /usr/share/tesseract-ocr/5/tessdata \
    https://github.com/tesseract-ocr/tessdata_best/raw/main/jpn_vert.traineddata
```

## 재현 절차

```bash
# 0. 정답지 변환 (루비 유지+장음 정규화 / 본문만)
python ocr_pipeline/json_to_gt.py "gt_json/*.json" -o ./gt \
    --dash-to-choon --exclude-page 177
python ocr_pipeline/json_to_gt.py "gt_json/*.json" -o ./gt_noruby \
    --drop-ruby --exclude-page 177

# 1. 전처리 (4.1~4.3) — 검출 시각화는 --debug
python ocr_pipeline/preprocess.py ./images ./preprocessed --debug

# 2. 루비 분리 (4.4)
python ocr_pipeline/strip_ruby.py ./preprocessed ./preprocessed_noruby

# 3. OCR 실행 (기준선 / 전처리 후) — GPU는 --gpu
python ocr_pipeline/run_baseline_ocr.py ./images ./results_before
python ocr_pipeline/run_local_ocr.py ./preprocessed_noruby ./results_after
python ocr_pipeline/run_tesseract.py baseline ./images ./results_before
python ocr_pipeline/run_tesseract.py after ./preprocessed_noruby ./results_after

# 4. 평가 (전/후 비교 + 오류 분해)
python ocr_pipeline/evaluate_cer.py --ref-dir ./gt_noruby \
    --hyp-dir ./results_before/tesseract \
    --hyp-dir2 ./results_after/tesseract --csv compare.csv
```

모든 실행 파라미터는 각 출력 폴더의 `meta.json` / `params.json` /
`strip_ruby_params.json`에 자동 기록됩니다.

## 정답지(JSON) 스키마

```json
{
  "page": 18,                 // 책 페이지 번호
  "contents": "局員須知日鮮会話(1912)",
  "line_id": "018_01",        // 페이지 내 행 식별자(전사 순서)
  "text_type": "word",        // word/sent/title_1~3/page_num/anno/info
  "page_position": "top",     // 페이지 내 위치(top/mid/bot, col_N 등)
  "hanguel_position": "none",
  "text_ja": "朝鮮{デウセン}",  // 일본어(중괄호 안은 루비)
  "text_ko": "죠션{チヨ-ソン}", // 한국어(중괄호 안은 발음 가타카나, '-'는 장음)
  "note": ""
}
```

입력 지침: 인쇄 상태로 구분이 어려운 가나 대소문자(ツ/ッ 등)는 대문자로
정규화하였고, p행/b행 가나는 시각적으로 판독 가능한 형태를 따랐습니다
(세부 지침은 논문 3.1절 참조).

## 평가 규칙

CER = (삽입+대체+삭제)/정답 문자 수. 비교 전에 유니코드 NFC 정규화와
공백·개행 제거를 적용합니다. 루비의 중괄호는 지면에 없는 마크업이므로
제거하며, 루비 분리 조건의 출력은 본문 정답지(`gt_noruby/`)와 대조합니다.

## 라이선스

- 코드: MIT License (`LICENSE`)
- 정답지(JSON·txt) 및 실험 결과: CC BY 4.0
- 원시 데이터(스캔 이미지): 원문은 저작권 보호 기간 만료.
  스캔본은 도쿄경제대학 도서관 사쿠라이 요시유키 문고 소장 디지털
  아카이브 자료로, 본 저장소에는 포함하지 않으며 위의 취득 안내를
  참조하십시오. 이용 시 소장처를 표기하십시오.

## 인용

```
[게재 확정 후 서지 정보 및 Zenodo DOI 기입]
```
