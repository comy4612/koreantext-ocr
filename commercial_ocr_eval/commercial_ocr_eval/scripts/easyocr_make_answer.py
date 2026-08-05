import easyocr
import json
import os
import glob

# =====================================================================
# 1. 설정
# =====================================================================
IMAGE_DIR = '../images'
OUTPUT_DIR = '../ocr_output/easyocr_answer'

os.makedirs(OUTPUT_DIR, exist_ok=True)

# EasyOCR 리더기 생성 (한국어, 일본어 동시 로드)
# GPU가 있다면 gpu=True로 하시면 훨씬 빠릅니다. 없다면 False로 두세요.
print("⏳ EasyOCR 모델을 메모리에 로드하는 중입니다... (최초 1회 시간이 걸릴 수 있습니다)")
reader = easyocr.Reader(['ko'], gpu=True) 

# =====================================================================
# 2. 폴더 내 이미지 일괄 실행
# =====================================================================
if __name__ == "__main__":
    valid_extensions = ('*.jpg', '*.jpeg', '*.png')
    image_files = []
    
    for ext in valid_extensions:
        image_files.extend(glob.glob(os.path.join(IMAGE_DIR, ext)))
        
    if not image_files:
        print(f"⚠️ '{IMAGE_DIR}' 폴더에 처리할 이미지 파일이 없습니다.")
    else:
        print(f"🔍 총 {len(image_files)}개의 이미지를 찾았습니다. EasyOCR 처리를 시작합니다!\n")
        
        for idx, image_path in enumerate(image_files, 1):
            base_name = os.path.basename(image_path)
            print(f"[{idx}/{len(image_files)}] '{base_name}' ➔ EasyOCR로 텍스트 추출 중... 🚀")
            
            # EasyOCR 실행 (결과 포맷: [ [좌표], 텍스트, 신뢰도 ])
            raw_result = reader.readtext(image_path)

            if raw_result:
                # Numpy 데이터 타입을 순수 Python 타입으로 변환 (JSON 저장을 위해)
                clean_result = []
                for bbox, text, prob in raw_result:
                    clean_bbox = [[float(point[0]), float(point[1])] for point in bbox]
                    clean_result.append({
                        "boundingPoly": clean_bbox,
                        "text": text,
                        "confidence": float(prob)
                    })

                file_no_ext = base_name.rsplit('.', 1)[0]
                output_filename = os.path.join(OUTPUT_DIR, f"{file_no_ext}_easyocr_result.json")
                
                with open(output_filename, 'w', encoding='utf-8') as f:
                    json.dump(clean_result, f, ensure_ascii=False, indent=2)
                    
                print(f"   ✅ 저장 완료: {os.path.basename(output_filename)}\n")
            else:
                print(f"   ⚠️ 텍스트를 찾지 못했거나 처리 실패: '{base_name}'\n")

        print("🎉 EasyOCR 처리가 모두 완료되었습니다!")