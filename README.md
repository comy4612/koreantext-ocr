# 근대 한국어 학습서 OCR 전처리 워크플로우 파일럿 검증

Preprocessing Workflow for OCR of Early Modern Korean Textbooks for Japanese
Learners: Pilot Validation Code and Data

근대(19세기 말~20세기 초) 일본인을 위한 한국어 학습서의 디지털화를 위한 전처리
워크플로우의 구현 코드, 평가 자료(원본 이미지·정답지), 실험 결과입니다.
세로쓰기, 일·한 병렬 배치, 루비 문자(후리가나·가타카나 발음 표기)라는 구조적
난제를 다루는 단계별 전처리(페이지 영역 분할, 언어 영역 판별, 컬럼 분리,
본문·주석 문자 분리)를 제공하고, 전처리 적용 전후의 CER(문자 단위 오류율)를
삽입·대체·삭제로 분해하여 비교합니다. 문자 단위 정밀도·재현율·F1도 함께
산출합니다.

## 저장소 구조

```
├── ocr_pipeline/              # 전처리·OCR·평가 스크립트
│   ├── preprocess.py          #   4.1~4.3: 스프레드 분리, 잡음 제거,
│   │                          #   영역 분할(허프 변환), 컬럼 분리
│   ├── strip_ruby.py          #   4.4: 본문·주석(루비) 문자 분리
│   │                          #   --ruby-output 으로 루비 계층도 별도 출력
│   ├── run_baseline_ocr.py    #   기준선: 원본 스캔면 전체 EasyOCR
│   ├── run_local_ocr.py       #   전처리 후: 컬럼 단위 EasyOCR(ko/ja 박스 앙상블)
│   ├── run_tesseract.py       #   Tesseract(kor_vert+jpn_vert) 전/후 실행
│   ├── run_ocr.py             #   (선택) 클라우드 API 호출 + 언어 판별 함수
│   ├── json_to_gt.py          #   JSON 정답지 → 평가용 txt 변환
│   └── evaluate_cer.py        #   CER + 삽입·대체·삭제 분해 + 정밀도·재현율·F1
├── commercial_ocr_eval/       # 상용 OCR 5종 평가
│   ├── ocr_output/            #   엔진별 호출 결과(JSON·txt)
│   └── scripts/
│       ├── *_make_answer.py   #   API 호출 스크립트
│       ├── *_cer_result_*.py  #   1차 산출 당시의 채점 스크립트
│       └── rescore_commercial.py  # 재채점 — 정답지 축을 통일하여 재산출
├── images/                    # 평가 자료 원본 이미지 20장(4종 40면)
├── gt_json/                   # 정답지 원본(JSON, 4종 40면)
├── gt/                        # 평가용 정답지 — 루비 포함
├── gt_noruby/                 # 평가용 정답지 — 본문 문자만
├── gt_rubyonly/               # 평가용 정답지 — 루비 문자만
├── gt_lang/                   # 평가용 정답지 — 언어별(_ja/_ko) 분리
├── results_before/            # 기준선(전처리 없음) 인식 결과
├── results_after/             # 분할만 적용한 인식 결과
├── results_after_noruby/      # 분할+루비 분리 — 본문 계층(Tesseract)
├── results_after_noruby_easy/ # 분할+루비 분리 — 본문 계층(EasyOCR)
├── results_ruby/              # 루비 계층 인식 결과
├── compare_*.csv, f1_*.csv    # 조건별 비교표
├── ENVIRONMENT.md             # 실행 환경·모델 가중치 판본과 해시
├── requirements.txt
└── LICENSE
```

## 대상 문헌

모두 **東京經濟大學圖書館 櫻井義之文庫** 소장본입니다.

| 약칭 | 서명 | 저자·편자 | 간행 | 영구 URI |
|---|---|---|---|---|
| 국원 | 局員須知日鮮會話 | 韓圭復·林田虎雄 編纂 | 京城: 朝鮮總督府臨時土地調査局, 1912 | https://tku.repo.nii.ac.jp/records/2007328 |
| 신선 | 新撰正則日鮮會話 | 齋藤助昇 著 | 京城: 日韓書房, 1912 | https://tku.repo.nii.ac.jp/records/2007548 |
| 국어 | 國語鮮語雙舌通解 | 小野綱方 著 | 京城: 日韓印刷, 1913 | https://tku.repo.nii.ac.jp/records/2007513 |
| 포켓 | ポケット朝鮮語獨學 | 弓場重榮 著 | 京城: 日韓書房, 1915 | https://tku.repo.nii.ac.jp/records/2007421 |

> 서명은 원본 표기(구자체)를 따릅니다. 소장 기관 목록은 신자체
> (`局員須知日鮮会話`, `国語鮮語雙舌通解`, `ポケット朝鮮語独学`)로 되어 있습니다.
> 리포지터리는 2026년 9월 DSpace에서 WEKO3로 이관되었으며, 이전 주소
> (`repository.tku.ac.jp`)는 더 이상 유효하지 않습니다.

평가에 사용한 면은 다음과 같습니다.

| 약칭 | 사용 면 |
|---|---|
| 국원 | 18–19, 20–21, 60–61, 62–63, 64–65 |
| 신선 | 76–77, 78–79, 112–113, 114–115, 116–117 |
| 국어 | 46–47, 48–49, 94–95, 96–97, 98–99 |
| 포켓 | 38–39, 40–41, 152–153, 154–155, 156–157 |

원본 이미지는 `images/`에 포함되어 있습니다. 출처와 이용 조건은
`images/README.md`를 참조하십시오.

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

세로쓰기 학습 모델은 **`tessdata_best`** 판본을 사용합니다. 세 판본
(`tessdata`, `tessdata_fast`, `tessdata_best`) 가운데 정확도가 가장 높으며,
판본이 다르면 인식 결과가 달라집니다. 파일 크기와 해시값은 `ENVIRONMENT.md`에
기록해 두었습니다.

## 재현 절차

```bash
# 0. 정답지 변환 (루비 포함 / 본문만 / 루비만)
python ocr_pipeline/json_to_gt.py "gt_json/*.json" -o ./gt \
    --dash-to-choon --exclude-page 177
python ocr_pipeline/json_to_gt.py "gt_json/*.json" -o ./gt_noruby \
    --drop-ruby --exclude-page 177
python ocr_pipeline/json_to_gt.py "gt_json/*.json" -o ./gt_rubyonly \
    --ruby-only --dash-to-choon --exclude-page 177

# 1. 전처리 (4.1~4.3) — 검출 시각화는 --debug
python ocr_pipeline/preprocess.py ./images ./preprocessed --debug

# 2. 루비 분리 (4.4) — 본문 계층과 루비 계층을 함께 출력
python ocr_pipeline/strip_ruby.py ./preprocessed ./preprocessed_noruby \
    --ruby-output ./preprocessed_rubyonly

# 3. OCR 실행 (기준선 / 전처리 후) — GPU는 --gpu
python ocr_pipeline/run_baseline_ocr.py ./images ./results_before
python ocr_pipeline/run_local_ocr.py ./preprocessed_noruby ./results_after_noruby_easy
python ocr_pipeline/run_tesseract.py baseline ./images ./results_before
python ocr_pipeline/run_tesseract.py after ./preprocessed_noruby ./results_after_noruby

# 4. 평가 — 전/후 비교, 오류 분해, 정밀도·재현율·F1
python ocr_pipeline/evaluate_cer.py --ref-dir ./gt_noruby \
    --hyp-dir ./results_before/tesseract \
    --hyp-dir2 ./results_after_noruby/tesseract --csv compare_tess.csv

# 5. (선택) 상용 OCR 5종 재채점 — 3장과 5장의 정답지 축을 통일
cd commercial_ocr_eval/scripts
python rescore_commercial.py --root .. --gt-mode body --csv ../rescore_body.csv
python rescore_commercial.py --root .. --gt-mode full --csv ../rescore_full.csv
```

모든 실행 파라미터는 각 출력 폴더의 `meta.json` / `params.json` /
`strip_ruby_params.json`에 자동 기록됩니다. 실행 환경은 `ENVIRONMENT.md`를
참조하십시오.

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
정규화하였고, p행/b행 가나는 시각적으로 판독 가능한 형태를 따랐습니다.

## 평가 규칙

CER = (삽입 + 대체 + 삭제) / 정답 문자 수.

비교 전에 유니코드 NFC 정규화와 공백·개행 제거를 적용합니다. 루비의 중괄호는
지면에 인쇄되지 않은 마크업이므로 제거합니다. 정답지는 목적에 따라 세 가지를
사용합니다.

| 정답지 | 구성 | 대조 대상 |
|---|---|---|
| `gt/` | 루비 포함 전체 | 전처리 없는 기준선 |
| `gt_noruby/` | 본문 문자만 | 루비 분리 조건의 본문 계층 |
| `gt_rubyonly/` | 루비 문자만 | 루비 분리 조건의 루비 계층 |

CER는 삽입 오류가 많으면 100%를 넘어 해석이 어려우므로, 문자 단위
정밀도·재현율·F1을 함께 산출합니다. 재현율은 검출 누락(삭제 오류)에,
정밀도는 잡음 혼입(삽입 오류)에 각각 대응합니다.

## 라이선스

- 코드: MIT License (`LICENSE`)
- 정답지(JSON·txt) 및 실험 결과: CC BY 4.0
- 원본 스캔 이미지: 간행물 자체는 저작권 보호 기간이 만료되었습니다.
  디지털 이미지는 東京經濟大學圖書館 櫻井義之文庫 소장본으로, 교육·연구
  목적의 이용 범위에서 수록합니다. 자세한 사항은 `images/README.md`를
  참조하고, 이용 시 소장처를 표기하십시오.

## 인용

```
김준수(2026), koreantext-ocr: 근대 한국어 학습서 OCR 전처리 워크플로우
(버전 1.2.0)[컴퓨터 소프트웨어], Zenodo.
https://doi.org/10.5281/zenodo.21809270
```

개념 DOI(`10.5281/zenodo.21809270`)는 항상 최신 판본으로 연결됩니다. 특정
판본을 인용하려면 Zenodo의 해당 버전 DOI를 사용하십시오.
