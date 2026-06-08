import io

from oh_hell.cards import Card, Suit
from oh_hell.render import RESET, Renderer, should_color


def test_disabled_renderer_is_plain_text():
    r = Renderer(enabled=False)
    assert r.card(Card(14, Suit.HEARTS)) == "A♥"
    assert r.bold("hi") == "hi"
    assert "\033" not in r.cards([Card(2, Suit.CLUBS), Card(10, Suit.SPADES)])


def test_enabled_renderer_colors_red_suit():
    r = Renderer(enabled=True)
    out = r.card(Card(14, Suit.HEARTS))
    assert out.startswith("\033[31m") and out.endswith(RESET)
    assert "A♥" in out


def test_spades_have_no_color_code_even_when_enabled():
    # Spades use the terminal default, so no escape codes are added.
    r = Renderer(enabled=True)
    assert r.card(Card(13, Suit.SPADES)) == "K♠"


def test_should_color_modes():
    assert should_color("always") is True
    assert should_color("never") is False
    # A plain StringIO is not a TTY, so 'auto' must be False.
    assert should_color("auto", stream=io.StringIO()) is False


def test_should_color_respects_no_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert should_color("auto") is False
    # 'always' still wins over NO_COLOR (explicit user request).
    assert should_color("always") is True
