# Qt-Pymahjong

This is a riichi mahjong game, based on `pymahjong` with a simple GUI, using Unicode chars of Mahjong tiles.

![](./img/sample_ui.jpg)

Due to the unique mechanism of `pymahjong`, it's awkward sometimes to make the game engine run as a player usually expects. I've tried my best to fit the habit of a common player and hope to make the environment follow the rules as Tenhou or MajSoul.

### Installation

`pip install -r requirements.txt`

Some packages can be install by yourself, as is notated in the `.txt` file.

**Note: If you're using the master branch of `pymahjong` or the current pip release version, replace the `env_pymahjong.py` under the initial location (usually under `${CONDA_ENV_LOCATION}/Lib/site-packages/pymahjong/`) with the one given in this repo, or the program may probably NOT FUNCTION well!** (Due to some initial bugs in the version)

**If you're using the [Develop-EncoderV2](https://github.com/Agony5757/mahjong/tree/Develop-EncoderV2) branch and managed to install `pymahjong` from source, no extra operation will be needed.**

### Get checkpoints for AI Agents

From the official [release](https://github.com/Agony5757/mahjong/releases/v1.0.2) to get the `*.pth` official checkpoints and put them under `chkpt/`.

### Run

`python qt_ui.py [-c <config_yaml>]`. For example, for a typical game the setting is stored at `config/default.yaml` by default, and it's recommended to read the notations in this default yaml before you define a new game.

Other available parameters (at present):

`-f`: Automatically execute a game (feasible for debugging)

### Mechanisms which may cause behaviour unexpected

#### May be fixed by future work (python code only):

The randomness to choose a tile to An-Kan or Ka-Kan when multiple choices are available (though rare in real scenarios)

#### Require diving into the cpp core to fix:

The fixed priority of red doras when discarding or making a call. This seems proper under most cases but may cause some damage under extreme cases (For example, a player decide to make Kokushi but with a pair of 5p in hand with one of red. He discards them sequentially, but the next 5p, literally 0p, is ronned by another player who tenpaied after the first 5p and make the lose points absolutely more.)

### Character notations

`%`: the last tile discarded

`@`: the tile was discarded after drawn, not from hand

`*`: the tile of red dora (Unicode majhong tiles don't have aka-tiles)

ARROWS: indicating where it came from in callings

`<>`: the tile declaring riichi

### Features on the way...

- Show who made a call just the moment
- More creative ideas perhaps?
- ...