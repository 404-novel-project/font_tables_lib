import copy
import hashlib
import json
from functools import lru_cache
import asyncio
import hashlib
import io
import tempfile
from typing import Union
from fontTools.ttLib import woff2, ttFont

def woff2_to_ttf(input_bytest: bytes):
    """将 woff2 bytes 转捣为 TTFont 对象"""
    with io.BytesIO(input_bytest) as input_file:
        with tempfile.TemporaryFile() as tmp:
            woff2.decompress(input_file, tmp)
            tmp.seek(0)
            ttf = ttFont.TTFont(tmp)
            return ttf


async def get_font(font_path: str) -> dict[str, Union[str, bytes, ttFont.TTFont]]:
    font_bytes = await asyncio.to_thread(lambda: open(font_path, 'rb').read())
    m = hashlib.sha1()
    m.update(font_bytes)
    hashsum = m.hexdigest()
    # 取font_path文件名作为字体名
    font_name = font_path.split('/')[-1].split('.')[0]
    return {
        "name": font_name,
        "bytes": font_bytes,
        "ttf": woff2_to_ttf(font_bytes),
        "hashsum": hashsum,
    }


def get_charater_hex(chac: str):
    return str(hex(ord(chac))).replace('0x', 'U+')


@lru_cache
def load_std_font_coord_table(COORD_TABLE_PATH) -> list[
    tuple[
        str,
        list[tuple[int, int]]
    ]
]:
    """载入字体标准coordTable"""

    with open(COORD_TABLE_PATH, 'r') as f:
        _t = json.load(f)
        return sorted(_t, key=lambda x: x[0])


def is_coor_match(x, y) -> bool:
    """比较 coor"""

    # 如果字符 coor 长度相同
    if len(x) == len(y):
        match = True
        # 逐一比较各点
        for ii in range(len(x)):
            rx, ry = x[ii]
            lx, ly = y[ii]
            if rx != lx or ry != ly:
                match = False
                break
        return match
    else:
        return False


def merge_coor_table(source, target):
    source_copy = copy.copy(source)
    for j in source:
        for k in target:
            if j[0] == k[0] and is_coor_match(j[1], k[1]):
                source_copy.remove(j)
    return sorted([*target, *source_copy], key=lambda x: x[0])


def deduplicate_coor_table(source: list):
    rm_list = []
    source_length = len(source)
    for j in range(source_length):
        for k in range(source_length):
            if j > k and \
                    source[j][0] == source[k][0] and is_coor_match(source[j][1], source[k][1]):
                if k not in rm_list:
                    rm_list.append(k)

    target = []
    for index, value in enumerate(source):
        if index not in rm_list:
            target.append(value)

    return target
