# images/ — 평가 자료 원본 이미지

> 저장소의 `images/README.md`로 복사하여 사용한다.

---

## 수록 범위

본 연구의 평가 자료 **4종 문헌 40면(스캔면 20장)** 전체이다. 논문에는 지면 제약으로
일부만 도판으로 수록하였으며, 전체는 이 폴더에서 확인할 수 있다.

파일명은 정답지(`gt/`, `gt_noruby/`, `gt_rubyonly/`)와 일대일로 대응한다.

```
images/1913_국어선어쌍설통해_p046-047.jpg
gt/1913_국어선어쌍설통해_p046-047.txt
```

| 문헌 | 수록 면 | 파일 수 |
|---|---|---|
| 『국원수지일선회화』(1912) | 18–19, 20–21, 60–61, 62–63, 64–65 | 5 |
| 『신찬정칙일선회화』(1912) | 76–77, 78–79, 112–113, 114–115, 116–117 | 5 |
| 『국어선어쌍설통해』(1913) | 46–47, 48–49, 94–95, 96–97, 98–99 | 5 |
| 『포켓조선어독학』(1915) | 38–39, 40–41, 152–153, 154–155, 156–157 | 5 |

해상도는 약 5,000 × 3,550px, JPEG, 합계 약 21MB이다.

## 출처

모두 **東京經濟大學圖書館 櫻井義之文庫** 소장본이며, 동 대학 학술기관 리포지터리를
통해 공개된 디지털 이미지이다.

| 약칭 | 서명 | 저자·편자 | 간행 | 영구 URI |
|---|---|---|---|---|
| 국원 | 局員須知日鮮會話 | 韓圭復·林田虎雄 編纂 | 京城: 朝鮮總督府臨時土地調査局, 1912 | https://tku.repo.nii.ac.jp/records/2007328 |
| 신선 | 新撰正則日鮮會話 | 齋藤助昇 著 | 京城: 日韓書房, 1912 | https://tku.repo.nii.ac.jp/records/2007548 |
| 국어 | 國語鮮語雙舌通解 | 小野綱方 著 | 京城: 日韓印刷, 1913 | https://tku.repo.nii.ac.jp/records/2007513 |
| 포켓 | ポケット朝鮮語獨學 | 弓場重榮 著 | 京城: 日韓書房, 1915 | https://tku.repo.nii.ac.jp/records/2007421 |

> 해당 리포지터리는 2026년 9월 DSpace에서 WEKO3로 이관되었다. 이전 주소
> (`repository.tku.ac.jp`)는 더 이상 유효하지 않다.

## 저작권 및 이용 조건

- **간행물**: 1912~1915년 간행물로 저작권 보호기간이 만료되었다.
- **디지털 이미지**: 소장 기관이 제공한 것이다. 해당 리포지터리는 교육·연구 목적의
  이용을 허용하고 있으며, 본 저장소는 학술 연구의 재현성 확보를 목적으로 평가 자료를
  수록한다.
- 소장 기관의 요청이 있을 경우 즉시 조치한다.

이 자료를 사용하는 경우 원 소장처를 밝혀 주기 바란다.

## 재현 절차

```bash
python ocr_pipeline/preprocess.py  images/ preprocessed/
python ocr_pipeline/strip_ruby.py  preprocessed/ preprocessed_noruby/ \
       --ruby-output preprocessed_rubyonly/
python ocr_pipeline/run_tesseract.py  preprocessed_noruby/ results_after_noruby/
python ocr_pipeline/evaluate_cer.py   --ref-dir gt_noruby \
       --hyp-dir results_before/tesseract --hyp-dir2 results_after_noruby/tesseract
```

실행 환경과 모델 가중치의 판본은 저장소 최상위의 `ENVIRONMENT.md`를 참조할 것.
