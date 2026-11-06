"""中枢决策：把融合后的情绪变成表情、动作和语音。"""
from .composite import expression_vector
from .policy import ExpressionCommand, decide

__all__ = ["ExpressionCommand", "decide", "expression_vector"]
