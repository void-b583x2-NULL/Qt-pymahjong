from pymahjong.models import VLOGMahjong
from pymahjong import MahjongEnv
import torch
import numpy as np

class MajAgent(object):
    def __init__(self, type='random', path=None) -> None:
        super().__init__()
        self.type = type
        
        if type != "random":
            state_dict = torch.load(path, map_location="cpu")
            if "f_s2q.network_modules.0.weight" in state_dict:
                alg = "ddqn"
            elif "f_s2pi0.network_modules.0.weight" in state_dict:
                alg = "bc"
            else:
                raise Exception("Unknown model")
            self.agent = VLOGMahjong(algorithm=alg)

            keys = list(state_dict.keys())
            for key in keys:
                if key not in list(self.agent.state_dict().keys()):
                    state_dict.pop(key)
            self.agent.load_state_dict(state_dict)
            
    def select_action(self,obs,valid_actions):
        if self.type == 'random':
            if MahjongEnv.PASS_RESPONSE in valid_actions:
                valid_actions = valid_actions[:-1]
            return np.random.choice(valid_actions)
        else:
            return self.agent.select(obs,valid_actions,greedy=True)