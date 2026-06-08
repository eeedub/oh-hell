"""A determinized Monte Carlo card-play strategy.

The idea (a standard technique for trick-taking games, sometimes called
Perfect-Information Monte Carlo):

1. We can see our own hand and everything that's been played, but not how the
   unseen cards are split among the opponents.
2. So we *guess*: deal the unseen cards to the opponents at random many times.
   Each random deal is a "determinization" — a full-information world that is
   consistent with what we actually know.
3. For each card we could legally play, we play every determinization out to the
   end of the round using the fast greedy policy, and record our resulting round
   score (tricks + the 10-point bonus for hitting our bid exactly).
4. We play the card with the best *average* score across all the samples.

Bidding still uses the inherited heuristic — only card play is Monte Carlo.
"""

from __future__ import annotations

import random

from .cards import Card, Suit
from .game import EXACT_BONUS
from .player import AIPlayer, greedy_play
from .rules import legal_plays, trick_winner_index

FULL_DECK = [Card(rank, suit) for suit in Suit for rank in range(2, 15)]


class MonteCarloPlayer(AIPlayer):
    """Plays cards by sampling opponents' hands and rolling out the round.

    ``samples`` is the number of random deals evaluated — higher is stronger but
    slower. Every candidate card is scored against the *same* sampled deals
    (Common Random Numbers), which lowers the variance of the comparison, so the
    default can be modest. Pass an ``rng`` for reproducible play.
    """

    def __init__(self, name: str, *, samples: int = 30, rng: random.Random | None = None) -> None:
        super().__init__(name)
        self.samples = samples
        self._rng = rng or random.Random()

    def choose_card(self, *, legal, trick, trump, lead_suit, seen, players=None, leader=0):
        # Nothing to decide, or the engine didn't give us the table state we
        # need to simulate: fall back to the cheap greedy policy.
        if players is None or len(legal) == 1:
            return greedy_play(legal, [c for _, c in trick], trump, self.bid, self.tricks_won)

        n = len(players)
        my_seat = players.index(self)
        counts = [len(p.hand) for p in players]        # cards left per seat (public)
        bids = [p.bid for p in players]                # announced bids (public)
        base_tricks = [p.tricks_won for p in players]  # tricks taken so far (public)

        # Cards that cannot be in an opponent's hand: ours, those already played
        # this round, and those on the table in the current trick.
        known = set(self.hand) | set(seen) | {c for _, c in trick}
        pool = [c for c in FULL_DECK if c not in known]

        # The in-progress trick as (seat, card) in play order from the leader.
        trick_so_far = [((leader + i) % n, card) for i, (_, card) in enumerate(trick)]
        opp_seats = [s for s in range(n) if s != my_seat]

        # Our hand minus each candidate, precomputed once.
        my_hands_after = [[c for c in self.hand if c != card] for card in legal]
        next_seat = (my_seat + 1) % n

        # Common Random Numbers: deal one world per sample and score *every*
        # candidate card against that same world. Fewer shuffles, and the paired
        # comparison lowers variance in the choice below.
        totals = [0.0] * len(legal)
        for _ in range(self.samples):
            self._rng.shuffle(pool)
            opp_hands = {}
            idx = 0
            for s in opp_seats:
                opp_hands[s] = pool[idx:idx + counts[s]]
                idx += counts[s]

            for ci, card in enumerate(legal):
                hands: list[list[Card]] = [[] for _ in range(n)]
                for s in opp_seats:
                    hands[s] = list(opp_hands[s])  # _play_out mutates, so copy
                hands[my_seat] = list(my_hands_after[ci])

                tricks_won = list(base_tricks)
                opening = list(trick_so_far) + [(my_seat, card)]
                _play_out(hands, tricks_won, trump, bids, n, opening, next_seat)

                mine = tricks_won[my_seat]
                totals[ci] += mine + (EXACT_BONUS if mine == self.bid else 0)

        # max keeps the first index on ties -> same "first legal card" tie-break.
        best_ci = max(range(len(legal)), key=lambda i: totals[i])
        return legal[best_ci]


def _play_out(hands, tricks_won, trump, bids, n, trick, next_seat):
    """Finish ``trick`` and play out the rest of the round with greedy policy.

    ``trick`` is the in-progress trick as a list of (seat, card) in play order.
    Mutates ``hands`` and ``tricks_won`` in place.
    """
    while True:
        while len(trick) < n:
            seat = next_seat
            lead_suit = trick[0][1].suit if trick else None
            legal = legal_plays(hands[seat], lead_suit)
            card = greedy_play(legal, [c for _, c in trick], trump, bids[seat], tricks_won[seat])
            hands[seat].remove(card)
            trick.append((seat, card))
            next_seat = (next_seat + 1) % n

        winner_seat = trick[trick_winner_index([c for _, c in trick], trump)][0]
        tricks_won[winner_seat] += 1
        if not hands[winner_seat]:  # every hand is now empty: round over
            return
        trick = []
        next_seat = winner_seat
