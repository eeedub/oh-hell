import pytest

from oh_hell.cards import Suit
from oh_hell.game import Game, deal_pattern, max_hand_size
from oh_hell.player import AIPlayer, Player


def test_deal_pattern_down_and_up():
    assert deal_pattern("3..1..3", 4) == [3, 2, 1, 2, 3]


def test_deal_pattern_single_run():
    assert deal_pattern("1..5", 7) == [1, 2, 3, 4, 5]


def test_deal_pattern_clamped_and_collapsed():
    # 7 players -> max 7 cards each; a request for 10 collapses to a 7 plateau.
    assert max_hand_size(7) == 7
    assert deal_pattern("10..8", 7) == [7]


def test_max_hand_size():
    assert max_hand_size(4) == 12
    assert max_hand_size(2) == 25


def test_full_game_runs_and_has_winner():
    players = [AIPlayer(n) for n in ("A", "B", "C", "D")]
    game = Game(players, pattern="3..1..3", seed=1)
    results = game.play()
    assert len(results) == 5
    assert game.winner in players
    # Total score equals the sum of every round's gains.
    for player in players:
        assert player.score == sum(r.round_scores[player.name] for r in results)


def test_each_round_distributes_exactly_hand_size_tricks():
    players = [AIPlayer(n) for n in ("A", "B", "C")]
    game = Game(players, pattern="1..5..1", seed=7)
    for result in game.play():
        assert sum(result.tricks.values()) == result.hand_size


def test_scoring_exact_bid_gets_bonus():
    class FixedBid(AIPlayer):
        """Always bids a preset number, then plays like the normal bot."""

        def __init__(self, name, bid):
            super().__init__(name)
            self._fixed = bid

        def choose_bid(self, **kwargs):
            return min(self._fixed, kwargs["hand_size"])

    players = [FixedBid("A", 1), FixedBid("B", 0), FixedBid("C", 0)]
    game = Game(players, pattern="1", hook=False, seed=3, exact_bonus=10)
    [result] = game.play()
    for player in players:
        made = result.tricks[player.name] == result.bids[player.name]
        expected = result.tricks[player.name] + (10 if made else 0)
        assert result.round_scores[player.name] == expected


def test_hook_forbids_dealer_balancing_bid():
    seen = {}

    class Recorder(AIPlayer):
        def choose_bid(self, **kwargs):
            seen[self.name] = kwargs["forbidden_bid"]
            return super().choose_bid(**kwargs)

    players = [Recorder(n) for n in ("A", "B", "C")]
    game = Game(players, pattern="2", hook=True, seed=5)
    game.play()
    # Round 1 dealer is player A (index 0); only the dealer sees a forbidden bid.
    assert seen["A"] is not None
    assert seen["B"] is None and seen["C"] is None


def test_rejects_bad_player_count():
    with pytest.raises(ValueError):
        Game([AIPlayer("solo")])


def test_base_player_interface_is_abstract():
    p = Player("x")
    with pytest.raises(NotImplementedError):
        p.choose_bid(trump=Suit.SPADES, hand_size=1, bids_so_far=[], is_dealer=False, forbidden_bid=None)
