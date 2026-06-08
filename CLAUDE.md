# CLAUDE.md

Guidance for Claude Code when working in this repo: the **Oh Hell** card-game
simulator.

## What this is

A pure-Python (standard library only) simulator for the trick-taking game Oh
Hell. Rules: https://officialgamerules.org/game-rules/oh-hell/ — 52-card deck,
variable deal patterns, trump from the flipped card, optional dealer "hook", and
exact-bid scoring (1 point per trick + 10 bonus for hitting your bid exactly).

## Commands

```bash
# One-time setup
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

.venv/bin/python -m pytest                       # run the tests
.venv/bin/python -m oh_hell simulate --seed 7    # watch a game
.venv/bin/python -m oh_hell play [--bot mc]      # play against the bots
.venv/bin/python -m oh_hell bench [--bot mc]     # measure a bot's quality
```

No third-party runtime dependencies; `pytest` (dev only) is the sole extra.

## Architecture

- `cards.py` — `Card`, `Suit`, `Deck`.
- `rules.py` — pure rule helpers (legal plays, trick winner); no state.
- `player.py` — `Player` base; greedy `AIPlayer`; `HumanPlayer`; the shared pure
  policy `greedy_play()` and `card_value()`.
- `montecarlo.py` — `MonteCarloPlayer`: determinized rollouts; reuses
  `greedy_play` as its rollout policy.
- `game.py` — the engine: dealing, bidding (+ hook), trick play, scoring; owns a `Renderer`.
- `render.py` — terminal color & layout (`Renderer`, `should_color`, `rule`).
- `benchmark.py` — `run_benchmark()` and `compare()` for measuring bots.
- `cli.py` — the `simulate` / `play` / `bench` commands.

## Conventions (important)

- **Measure bot changes; never trust intuition.** Any change to bidding or card
  play must be A/B-tested with `benchmark.compare()` (metric: exact-bid hit
  rate). Keep it only if the number improves; otherwise revert. Several
  plausible heuristics have been dropped exactly this way.
- **Prove behavior-preserving refactors.** When refactoring the greedy policy,
  confirm the baseline benchmark is unchanged (e.g. `bench --games 500 --seed 0`
  stays byte-identical).
- **Card play lives in `greedy_play()`.** `AIPlayer` and the Monte Carlo rollouts
  share it — change it in one place.
- `choose_card` receives `seen` (cards played this round) and `players`/`leader`
  as *public* game state for smarter strategies; the greedy bot ignores them. A
  strategy must NOT read opponents' hand **contents** — only counts, bids, and
  tricks-won are public.
- Color must auto-disable when not on a TTY and respect `NO_COLOR`. Never put
  ANSI codes in `Card.__str__` or anything tests parse. Keep emoji out of
  aligned card rows (they're double-width and break alignment).
- Tests are fast and deterministic (seeded RNG). Keep them that way; tests that
  instantiate `MonteCarloPlayer` use small `samples`.

## Gotchas

- Each round leaves ≥1 undealt card to flip for trump, so
  `max_hand_size = (52 - 1) // players`.
- `MonteCarloPlayer` is slow (pure Python); benchmark it with fewer games.
