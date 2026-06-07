from oh_hell.benchmark import compare, run_benchmark
from oh_hell.player import AIPlayer


def test_run_benchmark_basic_shape():
    result = run_benchmark(games=20, players=4, pattern="3..1..3", seed=0)
    assert result.games == 20
    # Every game has the same number of rounds; each round records every player.
    assert result.rounds == 20 * 5 * 4
    assert len(result.scores) == 20 * 4
    assert 0.0 <= result.hit_rate <= 1.0
    assert 0 <= result.exact_bids <= result.rounds


def test_run_benchmark_is_reproducible():
    a = run_benchmark(games=30, pattern="2..1..2", seed=7)
    b = run_benchmark(games=30, pattern="2..1..2", seed=7)
    assert a.exact_bids == b.exact_bids
    assert a.scores == b.scores


def test_by_hand_size_totals_match():
    result = run_benchmark(games=15, players=3, pattern="1..4..1", seed=1)
    total_rounds = sum(rounds for _, rounds in result.by_hand_size.values())
    total_exact = sum(exact for exact, _ in result.by_hand_size.values())
    assert total_rounds == result.rounds
    assert total_exact == result.exact_bids


def test_compare_identical_strategies_is_roughly_even():
    # Same strategy on both sides: hit rates should be close (seat swap cancels bias).
    result = compare(AIPlayer, AIPlayer, games=200, pattern="5..1..5", seed=0)
    assert result.candidate_rounds == result.baseline_rounds
    assert abs(result.candidate_hit_rate - result.baseline_hit_rate) < 0.05


def test_compare_detects_a_weaker_strategy():
    class AlwaysZero(AIPlayer):
        """Deliberately bad: always bids zero, so it rarely hits in big hands."""

        def choose_bid(self, **kwargs):
            return 0

    result = compare(AlwaysZero, AIPlayer, games=300, pattern="6..1..6", seed=3)
    # The normal bot should clearly out-hit the always-zero bidder.
    assert result.baseline_hit_rate > result.candidate_hit_rate
