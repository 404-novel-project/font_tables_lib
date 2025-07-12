import json
import os
import asyncio
from paddle_ocr_extractor import extract_characters_unified_workflow # Import the unified function
from slow import load_Font, load_std_guest_range, init_true_font
from commonly_used_character import character_list_7000 as character_list

async def main():
    # 获取 sample_font文件夹下所有文件的路径
    sample_font_path = os.path.join(os.path.dirname(__file__), 'sample_font')
    sample_font_list = os.listdir(sample_font_path)
    TRUE_FONT_PATH = os.path.join(os.path.dirname(__file__), 'true_font')

    COORD_TABLE_PATH = os.path.join(TRUE_FONT_PATH, 'coorTable.json')
    GEN_DIR = os.path.join(os.path.dirname(__file__), 'gen')
    true_font = ["Microsoft-YaHei",
                 "SourceHanSansSC-Normal",
                 "SourceHanSansSC-Regular",
                 "Founder-Lanting"]
    if not os.path.exists(GEN_DIR):
        os.makedirs(GEN_DIR)

    # Unified workflow: PaddleOCR first, then fallback for failed characters only
    print("\n--- Running unified workflow (PaddleOCR + targeted fallback) ---")
    
    # Set up fallback parameters (same as used in image similarity method)
    std_font_dict = {}
    for font_name in true_font:
        std_font_dict[font_name] = load_Font(
            os.path.join(TRUE_FONT_PATH, font_name + '.otf')
        )
    init_true_font(std_font_dict, TRUE_FONT_PATH, COORD_TABLE_PATH)
    guest_range = list(
        {*load_std_guest_range(COORD_TABLE_PATH), *character_list})
    
    for sample_font_filename in sample_font_list:
        print(f'Processing {sample_font_filename} with unified workflow')
        full_font_path = os.path.join(sample_font_path, sample_font_filename)
        try:
            # Run unified workflow (PaddleOCR + fallback for failed characters only)
            unified_result = await asyncio.to_thread(
                extract_characters_unified_workflow, 
                full_font_path, 
                std_font_dict, 
                guest_range, 
                TRUE_FONT_PATH,
                #10  # Limit to first 10 characters for testing
            )
            with open(os.path.join(GEN_DIR, sample_font_filename + '.json'), 'w', encoding='utf-8') as f:
                json.dump(unified_result, f)
            print(f"Saved unified workflow output to {os.path.join(GEN_DIR, sample_font_filename + '.json')}")
        except Exception as e:
            print(f"Error processing {sample_font_filename} with unified workflow: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(main())