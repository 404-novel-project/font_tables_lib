import json
import math
from functools import lru_cache
from typing import IO
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import ttFont

from commonly_used_character import character_list
from exception import ImageMatchError
from quick import list_ttf_characters
from lib import load_std_font_coord_table

# 默认字号 32 px
# 行高 1.2 倍
FONT_SIZE = 96
IMAGE_SIZE = (math.ceil(FONT_SIZE * 1.2), math.ceil(FONT_SIZE * 1.2))
instance_path = os.path.join(os.path.dirname(__file__),'true_font')
SOURCE_HAN_SANS_SC_NORMAL_NPZ_PATH = os.path.join(
    instance_path, 'SourceHanSansSC-Normal.npz')
SOURCE_HAN_SANS_SC_REGULARL_NPZ_PATH = os.path.join(
    instance_path, 'SourceHanSansSC-Regular.npz')
SOURCE_HAN_SANS_SC_NORMAL_JSON_PATH = os.path.join(
    instance_path, 'SourceHanSansSC-Normal.json')
SOURCE_HAN_SANS_SC_REGULARL_JSON_PATH = os.path.join(
    instance_path, 'SourceHanSansSC-Regular.json')
@lru_cache
def _load_font(font, size=FONT_SIZE):
    return ImageFont.truetype(font, size=size)


def load_SourceHanSansSC_Normal(SOURCE_HAN_SANS_SC_NORMAL_PATH) -> ImageFont.FreeTypeFont:
    return _load_font(SOURCE_HAN_SANS_SC_NORMAL_PATH)


def load_SourceHanSansSC_Regular(SOURCE_HAN_SANS_SC_REGULAR_PATH) -> ImageFont.FreeTypeFont:
    return _load_font(SOURCE_HAN_SANS_SC_REGULAR_PATH)


def load_std_guest_range(COORD_TABLE_PATH) -> list[str]:
    return list(set(
        filter(
            lambda x: x != 'x',
            map(
                lambda x: x[0],
                load_std_font_coord_table(COORD_TABLE_PATH)
            ))
    ))


def _get_offset(im: Image, font: ImageFont.FreeTypeFont, text: str):
    im_width, im_heigth = im.size

    # 获取文字默认位置（默认偏移）
    # https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html
    # https://pillow.readthedocs.io/en/stable/reference/ImageFont.html#PIL.ImageFont.FreeTypeFont.getbbox
    text_bbox = font.getbbox(text)

    text_width = font.getlength(text)
    text_height = text_bbox[3] - text_bbox[1]

    # 使文字居中理论偏移量
    _offset_x = (im_width - text_width) / 2
    _offset_y = (im_heigth - text_height) / 2

    # 计算所需偏移
    offset_x = _offset_x - text_bbox[0]
    offset_y = _offset_y - text_bbox[1]
    return offset_x, offset_y


@lru_cache(maxsize=3500)
def draw(text: str, font: ImageFont.FreeTypeFont, size: tuple[int, int] = IMAGE_SIZE):
    image = Image.new("1", size, "white")
    d = ImageDraw.Draw(image)
    d.text(_get_offset(image, font, text), text, font=font, fill="black")
    return image


def compare_im_np(test_array: np.ndarray, std_array: np.ndarray):
    if test_array.shape != std_array.shape:
        raise ImageMatchError("图像大小不一致")

    # 获取图像黑色部分
    test_black_array = test_array == False
    std_black_array = std_array == False

    # 求出共同黑色部分
    common_black_array = test_black_array & std_black_array

    # 输出共同黑色部分占测试图像比例
    return np.count_nonzero(common_black_array) / np.count_nonzero(test_black_array)


def init_true_font(std_font_dict, COORD_TABLE_PATH):
    sourceHanSansSCNormal = std_font_dict.get('SourceHanSansSC-Normal')
    sourceHanSansSCRegular = std_font_dict.get('SourceHanSansSC-Regular')
    if os.path.exists(SOURCE_HAN_SANS_SC_NORMAL_NPZ_PATH) is not True:
        save_std_im_np_arrays(sourceHanSansSCNormal,
                              COORD_TABLE_PATH,
                            SOURCE_HAN_SANS_SC_NORMAL_NPZ_PATH)
    if os.path.exists(SOURCE_HAN_SANS_SC_REGULARL_NPZ_PATH) is not True:
        save_std_im_black_point_rates(
            sourceHanSansSCNormal, 
            COORD_TABLE_PATH,
            SOURCE_HAN_SANS_SC_NORMAL_JSON_PATH)
    if os.path.exists(SOURCE_HAN_SANS_SC_REGULARL_NPZ_PATH) is not True:
        save_std_im_np_arrays(sourceHanSansSCRegular,
                              COORD_TABLE_PATH,
                            SOURCE_HAN_SANS_SC_REGULARL_NPZ_PATH)
    if os.path.exists(SOURCE_HAN_SANS_SC_REGULARL_JSON_PATH) is not True:
        save_std_im_black_point_rates(
            sourceHanSansSCRegular, 
            COORD_TABLE_PATH,
            SOURCE_HAN_SANS_SC_REGULARL_JSON_PATH)

def match_test_im_with_cache(test_im: Image, std_font: ImageFont.FreeTypeFont, guest_range: list[str]):
    test_array = np.asarray(test_im)
    npz_path_dict = {
        "Source Han Sans SC Normal": SOURCE_HAN_SANS_SC_NORMAL_NPZ_PATH,
        "Source Han Sans SC Regular": SOURCE_HAN_SANS_SC_REGULARL_NPZ_PATH
    }
    npz_path = npz_path_dict.get(' '.join(std_font.getname())) \
               or SOURCE_HAN_SANS_SC_NORMAL_NPZ_PATH

    josn_path_dict = {
        "Source Han Sans SC Normal": SOURCE_HAN_SANS_SC_NORMAL_JSON_PATH,
        "Source Han Sans SC Regular": SOURCE_HAN_SANS_SC_REGULARL_JSON_PATH
    }
    josn_path = josn_path_dict.get(' '.join(std_font.getname())) \
                or SOURCE_HAN_SANS_SC_NORMAL_JSON_PATH

    std_im_np_arrays = load_std_im_np_arrays(npz_path)
    std_im_black_point_rates = load_std_im_black_point_rates(josn_path)

    match_result = {}

    most_match_rate: float = 0.0
    most_match: str = ''

    test_im_black_point_rate = get_im_black_point_rate(test_im)
    for text in guest_range:
        if abs(test_im_black_point_rate - std_im_black_point_rates[text]) / test_im_black_point_rate > 0.2:
            # 跳过黑色比例相较其自身差异 20% 以上的标准字符
            continue

        std_array = std_im_np_arrays[text]
        match_rate = compare_im_np(test_array, std_array)

        match_result[text] = match_rate

        if match_rate > most_match_rate:
            most_match = text
            most_match_rate = match_rate

    return most_match, match_result


def save_std_im_np_arrays(std_font: ImageFont.FreeTypeFont, COORD_TABLE_PATH:str, npz_path: str):
    guest_range = list(
        {*load_std_guest_range(COORD_TABLE_PATH), *character_list})

    npz_dict = {}

    for text in guest_range:
        std_im = draw(text, std_font)
        std_array = np.asarray(std_im)
        npz_dict[text] = std_array

    np.savez_compressed(npz_path, **npz_dict)


@lru_cache
def load_std_im_np_arrays(npz_path: str):
    with np.load(npz_path, mmap_mode='r') as _std_im_np_arrays:
        std_im_np_arrays = {}
        for key in _std_im_np_arrays.keys():
            std_im_np_arrays[key] = _std_im_np_arrays.get(key)

    return std_im_np_arrays


def get_im_black_point_rate(im: Image):
    std_array = np.asarray(im)
    std_black_array = std_array == False
    return np.count_nonzero(std_black_array) / std_array.size


def save_std_im_black_point_rates(std_font: ImageFont.FreeTypeFont, COORD_TABLE_PATH:str, josn_path: str):
    guest_range = list(
        {*load_std_guest_range(COORD_TABLE_PATH), *character_list})

    json_dict = {}

    for text in guest_range:
        std_im = draw(text, std_font)
        json_dict[text] = get_im_black_point_rate(std_im)

    with open(josn_path, 'w') as f:
        json.dump(json_dict, f)


@lru_cache
def load_std_im_black_point_rates(josn_path: str):
    with open(josn_path, 'r') as f:
        return json.load(f)


def match_font_1(test_font: ImageFont.FreeTypeFont, test_font_characters: list[str],
               std_font: ImageFont.FreeTypeFont, guest_range: list[str]):
    out = {}
    for test_char in test_font_characters:
        test_im = draw(test_char, test_font)
        most_match_char, test_match_result = match_test_im_with_cache(test_im, std_font, guest_range)
        out[test_char] = most_match_char

    return out


def match_font(font_fd: IO, font_ttf: ttFont.TTFont,
                     std_font, guest_range):
    image_font = _load_font(font_fd)
    characters = list(filter(lambda x: x != 'x', list_ttf_characters(font_ttf)))

    return match_font_1(
        image_font, characters,
        std_font, guest_range
    )


def match_font_one_character(test_character: str, font_fd: IO,
                                   std_font, guest_range):
    image_font = _load_font(font_fd)
    return match_font_1(
        image_font, [test_character],
        std_font, guest_range
    )