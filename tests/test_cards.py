import random

import pytest

from oh_hell.cards import Card, Deck, Suit, rank_name
from oh_hell.rules import legal_plays, trick_winner_index


def test_card_str_and_validation():
    assert str(Card(14, Suit.SPADES)) == "A♠"
    assert str(Card(10, Suit.HEARTS)) == "10♥"
    assert rank_name(11) == "J"
    with pytest.raises(ValueError):
        Card(1, Suit.CLUBS)


def test_deck_has_52_unique_cards():
    deck = Deck()
    assert len(deck) == 52
    assert len(set(deck.cards)) == 52


def test_deal_removes_cards():
    deck = Deck(random.Random(0))
    hand = deck.deal(5)
    assert len(hand) == 5
    assert len(deck) == 47


def test_shuffle_is_deterministic_with_seed():
    a = Deck(random.Random(42))
    b = Deck(random.Random(42))
    a.shuffle()
    b.shuffle()
    assert a.cards == b.cards


def test_legal_plays_must_follow_suit():
    hand = [Card(5, Suit.HEARTS), Card(9, Suit.HEARTS), Card(2, Suit.CLUBS)]
    legal = legal_plays(hand, Suit.HEARTS)
    assert set(legal) == {Card(5, Suit.HEARTS), Card(9, Suit.HEARTS)}


def test_legal_plays_when_void_allows_anything():
    hand = [Card(5, Suit.HEARTS), Card(2, Suit.CLUBS)]
    assert set(legal_plays(hand, Suit.SPADES)) == set(hand)


def test_trick_winner_trump_beats_lead():
    # Hearts led, spades is trump: the low trump wins.
    trick = [Card(14, Suit.HEARTS), Card(2, Suit.SPADES), Card(13, Suit.HEARTS)]
    assert trick_winner_index(trick, Suit.SPADES) == 1


def test_trick_winner_highest_lead_when_no_trump():
    trick = [Card(7, Suit.DIAMONDS), Card(10, Suit.DIAMONDS), Card(14, Suit.CLUBS)]
    assert trick_winner_index(trick, Suit.SPADES) == 1
