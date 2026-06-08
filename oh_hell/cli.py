"""Command-line interface for the Oh Hell simulator.

Three subcommands::

    oh-hell simulate   # bots play a full game (or many, for statistics)
    oh-hell play       # you play against the bots in the terminal
    oh-hell bench      # measure bot quality (exact-bid hit rate)

Use ``--bot mc`` for the stronger Monte Carlo bots. Run
``python -m oh_hell --help`` for all options.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from .benchmark import run_benchmark
from .game import Game, max_hand_size
from .montecarlo import MonteCarloPlayer
from .player import AIPlayer, HumanPlayer
from .render import Renderer, should_color


def _bot_names(n: int) -> list[str]:
    pool = ["Ada", "Babbage", "Curie", "Dijkstra", "Euler", "Fermat", "Gauss"]
    return pool[:n]


def make_bot(args: argparse.Namespace, name: str) -> AIPlayer:
    """Build a bot of the type selected on the command line."""
    if getattr(args, "bot", "greedy") == "mc":
        return MonteCarloPlayer(name, samples=args.mc_samples)
    return AIPlayer(name)


def make_renderer(args: argparse.Namespace) -> Renderer:
    return Renderer(enabled=should_color(getattr(args, "color", "auto")))


def cmd_simulate(args: argparse.Namespace) -> int:
    if args.games == 1:
        renderer = make_renderer(args)
        players = [make_bot(args, name) for name in _bot_names(args.players)]
        game = Game(
            players,
            pattern=args.pattern,
            hook=not args.no_hook,
            seed=args.seed,
            verbose=True,
            renderer=renderer,
        )
        print(renderer.bold("🃏 Oh Hell"))
        game.play()
        return 0

    # Many games: stay quiet and report how often each seat wins.
    wins: Counter[str] = Counter()
    for i in range(args.games):
        players = [make_bot(args, name) for name in _bot_names(args.players)]
        seed = None if args.seed is None else args.seed + i
        game = Game(players, pattern=args.pattern, hook=not args.no_hook, seed=seed)
        game.play()
        wins[game.winner.name] += 1

    print(f"Results over {args.games} games ({args.players} players):")
    for name in _bot_names(args.players):
        pct = 100 * wins[name] / args.games
        print(f"  {name:10s} {wins[name]:5d} wins  ({pct:4.1f}%)")
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    name = args.name or "You"
    renderer = make_renderer(args)
    players = [HumanPlayer(name, renderer=renderer)]
    players += [make_bot(args, n) for n in _bot_names(args.players)[: args.players - 1]]

    game = Game(
        players,
        pattern=args.pattern,
        hook=not args.no_hook,
        seed=args.seed,
        verbose=True,
        renderer=renderer,
    )
    print(renderer.bold("🃏 Welcome to Oh Hell!") + " You're playing against the bots.")
    game.play()
    print(f"\nThanks for playing, {name}.")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    # A fixed seed by default keeps the benchmark reproducible run-to-run.
    seed = 0 if args.seed is None else args.seed
    result = run_benchmark(
        strategy=lambda name: make_bot(args, name),
        games=args.games,
        players=args.players,
        pattern=args.pattern,
        hook=not args.no_hook,
        seed=seed,
    )
    pattern = args.pattern or "1..max..1 (default)"
    print(
        f"Benchmark: {args.games} games, {args.players} players, "
        f"pattern {pattern}, hook {'off' if args.no_hook else 'on'}, seed {seed}"
    )
    print(
        f"  Exact-bid hit rate : {100 * result.hit_rate:5.1f}%  "
        f"({result.exact_bids}/{result.rounds} rounds)"
    )
    print(f"  Average final score: {result.avg_score:6.1f}")
    print("  Hit rate by hand size:")
    for size, (exact, rounds) in result.by_hand_size.items():
        bar = "#" * round(20 * exact / rounds) if rounds else ""
        print(f"    {size:2d} card(s): {100 * exact / rounds:5.1f}%  {bar}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oh-hell",
        description="A simulator for the trick-taking card game Oh Hell.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("-p", "--players", type=int, default=4, help="number of players (2-7)")
        p.add_argument(
            "--pattern",
            default=None,
            help="deal pattern, e.g. '10..1..10' or '1..7' (default: 1..max..1)",
        )
        p.add_argument("--no-hook", action="store_true", help="disable the dealer 'hook' rule")
        p.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible games")
        p.add_argument(
            "--bot",
            choices=["greedy", "mc"],
            default="greedy",
            help="bot type: 'greedy' heuristic (fast) or 'mc' Monte Carlo (stronger, slower)",
        )
        p.add_argument(
            "--mc-samples", type=int, default=60, help="rollouts per card for the Monte Carlo bot"
        )
        p.add_argument(
            "--color",
            choices=["auto", "always", "never"],
            default="auto",
            help="colorize output (auto: only when writing to a terminal)",
        )

    sim = sub.add_parser("simulate", help="watch bots play")
    add_common(sim)
    sim.add_argument("-n", "--games", type=int, default=1, help="number of games to simulate")
    sim.set_defaults(func=cmd_simulate)

    play = sub.add_parser("play", help="play against the bots")
    add_common(play)
    play.add_argument("--name", default=None, help="your display name")
    play.set_defaults(func=cmd_play)

    bench = sub.add_parser("bench", help="measure bot quality (exact-bid hit rate)")
    add_common(bench)
    bench.add_argument("-n", "--games", type=int, default=1000, help="number of games to run")
    bench.set_defaults(func=cmd_bench)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not 2 <= args.players <= 7:
        parser.error("players must be between 2 and 7")
    if max_hand_size(args.players) < 1:
        parser.error("too many players for a 52-card deck")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
