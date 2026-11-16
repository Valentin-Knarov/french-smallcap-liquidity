"""Ligne de commande : python -m smallcap_liquidity [--demo] [--position 5000000] [--participation 0.2]"""

from __future__ import annotations

import argparse
from pathlib import Path

from smallcap_liquidity.data import load_yahoo, simulate_universe
from smallcap_liquidity.report import write_excel, write_html
from smallcap_liquidity.study import run_study
from smallcap_liquidity.universe import DEMO_UNIVERSE, UNIVERSE


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Étude de liquidité des small & mid caps françaises")
    ap.add_argument("--demo", action="store_true", help="données simulées (sans connexion internet)")
    ap.add_argument("--position", type=float, default=5e6, help="taille de la position à liquider, en € (défaut 5 M€)")
    ap.add_argument("--participation", type=float, default=0.20, help="taux de participation au volume (défaut 20 %%)")
    ap.add_argument("--impact", type=float, default=0.7, help="constante d'impact Y (défaut 0,7)")
    ap.add_argument("--tickers", nargs="*", help="tickers Yahoo à étudier (défaut : univers intégré)")
    ap.add_argument("--out", type=Path, default=Path("output"), help="dossier de sortie")
    args = ap.parse_args(argv)

    tickers = args.tickers or list(DEMO_UNIVERSE if args.demo else UNIVERSE)
    print(f"Chargement de {len(tickers)} titres ({'démo' if args.demo else 'Yahoo Finance, 5 ans'})…")
    data = simulate_universe(tickers) if args.demo else load_yahoo(tickers)
    missing = sorted(set(tickers) - set(data))
    if missing:
        print(f"Sans données : {', '.join(missing)}")

    table = run_study(data, args.position, args.participation, args.impact)
    params = {
        "Source": "Démo (données simulées)" if args.demo else "Yahoo Finance",
        "Position (€)": args.position,
        "Participation p": args.participation,
        "Constante d'impact Y": args.impact,
        "Titres étudiés": len(table),
    }
    xlsx = write_excel(table, params, args.out / "etude_liquidite.xlsx")
    html = write_html(table, params, args.out / "etude_liquidite.html")
    print(table[["Nom", "Classe", "Score de liquidité", "Jours de sortie — Stress historique"]].round(1).to_string())
    print(f"\nRapports : {xlsx}  ·  {html}")


if __name__ == "__main__":
    main()
