from enum import Enum
import numpy as np
from pymahjong import MahjongEnv
from typing import Union

JI_TILE = "東南西北白發中"
JI_DECODE = dict((f"{i+1}z", JI_TILE[i]) for i in range(len(JI_TILE)))


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
            return self.calling_str


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

REMOVE_TILE_MARKS={ord(i):None for i in 'h-r'}

def get_turn_from_river_tile(tile: str) -> int:
    t = tile[2:]
    t = t.translate(REMOVE_TILE_MARKS)
    assert t.isdigit(), tile
    return int(t)