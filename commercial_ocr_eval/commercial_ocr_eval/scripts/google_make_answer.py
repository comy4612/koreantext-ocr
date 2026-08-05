import requests
import base64
import json
import os
import glob
import time

# =====================================================================
# 1. 구글 API 키 설정 (웹에서 복사한 문자열을 여기에 넣으세요!)
# =====================================================================
API_KEY = ""

# 구글 비전 API 엔드포인트 주소 (뒤에 키가 붙습니다)
VISION_API_URL = f"https://vision.googleapis.com/v1/images:annotate?key={API_KEY}"

# =====================================================================
# 2. 폴더 설정
# =====================================================================
IMAGE_DIR = '../images'
OUTPUT_DIR = '../ocr_output/google_answer'

# 결과물을 저장할 폴더가 없으면 만듭니다.
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_google_ocr_result(image_path):
    """문자열 API 키와 requests를 이용해 구글 Vision API를 호출합니다."""
    
    # 이미지를 구글이 읽을 수 있게 Base64 텍스트로 변환
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    # 구글 API가 요구하는 필수 JSON 데이터 형식 (문서 전용 고해상도 모드 적용)
    request_payload = {
        "requests": [
            {
                "image": {
                    "content": encoded_string
                },
                "features": [
                    {
                        "type": "DOCUMENT_TEXT_DETECTION" # 일반 사진이 아닌 문서 모드
                    }
                ]
            }
        ]
    }

    # API 서버로 전송
    response = requests.post(VISION_API_URL, json=request_payload)
    
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
        print(f"🔍 총 {len(image_files)}개의 이미지를 찾았습니다. 구글 OCR 처리를 시작합니다!\n")
        
        for idx, image_path in enumerate(image_files, 1):
            base_name = os.path.basename(image_path)
            print(f"[{idx}/{len(image_files)}] '{base_name}' ➔ 구글 클라우드 서버에 전송 중... 🚀")
            
            result_data = get_google_ocr_result(image_path)

            # 결과가 정상적으로 돌아왔고, 텍스트 응답이 있는지 확인
            if result_data and 'responses' in result_data and 'fullTextAnnotation' in result_data['responses'][0]:
                file_no_ext = base_name.rsplit('.', 1)[0]
                output_filename = os.path.join(OUTPUT_DIR, f"{file_no_ext}_google_result.json")
                
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)
                    
                print(f"   ✅ 저장 완료: {os.path.basename(output_filename)}\n")
            else:
                print(f"   ⚠️ 텍스트를 찾지 못했거나 처리 실패: '{base_name}'\n")
                
            time.sleep(1) # API 호출 제한 방지

        print("🎉 구글 OCR 처리가 모두 완료되었습니다!")