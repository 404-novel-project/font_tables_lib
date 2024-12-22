import io
from typing import Union


from commonly_used_character import character_list
from slow import (
    load_Font,
    load_std_guest_range, match_font, match_font, init_true_font
)
from lib import  get_font


async def match_font_tool(font_path,SC_Normal_path, SC_Regular_path,YaHei_path, COORD_TABLE_PATH):
    font = await get_font(font_path)

    options = {
        "std_font": "SourceHanSansSC-Normal",
        "guest_range": "jjwxc"
    }

    std_font_dict = {
        "SourceHanSansSC-Normal": load_Font(SC_Normal_path),
        "SourceHanSansSC-Regular": load_Font(SC_Regular_path),
        "Microsoft-YaHei": load_Font(YaHei_path),
    }
    init_true_font(std_font_dict, COORD_TABLE_PATH)
    guest_range = load_std_guest_range(COORD_TABLE_PATH)
    most_match_table = None
    most_match_confidence = 0
    for std_font in std_font_dict.values():
        with io.BytesIO(font.get('bytes')) as font_fd:
            table, match_confidence = match_font(
                font_fd, font.get('ttf'),
                std_font, guest_range
            )
            if match_confidence > most_match_confidence:
                most_match_table = table
                most_match_confidence = match_confidence
    return most_match_table


