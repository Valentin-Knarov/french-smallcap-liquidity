"""Étude complète : indicateurs, liquidité de sortie et score pour tout l'univers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from smallcap_liquidity import exit as ex
from smallcap_liquidity import metrics
from smallcap_liquidity.universe import name, segment

MIN_HISTORY = 250

# Indicateurs entrant dans le score, et sens : +1 si « plus haut = plus liquide ».
SCORE_COMPONENTS = {
    "ADV 60 j (€)": +1,
    "Amihud (bps / M€)": -1,
    "Spread estimé (bps)": -1,
    "Séances sans volume": -1,
    "Jours de sortie — Stress historique": -1,
}


def classify(score: float) -> str:
    """Classe de liquidité à partir du score (0–100)."""
    if score >= 75:
        return "A — très liquide"
    if score >= 50:
        return "B — liquide"
    if score >= 25:
        return "C — peu liquide"
    return "D — illiquide"


def analyze_stock(df: pd.DataFrame, position_eur: float, participation: float, y: float) -> dict:
    normal = ex.normal_scenario(df)
    scenarios = [normal, ex.historical_stress(df), ex.shock_scenario(normal)]
    row = {
        "Dernier cours (€)": float(df["close"].iloc[-1]),
        "ADV 60 j (€)": metrics.adv_eur(df, 60),
        "Médiane 60 j (€)": normal.volume_eur,
        "Volatilité annualisée": normal.daily_vol * np.sqrt(metrics.TRADING_DAYS),
        "Spread estimé (bps)": normal.spread * 1e4,
        "Amihud (bps / M€)": metrics.amihud(df, 250),
        "Séances sans volume": metrics.zero_volume_share(df, 250),
    }
    for sc in scenarios:
        m = ex.exit_metrics(sc, position_eur, participation, y)
        for k, v in m.items():
            row[f"{k} — {sc.name}"] = v
        row[f"Volume réf. (€) — {sc.name}"] = sc.volume_eur
        row[f"Spread (bps) — {sc.name}"] = sc.spread * 1e4
        row[f"Volatilité j — {sc.name}"] = sc.daily_vol
    # Décision prudente : on retient le pire des trois scénarios
    row["Jours de sortie — Pire scénario"] = max(row[f"Jours de sortie — {sc.name}"] for sc in scenarios)
    row["Coût de sortie (bps) — Pire scénario"] = max(row[f"Coût de sortie (bps) — {sc.name}"] for sc in scenarios)
    return row


def liquidity_score(table: pd.DataFrame) -> pd.Series:
    """Score 0–100 : moyenne des rangs centiles des indicateurs (100 = le plus liquide de l'univers).

    Les rangs rendent le score insensible aux unités et aux valeurs extrêmes. Le score est
    relatif : il classe les titres entre eux, il ne dit pas qu'un titre est liquide dans l'absolu.
    """
    ranks = []
    for col, direction in SCORE_COMPONENTS.items():
        r = table[col].rank(pct=True, ascending=direction > 0)
        ranks.append(r)
    return (pd.concat(ranks, axis=1).mean(axis=1) * 100).round(1)


def run_study(
    data: dict[str, pd.DataFrame], position_eur: float = 5e6, participation: float = 0.20, y: float = 0.7
) -> pd.DataFrame:
    """Tableau de synthèse : une ligne par titre, trié du plus liquide au moins liquide.

    position_eur : taille de la position à liquider (€), identique pour tous les titres
    participation : taux de participation au volume p
    y : constante d'impact Y
    """
    rows = {}
    for ticker, df in data.items():
        if len(df) < MIN_HISTORY:
            continue
        rows[ticker] = {"Nom": name(ticker), "Segment": segment(ticker),
                        **analyze_stock(df, position_eur, participation, y)}
    if not rows:
        raise ValueError(f"Aucun titre avec au moins {MIN_HISTORY} séances d'historique.")
    table = pd.DataFrame.from_dict(rows, orient="index")
    table.index.name = "Ticker"
    table["Score de liquidité"] = liquidity_score(table)
    table["Classe"] = table["Score de liquidité"].map(classify)
    return table.sort_values("Score de liquidité", ascending=False)
