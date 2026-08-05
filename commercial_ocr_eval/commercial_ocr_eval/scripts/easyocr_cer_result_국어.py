import os
import json
import re

# =====================================================================
# 1. CER 계산용 레벤슈타인 거리 함수
# =====================================================================
def levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]

def calculate_cer(gt_text, ocr_text):
    gt_clean = re.sub(r'\s+', '', gt_text)
    ocr_clean = re.sub(r'\s+', '', ocr_text)
    
    if len(gt_clean) == 0:
        return 0.0, 0, 0
    
    dist = levenshtein_distance(gt_clean, ocr_clean)
    cer = dist / len(gt_clean)
    return cer, dist, len(gt_clean)

# =====================================================================
# 2. 텍스트 정제 및 EasyOCR 전용 정렬 함수
# =====================================================================
def clean_gt_text(text):
    text = re.sub(r'[{}(),「」『』。、∘]', '', text)
    return text

def sort_vertical_easyocr(ocr_items):
    """
    EasyOCR의 좌표를 이용해 세로쓰기(우->좌, 상->하) 순서로 정렬합니다.
    """
    boxes = []
    
    for item in ocr_items:
        text = item.get('text', '')
        bbox = item.get('boundingPoly', [])
        
        if not bbox or len(bbox) != 4:
            continue
            
        # bbox는 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] 형태
        xs = [point[0] for point in bbox]
        ys = [point[1] for point in bbox]
        
        center_x = sum(xs) / len(xs)
        center_y = sum(ys) / len(ys)
        
        boxes.append({
            'text': text,
            'cx': center_x,
            'cy': center_y
        })
    
    # 세로쓰기 정렬: X좌표 내림차순(우->좌), Y좌표 오름차순(상->하)
    boxes.sort(key=lambda b: (-round(b['cx'] / 100), b['cy']))
    
    return "".join([b['text'] for b in boxes])

# =====================================================================
# 3. 다중 페이지 일괄 채점 함수
# =====================================================================
def evaluate_multiple_pages(gt_json_path, ocr_dir, page_to_ocr_map):
    try:
        with open(gt_json_path, 'r', encoding='utf-8') as f:
            gt_data = json.load(f)
    except Exception as e:
        print(f"❌ [에러] 정답지 파일({gt_json_path})을 읽을 수 없습니다: {e}")
        return
        
    total_distance = 0
    total_characters = 0
    
    print("=" * 90)
    print(f"📊 EasyOCR (Open Source) 성능 평가 (대조 정답지: {os.path.basename(gt_json_path)})")
    print("=" * 90)

    for target_pages, ocr_filename in page_to_ocr_map.items():
        ocr_file_path = os.path.join(ocr_dir, ocr_filename)
        
        if isinstance(target_pages, int):
            target_pages = [target_pages]
            
        try:
            # 1) GT 텍스트 추출
            page_gt_texts = []
            for item in gt_data:
                if item.get("page") in target_pages:
                    text_ja = clean_gt_text(item.get("text_ja", ""))
                    text_ko = clean_gt_text(item.get("text_ko", ""))
                    page_gt_texts.append(text_ja + text_ko)
                    
            full_gt_text = "".join(page_gt_texts)
            
            # 2) EasyOCR 결과 로드
            with open(ocr_file_path, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
                
            full_ocr_text = sort_vertical_easyocr(ocr_data)
            
            # 3) CER 계산
            cer, dist, chars = calculate_cer(full_gt_text, full_ocr_text)
            
            total_distance += dist
            total_characters += chars
            
            # 4) 결과 출력
            page_label = f"{target_pages[0]}~{target_pages[-1]}쪽" if len(target_pages) > 1 else f"{target_pages[0]}쪽"
            print(f"📄 [{page_label} 이미지] CER: {cer:.2%} (오류: {dist}자 / 전체: {chars}자) | 파일: {ocr_filename}")
            print(f"   - GT 정답 : {full_gt_text[:60]}...")
            print(f"   - OCR결과 : {full_ocr_text[:60]}...\n")
            
        except FileNotFoundError:
            print(f"❌ [에러] OCR 결과 파일({ocr_file_path})을 찾을 수 없습니다.\n")
        except Exception as e:
            print(f"❌ [에러] {target_pages} 페이지 처리 중 문제 발생: {e}\n")

    if total_characters > 0:
        overall_cer = total_distance / total_characters
        print("=" * 90)
        print(f"🏆 [최종 종합 결과] Total CER: {overall_cer:.2%} (총 오탈자: {total_distance}자 / 총 정답 글자수: {total_characters}자)")
        print("=" * 90)
    else:
        print("⚠️ 채점할 데이터가 없습니다.")

# =====================================================================
# 4. 실행 세팅 (이곳을 수정하세요!)
# =====================================================================
if __name__ == "__main__":
    # 1. 평가할 정답지(GT) 파일 경로
    GT_FILE_PATH = "../../gt_json/1913 국어선어쌍성통해_after.json" 
    
    # 2. EasyOCR 결과 파일들이 들어있는 폴더 경로
    OCR_DIR = "../ocr_output/easyocr_answer"
    
    # 3. 매핑
    PAGE_OCR_MAPPING = {
        (46, 47): "OCR_TEST_1913 國語鮮語雙舌通解_page1_easyocr_result.json",
        (48, 49): "OCR_TEST_1913 國語鮮語雙舌通解_page2_easyocr_result.json",
        (94, 95): "OCR_TEST_1913 國語鮮語雙舌通解_page3_easyocr_result.json",
        (96, 97): "OCR_TEST_1913 國語鮮語雙舌通解_page4_easyocr_result.json",
        (98, 99): "OCR_TEST_1913 國語鮮語雙舌通解_page5_easyocr_result.json"
    }
    
    print("🚀 EasyOCR 채점 스크립트 실행 시작!")
    evaluate_multiple_pages(GT_FILE_PATH, OCR_DIR, PAGE_OCR_MAPPING)
    print("🏁 스크립트 실행 종료!")