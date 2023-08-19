from enum import Enum
import numpy as np
from pymahjong import MahjongEnv
from typing import Union

JI_TILE = "東南西北白發中"
# JI_DECODE = dict((f"{i+1}z", JI_TILE[i]) for i in range(len(JI_TILE)))
# graphic utils (ultimate!!)

JI_DECODE = {}
# zipai
JI_DECODE.update({f"{i}z": chr(0x1F000 - 1 + i) for i in range(1, 8)})
JI_DECODE["5z"] = JI_DECODE["7z"]
JI_DECODE["7z"] = chr(0x1F004)

for idx, c in enumerate("msp"):
    JI_DECODE.update({f"{i}{c}": chr(0x1F007 - 1 + idx * 9 + i) for i in range(1, 10)})

JI_DECODE.update({f"0{c}": f"{JI_DECODE[f'5{c}']}*" for c in "mps"})


# print(JI_DECODE['0s'])
TILE_BACK = chr(0x1F02B)
JI_DECODE["**"] = TILE_BACK


def tile_exp(tile: str) -> str:
    return JI_DECODE.get(tile, tile)


WIND_TRANSLATION_TABLE = {
    "east": "東",
    "south": "南",
    "west": "西",
    "north": "北",
}

ACTION_SEQ = """チーMIN
チーMID
チーMAX
ポン
アンカン
ミンカン
カーカン
リーチ
ロン
ツモ
九種九牌
DAMA
PASS""".split()


ACTION_TRANSLATION_TABLE = dict((i + 34, ACTION_SEQ[i]) for i in range(len(ACTION_SEQ)))

TILE_LIST = [f"{i}{c}" for c in "mpsz" for i in range(1, 10)][:-2]
ACTION_TRANSLATION_TABLE.update((i, tile_exp(TILE_LIST[i])) for i in range(34))

ARROWS = "↑←↓→"


def notation_to_idx(tile: str) -> int:
    assert len(tile) == 2 and tile[0].isdigit() and tile[1] in "mpsz"
    tile_num = int(tile[0])
    if tile_num == 0:
        tile_num = 5
    return "mpsz".index(tile[1]) * 9 + (tile_num - 1)


class CallingCategory(Enum):
    Shun = 0
    Ko = 1
    Minkan = 3
    Ankan = 2
    Kakan = 4

    @staticmethod
    def to_category(key: int):
        assert (
            0 <= key
            and key < 5
            or MahjongEnv.CHILEFT <= key
            and key <= MahjongEnv.PASS_RIICHI
        ), "key out of range"
        if key < 5:
            return CallingCategory(key)
        else:
            return CallingCategory(
                key - MahjongEnv.CHIRIGHT if key > MahjongEnv.CHIRIGHT else 0
            )


class CallingInfo(object):
    def __init__(
        self, calling_str: str, calling_type: CallingCategory, from_player: int
    ) -> None:
        super().__init__()
        self.calling_str = calling_str
        self.calling_type = calling_type
        self.from_player = from_player

    def __find_parenthized(self) -> str:
        if "(" in self.calling_str:
            left_idx, right_idx = self.calling_str.index("("), self.calling_str.index(
                ")"
            )
            return self.calling_str[left_idx + 1 : right_idx]
        else:
            return self.calling_str[:2]

    def __str__(self) -> str:
        if self.calling_type == CallingCategory.Minkan:
            tile = self.__find_parenthized()
            # to show directness, place \rightarrow on the left of a tile
            if self.from_player == 3:
                return f"{tile}{tile}({ARROWS[self.from_player]}{tile}){tile}"
            else:
                return f"{tile}{tile}({tile}{ARROWS[self.from_player]}){tile}"
        elif self.calling_type == CallingCategory.Kakan:
            tile = self.__find_parenthized()
            if self.from_player == 3:
                return f"{tile}({ARROWS[self.from_player]}{tile}){tile}({tile})"
            else:
                return f"{tile}({tile}{ARROWS[self.from_player]}){tile}({tile})"
        elif self.calling_type != CallingCategory.Ankan:
            ret_str = self.calling_str
            if self.from_player == 3:
                left_idx = ret_str.index("(") + 1
                return (
                    ret_str[:left_idx] + ARROWS[self.from_player] + ret_str[left_idx:]
                )
            else:
                right_idx = ret_str.index(")")
                return (
                    ret_str[:right_idx] + ARROWS[self.from_player] + ret_str[right_idx:]
                )
        else:
            tile = self.calling_str[:2]
            return f"**{tile}{tile}**"


DISCARDING_SEQ = list(range(MahjongEnv.MAHJONG_TILE_TYPES))
DISCARDING_SEQ.extend(
    [MahjongEnv.ANKAN, MahjongEnv.KAKAN, MahjongEnv.RIICHI, MahjongEnv.PASS_RESPONSE]
)


def is_discarding(actions: Union[int, np.ndarray]) -> bool:
    """_summary_
    Deprecated function which may not be in use.
    Args:
        actions (Union[int, np.ndarray]): _description_

    Returns:
        bool: _description_
    """
    if isinstance(actions, int):
        return actions < MahjongEnv.MAHJONG_TILE_TYPES or actions == MahjongEnv.TSUMO
    return (
        np.sum(
            actions[
                np.logical_or(
                    actions < MahjongEnv.MAHJONG_TILE_TYPES, actions == MahjongEnv.TSUMO
                )
            ]
        )
        > 0
    )


def is_forward_call(a: int) -> bool:
    return a >= MahjongEnv.CHILEFT and a <= MahjongEnv.PON or a == MahjongEnv.MINKAN


REMOVE_TILE_MARKS = {ord(i): None for i in "h-r"}


def get_turn_from_river_tile(tile: str) -> int:
    t = tile[2:]
    t = t.translate(REMOVE_TILE_MARKS)
    assert t.isdigit(), tile
    return int(t)


YAKU_LIST = [
    "无役",
    "立直",
    "断幺九",
    "门前清自摸和",
    "自风 東",
    "自风 南",
    "自风 西",
    "自风 北",
    "场风 東",
    "场风 南",
    "场风 西",
    "场风 北",
    "役牌 白",
    "役牌 發",
    "役牌 中",
    "平和",
    "一杯口",
    "枪杠",
    "岭上开花",
    "海底捞月",
    "河底捞鱼",
    "一发",
    "寳牌",
    "裏寳牌",
    "赤寳牌",
    "北寳牌",
    "混全带幺九",
    "一气通贯",
    "三色同顺",
    "一番",
    "两立直",
    "三色同刻",
    "三杠子",
    "对对和",
    "三暗刻",
    "小三元",
    "混老头",
    "七对子",
    "混全带幺九",
    "一气通贯",
    "三色同顺",
    "纯全带幺九",
    "混一色",
    "二番",
    "二杯口",
    "纯全带幺九",
    "混一色",
    "三番",
    "清一色",
    "五番",
    "清一色",
    "六番",
    "流局满贯",
    "满贯",
    "天和",
    "地和",
    "大三元",
    "四暗刻",
    "字一色",
    "绿一色",
    "清老头",
    "国士无双",
    "小四喜",
    "四杠子",
    "九莲宝灯",
    "役满",
    "四暗刻单骑",
    "国士无双十三面",
    "纯正九莲宝灯",
    "大四喜",
    "双倍役满",
]

# print(YAKU_LIST[54])
YAKU_LIST_SEP = [
    YAKU_LIST.index(item) for item in ["一番", "二番", "三番", "五番", "六番", "满贯", "役满", "双倍役满"]
]

# 8 categories
YAKU_SUFFIXES = ["+1", "+2", "+3", "+5", "+6", "满贯", "役满", "双倍役满"]


def get_yaku_suffix(yaku_index: int) -> str:
    assert yaku_index < YAKU_LIST_SEP[-1]
    for ind, sf in zip(YAKU_LIST_SEP, YAKU_SUFFIXES):
        if yaku_index < ind:
            return sf
