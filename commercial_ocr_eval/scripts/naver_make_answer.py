import requests
import uuid
import time
import json
import os
import glob

# =====================================================================
# 1. API 설정 (네이버 클라우드 플랫폼에서 발급받은 정보 입력)
# =====================================================================
API_URL = ""   # 실제 Invoke URL로 변경하세요.
SECRET_KEY = ""  # 실제 Secret Key로 변경하세요.

# =====================================================================
# 2. 테스트할 이미지가 모여있는 "폴더" 경로 설정
# =====================================================================
IMAGE_DIR = '../images' # 예: 이미지들이 들어있는 폴더 경로로 맞춰주세요.
OUTPUT_DIR = '../ocr_output/naver_answer'

os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_naver_ocr_result(image_path, api_url, secret_key):
    """
    네이버 CLOVA OCR API를 호출하여 인식 결과를 받아오는 함수입니다.
    """
    # 파일 확장자에 맞춰 format을 동적으로 할당 (jpg, jpeg, png 등)
    ext = os.path.splitext(image_path)[-1].lower().replace('.', '')
    if ext == 'jpeg':
        ext = 'jpg'
        
    request_json = {
        'images': [
            {
                'format': ext, 
                'name': 'demo'
            }
        ],
        'requestId': str(uuid.uuid4()),
        'version': 'V2',
        'timestamp': int(round(time.time() * 1000))
    }

    payload = {'message': json.dumps(request_json).encode('UTF-8')}
    headers = {'X-OCR-SECRET': secret_key}
    
    # with문을 사용하여 파일 열기 및 닫기를 안전하게 처리
    with open(image_path, 'rb') as f:
        files = [('file', f)]
        response = requests.post(api_url, headers=headers, data=payload, files=files)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ 에러 발생 (상태 코드: {response.status_code})")
        print(response.text)
        return None

# =====================================================================
# 3. 폴더 내 모든 이미지 일괄 실행 및 결과 저장
# =====================================================================
if __name__ == "__main__":
    # 지원하는 이미지 확장자 검색
    valid_extensions = ('*.jpg', '*.jpeg', '*.png')
    image_files = []
    
    for ext in valid_extensions:
        image_files.extend(glob.glob(os.path.join(IMAGE_DIR, ext)))
        
    if not image_files:
        print(f"⚠️ '{IMAGE_DIR}' 폴더에 처리할 이미지 파일이 없습니다.")
    else:
        print(f"🔍 총 {len(image_files)}개의 이미지를 찾았습니다. 일괄 처리를 시작합니다!\n")
        
        # 찾은 이미지들을 하나씩 반복하며 처리
        for idx, image_path in enumerate(image_files, 1):
            base_name = os.path.basename(image_path)
            print(f"[{idx}/{len(image_files)}] '{base_name}' ➔ 네이버 CLOVA 서버에 전송 중... 🚀")
            
            result_data = get_naver_ocr_result(image_path, API_URL, SECRET_KEY)

            if result_data:
                # 원본 이미지 이름에서 확장자를 떼고, 뒤에 _ocr_result.json 을 붙여서 파일명 생성
                file_no_ext = base_name.rsplit('.', 1)[0]
                
                # 저장할 경로 설정 (엔진별 결과 폴더에 저장됩니다)
                output_filename = os.path.join(OUTPUT_DIR, f"{file_no_ext}_ocr_result.json")
                
                # API 응답(텍스트+좌표 등 전체 데이터)을 JSON 파일로 예쁘게 저장
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)
                    
                print(f"   ✅ 저장 완료: {os.path.basename(output_filename)}\n")
                
                # API 호출 제한(Rate Limit) 방지를 위한 1초 대기 (안전장치)
                time.sleep(1) 
            else:
                print(f"   ❌ 처리 실패: '{base_name}'\n")

        print("🎉 모든 이미지 처리가 성공적으로 완료되었습니다!")