import os
import json
import re

# =====================================================================
# 1. CER (Character Error Rate) 계산용 레벤슈타인 거리 함수
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
    # 공백 및 줄바꿈 제거 (순수 문자 단위 인식률 평가)
    gt_clean = re.sub(r'\s+', '', gt_text)
    ocr_clean = re.sub(r'\s+', '', ocr_text)
    
    if len(gt_clean) == 0:
        return 0.0, 0, 0
    
    dist = levenshtein_distance(gt_clean, ocr_clean)
    cer = dist / len(gt_clean)
    return cer, dist, len(gt_clean)

# =====================================================================
# 2. 텍스트 정제 및 정렬 함수
# =====================================================================
def clean_gt_text(text):
    # 정답지에 있는 루비 괄호와 특수 문장 부호 제거 (OCR 평가의 공정성을 위함)
    text = re.sub(r'[{}(),「」『』。、∘]', '', text)
    return text

def sort_vertical_ocr(fields):
    """
    네이버 OCR의 Bounding Box 좌표를 이용해 세로쓰기(우측->좌측, 상단->하단) 순서로 정렬
    """
    boxes = []
    for field in fields:
        vertices = field['boundingPoly']['vertices']
        xs = [v['x'] for v in vertices]
        ys = [v['y'] for v in vertices]
        
        # 박스의 중심 좌표(Center X, Y) 계산
        center_x = sum(xs) / len(xs)
        center_y = sum(ys) / len(ys)
        
        boxes.append({
            'text': field['inferText'],
            'cx': center_x,
            'cy': center_y
        })
    
    # X좌표 기준 내림차순(우->좌), Y좌표 기준 오름차순(상->하)
    # X좌표를 약 100픽셀 단위로 묶어 같은 세로줄(Column)로 인식하도록 처리
    boxes.sort(key=lambda b: (-round(b['cx'] / 100), b['cy']))
    
    return "".join([b['text'] for b in boxes])

# =====================================================================
# 3. 다중 페이지 일괄 채점 함수
# =====================================================================
def evaluate_multiple_pages(gt_json_path, ocr_dir, page_to_ocr_map):
    # 정답지(GT) 로드
    try:
        with open(gt_json_path, 'r', encoding='utf-8') as f:
            gt_data = json.load(f)
    except Exception as e:
        print(f"❌ [에러] 정답지 파일({gt_json_path})을 읽을 수 없습니다: {e}")
        return
        
    total_distance = 0
    total_characters = 0
    
    print("=" * 90)
    print(f"📊 NAVER CLOVA OCR 성능 평가 (대조 정답지: {os.path.basename(gt_json_path)})")
    print("=" * 90)

    for target_pages, ocr_filename in page_to_ocr_map.items():
        ocr_file_path = os.path.join(ocr_dir, ocr_filename)
        
        # target_pages가 단일 숫자면 리스트로 묶어줌 (1장 이미지 = 1페이지일 경우 대응)
        if isinstance(target_pages, int):
            target_pages = [target_pages]
            
        try:
            # 1) 해당 페이지의 정답(GT) 텍스트 긁어모으기
            page_gt_texts = []
            for item in gt_data:
                if item.get("page") in target_pages:
                    text_ja = clean_gt_text(item.get("text_ja", ""))
                    text_ko = clean_gt_text(item.get("text_ko", ""))
                    page_gt_texts.append(text_ja + text_ko)
                    
            full_gt_text = "".join(page_gt_texts)
            
            # 2) 네이버 OCR 결과 로드 및 텍스트 정렬
            with open(ocr_file_path, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)
                
            fields = ocr_data['images'][0]['fields']
            full_ocr_text = sort_vertical_ocr(fields)
            
            # 3) CER(오류율) 계산
            cer, dist, chars = calculate_cer(full_gt_text, full_ocr_text)
            
            total_distance += dist
            total_characters += chars
            
            # 4) 개별 페이지 결과 출력
            page_label = f"{target_pages[0]}~{target_pages[-1]}쪽" if len(target_pages) > 1 else f"{target_pages[0]}쪽"
            print(f"📄 [{page_label} 이미지] CER: {cer:.2%} (오류: {dist}자 / 전체: {chars}자) | 파일: {ocr_filename}")
            
            # 텍스트 앞부분 50자 요약 출력
            print(f"   - GT 정답 : {full_gt_text[:60]}...")
            print(f"   - OCR결과 : {full_ocr_text[:60]}...\n")
            
        except FileNotFoundError:
            print(f"❌ [에러] OCR 결과 파일({ocr_file_path})을 찾을 수 없습니다.\n")
        except Exception as e:
            print(f"❌ [에러] {target_pages} 페이지 처리 중 문제 발생: {e}\n")

    # 5) 최종 종합 결과 출력
    if total_characters > 0:
        overall_cer = total_distance / total_characters
        print("=" * 90)
        print(f"🏆 [최종 종합 결과] Total CER: {overall_cer:.2%} (총 오탈자: {total_distance}자 / 총 정답 글자수: {total_characters}자)")
        print("=" * 90)
    else:
        print("⚠️ 채점할 데이터가 없습니다. 매핑 딕셔너리나 파일 경로를 확인해 주세요.")

# =====================================================================
# 4. 실행 세팅 (여기를 수정하여 사용하세요!)
# =====================================================================
if __name__ == "__main__":
    # 1. 평가할 정답지(GT) 파일 경로
    GT_FILE_PATH = "../../gt_json/1912 국원수지일선회화_after.json" 
    
    # 2. 네이버 OCR 결과 파일들이 들어있는 폴더 경로
    OCR_DIR = "../ocr_output/naver_answer"
    
    # 3. [채점할 페이지 번호 : "./naver_answer" 안에 있는 OCR 결과 파일명]
    # 1장 이미지에 2페이지가 있다면 괄호 ( )로 묶어주세요.
    PAGE_OCR_MAPPING = {
        (18, 19): "OCR_TEST_1912 局員須知日鮮会話_page1_ocr_result.json",
        (20, 21): "OCR_TEST_1912 局員須知日鮮会話_page2_ocr_result.json",
        (60, 61): "OCR_TEST_1912 局員須知日鮮会話_page3_ocr_result.json",
        (62, 63): "OCR_TEST_1912 局員須知日鮮会話_page4_ocr_result.json",
        (64, 65): "OCR_TEST_1912 局員須知日鮮会話_page5_ocr_result.json" 
        # 예시: 1912 국원수지일선회화의 3, 4페이지가 한 이미지에 있을 때
        # (3, 4): "OCR_TEST_1912 局員須知日鮮会話_page3_ocr_result.json",
        
        # 예시: 단일 페이지일 때
        # 5: "OCR_TEST_1912 局員須知日鮮会話_page5_ocr_result.json",
    }
    print("🚀 스크립트 실행 시작!") # 추가: 실행 확인용 프린트문
    evaluate_multiple_pages(GT_FILE_PATH, OCR_DIR, PAGE_OCR_MAPPING)
    print("🏁 스크립트 실행 종료!") # 추가: 종료 확인용 프린트문
    # 채점 시작!