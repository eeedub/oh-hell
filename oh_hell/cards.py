"""Cards, suits, and the deck.

A card is identified by a *rank* (2-14, where 11=J, 12=Q, 13=K, 14=A) and a
:class:`Suit`. Cards are immutable and hashable so they can live in sets and be
used as dictionary keys.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum


class Suit(Enum):
    """The four suits, rendered with their playing-card symbols."""

    CLUBS = "♣"
    DIAMONDS = "♦"
    HEARTS = "♥"
    SPADES = "♠"

    def __str__(self) -> str:  # so f"{suit}" prints the symbol
        return self.value


# Map a numeric rank to its short display name. 2-10 print as themselves.
RANK_NAMES = {11: "J", 12: "Q", 13: "K", 14: "A"}

LOWEST_RANK = 2
HIGHEST_RANK = 14  # Ace high


def rank_name(rank: int) -> str:
    """Return the short label for a rank, e.g. 14 -> 'A', 7 -> '7'."""
    return RANK_NAMES.get(rank, str(rank))


@dataclass(frozen=True)
class Card:
    """A single playing card. Immutable and hashable."""

    rank: int
    suit: Suit

    def __post_init__(self) -> None:
        if not LOWEST_RANK <= self.rank <= HIGHEST_RANK:
            raise ValueError(f"rank must be {LOWEST_RANK}-{HIGHEST_RANK}, got {self.rank}")

    def __str__(self) -> str:
        return f"{rank_name(self.rank)}{self.suit.value}"

    def __repr__(self) -> str:
        return f"Card({self.rank}, {self.suit.name})"


class Deck:
    """A standard 52-card deck that can be shuffled and dealt from."""

    def __init__(self, rng: random.Random | None = None) -> None:
        # An explicit RNG makes games reproducible (handy for tests/simulations).
        self._rng = rng or random.Random()
        self.cards: list[Card] = [
            Card(rank, suit)
            for suit in Suit
            for rank in range(LOWEST_RANK, HIGHEST_RANK + 1)
        ]

    def __len__(self) -> int:
        return len(self.cards)

    def shuffle(self) -> None:
        self._rng.shuffle(self.cards)

    def deal(self, count: int) -> list[Card]:
        """Remove and return ``count`` cards from the top of the deck."""
        if count > len(self.cards):
            raise ValueError(f"cannot deal {count} cards; only {len(self.cards)} left")
        dealt, self.cards = self.cards[:count], self.cards[count:]
        return dealt

    def deal_one(self) -> Card:
        """Remove and return a single card (used to flip the trump card)."""
        return self.deal(1)[0]
