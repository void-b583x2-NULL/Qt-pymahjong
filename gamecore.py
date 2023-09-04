from pymahjong import MahjongEnv
from agent import MajAgent
from utils import CallingInfo, CallingCategory
from typing import Union, List, Tuple, Dict
import numpy as np
import yaml
from collections import defaultdict

from functools import reduce
from ui_utils import print_callings, print_river, print_hand, print_dora_list
from utils import get_turn_from_river_tile


from utils import (
    WIND_TRANSLATION_TABLE,
    # is_discarding,
    is_forward_call,
    notation_to_idx,
    tile_exp,
)

WINDS = list(WIND_TRANSLATION_TABLE.keys())
# print(WINDS)

import time

# START_POINT = 30000
# BONUSES = np.array([15, 5, -5, -15], dtype=np.float32)

np.random.seed(int(time.time()))


class MahjongGameCore(object):
    def __init__(
        self,
        config: dict
        # total_games=8, enable_more_games=True, agents=["ddqn", "bc", "ddqn"]
    ) -> None:
        super().__init__()

        self.max_game_count = config["n_games"]
        self.extra = 0
        self.enable_more_games = config["more_games"]
        self.negative_continue = config["negative_continue"]
        self.enable_honba_fee = config["enable_honba_fee"]
        self.AL_continue = config["AL_continue"]

        self.START_POINT = config["REACH_PT"]
        MahjongEnv.INIT_POINTS = config["START_POINT"]
        self.BONUSES = config["BONUS_POINTS"]
        self.BONUSES = np.array(self.BONUSES, dtype=np.float32)

        # print(MahjongEnv.INIT_POINTS)

        self.env = MahjongEnv()
        self.game_status = None
        self.terminated = False
        self.reset()

        self.agents = []
        for type in config["opponents"]:
            path = None
            if type == "ddqn":
                path = "chkpt/mahjong_VLOG_CQL.pth"
            elif type == "bc":
                path = "chkpt/mahjong_VLOG_BC.pth"
            self.agents.append(MajAgent(type, path))

    def is_terminated(self):
        return self.terminated

    def reset(self, change_oya=True, no_win=False):
        if self.game_status is None:
            self.game_status = {
                "oya": np.random.randint(4),
                "game_wind": "east",
                "game_count": 0,
                "honba": 0,
                "riichibo": 0,
                "cumulative_scores": np.zeros((4,), dtype=np.int32),
            }
        else:
            if (
                self.enable_more_games
                and self.extra < 4
                and np.max(self.game_status["cumulative_scores"])
                < self.START_POINT - MahjongEnv.INIT_POINTS
            ):  # more games
                self.extra += 1

            self.game_status["game_count"] += change_oya

            if (
                self.game_status["game_count"] >= self.max_game_count + self.extra
                or not self.negative_continue
                and np.min(self.game_status["cumulative_scores"])
                < -MahjongEnv.INIT_POINTS
                or self.game_status["game_count"] >= self.max_game_count
                and np.max(self.game_status["cumulative_scores"])
                >= self.START_POINT - MahjongEnv.INIT_POINTS
            ):
                self.game_status["game_count"] -= change_oya
                self.terminated = True
                return

            # AL oya 1st fast terminate
            if (
                not self.AL_continue
                and self.game_status["game_count"] == self.max_game_count - 1
                and not change_oya
                and np.max(self.game_status["cumulative_scores"])
                == self.game_status["cumulative_scores"][self.game_status["oya"]]
                and np.max(self.game_status["cumulative_scores"])
                > -np.sort(-self.game_status["cumulative_scores"])[1]
                and np.max(self.game_status["cumulative_scores"])
                >= self.START_POINT - MahjongEnv.INIT_POINTS
            ):
                self.terminated = True
                return

            self.game_status["oya"] = (self.game_status["oya"] + change_oya) % 4
            if no_win or not change_oya:
                self.game_status["honba"] += 1
            else:
                self.game_status["honba"] = 0

            self.game_status["game_wind"] = WINDS[
                self.game_status["game_count"] // 4 % 4
            ]

        self.env.reset(
            oya=self.game_status["oya"], game_wind=self.game_status["game_wind"]
        )
        self.current_turn = 0
        self.last_player_idx = -1
        self.last_action = (
            -1
        )  # only for discard and will be maintained in update board !!
        self.winners = []
        self.player_calling_info: List[List[CallingInfo]] = [[] for _ in range(4)]
        self.player_infos = []
        self._request_table: Dict[
            int, Tuple[int, int, int]
        ] = {}  # action, turn, from_idx

    def check_tenpai(self, player_idx: int):
        ten_tiles = self.env.t.players[player_idx].tenpai_to_string()
        ten_list = [ten_tiles[i : i + 2] for i in range(0, len(ten_tiles), 2)]
        # player_hand_str = self.get_player_info(player_idx)["Hand"]
        # player_hand_str = player_hand_str.replace("0", "5")  # red doras

        # if not self._checker.convert_strlist_to_tiles(player_hand_str):
        #     return False
        # ten_list = self._checker.CheckTen().split()
        total_tile_str = self.get_player_info(player_idx)["Hand"]
        # + " ".join(
        #     str(calling) for calling in self.player_calling_info[player_idx]
        # )
        ret_list = []
        for ten in ten_list:
            if total_tile_str.count(ten) < 4:  # avoid virtual ten
                ret_list.append(ten)
        return len(ret_list) > 0

    def get_player_info(self, player_idx: int) -> defaultdict:
        enti = self.env.t.players[player_idx]
        player_raw_str = enti.to_string()
        player_hand_dict = defaultdict(str)
        player_hand_dict.update(yaml.load(player_raw_str, Loader=yaml.FullLoader))
        if player_hand_dict["River"] is None:
            player_hand_dict["River"] = ""

        player_hand_dict["Furiten"] = (
            enti.riichi_furiten or enti.sutehai_furiten or enti.toujun_furiten
        )
        return player_hand_dict

    def _update_player_infos(self):
        """
        This function is responsible for dealing with call requests from players.
        Generally, Chi < [Pon,MinKan] < Ron.
        Due to the mechanism of query, requests should be stored, and finally compared to get the final action.

        The key problem is to address automatic discarding...

        """
        self.player_infos = [self.get_player_info(i) for i in range(4)]
        # maintain last tile
        max_turn, max_idx = -1, -1
        cumulative_tileinfo_river = []
        for idx, player_hand_dict in enumerate(self.player_infos):
            player_river: List[str] = player_hand_dict["River"].split()
            cumulative_tileinfo_river.extend([t[2:] for t in player_river])
            if len(player_river) > 0:
                last_tile = player_river[-1]
                last_turn = get_turn_from_river_tile(last_tile)
                if last_turn > max_turn:
                    max_turn, max_idx = last_turn, idx
        self.last_player_idx = max_idx
        self.current_turn = max_turn

        # update_fuuro
        if len(self._request_table) > 0:
            requests = list(self._request_table.values())
            req_turn = requests[0][1]
            # assert all req_turn should be the same in _request_table!
            cumulative_tileinfo_river = " ".join(cumulative_tileinfo_river) + " "
            assert str(req_turn) in cumulative_tileinfo_river, req_turn
            req_index = cumulative_tileinfo_river.index(str(req_turn))
            cumulative_tileinfo_river = cumulative_tileinfo_river[req_index:]
            if "-" in cumulative_tileinfo_river[: cumulative_tileinfo_river.index(" ")]:
                # That means the corresponding tile has been called!
                # compare to get who executed the operation
                action, act_idx = 0, -1
                for player_idx, request in self._request_table.items():
                    a = request[0]
                    if a > action:
                        action, act_idx = a, player_idx
                assert act_idx > -1
                self._update_player_fuuro(act_idx)

    def _update_player_fuuro(
        self,
        player_idx: int,
    ):
        # calculate the final result
        # if len(self._request_table) > 0:  # Calls to be settled

        a, _, from_idx = self._request_table[player_idx]
        curr_player_id = player_idx
        assert is_forward_call(a)
        player_hand_dict = self.player_infos[curr_player_id]
        self.player_calling_info[curr_player_id].append(
            CallingInfo(
                player_hand_dict["Calls"].split()[-1],
                CallingCategory.to_category(a),
                from_idx,
            )
        )
        self._request_table.clear()

    def _render_ankan_player_request(self, curr_player_id: int):
        # a == MahjongEnv.ANKAN:
        # player_hand_dict = self.get_player_info(curr_player_id)
        player_hand_dict = self.player_infos[curr_player_id]
        self.player_calling_info[curr_player_id].append(
            CallingInfo(
                player_hand_dict["Calls"].split()[-1],
                CallingCategory.Ankan,
                curr_player_id,
            )
        )

    def _render_kakan_player_request(self, curr_player_id: int, old_hand_dict: dict):
        # a == MahjongEnv.KAKAN:
        # use the stored old hand str
        last_fuuro_raw_list = old_hand_dict["Calls"].split()
        fuuro_raw_list = self.player_infos[curr_player_id]["Calls"].split()
        for fuuro in fuuro_raw_list:
            if fuuro not in last_fuuro_raw_list:
                break
        # fuuro in "?x?x?x?x" format
        for i, calling in enumerate(self.player_calling_info[curr_player_id]):
            if fuuro[:2] in calling.calling_str:
                self.player_calling_info[curr_player_id][
                    i
                ].calling_type = CallingCategory.Kakan
                break

    def step(self, action=None, specified_tile: Union[int, str, None] = None):
        if not self.env.is_over():
            curr_player_id = self.env.get_curr_player_id()

            if action is None:  # Not pre ordered
                if curr_player_id == 0:
                    # This part of code should only be triggered when -f is enabled to fast pass through
                    valid_actions = self.env.get_valid_actions()
                    if MahjongEnv.PASS_RESPONSE in valid_actions:
                        valid_actions = valid_actions[:-1]
                    a = np.random.choice(valid_actions)
                else:
                    a = self.agents[curr_player_id - 1].select_action(
                        self.env.get_obs(curr_player_id),
                        self.env.get_valid_actions(nhot=True),
                    )
            else:
                a = action

            # Note. Due to the unique mechanism of the repo, we need to first save the requests of each player, and then make a decision.
            if is_forward_call(a):
                self._request_table[curr_player_id] = (
                    a,
                    self.current_turn,
                    self.last_player_idx,
                )

            if a == MahjongEnv.KAKAN:
                # At present there's literally no means to decide which one to ka-kan, so save in advance...
                # player_hand_dict_o = self.get_player_info(curr_player_id)
                player_hand_dict_o = self.player_infos[curr_player_id].copy()

            if specified_tile:
                if isinstance(specified_tile, str):
                    specified_tile = notation_to_idx(specified_tile)

            # step function
            self.env.step(
                curr_player_id,
                a,
            )  # TODO: specified_tile=specified_tile
            self._update_player_infos()

            # aftercare of the gameboard...

            # ##########################################################################
            # ######## Deprecated ########
            # if not self.env.is_over():
            #     next_actions = self.env.get_valid_actions()
            # if len(self._request_table) > 0 and (
            #     self.env.is_over() or is_discarding(next_actions)
            # ):
            #     # TODO: shiti banner will cause the player skip its decision process and calls error.
            #     self._update_player_fuuro(self.env.get_curr_player_id())
            # ##########################################################################

            if a == MahjongEnv.ANKAN:
                self._render_ankan_player_request(curr_player_id)
            elif a == MahjongEnv.KAKAN:
                self._render_kakan_player_request(curr_player_id, player_hand_dict_o)
            # for win cases...
            elif a == MahjongEnv.TSUMO:
                self.winners.append(curr_player_id)
                self.last_player_idx = curr_player_id  # `_update_player_infos()` count the one with the maximum tuen as last_idx
                self.last_action = a
            elif a == MahjongEnv.RON:
                self.winners.append(curr_player_id)
                self.loser = self.last_player_idx  # the one lose points
            # if is_discarding(a) or a in (
            #     MahjongEnv.RIICHI,
            #     MahjongEnv.TSUMO,
            #     MahjongEnv.RON,
            # ):  # last one to take the real effect. As we always discard a tile when make a call, that needn't be addressed
            if self.env.is_over():
                self.calc_scores()
        else:
            # reset
            if len(self.winners) > 0:
                change_oya = self.game_status["oya"] not in self.winners
            else:
                change_oya = not self.check_tenpai(self.game_status["oya"])

            self.reset(change_oya=change_oya, no_win=len(self.winners) == 0)

    def calc_scores(self):
        payoffs = np.array(self.env.get_payoffs(), dtype=np.int32)

        # honba scores are not included and needs to be calced
        if self.last_action == MahjongEnv.TSUMO:
            assert len(self.winners) == 1, "Should be only 1 tsumoer"
            payoffs[self.winners[0]] += (
                100 * 4 * self.game_status["honba"] * self.enable_honba_fee
                + 1000 * self.game_status["riichibo"]
            )
            payoffs -= 100 * self.game_status["honba"] * self.enable_honba_fee
            self.game_status["riichibo"] = 0
        elif len(self.winners) > 0:
            for i in range(
                self.loser + 1, self.loser + 5
            ):  # headfirst to get honba and riichibos
                if i % 4 in self.winners:
                    break
            payoffs[i % 4] += (
                100 * 3 * self.game_status["honba"] * self.enable_honba_fee
                + 1000 * self.game_status["riichibo"]
            )
            payoffs[self.loser] -= (
                100 * 3 * self.game_status["honba"] * self.enable_honba_fee
            )
            self.game_status["riichibo"] = 0
        else:
            for player_hand_info in self.player_infos:
                self.game_status["riichibo"] += player_hand_info["Riichi"]

        self.payoffs = payoffs
        self.game_status["cumulative_scores"] += payoffs
        print(self.game_status["cumulative_scores"] + MahjongEnv.INIT_POINTS)

    def calc_final_scores(self) -> np.ndarray:
        # final scores: count riichibo
        self.game_status["cumulative_scores"][0] = -np.sum(
            self.game_status["cumulative_scores"][1:]
        )
        self.game_status["riichibo"] = 0

        final_scores = np.array(self.game_status["cumulative_scores"], dtype=np.float32)
        final_scores = (
            final_scores - (self.START_POINT - MahjongEnv.INIT_POINTS)
        ) / 1000
        # trick:slightly modify the value to enable sorting with seats
        priority_seats = np.zeros((4,))
        old_oya = (self.game_status["oya"] - self.game_status["game_count"]) % 4

        for i, seat in enumerate(range(old_oya, old_oya + 4)):
            priority_seats[seat % 4] = i

        final_scores -= priority_seats * 1e-4
        displayed_scores = -np.sort(-final_scores)
        displayed_sequence = np.argsort(-final_scores)
        displayed_scores += self.BONUSES

        final_scores = np.round(displayed_scores, 1)
        final_scores[0] = -np.sum(final_scores[1:]).round(1)

        self.game_status["cumulative_scores"] += MahjongEnv.INIT_POINTS
        return final_scores, displayed_sequence

    # information
    def get_dora_info_str(self) -> str:
        ret_str = (
            "寳牌指示: "
            + print_dora_list(self.env.t.dora_indicator, self.env.t.n_active_dora)
            + "\n"
        )
        if (
            self.env.is_over()
            and len(self.winners) > 0
            and reduce(
                lambda x, y: x or y,
                [self.env.t.players[i].riichi for i in self.winners],
            )
        ):
            # riichi ron
            ret_str += (
                "裏寳牌指示: "
                + print_dora_list(
                    self.env.t.uradora_indicator, self.env.t.n_active_dora
                )
                + "\n"
            )
        ret_str += "\n剩余: " + str(self.env.t.get_remain_tile())
        return ret_str

    def get_player_info_str(self, player_idx: int) -> str:
        player_hand_dict: dict = self.get_player_info(player_idx)
        player_calling_infos: List[CallingInfo] = self.player_calling_info[player_idx]
        game_status: dict = self.game_status
        # print row by row
        ret = f"{WIND_TRANSLATION_TABLE[player_hand_dict['Wind'].lower()]}"
        ret += "*" if self.env.get_curr_player_id() == player_idx else ""

        current_score = (
            game_status["cumulative_scores"][player_idx] + MahjongEnv.INIT_POINTS
        )
        if not self.env.is_over():
            current_score -= player_hand_dict["Riichi"] * 1000
        ret += f"\t{current_score}\n"

        mask_noneed = False

        if self.env.is_over():
            # calculate which cases should the tiles be open
            if len(self.winners) > 0:  # RON,TSUMO
                mask_noneed = player_idx in self.winners
            else:
                mask_noneed = self.check_tenpai(player_idx)
            if self.env.t.players[player_idx].riichi:
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
        ret += print_river(player_hand_dict["River"].split(), self.current_turn)
        ret += "リーチ " if player_hand_dict["Riichi"] else ""
        if player_idx == 0 or mask_noneed:
            tenpai = self.env.t.players[player_idx].tenpai_to_string()
            if len(tenpai) > 0:
                tenpai = [tenpai[i : i + 2] for i in range(0, len(tenpai), 2)]
                tenpai = "".join(tile_exp(tile) for tile in tenpai)
                ret += tenpai + " 待ち"
                if player_hand_dict["Furiten"]:
                    ret += " 振听"
        ret += "\n"
        return ret


# gc = MahjongGameCore()

if __name__ == "__main__":
    test_gc = MahjongGameCore(100)
    while not test_gc.is_terminated():
        test_gc.step()
