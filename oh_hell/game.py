"""The Oh Hell game engine.

Implements the rules from https://officialgamerules.org/game-rules/oh-hell/:

* A standard 52-card deck.
* A configurable deal pattern (the number of cards per hand changes each round).
* Trump is the suit of the card flipped after the deal.
* Players bid the exact number of tricks they expect to take. "The hook"
  (optional) forbids the dealer from making the bids sum to the trick count.
* Follow suit if you can; highest trump wins, otherwise highest card of the led
  suit.
* Scoring: 1 point per trick taken, plus a 10-point bonus for an exact bid.
* Highest total score after the final round wins.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .cards import Card, Deck, Suit
from .player import Player
from .render import Renderer
from .rules import legal_plays, trick_winner_index

DECK_SIZE = 52
EXACT_BONUS = 10


def max_hand_size(num_players: int) -> int:
    """Largest hand each player can get while leaving a card to flip for trump."""
    return (DECK_SIZE - 1) // num_players


def deal_pattern(spec: str, num_players: int) -> list[int]:
    """Turn a pattern string into the list of hand sizes, one per round.

    Examples (``..`` means "count to")::

        "10..1..10"  -> 10, 9, ..., 1, 2, ..., 10
        "1..7"       -> 1, 2, 3, 4, 5, 6, 7

    Sizes are clamped to what the deck allows for the player count, and any
    consecutive duplicates produced by clamping are collapsed.
    """
    points = [int(p) for p in spec.split("..") if p.strip() != ""]
    if not points:
        raise ValueError(f"invalid deal pattern: {spec!r}")

    sizes: list[int] = []
    if len(points) == 1:
        sizes = [points[0]]
    else:
        for start, end in zip(points, points[1:]):
            step = 1 if end >= start else -1
            sizes.extend(range(start, end + step, step))

    cap = max_hand_size(num_players)
    clamped = [max(1, min(cap, n)) for n in sizes]

    collapsed: list[int] = []
    for n in clamped:
        if not collapsed or collapsed[-1] != n:
            collapsed.append(n)
    return collapsed


@dataclass
class RoundResult:
    """A snapshot of one finished round, for reporting/analysis."""

    round_number: int
    hand_size: int
    trump: Suit
    bids: dict[str, int]
    tricks: dict[str, int]
    round_scores: dict[str, int]
    total_scores: dict[str, int]


@dataclass
class Game:
    players: list[Player]
    pattern: str | None = None
    hook: bool = True
    exact_bonus: int = EXACT_BONUS
    seed: int | None = None
    verbose: bool = False
    output_fn: callable = print
    renderer: Renderer | None = None

    results: list[RoundResult] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if not 2 <= len(self.players) <= 7:
            raise ValueError("Oh Hell needs 2-7 players (3-7 recommended)")
        # Default to a no-color renderer; the CLI supplies a colored one.
        self.renderer = self.renderer or Renderer(enabled=False)
        self._rng = random.Random(self.seed)
        if self.pattern is None:
            cap = max_hand_size(len(self.players))
            self.pattern = f"1..{cap}..1"
        self.hand_sizes = deal_pattern(self.pattern, len(self.players))

    # --- output ----------------------------------------------------------
    def _say(self, message: str) -> None:
        if self.verbose:
            self.output_fn(message)

    # --- top level -------------------------------------------------------
    def play(self) -> list[RoundResult]:
        """Play every round in the pattern and return the per-round results."""
        for player in self.players:
            player.score = 0
        for round_number, hand_size in enumerate(self.hand_sizes, start=1):
            dealer_index = (round_number - 1) % len(self.players)
            result = self._play_round(round_number, hand_size, dealer_index)
            self.results.append(result)
        self._announce_winner()
        return self.results

    @property
    def standings(self) -> list[Player]:
        """Players sorted by score, highest first."""
        return sorted(self.players, key=lambda p: p.score, reverse=True)

    @property
    def winner(self) -> Player:
        return self.standings[0]

    # --- one round -------------------------------------------------------
    def _play_round(self, round_number: int, hand_size: int, dealer_index: int) -> RoundResult:
        deck = Deck(self._rng)
        deck.shuffle()
        for player in self.players:
            player.reset_for_round()
            player.hand = deck.deal(hand_size)
        trump_card = deck.deal_one()
        trump = trump_card.suit

        r = self.renderer
        plural = "s" if hand_size != 1 else ""
        header = (
            f"  {r.bold(f'Round {round_number}')}  ·  {hand_size} card{plural} each"
            f"  ·  trump {r.suit(trump)} {r.card(trump_card)}"
            f"  ·  dealer {self.players[dealer_index].name}"
        )
        self._say(f"\n{r.rule()}\n{header}\n{r.rule()}")

        self._collect_bids(hand_size, dealer_index, trump)
        self._play_tricks(hand_size, dealer_index, trump)

        return self._score_round(round_number, hand_size, trump)

    def _collect_bids(self, hand_size: int, dealer_index: int, trump: Suit) -> None:
        n = len(self.players)
        order = [(dealer_index + 1 + i) % n for i in range(n)]  # left of dealer first
        bids_so_far: list[int] = []
        for seat in order:
            player = self.players[seat]
            is_dealer = seat == dealer_index
            forbidden = None
            if self.hook and is_dealer:
                # The bid that would make totals equal the trick count.
                candidate = hand_size - sum(bids_so_far)
                if 0 <= candidate <= hand_size:
                    forbidden = candidate
            bid = player.choose_bid(
                trump=trump,
                hand_size=hand_size,
                bids_so_far=list(bids_so_far),
                is_dealer=is_dealer,
                forbidden_bid=forbidden,
            )
            player.bid = bid
            bids_so_far.append(bid)

        r = self.renderer
        bid_strs = "   ".join(
            f"{self.players[seat].name} {r.bold(str(self.players[seat].bid))}" for seat in order
        )
        total = sum(bids_so_far)
        # When the bids exactly cover the tricks, someone is guaranteed to miss.
        note = f"{total} bid / {hand_size} tricks"
        note = r.accent(note) if total != hand_size else r.bad(note + "  — all bids can't be made")
        self._say(f"  bids:  {bid_strs}     ({note})")

    def _play_tricks(self, hand_size: int, dealer_index: int, trump: Suit) -> None:
        n = len(self.players)
        leader = (dealer_index + 1) % n  # player left of dealer leads first
        seen: list[Card] = []  # cards played in completed tricks this round
        for trick_no in range(hand_size):
            trick: list[tuple[Player, Card]] = []
            lead_suit: Suit | None = None
            for offset in range(n):
                player = self.players[(leader + offset) % n]
                legal = legal_plays(player.hand, lead_suit)
                card = player.choose_card(
                    legal=legal,
                    trick=list(trick),
                    trump=trump,
                    lead_suit=lead_suit,
                    seen=list(seen),
                    players=self.players,
                    leader=leader,
                )
                if card not in legal:
                    raise ValueError(f"{player.name} played illegal card {card}")
                player.hand.remove(card)
                if lead_suit is None:
                    lead_suit = card.suit
                trick.append((player, card))

            seen.extend(c for _, c in trick)
            win_offset = trick_winner_index([c for _, c in trick], trump)
            winner = trick[win_offset][0]
            winner.tricks_won += 1
            leader = self.players.index(winner)

            r = self.renderer
            plays = "   ".join(f"{p.name} {r.card(c)}" for p, c in trick)
            self._say(
                f"  {r.dim(f'trick {trick_no + 1:>2}')}  {plays}   "
                + r.good(f"won by {winner.name}")
            )

    def _score_round(self, round_number: int, hand_size: int, trump: Suit) -> RoundResult:
        bids, tricks, round_scores = {}, {}, {}
        r = self.renderer
        width = max(len(p.name) for p in self.players)
        for player in self.players:
            made_it = player.tricks_won == player.bid
            gained = player.tricks_won + (self.exact_bonus if made_it else 0)
            player.score += gained
            bids[player.name] = player.bid
            tricks[player.name] = player.tricks_won
            round_scores[player.name] = gained
            mark = r.good("✓") if made_it else r.bad("✗")
            plus = r.bold(f"+{gained}".rjust(3))  # pad before styling to keep columns aligned
            self._say(
                f"  {mark} {player.name:<{width}}  bid {player.bid} took {player.tricks_won}"
                f"   {plus}   total {player.score}"
            )
        return RoundResult(
            round_number=round_number,
            hand_size=hand_size,
            trump=trump,
            bids=bids,
            tricks=tricks,
            round_scores=round_scores,
            total_scores={p.name: p.score for p in self.players},
        )

    def _announce_winner(self) -> None:
        r = self.renderer
        board = self.standings
        width = max(len(p.name) for p in self.players)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        self._say("\n" + r.bold("Final standings"))
        for rank, player in enumerate(board, start=1):
            badge = medals.get(rank, f"{rank}.")
            self._say(f"  {badge:<2} {player.name:<{width}}  {player.score}")
        self._say(r.bold(f"🏆 {board[0].name} wins!"))
