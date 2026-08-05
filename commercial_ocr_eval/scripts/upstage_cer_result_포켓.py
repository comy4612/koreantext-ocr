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
# 2. 텍스트 정제 및 업스테이지 전용 정렬 함수
# =====================================================================
def clean_gt_text(text):
    text = re.sub(r'[{}(),「」『』。、∘]', '', text)
    return text

def sort_vertical_upstage_ocr(words):
    """
    업스테이지 OCR의 단어(words) 좌표를 이용해 세로쓰기(우->좌, 상->하)로 정렬합니다.
    """
    boxes = []
    
    for word in words:
        text = word.get('text', '')
        
        # 업스테이지 좌표 추출 안전장치 (boundingBox -> vertices)
        bounding_box = word.get('boundingBox', {})
        vertices = bounding_box.get('vertices', [])
        
        if not vertices:
            continue
            
        xs = [v.get('x', 0) for v in vertices]
        ys = [v.get('y', 0) for v in vertices]
        
        center_x = sum(xs) / len(xs)
        center_y = sum(ys) / len(ys)
        
        boxes.append({
            'text': text,
            'cx': center_x,
            'cy': center_y
        })
    
    # 세로쓰기 정렬: X좌표 내림차순(우->좌), Y좌표 오름차순(상->하)
    # 100픽셀 단위로 세로 열(Column) 묶기
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
    print(f"📊 UPSTAGE DOCUMENT AI 성능 평가 (대조 정답지: {os.path.basename(gt_json_path)})")
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
            
            # 2) 업스테이지 OCR 결과 로드
            with open(ocr_file_path, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
                
            # 업스테이지 응답 구조에서 pages[0] 안의 words 배열 추출
            pages = ocr_data.get('pages', [])
            if not pages:
                raise ValueError("OCR 결과에 'pages' 데이터가 없습니다.")
                
            words = pages[0].get('words', [])
            
            # 3) 세로쓰기 정렬 및 병합
            full_ocr_text = sort_vertical_upstage_ocr(words)
            
            # 4) CER 계산
            cer, dist, chars = calculate_cer(full_gt_text, full_ocr_text)
            
            total_distance += dist
            total_characters += chars
            
            # 5) 결과 출력
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
    GT_FILE_PATH = "../../gt_json/1915 포켓조선어독학_after.json" 
    
    # 2. 네이버 OCR 결과 파일들이 들어있는 폴더 경로
    OCR_DIR = "../ocr_output/upstage_answer"
    
    # 3. [채점할 페이지 번호 : "./naver_answer" 안에 있는 OCR 결과 파일명]
    # 1장 이미지에 2페이지가 있다면 괄호 ( )로 묶어주세요.
    PAGE_OCR_MAPPING = {
        (38, 39): "OCR_TEST_1915 ポケット朝鮮語独学_page1_upstage_result.json",
        (40, 41): "OCR_TEST_1915 ポケット朝鮮語独学_page2_upstage_result.json",
        (152, 153): "OCR_TEST_1915 ポケット朝鮮語独学_page3_upstage_result.json",
        (154, 155): "OCR_TEST_1915 ポケット朝鮮語独学_page4_upstage_result.json",
        (156, 157): "OCR_TEST_1915 ポケット朝鮮語独学_page5_upstage_result.json" 
    }
    
    print("🚀 업스테이지 OCR 채점 스크립트 실행 시작!")
    evaluate_multiple_pages(GT_FILE_PATH, OCR_DIR, PAGE_OCR_MAPPING)
    print("🏁 스크립트 실행 종료!")