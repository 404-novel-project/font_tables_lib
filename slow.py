import json
import math
from functools import lru_cache
from typing import IO
import os
# from matplotlib import pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import ttFont
from tqdm import tqdm
from commonly_used_character import character_list_7000 as character_list
from exception import ImageMatchError
from quick import list_ttf_characters
from lib import load_std_font_coord_table

# 默认字号 32 px
# 行高 1.2 倍
FONT_SIZE = 96
IMAGE_SIZE = (math.ceil(FONT_SIZE * 1.2), math.ceil(FONT_SIZE * 1.2))

@lru_cache
def _load_font(font, size=FONT_SIZE):
    return ImageFont.truetype(font, size=size)


def load_Font(font) -> ImageFont.FreeTypeFont:
    return _load_font(font)



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

# left, upper, right, lower
def getbbox(image: Image.Image):
    pixels = image.load()  # 加载像素数据
    width, height = image.size
    x1 = width
    y1 = height
    x2 = -1
    y2 = -1

    for x in range(width):
        for y in range(height):
            if pixels[x, y] == 0:  # Assuming black is represented by 0
                x1 = min(x1, x)
                y1 = min(y1, y)
                x2 = max(x2, x)
                y2 = max(y2, y)
    if x1 == width:
        x1 = 0
    if y1 == height:
        y1 = 0
    if x2 == -1:
        x2 = width - 1
    if y2 == -1:
        y2 = height - 1
    len = max(x2 - x1, max(0, y2 - y1)) // 2
    xmid = (x1 + x2) // 2
    ymid = (y1 + y2) // 2
    x1 = max(xmid - len, 0)
    y1 = max(ymid - len, 0)
    x2 = min(xmid + len, width - 1)
    y2 = min(ymid + len, height - 1)
    return x1, y1, x2, y2

@lru_cache(maxsize=3500)
def draw(text: str, font: ImageFont.FreeTypeFont, size: tuple[int, int] = IMAGE_SIZE):
    image = Image.new("1", size, "white")
    d = ImageDraw.Draw(image)
    d.text(_get_offset(image, font, text), text, font=font, fill="black")
    bbox = getbbox(image)
    image = image.crop(bbox)
    image = image.resize(size, resample=3)
    return image

def compare_im_np(test_array: np.ndarray, std_array: np.ndarray):
    if test_array.shape != std_array.shape:
        raise ImageMatchError("图像大小不一致")

    # 获取图像黑色部分
    test_black_array = test_array == False
    std_black_array = std_array == False
    test_white_array = test_array == True
    std_white_array = std_array == True
    # 求出共同黑色部分
    common_black_array = test_black_array & std_black_array
    # 求出共同白色部分
    common_white_array = test_white_array & std_white_array
    # # 绘制图像
    # fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    # axes[0].imshow(test_black_array, cmap='gray')
    # axes[0].set_title('Test Black Array')
    # axes[1].imshow(std_black_array, cmap='gray')
    # axes[1].set_title('Standard Black Array')
    # axes[2].imshow(common_black_array, cmap='gray')
    # axes[2].set_title('Common Black Array')

    # for ax in axes:
    #     ax.axis('off')

    # plt.tight_layout()
    # plt.show()
    # 输出共同黑色部分占测试图像比例
    num_common_black = np.count_nonzero(common_black_array)
    num_test_black = np.count_nonzero(test_black_array)
    num_common_white = np.count_nonzero(common_white_array)
    num_test_white = np.count_nonzero(test_white_array)
    if num_test_black != 0 and num_test_white != 0:
        rate = ( num_common_black / num_test_black +
                    num_common_white / num_test_white ) / 2
    elif num_test_black == 0 and num_test_white != 0:
        rate = num_common_white / num_test_white
    elif num_test_black != 0 and num_test_white == 0:
        rate = num_common_black / num_test_black
    else:
        rate = 0
    return rate


def init_true_font(std_font_dict, TRUE_FONT_PATH, COORD_TABLE_PATH):
    for std_font in std_font_dict.keys():
        NPZ_PATH = os.path.join(TRUE_FONT_PATH, std_font + '.npz')
        JSON_PATH = os.path.join(TRUE_FONT_PATH, std_font + '.json')
        if os.path.exists(NPZ_PATH) is not True:
            save_std_im_np_arrays(std_font_dict.get(std_font),
                                COORD_TABLE_PATH,
                                NPZ_PATH)
        if os.path.exists(JSON_PATH) is not True:
            save_std_im_black_point_rates(
                std_font_dict.get(std_font),
                COORD_TABLE_PATH,
                JSON_PATH)


def match_test_im_with_cache(test_im: Image, std_font, guest_range: list[str], TRUE_FONT_PATH):
    test_array = np.asarray(test_im)
    npz_dict = {}
    josn_dict = {}
    for std_font_name in std_font.keys():
        NPZ_PATH = os.path.join(TRUE_FONT_PATH, std_font_name + '.npz')
        npz_dict[' '.join(std_font_name)] = load_std_im_np_arrays(NPZ_PATH)
        JSON_PATH = os.path.join(TRUE_FONT_PATH, std_font_name + '.json')
        josn_dict[' '.join(std_font_name)] = load_std_im_black_point_rates(JSON_PATH)
    most_match_rate: float = 0.0
    most_match: str = ''

    test_im_black_point_rate = get_im_black_point_rate(test_im)
    if test_im_black_point_rate == 0:
        text = ''
        return text
        
    for text in guest_range:
        for true_font_names in std_font.keys():
            std_im_np_arrays = npz_dict.get(' '.join(true_font_names))
            std_im_black_point_rates = josn_dict.get(' '.join(true_font_names))
            # if text != '「':
            #     continue
            if text not in std_im_np_arrays:
                continue
            if abs(test_im_black_point_rate - std_im_black_point_rates[text]) / test_im_black_point_rate > 0.2:
                # 跳过黑色比例相较其自身差异 20% 以上的标准字符
                continue
            std_array = std_im_np_arrays[text]
            match_rate = compare_im_np(test_array, std_array)
            if match_rate > most_match_rate:
                most_match = text
                most_match_rate = match_rate
    return most_match


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
                 std_font, guest_range: list[str], TRUE_FONT_PATH):
    out = {}
    print('match_font_1')
    for test_char in tqdm(test_font_characters, desc="Matching characters", total=len(test_font_characters)):
        # if test_char != '，':
        #     continue
        test_im = draw(test_char, test_font)
        most_match_char = match_test_im_with_cache(
            test_im, std_font, guest_range, TRUE_FONT_PATH)
        out[test_char] = most_match_char
    return out


def match_font(font_fd: IO, font_ttf: ttFont.TTFont,
               std_font, guest_range, TRUE_FONT_PATH):
    image_font = _load_font(font_fd)
    characters = list(filter(lambda x: x != 'x', list_ttf_characters(font_ttf)))

    return match_font_1(
        image_font, characters,
        std_font, guest_range, TRUE_FONT_PATH
    )


def match_font_one_character(test_character: str, font_fd: IO,
                                   std_font, guest_range):
    image_font = _load_font(font_fd)
    return match_font_1(
        image_font, [test_character],
        std_font, guest_range
    )
