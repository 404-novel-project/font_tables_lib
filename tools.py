import io
from typing import Union


from commonly_used_character import character_list
from slow import (
    load_SourceHanSansSC_Normal, load_SourceHanSansSC_Regular, 
    load_std_guest_range, match_font, match_font, init_true_font
)
from lib import  get_font


async def match_font_tool(font_path,SC_Normal_path, SC_Regular_path, COORD_TABLE_PATH):
    font = await get_font(font_path)

    options = {
        "std_font": "SourceHanSansSC-Normal",
        "guest_range": "jjwxc"
    }

    std_font_dict = {
        "SourceHanSansSC-Normal": load_SourceHanSansSC_Normal(SC_Normal_path),
        "SourceHanSansSC-Regular": load_SourceHanSansSC_Regular(SC_Regular_path)
    }
    init_true_font(std_font_dict, COORD_TABLE_PATH)
    guest_range_dict = {
        "jjwxc": load_std_guest_range(COORD_TABLE_PATH),
        "2500": character_list
    }
    std_font = std_font_dict.get(
        options.get('std_font') or "SourceHanSansSC-Normal"
    ) or load_SourceHanSansSC_Normal()
    guest_range = guest_range_dict.get(
        options.get('guest_range') or "jjwxc"
    ) or load_std_guest_range(COORD_TABLE_PATH)

    with io.BytesIO(font.get('bytes')) as font_fd:
        table = match_font(
            font_fd, font.get('ttf'),
            std_font, guest_range
        )
        return table


