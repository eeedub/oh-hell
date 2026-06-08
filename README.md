# Oh Hell 🃏

A simulator for the classic trick-taking card game **Oh Hell** (also known as
Oh Pshaw, Blackout, Blob, or Bust). You can watch AI bots play complete games,
run thousands of games to gather statistics, or sit down and play against the
bots yourself in the terminal.

The rules follow the
[Official Game Rules for Oh Hell](https://officialgamerules.org/game-rules/oh-hell/).

Pure Python, no dependencies — just the standard library. `pytest` is only
needed if you want to run the tests.

## The game in one paragraph

Each round, every player is dealt a hand (the size changes from round to round).
One extra card is flipped to set the **trump** suit. Players then **bid** the
*exact* number of tricks they think they'll win. You play out the tricks
(follow the led suit if you can; the highest trump wins, otherwise the highest
card of the led suit). You score **1 point per trick taken, plus a 10-point
bonus if you took exactly as many tricks as you bid**. Highest total after the
final round wins.

## Quick start

No install required:

```bash
# Watch four bots play one game, with full play-by-play
python -m oh_hell simulate

# Play against three bots
python -m oh_hell play

# Play against the stronger Monte Carlo bots
python -m oh_hell play --bot mc

# Simulate 1000 games and see how often each seat wins
python -m oh_hell simulate --games 1000

# Measure how good the bot is (exact-bid hit rate)
python -m oh_hell bench
```

Or install it so the `oh-hell` command is available everywhere:

```bash
pip install -e .
oh-hell play
```

## Command reference

There are three subcommands: `simulate`, `play`, and `bench`. They share these options:

| Option | Default | Meaning |
| --- | --- | --- |
| `-p, --players N` | `4` | Number of players (2–7; 3–7 recommended) |
| `--pattern SPEC` | `1..max..1` | Cards-per-round pattern, e.g. `10..1..10` or `1..7` |
| `--no-hook` | off | Disable "the hook" (the dealer's bid restriction) |
| `--seed N` | random | Seed the RNG for reproducible games |
| `--bot {greedy,mc}` | `greedy` | Bot strategy (see [Bot strategies](#bot-strategies)) |
| `--mc-samples N` | `30` | Rollouts for the `mc` bot (higher = stronger, slower) |
| `--color {auto,always,never}` | `auto` | Colorize the play-by-play (`auto` = only on a terminal) |

```bash
# A short 3-player game that climbs 1→5 and back to 1, no hook rule
python -m oh_hell simulate -p 3 --pattern "1..5..1" --no-hook

# Reproduce an exact game
python -m oh_hell simulate --seed 42
```

### Output & color

The `simulate` (single game) and `play` commands print a colorized play-by-play:
each round starts with a full-width ruled header, cards are colored by suit (♥ red, ♦ blue,
♣ green, ♠ default), the trick winner and made bids are highlighted, and the
final standings use 🥇🥈🥉 / 🏆. Color
turns on automatically only when writing to a terminal, so piped or redirected
output stays plain (it also respects the `NO_COLOR` convention). Force it with
`--color always` or disable it with `--color never`.

### Deal patterns

A pattern is a list of waypoints joined by `..`. The game counts from one
waypoint to the next:

- `10..1..10` → 10, 9, 8, …, 1, 2, …, 10
- `1..7` → 1, 2, 3, 4, 5, 6, 7

Hand sizes are automatically clamped to what a 52-card deck allows for the
player count (one card is always reserved to flip for trump).

## Bot strategies

There are two bots, chosen with `--bot`:

- **`greedy`** (default) — a fast heuristic. It estimates its bid by adding up
  each card's chance of winning, and plays simply: win tricks cheaply while it
  still needs them, and once its bid is made, "duck high" by shedding its most
  dangerous card on tricks it doesn't want.

- **`mc`** — a stronger [determinized Monte Carlo](https://en.wikipedia.org/wiki/Monte_Carlo_tree_search)
  player. For each card it could play, it deals the unseen cards to the
  opponents at random many times, plays each imagined hand out to the end with
  the greedy policy, and picks the card with the best *average* result. The same
  sampled deals are reused for every candidate card (Common Random Numbers),
  which makes the comparison fair and keeps the needed sample count low. It bids
  with the same heuristic but plays much better — at the cost of being far
  slower. Tune the trade-off with `--mc-samples`.

In head-to-head benchmarking the Monte Carlo bot beats the greedy bot by roughly
**6–7 points of exact-bid hit rate**. It's slow, so benchmark it over fewer
games:

```bash
python -m oh_hell bench --bot mc --mc-samples 40 --games 100
```

## Measuring the bot (benchmarking)

How do you know whether a change to the bot actually made it *better*? You
measure it. The `bench` command plays many games and reports the **exact-bid
hit rate** — the fraction of rounds where a player took exactly as many tricks
as they bid. That's where the big +10 bonus comes from, and unlike the win rate
it doesn't depend on the opponents, so it cleanly reflects skill.

```bash
python -m oh_hell bench --games 1000
```

```
Exact-bid hit rate :  48.5%  (...)
Average final score:  147.6
Hit rate by hand size:
   1 card(s):  68.2%  ##############
  ...
  12 card(s):  45.1%  #########
```

The per-hand-size breakdown is the useful part: the bot bids most accurately in
small hands and less so in large ones, where *card play* decides whether you
hit your bid. The harness is what made it safe to improve that play — see
below.

To A/B-test a new strategy against the current one, use `compare` from Python.
It seats equal numbers of each bot at shared tables (swapping seats to cancel
positional bias) and reports both hit rates:

```python
from oh_hell.benchmark import compare
from oh_hell.player import AIPlayer

class MyBot(AIPlayer):
    ...  # override choose_bid / choose_card

result = compare(MyBot, AIPlayer, games=2000)
print(result.candidate_hit_rate, "vs", result.baseline_hit_rate)
```

Two lessons this harness taught the project, both by measurement:

> An intuitive bidding "improvement" (reacting to the running bid total) turned
> out to make the bot slightly *worse*, so it was dropped.

> A card-play change — once you've made your bid, "duck high" by shedding your
> most dangerous card on tricks you don't want, instead of always your lowest —
> raised the head-to-head hit rate by about **4 points** and was kept. (A first
> version of it actually *lost* points by throwing away cards the bot still
> needed; the benchmark caught that before it shipped.)

> Several further card-play heuristics (smarter leading, position-aware
> following) were measured and **dropped** because they didn't help. The next
> real gain came from a different *kind* of player — the Monte Carlo bot — which
> beat the greedy bot by about **6–7 points** of hit rate.

Always benchmark the change instead of trusting the intuition.

## The hook rule

"The hook" (on by default) forbids the **dealer** from making a bid that would
cause the total of all bids to equal the number of tricks in the round. This
guarantees at least one player misses their bid each round. Turn it off with
`--no-hook`.

## Project layout

```
oh_hell/
  cards.py    # Card, Suit, Deck
  rules.py    # pure rule helpers (legal plays, trick winner)
  player.py     # Player base, greedy AIPlayer bot, HumanPlayer, shared policy
  montecarlo.py # MonteCarloPlayer: stronger bot via determinized rollouts
  game.py       # the game engine: dealing, bidding, tricks, scoring
  benchmark.py  # measure/compare bot strategies (exact-bid hit rate)
  render.py     # terminal color / styling for the play-by-play
  cli.py        # command-line interface
tests/          # pytest suite
```

The engine is usable as a library too:

```python
from oh_hell import Game, AIPlayer

game = Game([AIPlayer(n) for n in "ABCD"], pattern="5..1..5", seed=1)
game.play()
print(game.winner.name, game.winner.score)
```

## Running the tests

```bash
pip install pytest
pytest
```

## License

[MIT](LICENSE)
