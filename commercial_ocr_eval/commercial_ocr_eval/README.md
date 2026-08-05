# 상용 OCR 성능 평가 (논문 3절)

근대 한국어 학습서 4종 40페이지를 대상으로 상용·공개 OCR 5종의 인식
성능을 CER로 평가한 실험의 코드와 결과입니다. 전처리를 적용하지 않은
원본 스캔 이미지를 각 엔진에 그대로 투입하여, 세로쓰기·다국어 병기·
루비 문자라는 문헌 구조가 일반 OCR의 설계 가정과 충돌함을 확인한
파일럿 테스트에 해당합니다.

전처리 워크플로우 적용 전후를 비교한 검증 실험은 저장소 최상위의
`ocr_pipeline/`과 `results/`를 참조하십시오.

## 평가 대상 엔진

| 엔진 | 유형 | 호출 방식 |
|---|---|---|
| Google Cloud Vision | 클라우드 API | REST (`images:annotate`, TEXT_DETECTION) |
| NAVER CLOVA OCR | 클라우드 API | REST (General OCR V2) |
| Upstage Document AI | 클라우드 API | REST (Document OCR) |
| EasyOCR | 오픈소스 라이브러리 | 로컬 실행 (ko+ja 동시 적용) |
| Adobe Acrobat OCR | 데스크톱 소프트웨어 | GUI에서 PDF OCR 실행 후 txt 추출 |

## 구조

```
commercial_ocr_eval/
├── scripts/
│   ├── *_make_answer.py      # 엔진별 OCR 실행 → 결과 JSON 저장
│   │                         #   (google / naver / upstage / easyocr)
│   └── *_cer_result_*.py     # 엔진별·문헌별 CER 산출
│                             #   (엔진 5종 × 문헌 4종 = 20개)
└── ocr_output/
    ├── google_answer/        # 페이지별 원시 응답 JSON (좌표 포함)
    ├── naver_answer/
    ├── upstage_answer/
    ├── easyocr_answer/
    └── acrobat_answer/       # 문헌별 추출 텍스트 (txt)
```

문헌 약칭: 국원(局員須知日鮮会話, 1912), 신선(新撰正則日鮮会話, 1912),
국어(國語鮮語雙舌通解, 1913), 포켓(ポケット朝鮮語独学, 1915).
각 문헌 5개 스캔면(= 책 10페이지), 총 20개 스캔면을 사용하였습니다.

## 실행 방법

### 1. 준비

CER 산출만 할 경우 별도 준비가 필요 없습니다. 정답지는 최상위
`gt_json/`을, 인식 결과는 `ocr_output/`을 상대 경로로 참조하도록
설정되어 있어, `scripts/` 폴더에서 바로 실행하면 됩니다.

OCR을 다시 실행하려면 원시 데이터(스캔 이미지)가 필요합니다. 이미지는
소장 기관의 이용 정책에 따라 본 저장소에 포함하지 않으므로, 최상위
README의 "원시 데이터 취득 안내"를 참조하여 내려받은 뒤 이 폴더에
`images/`를 만들어 배치하십시오. 파일명은 `ocr_output/` 안의 결과
파일명과 대응합니다(예: `OCR_TEST_1912 局員須知日鮮会話_page1.jpg`).

### 2. OCR 실행 (선택)

`ocr_output/`에 실행 결과가 이미 포함되어 있으므로 재실행 없이 CER
산출만으로 결과를 검증할 수 있습니다. 다시 실행하려면 각 스크립트
상단의 API 키·엔드포인트를 채운 뒤 실행하십시오.

```bash
cd scripts
python google_make_answer.py     # API_KEY 필요
python naver_make_answer.py      # API_URL(Invoke URL), SECRET_KEY 필요
python upstage_make_answer.py    # API_KEY 필요
python easyocr_make_answer.py    # 키 불필요(로컬 실행)
```

공개 저장소이므로 스크립트의 키 변수는 빈 문자열로 두었습니다.
Adobe Acrobat은 GUI 소프트웨어이므로 스크립트가 없으며, PDF에 OCR을
적용한 뒤 텍스트로 내보낸 결과가 `ocr_output/acrobat_answer/`에
문헌 단위로 저장되어 있습니다.

### 3. CER 산출

```bash
cd scripts

# 엔진별 × 문헌별 (엔진: google/naver/upstage/easyocr/acrobat,
#                 문헌: 국원/신선/국어/포켓)
python "google_cer_result_국원.py"
python "naver_cer_result_신선.py"

# 전체 20개 일괄 실행
for f in *_cer_result_*.py; do echo "== $f"; python "$f"; done
```

각 스크립트는 정답지 JSON의 해당 페이지를 읽어 문자열로 직렬화하고,
공백·개행과 지정 기호를 제거한 뒤 레벤슈타인 거리 기반으로 CER를
산출하여 페이지별·문헌별 결과를 출력합니다.

## 저장소 반영 시 변경 사항

스크립트는 실험 당시의 코드를 그대로 보존하되, 저장소 폴더 구조에
맞추어 다음 경로 변수만 수정하였습니다(알고리즘·평가 방식은 동일).

- `GT_FILE_PATH`: 스크립트와 같은 폴더 → `../../gt_json/`
- `OCR_DIR`: `./<엔진>_answer` → `../ocr_output/<엔진>_answer`
- `IMAGE_DIR`: `./images` → `../images`
- `OUTPUT_DIR`: `./<엔진>_answer` → `../ocr_output/<엔진>_answer`
  (CLOVA 스크립트는 결과를 이미지 폴더에 저장하던 것을 다른 엔진과
  동일하게 엔진별 결과 폴더로 변경)

아울러 공개 저장소이므로 API 키·엔드포인트 변수는 빈 문자열로
비워 두었습니다.

## 평가 방법 요약

- **지표**: CER = 편집 거리 / 정답 문자 수. 삽입 오류가 많으면 100%를
  초과할 수 있습니다(Carrasco 2014).
- **정규화**: 공백·개행 제거, 루비 마크업의 중괄호 및 일부 구두점 제거.
- **읽기 순서 보정**: Google·NAVER·Upstage는 검출 박스의 좌표를 이용해
  세로쓰기 순서(우→좌, 상→하)로 정렬한 뒤 대조합니다. 엔진마다 응답
  구조가 다르므로 정렬 함수가 엔진별로 구현되어 있습니다.
- **Acrobat**: 좌표 정보가 없어 추출된 텍스트 순서를 그대로 사용합니다.

## 참고

이 실험은 전처리의 필요성을 확인하기 위한 진단 단계이며, 여기서 관찰된
오류 유형(다단 레이아웃 미분리로 인한 삽입 오류, 루비 혼입, 언어 모델
충돌)이 `ocr_pipeline/`의 전처리 워크플로우 설계 근거가 되었습니다.
