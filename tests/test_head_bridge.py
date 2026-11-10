import time

import numpy as np

from agent.composite import expression_vector
from agent.head_bridge import HeadBridge


def test_sim_follows_target_without_hardware():
    b = HeadBridge(sim=True, hz=100, alpha=1.0).start()
    try:
        target = expression_vector("happy", 0.8)
        b.set_target(target)
        time.sleep(0.1)
        assert np.allclose(b.current, target, atol=1e-6)
        assert b.sim
    finally:
        b.close()


def test_dict_target_is_accepted():
    b = HeadBridge(sim=True, hz=100, alpha=1.0).start()
    try:
        b.set_target({"CUL": 1.0})
        time.sleep(0.1)
        assert b.current.shape == (22,)
        assert b.current.max() > 0.5
    finally:
        b.close()
