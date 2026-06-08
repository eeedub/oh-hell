import io

from oh_hell.cards import Card, Suit
from oh_hell.render import RESET, Renderer, should_color, visible_len


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


def test_visible_len_ignores_color_codes():
    r = Renderer(enabled=True)
    assert visible_len(r.card(Card(14, Suit.HEARTS))) == 2  # "A♥"
    assert visible_len(r.bold("hello")) == 5


def test_box_borders_match_content_width():
    r = Renderer(enabled=False)
    top, middle, bottom = r.box("Round 1").splitlines()
    # Box is sized to the content plus one space of padding on each side.
    assert top == "┌─────────┐"
    assert middle == "│ Round 1 │"
    assert bottom == "└─────────┘"


def test_box_width_correct_even_with_color():
    r = Renderer(enabled=True)
    top, middle, bottom = r.box(r.bold("Round 1")).splitlines()
    # Borders are measured by visible width, so top and bottom still match.
    assert visible_len(top) == visible_len(bottom) == visible_len(middle)


def test_should_color_respects_no_color_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert should_color("auto") is False
    # 'always' still wins over NO_COLOR (explicit user request).
    assert should_color("always") is True
