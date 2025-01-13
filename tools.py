import io
import os
from typing import Union


from commonly_used_character import character_list_7000 as character_list
from slow import (
    load_Font,
    load_std_guest_range, match_font, match_font, init_true_font
)
from lib import  get_font


async def match_font_tool(font_path, TRUE_FONT_PATH, true_font, COORD_TABLE_PATH):
    font = await get_font(font_path)
    std_font_dict = {}
    for font_name in true_font:
        std_font_dict[font_name] = load_Font(
            os.path.join(TRUE_FONT_PATH, font_name + '.otf')
        )
    init_true_font(std_font_dict, TRUE_FONT_PATH, COORD_TABLE_PATH)
    # guest_range = load_std_guest_range(COORD_TABLE_PATH)
    guest_range = list(
        {*load_std_guest_range(COORD_TABLE_PATH), *character_list})
    with io.BytesIO(font.get('bytes')) as font_fd:
        table = match_font(
            font_fd, font.get('ttf'),
            std_font_dict, guest_range, TRUE_FONT_PATH
        )
        return table


