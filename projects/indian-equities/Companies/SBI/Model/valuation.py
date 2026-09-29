"""Reproduce SBI's personal-research equity valuation; Python standard library only."""

from __future__ import annotations

import json
from pathlib import Path


def value(book_per_share: float, near_roe: float, payout: float,
          terminal_roe: float, terminal_growth: float, cost_equity: float,
          years: int = 5) -> dict[str, float]:
    if not (0 < terminal_growth < min(cost_equity, terminal_roe) < 1):
        raise ValueError("Require 0 < terminal growth < cost of equity and terminal ROE < 1")
    if not (0 < near_roe < 1 and 0 < terminal_roe < 1 and 0 <= payout <= 1):
        raise ValueError("ROE and payout assumptions out of range")

    book = book_per_share
    dividend_pv = 0.0
    for year in range(1, years + 1):
        earnings = book * near_roe
        dividend = earnings * payout
        dividend_pv += dividend / (1 + cost_equity) ** year
        book += earnings - dividend

    # Terminal distribution is consistent with long-run book growth:
    # earnings on end-year-5 book less the capital retained to grow it at g.
    terminal_dividend = book * (terminal_roe - terminal_growth)
    terminal_value = terminal_dividend / (cost_equity - terminal_growth)
    terminal_pv = terminal_value / (1 + cost_equity) ** years
    return {
        "book_year_5": book,
        "dividends_pv": dividend_pv,
        "terminal_pv": terminal_pv,
        "fair_value": dividend_pv + terminal_pv,
    }


def main() -> None:
    assumptions = json.loads(Path(__file__).with_name("assumptions.json").read_text())
    book = assumptions["standalone_equity_crore"] / assumptions["shares_crore"]
    price = assumptions["close_inr"]
    near_roe = assumptions["five_year_roe"]
    payout = assumptions["five_year_payout"]
    growth = assumptions["terminal_book_growth"]
    rows = []
    expected = 0.0
    for r in assumptions["terminal_roe_debate"]:
        row = []
        for k in assumptions["cost_equity_debate"]:
            result = value(book, near_roe, payout, r["value"], growth, k["value"])
            probability = r["probability"] * k["probability"]
            expected += probability * result["fair_value"]
            row.append(round(result["fair_value"], 2))
        rows.append(row)

    assert abs(sum(x["probability"] for x in assumptions["terminal_roe_debate"]) - 1) < 1e-9
    assert abs(sum(x["probability"] for x in assumptions["cost_equity_debate"]) - 1) < 1e-9
    assert book > 0 and price > 0
    assert min(map(min, rows)) <= expected <= max(map(max, rows))
    print(f"Standalone reported equity/share: ₹{book:.2f}")
    columns = ", ".join(f"{x['value']:.0%}" for x in assumptions["cost_equity_debate"])
    print(f"Grid columns: cost of equity {columns}")
    for scenario, row in zip(assumptions["terminal_roe_debate"], rows):
        print(f"Terminal ROE {scenario['value']:.0%}: " + " | ".join(f"₹{x:.2f}" for x in row))
    likely_roe = max(assumptions["terminal_roe_debate"], key=lambda x: x["probability"])
    likely_cost = max(assumptions["cost_equity_debate"], key=lambda x: x["probability"])
    likely = value(book, near_roe, payout, likely_roe["value"], growth, likely_cost["value"])["fair_value"]
    print(f"Most-likely cell: ₹{likely:.2f}")
    print(f"Probability-weighted fair value: ₹{expected:.2f}")
    print(f"Price: ₹{price:.2f}; expected value gap: {(expected / price - 1) * 100:.2f}%")


if __name__ == "__main__":
    main()
