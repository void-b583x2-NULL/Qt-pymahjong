from typing import List
from utils import (
    JI_DECODE,
    WIND_TRANSLATION_TABLE,
    ARROWS,
    CallingInfo,
    tile_exp,
    get_turn_from_river_tile,
)
from pymahjong import MahjongEnv
import numpy as np

# from gamecore import MahjongGameCore
RIVER_WIDTH = 9


def print_hand(player_hand_list: List[str], mask_hand: bool = False) -> str:
    pl_list = [tile_exp(tile) for tile in player_hand_list]
    if not mask_hand:
        hands = " ".join(pl_list)
    else:
        hands = " ".join("**" for _ in pl_list)
    return hands


def print_callings(player_calling_infos: List[CallingInfo]) -> str:
    if len(player_calling_infos) < 1:
        return ""
    player_calling_strinfos = [str(item) for item in player_calling_infos]
    if len(player_calling_strinfos) > 2:
        player_calling_strinfos[2] = "\n  |" + player_calling_strinfos[2]
    ret_str = "|".join(player_calling_strinfos)
    for z, z_exp in JI_DECODE.items():
        if z in ret_str:
            ret_str = ret_str.replace(z, z_exp)

    return f"[{ret_str}]"


def print_river(
    player_river_list: List[str], max_turn: int, enable_discard_from=False
) -> str:
    print_str_ct = 1
    ret = ""
    encounter_r, printed_r = False, False
    for tile in player_river_list:
        tile_name, extra_info = tile[:2], tile[2:]
        tile_name = tile_exp(tile_name)

        # 0. riichi encounter update
        if not encounter_r:
            encounter_r = "r" in extra_info

        # 1. skip discarded
        if "-" in extra_info:
            continue

        tile_turn = get_turn_from_river_tile(tile)

        if encounter_r and not printed_r:
            ret += f"<{tile_name}>"
            printed_r = True
        else:
            ret += tile_name
        if tile_turn == max_turn:
            ret += "%" if "h" in extra_info else "@%"  # %:last tile @: not from hand
        elif enable_discard_from and "h" not in extra_info:
            ret += "@"

        ret += "\n" if print_str_ct % RIVER_WIDTH == 0 else " "
        print_str_ct += 1
    return ret + "\n"


def print_player(gc, player_idx: int, is_over=False) -> str:
    """
    This code is to print necessary info from a given maj field string
    """
    DeprecationWarning(
        "This function is deprecated. Use `gc.get_player_info_str` instead."
    )
    player_hand_dict: dict = gc.get_player_info(player_idx)
    player_calling_infos: List[CallingInfo] = gc.player_calling_info[player_idx]
    game_status: dict = gc.game_status
    # print row by row
    ret = f"{WIND_TRANSLATION_TABLE[player_hand_dict['Wind'].lower()]}"
    ret += "*" if gc.env.get_curr_player_id() == player_idx else ""
    current_score = game_status['cumulative_scores'][player_idx]+MahjongEnv.INIT_POINTS
    if not gc.env.is_over():
        current_score-=player_hand_dict['Riichi']*1000
    ret += f"\t{current_score}\n"
    if is_over:
        mask_noneed = False
        # calculate which cases should the tiles be open
        if len(gc.winners) > 0:  # RON,TSUMO
            mask_noneed = player_idx in gc.winners
        else:
            mask_noneed = gc.check_tenpai(player_idx)
        if gc.env.t.players[player_idx].riichi:
            mask_noneed = True

        ret += (
            print_hand(
                player_hand_dict["Hand"].split(),
                not (player_idx == 0 or mask_noneed),
            )
            + "\n"
        )
    else:
        ret += (
            print_hand(
                player_hand_dict["Hand"].split(),
                player_idx != 0,
            )
            + "\n"
        )
    ret += ">" + print_callings(player_calling_infos) + "\n"
    ret += print_river(player_hand_dict["River"].split(), gc.current_turn)
    ret += "リーチ" if player_hand_dict["Riichi"] else "" + "\n"
    return ret


def print_dora_list(dora_ind_list: list, n_active_dora: int) -> str:
    dora_indicators = [
        JI_DECODE.get(item.to_string(), item.to_string())
        for item in dora_ind_list[:n_active_dora]
    ]
    dora_indicators.extend(["**"] * (5 - n_active_dora))
    return f"[{'|'.join(dora_indicators)}]"


def print_game_status(game_status: dict) -> str:
    return (
        f"{WIND_TRANSLATION_TABLE[game_status['game_wind']]}{game_status['game_count'] % 4 +1}局 {game_status['honba']}本場"
        + f"\n場供: {1000*game_status['riichibo']}"
    )


def print_curr_scores(_scores: np.ndarray) -> str:
    scores = [f"{'+' if sc>0 else ''}{sc}" for sc in _scores]
    ret = f"Player 2: {scores[2]}{ARROWS[0]}\nPlayer 3: {scores[3]}{ARROWS[1]}\nPlayer 1: {scores[1]}{ARROWS[-1]}\nPlayer 0: {scores[0]}{ARROWS[-2]}"
    return ret


if __name__ == "__main__":
    from gamecore import MahjongGameCore

    gc = MahjongGameCore()

    # dora on left up
    print(print_dora_list(gc.env.t.dora_indicator, gc.env.t.n_active_dora))

    print(print_game_status(gc.game_status))

    print(print_player(gc, 2))

    print(print_player(gc, 3))

    print(print_player(gc, 1))

    print(print_player(gc, 0))
