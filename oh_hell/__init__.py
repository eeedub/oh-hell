"""Oh Hell — a trick-taking card game simulator.

Public API re-exports so callers can do, e.g.::

    from oh_hell import Game, AIPlayer, HumanPlayer
"""

from .cards import Card, Suit, Deck, RANK_NAMES
from .player import Player, AIPlayer, HumanPlayer
from .game import Game, RoundResult, deal_pattern

__all__ = [
    "Card",
    "Suit",
    "Deck",
    "RANK_NAMES",
    "Player",
    "AIPlayer",
    "HumanPlayer",
    "Game",
    "RoundResult",
    "deal_pattern",
]

__version__ = "0.1.0"
