import sys
import typing

from PyQt6.QtCore import QObject, QSize, Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QMessageBox,
)

from pymahjong import MahjongEnv
import time
from functools import partial
from typing import Union, List
import numpy as np

from utils import ACTION_TRANSLATION_TABLE
from ui_utils import print_game_status, print_curr_scores, print_detailed_winner_info
from enum import IntEnum

from gamecore import MahjongGameCore


class GameSignalType(IntEnum):
    current_player_response = 200
    is_over = -1024
    running = 255


DELAY = 1.5  # seconds

from argparse import ArgumentParser


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config/default.yaml",
        help="base config for customized game control",
    )

    parser.add_argument(
        "--fast_through", "-f", action="store_true", help="fast terminate"
    )
    args = parser.parse_args()
    return args


# Subclass QMainWindow to customize your application's main window
class MainWindow(QMainWindow):
    def __init__(self, config: dict, qsize=(1350, 800), font_sizes=(18, 14, 16)):
        super().__init__()
        self.config = config

        self.setWindowTitle("リーチ麻雀")
        self.setStyleSheet("QWidget{background-color:#f4f4f4}")
        self.font_sizes = font_sizes

        self.setFixedSize(QSize(*qsize))

        self.board_layout = QGridLayout()

        self.info_labels = [QLabel() for _ in range(7)]
        for info_label in self.info_labels:
            font = info_label.font()
            font.setPointSize(self.font_sizes[0])
            info_label.setFont(font)
            info_label.setAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignJustify
            )
        # need further inspection...

        self.option_layout = QHBoxLayout()

        for i in range(2):
            for j in range(3):
                self.board_layout.addWidget(self.info_labels[i * 3 + j], i, j)
            self.board_layout.addWidget(self.info_labels[6], 2, 1)

        self.init_button = QPushButton("Start")
        self._set_font(self.init_button, self.font_sizes[1])
        self.option_layout.addWidget(self.init_button)
        self.init_button.clicked.connect(self.init_game)

        self.signal_list = []
        self._render_layout()

    @staticmethod
    def _set_font(obj: QWidget, font_size: int = 12, bold: bool = False):
        font = obj.font()
        font.setPointSize(font_size)
        font.setBold(bold)
        obj.setFont(font)

    def _set_buttons_for_options(self):
        self.tiles_layout = QGridLayout()
        self.tiles_layout.setAlignment(None, Qt.AlignmentFlag.AlignTop)
        # self.tiles_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout = QGridLayout()
        self.actions_layout.setAlignment(None, Qt.AlignmentFlag.AlignTop)
        # self.actions_layout.setContentsMargins(0, 0, 0, 0)

        self.action_buttons = [QPushButton() for _ in MahjongEnv.ACTION_TYPES]

        self.board_layout.addLayout(self.tiles_layout, 2, 0)
        self.board_layout.addLayout(self.actions_layout, 2, 2)

        for i, tile in enumerate(self.action_buttons):
            if i < MahjongEnv.MAHJONG_TILE_TYPES:
                self.tiles_layout.addWidget(
                    tile, i // 9, i % 9, alignment=Qt.AlignmentFlag.AlignCenter
                )
                tile.setFixedSize(QSize(35, 50))
                self._set_font(tile, self.font_sizes[0])
            else:
                self.actions_layout.addWidget(
                    tile,
                    (i - MahjongEnv.MAHJONG_TILE_TYPES) // 5,
                    ((i - MahjongEnv.MAHJONG_TILE_TYPES)) % 5,
                    alignment=Qt.AlignmentFlag.AlignCenter,
                )
                tile.setFixedSize(QSize(90, 60))
                self._set_font(tile, self.font_sizes[1])

            tile.setEnabled(False)
            tile.setText(ACTION_TRANSLATION_TABLE[i])
            tile.clicked.connect(partial(self.run, i, True))

        # fill the rest two boxes
        self.status_label = [QLabel(), QLabel()]
        self.tiles_layout.addWidget(
            self.status_label[0],
            3,
            7,
            1,
            2,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self.actions_layout.addWidget(
            self.status_label[1],
            2,
            3,
            1,
            2,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        for label in self.status_label:
            self._set_font(label, self.font_sizes[-1], True)
            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignJustify
            )

        self.repaint()

    def _render_layout(self):
        self.page_layout = QVBoxLayout()
        self.page_layout.addLayout(self.board_layout)
        self.page_layout.addLayout(self.option_layout)

        # Set the central widget of the Window.

        self.widget = QWidget()
        self.widget.setLayout(self.page_layout)
        self.setCentralWidget(self.widget)

    def init_game(self):
        self.init_button.setEnabled(False)
        self.init_button.setText("")
        self.init_button.setVisible(False)
        self.run()

    def render(self):
        # time.sleep(0.3)
        # Option on display the core
        is_over = self.gc.env.is_over()

        # dora on left up
        # first row
        self.info_labels[0].setText(self.gc.get_dora_info_str())

        self.info_labels[2].setText(print_game_status(self.gc.game_status))
        self.info_labels[1].setText(self.gc.get_player_info_str(2))

        # second row
        self.info_labels[3].setText(self.gc.get_player_info_str(3))
        if is_over:
            self.info_labels[4].setText(print_curr_scores(self.gc.payoffs))
        else:
            self.info_labels[4].setText("")
        self.info_labels[5].setText(self.gc.get_player_info_str(1))

        self.info_labels[6].setText(self.gc.get_player_info_str(0))

        self.repaint()

    def _set_avail_buttons(self, actions: Union[List[int], np.ndarray]):
        for i in actions:
            self.action_buttons[i].setEnabled(True)
        # set prompts
        if MahjongEnv.TSUMO in actions:
            self.status_label[1].setText("ツモる？")
        elif MahjongEnv.RON in actions:
            self.status_label[1].setText("ロンる？")
        elif actions[0] < MahjongEnv.MAHJONG_TILE_TYPES:
            self.status_label[0].setText("何切る？")
        elif MahjongEnv.RIICHI in actions:
            self.status_label[1].setText("立直る？")
        else:
            self.status_label[1].setText("鳴牌なき？")
        if MahjongEnv.KAKAN in actions or MahjongEnv.ANKAN in actions:
            self.status_label[1].setText("カンる？")

    def _display_end_of_game(self):
        self.init_button.setEnabled(False)
        self.init_button.setVisible(False)
        displayed_scores, displayed_sequence = self.gc.calc_final_scores()
        set_str = ""

        for ranking, (idx, score) in enumerate(
            zip(displayed_sequence, displayed_scores)
        ):
            set_str += f"Ranking {ranking}: Player {idx}, score={self.gc.game_status['cumulative_scores'][idx]}, pt={score:.1f}\n"

        set_str += "The game has ended.\nTo start a new game, restart the program."
        # self.info_labels[4].setText(set_str)
        qbox = QMessageBox()
        qbox.setBaseSize(100, 50)
        self._set_font(qbox)
        qbox.setWindowTitle("終わり")
        qbox.setText(set_str)
        # qbox.setStandardButtons(QMessageBox.Ok)
        qbox.exec()
        self.repaint()

    def _display_win_info(self):
        off_result = self.gc.env.t.get_result()
        info_str = ""
        if len(self.gc.winners) > 0:
            for player_idx in self.gc.winners:
                info_str += print_detailed_winner_info(
                    player_idx,
                    off_result.results[player_idx],
                    off_result.result_type.value == 1,
                    player_idx == self.gc.game_status["oya"],
                )

        else:
            info_str = "流局 结算"
        qbox = QMessageBox()
        qbox.setBaseSize(100, 50)
        self._set_font(qbox)
        qbox.setWindowTitle("结算")
        qbox.setText(info_str)
        # qbox.setStandardButtons(QMessageBox.Ok)
        qbox.exec()

    def run(self, action=None, on_click=False):
        if not hasattr(self, "gc"):
            self.gc = MahjongGameCore(self.config)
            self._set_buttons_for_options()
            self.render()
        elif self.gc.env.is_over():
            self.gc.step()
            self.render()

        if self.gc.is_terminated():
            self._display_end_of_game()
            sys.exit(0)

        # clear status
        for bt in self.action_buttons:
            bt.setEnabled(False)
        for lb in self.status_label:
            lb.setText("")

        if on_click:
            self.gc.step(action=action)
            self.render()
        self.gt = GameRunThread(self.gc)
        self.gt.render.connect(self.receive_render_command)
        self.gt.start()

    def receive_render_command(self, sigval: GameSignalType):
        if sigval == GameSignalType.current_player_response:
            self._set_avail_buttons(self.gc.env.get_valid_actions())
        elif sigval == GameSignalType.is_over:
            self._display_win_info()
            self.init_button.setText("Continue?")
            self.init_button.setEnabled(True)
            self.init_button.setVisible(True)
        self.render()


class GameRunThread(QThread):
    render = pyqtSignal(GameSignalType)

    def __init__(self, gc: MahjongGameCore) -> None:
        super().__init__()
        self.gc = gc

    def run(self):
        if self.gc.env.get_curr_player_id() in [1, 2, 3]:
            time.sleep(DELAY)
        while not self.gc.is_terminated():
            if self.gc.env.get_curr_player_id() == 0:
                if args.fast_through:
                    self.gc.step()
                    self.render.emit(GameSignalType.running)
                else:
                    self.render.emit(GameSignalType.current_player_response)
                    break
            elif self.gc.env.get_curr_player_id() == -1:
                self.render.emit(GameSignalType.is_over)
                break
            else:
                self.gc.step()
                self.render.emit(GameSignalType.running)
                if self.gc.env.get_curr_player_id() not in (0, -1):
                    time.sleep(DELAY)


if __name__ == "__main__":
    import yaml

    args = parse_args()
    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    DELAY = config["step_time"]
    if args.fast_through:
        DELAY = 0.1

    app = QApplication(sys.argv)

    window = MainWindow(config)
    window.show()

    # Start the event loop.
    sys.exit(app.exec())
