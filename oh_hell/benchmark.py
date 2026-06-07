"""Benchmark harness for measuring bot quality.

The point of this module is to answer "did my change to the bot actually help?"
with numbers instead of intuition (a lesson learned the hard way — an
intuitive bidding tweak turned out to make the bot slightly *worse*).

The headline metric is the **exact-bid hit rate**: the fraction of rounds in
which a player took exactly as many tricks as they bid. That is where the big
+10 scoring bonus comes from, and — unlike the win rate — it does not depend on
how the opponents play, so it cleanly isolates the quality of a strategy.

Two entry points:

* :func:`run_benchmark` — characterise one strategy in absolute terms.
* :func:`compare` — A/B two strategies at shared tables to see which is better.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean

from .game import Game
from .player import AIPlayer, Player

# A factory is anything that takes a name and returns a Player (e.g. a class).
PlayerFactory = type[Player]


@dataclass
class BenchmarkResult:
    """Aggregate stats for a single strategy over many games."""

    games: int
    rounds: int
    exact_bids: int
    scores: list[int]                                # every player's final score
    by_hand_size: dict[int, tuple[int, int]] = field(default_factory=dict)  # size -> (exact, rounds)

    @property
    def hit_rate(self) -> float:
        return self.exact_bids / self.rounds if self.rounds else 0.0

    @property
    def avg_score(self) -> float:
        return mean(self.scores) if self.scores else 0.0


def _seed_for(base: int | None, i: int) -> int | None:
    return None if base is None else base + i


def run_benchmark(
    strategy: PlayerFactory = AIPlayer,
    *,
    games: int = 1000,
    players: int = 4,
    pattern: str | None = None,
    hook: bool = True,
    seed: int | None = 0,
) -> BenchmarkResult:
    """Play ``games`` games with a full table of ``strategy`` bots.

    A fixed ``seed`` (the default) makes the result reproducible — important so
    that re-running the benchmark after a code change is a fair comparison.
    """
    exact = 0
    rounds = 0
    scores: list[int] = []
    by_hand: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # size -> [exact, rounds]

    for i in range(games):
        table = [strategy(f"P{j}") for j in range(players)]
        game = Game(table, pattern=pattern, hook=hook, seed=_seed_for(seed, i))
        for result in game.play():
            for name, bid in result.bids.items():
                rounds += 1
                hit = bid == result.tricks[name]
                exact += hit
                by_hand[result.hand_size][0] += hit
                by_hand[result.hand_size][1] += 1
        scores.extend(p.score for p in table)

    return BenchmarkResult(
        games=games,
        rounds=rounds,
        exact_bids=exact,
        scores=scores,
        by_hand_size={size: tuple(v) for size, v in sorted(by_hand.items())},
    )


@dataclass
class ComparisonResult:
    """Head-to-head stats for a candidate strategy versus a baseline."""

    games: int
    candidate_exact: int
    candidate_rounds: int
    candidate_score: int
    baseline_exact: int
    baseline_rounds: int
    baseline_score: int
    candidate_seats: int  # how many of each sat at the table

    @property
    def candidate_hit_rate(self) -> float:
        return self.candidate_exact / self.candidate_rounds if self.candidate_rounds else 0.0

    @property
    def baseline_hit_rate(self) -> float:
        return self.baseline_exact / self.baseline_rounds if self.baseline_rounds else 0.0

    @property
    def candidate_avg_score(self) -> float:
        return self.candidate_score / (self.games * self.candidate_seats)

    @property
    def baseline_avg_score(self) -> float:
        return self.baseline_score / (self.games * self.candidate_seats)


def compare(
    candidate: PlayerFactory,
    baseline: PlayerFactory = AIPlayer,
    *,
    games: int = 2000,
    pattern: str | None = None,
    hook: bool = True,
    seed: int | None = 0,
) -> ComparisonResult:
    """Seat equal numbers of ``candidate`` and ``baseline`` bots together.

    Uses a 4-seat table (2 of each) and swaps their seats on alternate games to
    cancel out any positional advantage from the dealer rotation. The exact-bid
    hit rate is the fair way to read the result; the average score is shown too.
    """
    cand = {"exact": 0, "rounds": 0, "score": 0}
    base = {"exact": 0, "rounds": 0, "score": 0}

    for i in range(games):
        c0, c1 = candidate("C0"), candidate("C1")
        b0, b1 = baseline("B0"), baseline("B1")
        # Alternate the seating so neither side always sits in the same chairs.
        table = [c0, b0, c1, b1] if i % 2 == 0 else [b0, c0, b1, c1]
        candidate_names = {"C0", "C1"}

        game = Game(table, pattern=pattern, hook=hook, seed=_seed_for(seed, i))
        for result in game.play():
            for name, bid in result.bids.items():
                bucket = cand if name in candidate_names else base
                bucket["rounds"] += 1
                bucket["exact"] += bid == result.tricks[name]
        for p in table:
            bucket = cand if p.name in candidate_names else base
            bucket["score"] += p.score

    return ComparisonResult(
        games=games,
        candidate_exact=cand["exact"],
        candidate_rounds=cand["rounds"],
        candidate_score=cand["score"],
        baseline_exact=base["exact"],
        baseline_rounds=base["rounds"],
        baseline_score=base["score"],
        candidate_seats=2,
    )
