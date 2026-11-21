# 실험 환경 (Experiment Environment)

본 저장소의 실험을 재현하기 위한 환경 정보이다. 인식 결과는 엔진 버전뿐 아니라
**모델 가중치 파일의 판본**에 따라 달라지므로, 파일 크기와 SHA-256 해시를 함께 기록한다.

측정 시점: 2026-11-20
실행 환경: WSL (Ubuntu), conda environment `koreantext`

---

## 런타임 및 라이브러리

| 항목 | 버전 |
|---|---|
| Python | 3.11.15 |
| OpenCV | 5.0.0 |
| NumPy | 2.4.6 |
| EasyOCR | 1.7.2 |
| PyTorch | 2.13.0+cu130 (CUDA 13.0) |
| Tesseract | 5.3.4 |
| Leptonica | 1.82.0 |

### 확인 명령

```bash
python --version
python -c "import cv2, numpy, easyocr, torch; \
  print('opencv', cv2.__version__); print('numpy', numpy.__version__); \
  print('easyocr', easyocr.__version__); print('torch', torch.__version__)"
tesseract --version | head -2
```

---

## Tesseract 학습 모델

세로쓰기 전용 모델을 사용하였다. 배포판 패키지(`tesseract-ocr-kor-vert` 등)는
설치하지 않았으며, **`tessdata_best` 저장소의 파일을 직접 내려받아**
`/usr/share/tesseract-ocr/5/tessdata/`에 배치하였다.

`tessdata_best`는 Tesseract가 제공하는 세 판본(`tessdata`, `tessdata_fast`,
`tessdata_best`) 가운데 **정확도가 가장 높은 부동소수점 LSTM 모델**이다.
판본 확인은 파일 크기로 가능하다.

| 판본 | kor_vert.traineddata |
|---|---|
| tessdata | 1,128,590 B |
| tessdata_fast | 1,113,715 B |
| **tessdata_best (사용)** | **3,964,469 B** |

| 파일 | 크기 (B) | SHA-256 |
|---|---|---|
| `kor_vert.traineddata` | 3,964,469 | `e6c72327617c0bf195a9a8b631827bf102c75735bbb932126e6fa1c4656c7568` |
| `jpn_vert.traineddata` | 14,330,809 | `1258be6eb2a9851f18043234ad18cca13ed32690bfff62b335c898bbea371548` |

출처: https://github.com/tesseract-ocr/tessdata_best

### 설치

```bash
sudo curl -L -o /usr/share/tesseract-ocr/5/tessdata/kor_vert.traineddata \
  https://github.com/tesseract-ocr/tessdata_best/raw/main/kor_vert.traineddata
sudo curl -L -o /usr/share/tesseract-ocr/5/tessdata/jpn_vert.traineddata \
  https://github.com/tesseract-ocr/tessdata_best/raw/main/jpn_vert.traineddata

sha256sum /usr/share/tesseract-ocr/5/tessdata/*_vert.traineddata
```

---

## EasyOCR 모델

EasyOCR 1.7.2가 최초 실행 시 자동으로 내려받아 `~/.EasyOCR/model/`에 저장한 파일이다.

| 파일 | 역할 | 크기 (B) | SHA-256 |
|---|---|---|---|
| `craft_mlt_25k.pth` | 문자 영역 검출 (CRAFT) | 83,152,330 | `4a5efbfb48b4081100544e75e1e2b57f8de3d84f213004b14b85fd4b3748db17` |
| `korean_g2.pth` | 한국어 인식 (CRNN) | 16,081,533 | `ecdead53c909748aad74bc2f2beeab3e3ad751134db6335e97ea19f879ca407e` |
| `japanese_g2.pth` | 일본어 인식 (CRNN) | 17,321,277 | `afbb32b0485297de5a7c1f59aeecac12c69f32b15cedd3c3d8c2e8529de85af3` |

### 확인

```bash
ls -la ~/.EasyOCR/model/
sha256sum ~/.EasyOCR/model/*.pth
```

---

## 전처리 파라미터

실행 시점의 설정값은 출력 폴더에 자동으로 기록된다.

- `preprocessed/params.json` — 4.1~4.3단계
- `preprocessed_noruby/strip_ruby_params.json` — 4.4단계

| 단계 | 파라미터 | 값 |
|---|---|---|
| 4.1 영역 분할 | `gutter_min_ratio` | 0.30 |
| | `divider_min_width_ratio` | 0.55 |
| | `divider_min_seg` | 80 |
| | `divider_max_gap` | 18 |
| | `divider_bridge` | 40 |
| | `min_region_height` | 60 |
| 4.3 컬럼 분리 | `col_max_fill` | 0.45 |
| 4.4 루비 분리 | `close_kernel` | 5 |
| | `close_iter` | 2 |
| | `ruby_size_ratio` | 0.62 |
| | `min_blob_area` | 40 |
| | `right_bias` | 0.55 |

본문 글자 크기 기준은 영역 내 모든 글자 덩어리 높이의 **75분위수**,
루비 열 판정은 열 내 덩어리 높이의 **90분위수**를 사용한다. 중앙값을 쓰면
루비 글자 수가 본문보다 많은 어휘 페이지에서 루비 크기가 곧 기준값이 되어
분리가 이루어지지 않기 때문이다.

---

## 알려진 버전 의존성

**OpenCV 5.0.0** — `HoughLinesP`의 반환 배열 형태가 버전에 따라 다르다.
`preprocess.py`는 `np.asarray(segs).reshape(-1, 4)`로 형태를 통일하여
4.x 계열에서도 동작하도록 하였다.

---

## 인용

| 대상 | 인용 |
|---|---|
| OpenCV | Bradski, G. (2000). The OpenCV library. *Dr. Dobb's Journal of Software Tools*, 25(11), 120–125. |
| EasyOCR | Jaided AI. (2020). *EasyOCR* (Version 1.7.2) [Computer software]. https://github.com/JaidedAI/EasyOCR |
| Tesseract | Smith, R. (2007). An overview of the Tesseract OCR engine. *ICDAR 2007*, 629–633. https://doi.org/10.1109/ICDAR.2007.4376991 |
| CRAFT (검출기) | Baek, Y., Lee, B., Han, D., Yun, S., & Lee, H. (2019). Character region awareness for text detection. *CVPR*, 9365–9374. https://doi.org/10.1109/CVPR.2019.00959 |
| CRNN (인식기) | Shi, B., Bai, X., & Yao, C. (2017). An end-to-end trainable neural network for image-based sequence recognition and its application to scene text recognition. *IEEE TPAMI*, 39(11), 2298–2304. https://doi.org/10.1109/TPAMI.2016.2646371 |
| NumPy | Harris, C. R. et al. (2020). Array programming with NumPy. *Nature*, 585, 357–362. https://doi.org/10.1038/s41586-020-2649-2 |
| PyTorch | Paszke, A. et al. (2019). PyTorch: An imperative style, high-performance deep learning library. *NeurIPS*, 32, 8024–8035. |
| tessdata_best | tesseract-ocr. *tessdata_best* [Data set]. GitHub. https://github.com/tesseract-ocr/tessdata_best |
