"""Players: a base class plus an AI bot and an interactive human player.

Each round the engine asks a player two things:

* :meth:`Player.choose_bid` — how many tricks will you take?
* :meth:`Player.choose_card` — which card do you play next?

Subclasses answer those however they like. The engine owns the bookkeeping
(``hand``, ``bid``, ``tricks_won``, ``score``).
"""

from __future__ import annotations

from .cards import Card, Suit
from .rules import card_strength, trick_winner_index


class Player:
    """Common state and the interface the game engine calls into."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.hand: list[Card] = []
        self.bid: int = 0
        self.tricks_won: int = 0
        self.score: int = 0

    def reset_for_round(self) -> None:
        self.hand = []
        self.bid = 0
        self.tricks_won = 0

    # --- interface implemented by subclasses -----------------------------
    def choose_bid(
        self,
        *,
        trump: Suit,
        hand_size: int,
        bids_so_far: list[int],
        is_dealer: bool,
        forbidden_bid: int | None,
    ) -> int:
        raise NotImplementedError

    def choose_card(
        self,
        *,
        legal: list[Card],
        trick: list[tuple["Player", Card]],
        trump: Suit,
        lead_suit: Suit | None,
        seen: list[Card],
    ) -> Card:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"


class AIPlayer(Player):
    """A simple heuristic bot. Good enough to give a real game; not optimal."""

    def choose_bid(self, *, trump, hand_size, bids_so_far, is_dealer, forbidden_bid):
        expected = sum(self._card_value(card, trump) for card in self.hand)
        bid = round(expected)
        bid = max(0, min(hand_size, bid))

        # Honor "the hook": the dealer may not make the bids sum to the number
        # of tricks. Nudge toward the value that keeps us closest to estimate.
        if forbidden_bid is not None and bid == forbidden_bid:
            lower, upper = bid - 1, bid + 1
            if upper <= hand_size and (lower < 0 or expected >= bid):
                bid = upper
            else:
                bid = max(0, lower)
        return bid

    @staticmethod
    def _card_value(card: Card, trump: Suit) -> float:
        """Rough probability this card wins a trick."""
        if card.suit == trump:
            if card.rank >= 13:
                return 0.95
            if card.rank >= 11:
                return 0.75
            if card.rank >= 8:
                return 0.5
            return 0.3
        # Off-suit: only the very top cards are reliable winners.
        if card.rank == 14:
            return 0.85
        if card.rank == 13:
            return 0.55
        if card.rank == 12:
            return 0.25
        return 0.0

    def choose_card(self, *, legal, trick, trump, lead_suit, seen):
        # ``seen`` (cards already played this round) is available for strategies
        # that want to count cards; this heuristic doesn't need it.
        needs_more = self.tricks_won < self.bid

        # Cards currently on the table, in play order.
        played = [card for _, card in trick]

        if not played:
            # Leading: if we still need tricks, lead our strongest card; if we
            # have made our bid, lead our weakest to shed losers.
            return self._strongest(legal, trump, lead_suit=None) if needs_more \
                else self._weakest(legal, trump, lead_suit=None)

        current_lead = trick[0][1].suit
        winning_card = played[trick_winner_index(played, trump)]
        winners = [c for c in legal if self._beats(c, winning_card, trump, current_lead)]

        if needs_more:
            # Still chasing tricks: win as cheaply as possible if we can,
            # otherwise play low and keep our high cards for a later trick.
            if winners:
                return min(winners, key=lambda c: card_strength(c, trump, current_lead))
            return self._weakest(legal, trump, lead_suit=current_lead)

        # We've made our bid and want no more tricks. "Duck high": play the
        # highest card that still loses, shedding whatever is most likely to win
        # an unwanted trick later. If every legal card would win, take it as
        # cheaply as possible.
        losers = [c for c in legal if c not in winners]
        if losers:
            return max(losers, key=lambda c: self._card_value(c, trump))
        return min(legal, key=lambda c: card_strength(c, trump, current_lead))

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _beats(card: Card, other: Card, trump: Suit, lead_suit: Suit) -> bool:
        return card_strength(card, trump, lead_suit) > card_strength(other, trump, lead_suit)

    @staticmethod
    def _strongest(cards, trump, lead_suit):
        ref = lead_suit if lead_suit is not None else cards[0].suit
        return max(cards, key=lambda c: card_strength(c, trump, ref))

    @staticmethod
    def _weakest(cards, trump, lead_suit):
        ref = lead_suit if lead_suit is not None else cards[0].suit
        return min(cards, key=lambda c: card_strength(c, trump, ref))


class HumanPlayer(Player):
    """Plays via terminal prompts. Used by the interactive CLI mode."""

    def __init__(self, name: str, *, input_fn=input, output_fn=print) -> None:
        super().__init__(name)
        self._input = input_fn
        self._output = output_fn

    def choose_bid(self, *, trump, hand_size, bids_so_far, is_dealer, forbidden_bid):
        hand = " ".join(str(c) for c in sorted(self.hand, key=_sort_key))
        self._output(f"\nYour hand: {hand}")
        self._output(f"Trump: {trump}   Tricks this round: {hand_size}")
        if bids_so_far:
            self._output(f"Bids so far: {sum(bids_so_far)} (need not match)")
        forbidden = "" if forbidden_bid is None else f" (you may not bid {forbidden_bid} — the hook)"
        while True:
            raw = self._input(f"{self.name}, your bid 0-{hand_size}{forbidden}: ").strip()
            if not raw.isdigit():
                self._output("Please enter a whole number.")
                continue
            bid = int(raw)
            if not 0 <= bid <= hand_size:
                self._output(f"Bid must be between 0 and {hand_size}.")
                continue
            if bid == forbidden_bid:
                self._output("That bid is blocked by the hook. Pick another.")
                continue
            return bid

    def choose_card(self, *, legal, trick, trump, lead_suit, seen):
        if trick:
            table = "  ".join(f"{p.name}:{c}" for p, c in trick)
            self._output(f"\nOn the table: {table}")
        else:
            self._output("\nYou lead this trick.")
        ordered = sorted(legal, key=_sort_key)
        listing = "  ".join(f"[{i}] {c}" for i, c in enumerate(ordered))
        self._output(f"Legal plays (need {self.bid - self.tricks_won} more trick(s)): {listing}")
        while True:
            raw = self._input(f"{self.name}, choose a card 0-{len(ordered) - 1}: ").strip()
            if raw.isdigit() and 0 <= int(raw) < len(ordered):
                return ordered[int(raw)]
            self._output("Invalid choice, try again.")


def _sort_key(card: Card) -> tuple[int, int]:
    """Group a hand by suit then rank for tidy display."""
    suit_order = {Suit.SPADES: 0, Suit.HEARTS: 1, Suit.DIAMONDS: 2, Suit.CLUBS: 3}
    return (suit_order[card.suit], -card.rank)
