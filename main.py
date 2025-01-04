import json
import os
import asyncio
from uuid import uuid4
from tools import match_font_tool
async def main():
    # 获取 sample_font文件夹下所有文件的路径
    sample_font_path = os.path.join(os.path.dirname(__file__), 'sample_font')
    sample_font_list = os.listdir(sample_font_path)
    true_font_path = os.path.join(os.path.dirname(__file__), 'true_font')

    COORD_TABLE_PATH = os.path.join(true_font_path, 'coorTable.json')
    SOURCE_HAN_SANS_SC_NORMAL_PATH = os.path.join(
        true_font_path, 'SourceHanSansSC-Normal.otf')
    SOURCE_HAN_SANS_SC_REGULAR_PATH = os.path.join(
        true_font_path, 'SourceHanSansSC-Regular.otf')
    YAHEI_PATH = os.path.join(true_font_path, 'Microsoft-YaHei.otf')
    GEN_DIR = os.path.join(os.path.dirname(__file__), 'gen')
    if not os.path.exists(GEN_DIR):
        os.makedirs(GEN_DIR)

    for sample_font in sample_font_list:
        print(f'processing {sample_font}')
        result = await match_font_tool(os.path.join(sample_font_path,sample_font),
                        SOURCE_HAN_SANS_SC_NORMAL_PATH,
                        SOURCE_HAN_SANS_SC_REGULAR_PATH,
                        YAHEI_PATH,
                        COORD_TABLE_PATH)
        with open(os.path.join(GEN_DIR, sample_font + '.json'), 'w') as f:
            f.write(json.dumps(result))

if __name__ == '__main__':
    asyncio.run(main())