"""Players: a base class plus an AI bot and an interactive human player.

Each round the engine asks a player two things:

* :meth:`Player.choose_bid` — how many tricks will you take?
* :meth:`Player.choose_card` — which card do you play next?

Subclasses answer those however they like. The engine owns the bookkeeping
(``hand``, ``bid``, ``tricks_won``, ``score``).
"""

from __future__ import annotations

from .cards import Card, Suit
from .render import Renderer
from .rules import card_strength, trick_winner_index


def card_value(card: Card, trump: Suit) -> float:
    """Rough probability that a card wins a trick, ignoring trick context.

    Used both for bidding (summing a hand's values) and for judging which card
    is most "dangerous" to keep when shedding losers.
    """
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


def greedy_play(
    legal: list[Card],
    trick_cards: list[Card],
    trump: Suit,
    bid: int,
    tricks_won: int,
) -> Card:
    """The heuristic card-play policy as a pure function.

    ``legal`` are the cards we may play (in hand order); ``trick_cards`` are the
    cards already on the table this trick, in play order. This is the shared
    rollout policy used by both :class:`AIPlayer` and the Monte Carlo simulator.
    """
    needs_more = tricks_won < bid

    if not trick_cards:
        # Leading: strongest if chasing, weakest if avoiding. (The reference
        # suit is our first legal card, matching the original heuristic.)
        ref = legal[0].suit
        chooser = max if needs_more else min
        return chooser(legal, key=lambda c: card_strength(c, trump, ref))

    lead = trick_cards[0].suit
    winning_card = trick_cards[trick_winner_index(trick_cards, trump)]
    winners = [
        c for c in legal
        if card_strength(c, trump, lead) > card_strength(winning_card, trump, lead)
    ]

    if needs_more:
        # Still chasing: win as cheaply as possible, else play low and keep highs.
        if winners:
            return min(winners, key=lambda c: card_strength(c, trump, lead))
        return min(legal, key=lambda c: card_strength(c, trump, lead))

    # Bid already made: "duck high" — shed the most dangerous card that loses.
    losers = [c for c in legal if c not in winners]
    if losers:
        return max(losers, key=lambda c: card_value(c, trump))
    return min(legal, key=lambda c: card_strength(c, trump, lead))


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
        players: list["Player"] | None = None,
        leader: int = 0,
    ) -> Card:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r})"


class AIPlayer(Player):
    """A simple heuristic bot. Good enough to give a real game; not optimal."""

    def choose_bid(self, *, trump, hand_size, bids_so_far, is_dealer, forbidden_bid):
        expected = sum(card_value(card, trump) for card in self.hand)
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

    def choose_card(self, *, legal, trick, trump, lead_suit, seen, players=None, leader=0):
        # The greedy heuristic ignores ``seen``/``players``; those are here for
        # smarter strategies (e.g. the Monte Carlo player) that subclass this.
        return greedy_play(legal, [c for _, c in trick], trump, self.bid, self.tricks_won)


class HumanPlayer(Player):
    """Plays via terminal prompts. Used by the interactive CLI mode."""

    def __init__(self, name: str, *, input_fn=input, output_fn=print, renderer=None) -> None:
        super().__init__(name)
        self._input = input_fn
        self._output = output_fn
        self._r = renderer or Renderer(enabled=False)

    def choose_bid(self, *, trump, hand_size, bids_so_far, is_dealer, forbidden_bid):
        hand = self._r.cards(sorted(self.hand, key=_sort_key))
        self._output(f"\nYour hand: {hand}")
        self._output(f"Trump: {self._r.suit(trump)}   Tricks this round: {hand_size}")
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

    def choose_card(self, *, legal, trick, trump, lead_suit, seen, players=None, leader=0):
        if trick:
            table = "   ".join(f"{p.name} {self._r.card(c)}" for p, c in trick)
            self._output(f"\nOn the table: {table}")
        else:
            self._output("\nYou lead this trick.")
        ordered = sorted(legal, key=_sort_key)
        listing = "   ".join(f"{self._r.dim(f'[{i}]')} {self._r.card(c)}" for i, c in enumerate(ordered))
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
