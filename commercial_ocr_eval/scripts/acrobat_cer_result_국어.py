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
    # 공백 및 줄바꿈 제거 (순수 문자 단위 대조)
    gt_clean = re.sub(r'\s+', '', gt_text)
    ocr_clean = re.sub(r'\s+', '', ocr_text)
    
    if len(gt_clean) == 0:
        return 0.0, 0, 0
    
    dist = levenshtein_distance(gt_clean, ocr_clean)
    cer = dist / len(gt_clean)
    return cer, dist, len(gt_clean)

# =====================================================================
# 2. 텍스트 정제 함수
# =====================================================================
def clean_text(text):
    # 특수기호 및 루비 괄호 모두 제거
    text = re.sub(r'[{}(),「」『』。、∘]', '', text)
    return text

# =====================================================================
# 3. 다중 페이지 일괄 채점 함수 (TXT 파일용)
# =====================================================================
def evaluate_acrobat_pages(gt_json_path, ocr_dir, page_to_txt_map):
    try:
        with open(gt_json_path, 'r', encoding='utf-8') as f:
            gt_data = json.load(f)
    except Exception as e:
        print(f"❌ [에러] 정답지 파일({gt_json_path})을 읽을 수 없습니다: {e}")
        return
        
    total_distance = 0
    total_characters = 0
    
    print("=" * 90)
    print(f"📊 ADOBE ACROBAT OCR 성능 평가 (대조 정답지: {os.path.basename(gt_json_path)})")
    print("=" * 90)

    for target_pages, txt_filename in page_to_txt_map.items():
        txt_file_path = os.path.join(ocr_dir, txt_filename)
        
        if isinstance(target_pages, int):
            target_pages = [target_pages]
            
        try:
            # 1) GT 텍스트 추출 및 정제
            page_gt_texts = []
            for item in gt_data:
                if item.get("page") in target_pages:
                    text_ja = clean_text(item.get("text_ja", ""))
                    text_ko = clean_text(item.get("text_ko", ""))
                    page_gt_texts.append(text_ja + text_ko)
                    
            full_gt_text = "".join(page_gt_texts)
            
            # 2) Acrobat이 내보낸 TXT 파일 로드
            with open(txt_file_path, 'r', encoding='utf-8') as f:
                raw_ocr_text = f.read()
                
            # OCR 텍스트 정제
            full_ocr_text = clean_text(raw_ocr_text)
            
            # 3) CER 계산
            cer, dist, chars = calculate_cer(full_gt_text, full_ocr_text)
            
            total_distance += dist
            total_characters += chars
            
            # 4) 결과 출력
            page_label = f"{target_pages[0]}~{target_pages[-1]}쪽" if len(target_pages) > 1 else f"{target_pages[0]}쪽"
            print(f"📄 [{page_label} 이미지] CER: {cer:.2%} (오류: {dist}자 / 전체: {chars}자) | 파일: {txt_filename}")
            print(f"   - GT 정답 : {full_gt_text[:60]}...")
            print(f"   - OCR결과 : {full_ocr_text[:60]}...\n")
            
        except FileNotFoundError:
            print(f"❌ [에러] OCR 텍스트 파일({txt_file_path})을 찾을 수 없습니다.\n")
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
# 4. 실행 세팅
# =====================================================================
if __name__ == "__main__":
    # 1. 평가할 정답지(GT) 파일 경로
    GT_FILE_PATH = "../../gt_json/1913 국어선어쌍설통해_after.json" 
    
    # 2. Acrobat에서 추출한 .txt 파일이 있는 폴더
    OCR_DIR = "../ocr_output/acrobat_answer"
    
    # 3. 매핑: [(해당 txt 파일에 포함된 모든 GT 페이지 번호 리스트)] : "txt 파일명"
    # 예: txt 파일 하나에 18, 19, 20, 21, 60, 61, 62, 63, 64, 65페이지 내용이 다 들어있는 경우
    PAGE_TXT_MAPPING = {
        tuple([46, 47, 48, 49, 94, 95, 96, 97, 98, 99]): "Acrobat_answer_1913 國語鮮語雙舌通解.txt"
    }
    
    print("🚀 Acrobat OCR 채점 스크립트 실행 시작!")
    evaluate_acrobat_pages(GT_FILE_PATH, OCR_DIR, PAGE_TXT_MAPPING)
    print("🏁 스크립트 실행 종료!")