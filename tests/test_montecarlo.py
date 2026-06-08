import random

from oh_hell.cards import Card, Suit
from oh_hell.game import Game
from oh_hell.montecarlo import MonteCarloPlayer
from oh_hell.player import AIPlayer


def test_single_legal_card_is_forced():
    p = MonteCarloPlayer("mc", samples=5)
    p.hand = [Card(7, Suit.CLUBS)]
    p.bid, p.tricks_won = 0, 0
    card = p.choose_card(
        legal=list(p.hand), trick=[], trump=Suit.SPADES, lead_suit=None, seen=[]
    )
    assert card == Card(7, Suit.CLUBS)


def test_choose_card_returns_a_legal_card():
    # Build a 3-player table with the MC player to seat 0.
    mc = MonteCarloPlayer("mc", samples=20, rng=random.Random(1))
    opps = [AIPlayer("a"), AIPlayer("b")]
    players = [mc, *opps]
    mc.hand = [Card(14, Suit.HEARTS), Card(2, Suit.CLUBS), Card(9, Suit.SPADES)]
    for o in opps:
        o.hand = [Card(5, Suit.DIAMONDS), Card(6, Suit.DIAMONDS), Card(7, Suit.DIAMONDS)]
    for pl in players:
        pl.bid, pl.tricks_won = 1, 0

    chosen = mc.choose_card(
        legal=list(mc.hand), trick=[], trump=Suit.SPADES, lead_suit=None,
        seen=[], players=players, leader=0,
    )
    assert chosen in mc.hand


def test_play_is_reproducible_with_seeded_rng():
    def decide():
        mc = MonteCarloPlayer("mc", samples=30, rng=random.Random(42))
        opps = [AIPlayer("a"), AIPlayer("b")]
        players = [mc, *opps]
        mc.hand = [Card(14, Suit.HEARTS), Card(3, Suit.HEARTS), Card(9, Suit.SPADES)]
        for o in opps:
            o.hand = [Card(5, Suit.CLUBS), Card(6, Suit.CLUBS), Card(7, Suit.CLUBS)]
        for pl in players:
            pl.bid, pl.tricks_won = 1, 0
        return mc.choose_card(
            legal=list(mc.hand), trick=[], trump=Suit.SPADES, lead_suit=None,
            seen=[], players=players, leader=0,
        )

    assert decide() == decide()


def test_full_game_with_mc_players_is_valid():
    # An end-to-end game must still satisfy the basic invariants.
    players = [MonteCarloPlayer(f"P{i}", samples=8, rng=random.Random(i)) for i in range(4)]
    game = Game(players, pattern="3..1..3", seed=0)
    for result in game.play():
        assert sum(result.tricks.values()) == result.hand_size
    assert game.winner in players
