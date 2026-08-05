import requests
import json
import os
import glob
import time

# =====================================================================
# 1. 업스테이지 API 키 설정
# =====================================================================
# 업스테이지 콘솔(https://console.upstage.ai/)에서 발급받은 API 키를 입력하세요.
API_KEY = ""

# 업스테이지 Document AI (OCR) 엔드포인트
UPSTAGE_API_URL = ""

# =====================================================================
# 2. 폴더 설정
# =====================================================================
IMAGE_DIR = '../images'
OUTPUT_DIR = '../ocr_output/upstage_answer'

# 결과물을 저장할 폴더 생성
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_upstage_ocr_result(image_path):
    """Upstage OCR API를 호출합니다."""
    
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # 파일을 multipart/form-data 형식으로 전송
    with open(image_path, "rb") as f:
        files = {"document": f}
        # 업스테이지는 파일 키값으로 'document'를 사용합니다.
        response = requests.post(UPSTAGE_API_URL, headers=headers, files=files)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ 에러 발생 (상태 코드: {response.status_code})")
        print(response.text)
        return None

# =====================================================================
# 3. 폴더 내 이미지 일괄 실행
# =====================================================================
if __name__ == "__main__":
    valid_extensions = ('*.jpg', '*.jpeg', '*.png')
    image_files = []
    
    for ext in valid_extensions:
        image_files.extend(glob.glob(os.path.join(IMAGE_DIR, ext)))
        
    if not image_files:
        print(f"⚠️ '{IMAGE_DIR}' 폴더에 처리할 이미지 파일이 없습니다.")
    else:
        print(f"🔍 총 {len(image_files)}개의 이미지를 찾았습니다. 업스테이지 OCR 처리를 시작합니다!\n")
        
        for idx, image_path in enumerate(image_files, 1):
            base_name = os.path.basename(image_path)
            print(f"[{idx}/{len(image_files)}] '{base_name}' ➔ 업스테이지 서버에 전송 중... 🚀")
            
            result_data = get_upstage_ocr_result(image_path)

            if result_data:
                file_no_ext = base_name.rsplit('.', 1)[0]
                output_filename = os.path.join(OUTPUT_DIR, f"{file_no_ext}_upstage_result.json")
                
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)
                    
                print(f"   ✅ 저장 완료: {os.path.basename(output_filename)}\n")
            else:
                print(f"   ⚠️ 처리 실패: '{base_name}'\n")
                
            time.sleep(1) # API 호출 제한 방지

        print("🎉 업스테이지 OCR 처리가 모두 완료되었습니다!")