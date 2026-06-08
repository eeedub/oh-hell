"""Terminal rendering helpers: colored cards and small text styles.

Color is applied with ANSI escape codes and can be turned off entirely (for
piped output, ``NO_COLOR``, or ``--color never``). Cards use a four-color scheme
so every suit is distinguishable at a glance:

    ♠ spades   — default text color
    ♥ hearts   — red
    ♦ diamonds — bright blue
    ♣ clubs    — green

Emoji are used only as accents (medals, trophy), never inside aligned card rows,
because they are double-width and would break column alignment.
"""

from __future__ import annotations

import os
import re
import sys

from .cards import Card, Suit

RESET = "\033[0m"

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _sgr(*codes: int) -> str:
    return "".join(f"\033[{c}m" for c in codes)


def visible_len(text: str) -> int:
    """Length of ``text`` as displayed, ignoring ANSI color escape codes."""
    return len(_ANSI_RE.sub("", text))


# Foreground color per suit (empty string = leave at the terminal default).
SUIT_COLOR = {
    Suit.SPADES: "",
    Suit.HEARTS: _sgr(31),    # red
    Suit.DIAMONDS: _sgr(94),  # bright blue
    Suit.CLUBS: _sgr(32),     # green
}


def should_color(mode: str = "auto", stream=None) -> bool:
    """Decide whether to emit color for ``mode`` ('auto' | 'always' | 'never')."""
    if mode == "always":
        return True
    if mode == "never":
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    stream = stream if stream is not None else sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


class Renderer:
    """Wraps text in ANSI styles when ``enabled``; otherwise returns it plain."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def _style(self, text: str, *codes: str) -> str:
        codes = tuple(c for c in codes if c)
        if not self.enabled or not codes:
            return text
        return "".join(codes) + text + RESET

    # --- cards & suits ---------------------------------------------------
    def card(self, c: Card) -> str:
        return self._style(str(c), SUIT_COLOR.get(c.suit, ""))

    def cards(self, cards, sep: str = " ") -> str:
        return sep.join(self.card(c) for c in cards)

    def suit(self, s: Suit) -> str:
        return self._style(s.value, SUIT_COLOR.get(s, ""))

    # --- text styles -----------------------------------------------------
    def bold(self, text: str) -> str:
        return self._style(text, _sgr(1))

    def dim(self, text: str) -> str:
        return self._style(text, _sgr(2))

    def good(self, text: str) -> str:
        return self._style(text, _sgr(32))

    def bad(self, text: str) -> str:
        return self._style(text, _sgr(31))

    def accent(self, text: str) -> str:
        return self._style(text, _sgr(36))

    # --- layout ----------------------------------------------------------
    def box(self, text: str, pad: int = 1) -> str:
        """Draw a single-line box around ``text``.

        The width is computed from the *visible* length, so the border lines up
        even when ``text`` contains color codes. The border is dimmed so the
        content inside stands out.
        """
        inner = pad + visible_len(text) + pad
        gap = " " * pad
        top = self.dim("┌" + "─" * inner + "┐")
        bottom = self.dim("└" + "─" * inner + "┘")
        bar = self.dim("│")
        middle = f"{bar}{gap}{text}{gap}{bar}"
        return f"{top}\n{middle}\n{bottom}"
