"""Pure rule helpers shared by the players and the game engine.

These functions contain no state — they just answer questions about cards
("which of these wins the trick?", "what may I legally play?"). Keeping them
here lets both :mod:`oh_hell.player` and :mod:`oh_hell.game` use them without a
circular import.
"""

from __future__ import annotations

from .cards import Card, Suit


def legal_plays(hand: list[Card], lead_suit: Suit | None) -> list[Card]:
    """Return the cards in ``hand`` that may legally be played.

    You must follow the led suit if you can. If you have none of it (or you are
    leading the trick), any card is legal.
    """
    if lead_suit is None:
        return list(hand)
    following = [c for c in hand if c.suit == lead_suit]
    return following if following else list(hand)


def card_strength(card: Card, trump: Suit | None, lead_suit: Suit) -> tuple[int, int]:
    """Sortable strength of a card *within the context of a trick*.

    Trumps beat everything; the led suit beats off-suit cards; anything else is
    worthless (it cannot win). Higher tuples win.
    """
    if trump is not None and card.suit == trump:
        return (2, card.rank)
    if card.suit == lead_suit:
        return (1, card.rank)
    return (0, card.rank)


def trick_winner_index(cards: list[Card], trump: Suit | None) -> int:
    """Index of the winning card in a completed trick.

    ``cards`` is in play order, so ``cards[0]`` set the led suit.
    """
    if not cards:
        raise ValueError("a trick has no cards")
    lead_suit = cards[0].suit
    return max(
        range(len(cards)),
        key=lambda i: card_strength(cards[i], trump, lead_suit),
    )
