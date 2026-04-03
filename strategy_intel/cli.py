import argparse
import sys

from .models import EdgeComponent, ScoreCard
from .scorer import score_component
from .storage import load_components, save_component


FIELDS = [
    ("name",         "Name"),
    ("category",     "Category (e.g. momentum, volatility, mean_reversion)"),
    ("trigger",      "Trigger"),
    ("confirmation", "Confirmation"),
    ("regime",       "Regime (e.g. trend, range, macro_event)"),
    ("edge_source",  "Edge source (e.g. behavioral, structural, mechanical)"),
    ("execution",    "Execution (e.g. shares, options, spreads)"),
    ("invalidation", "Invalidation"),
    ("notes",        "Notes"),
]

SCORE_FIELDS = [
    ("persistence",    "Persistence    (1–5)"),
    ("crowding",       "Crowding       (1–5, lower = better)"),
    ("clarity",        "Clarity        (1–5)"),
    ("regime_fit",     "Regime fit     (1–5)"),
    ("exploitability", "Exploitability (1–5)"),
]


def _prompt(label: str) -> str:
    value = input(f"  {label}: ").strip()
    if not value:
        print(f"  [error] '{label}' cannot be empty.")
        sys.exit(1)
    return value


def _prompt_int(label: str) -> int:
    raw = _prompt(label)
    try:
        val = int(raw)
        if not (1 <= val <= 5):
            raise ValueError
        return val
    except ValueError:
        print(f"  [error] '{label}' must be an integer between 1 and 5.")
        sys.exit(1)


def cmd_add(_args) -> None:
    print("\n-- New Edge Component --\n")
    values = {key: _prompt(label) for key, label in FIELDS}

    print("\n-- Score --\n")
    score_values = {key: _prompt_int(label) for key, label in SCORE_FIELDS}

    score = ScoreCard(**score_values)
    component = EdgeComponent(**values, score=score)
    score_component(component)

    save_component(component)
    print(f"\n  Saved '{component.name}' — total score: {component.score.total_score}")


def cmd_list(_args) -> None:
    components = load_components()
    if not components:
        print("No components stored.")
        return

    scored = sorted(
        components,
        key=lambda c: c.score.total_score if c.score else 0,
        reverse=True,
    )

    print(f"\n{'#':<4} {'Score':<7} {'Category':<20} {'Name'}")
    print("-" * 60)
    for i, c in enumerate(scored, 1):
        score = f"{c.score.total_score:.2f}" if c.score else "—"
        print(f"{i:<4} {score:<7} {c.category:<20} {c.name}")
    print()


def cmd_query(args) -> None:
    term = args.term.lower()
    components = load_components()

    matches = [
        c for c in components
        if term in c.name.lower()
        or term in c.category.lower()
        or term in c.notes.lower()
    ]

    if not matches:
        print(f"No components matching '{args.term}'.")
        return

    matches.sort(key=lambda c: c.score.total_score if c.score else 0, reverse=True)

    for c in matches:
        score = f"{c.score.total_score:.2f}" if c.score else "—"
        print(f"\n[{score}] {c.name}  ({c.category})")
        print(f"  Trigger:      {c.trigger}")
        print(f"  Confirmation: {c.confirmation}")
        print(f"  Regime:       {c.regime}")
        print(f"  Edge source:  {c.edge_source}")
        print(f"  Execution:    {c.execution}")
        print(f"  Invalidation: {c.invalidation}")
        print(f"  Notes:        {c.notes}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(prog="strategy_intel")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("add", help="Add a new edge component")
    sub.add_parser("list", help="List all components sorted by score")

    q = sub.add_parser("query", help="Query components by keyword")
    q.add_argument("term", help="Search term")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "query":
        cmd_query(args)
    else:
        parser.print_help()
