"""Liquidité de sortie : combien de temps et combien coûte la vente d'une position, en temps normal et en stress.

Notations :
    X : taille de la position à vendre (€)
    V : volume journalier de référence du scénario (€)
    p : taux de participation au volume (part du marché que l'on s'autorise, 20 % par défaut)
    σ : volatilité journalière du scénario
    s : spread relatif du scénario
    Y : constante d'impact (0,7 par défaut)
    d : nombre de séances

Formules :
    jours de sortie       D = X / (p · V)
    part liquidable en d  min(1, p · V · d / X)
    coût de sortie        s/2 + Y · σ · √p      (demi-spread + impact en racine carrée)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from smallcap_liquidity import metrics

HORIZONS = (1, 5, 20)  # 1 jour, 1 semaine, 1 mois de bourse


@dataclass(frozen=True)
class Scenario:
    name: str
    volume_eur: float  # V
    daily_vol: float  # σ
    spread: float  # s


def normal_scenario(df: pd.DataFrame) -> Scenario:
    """Conditions récentes : montant médian échangé sur 60 séances, σ sur 60 séances, spread sur 6 mois."""
    return Scenario(
        "Normal",
        metrics.median_turnover_eur(df, 60),
        metrics.daily_volatility(df, 60),
        metrics.corwin_schultz(df, 120),
    )


def historical_stress(df: pd.DataFrame) -> Scenario:
    """Stress historique propre au titre, mesuré sur tout l'historique disponible.

    Volume : 10e centile du montant médian glissant sur 20 séances (les 10 % de périodes les plus sèches).
    Volatilité : 90e centile de la volatilité glissante sur 20 séances.
    Spread : 90e centile du spread Corwin-Schultz glissant sur 60 séances.
    Les trois pires niveaux sont combinés : scénario volontairement prudent.
    """
    return Scenario(
        "Stress historique",
        float(np.percentile(metrics.rolling_median_turnover_eur(df, 20), 10)),
        float(np.percentile(metrics.rolling_volatility(df, 20), 90)),
        float(np.percentile(metrics.rolling_spread(df, 60), 90)),
    )


def shock_scenario(base: Scenario, volume_haircut: float = 0.5, vol_mult: float = 2.0, spread_mult: float = 2.0) -> Scenario:
    """Choc uniforme appliqué au scénario normal (volume −50 %, volatilité ×2, spread ×2 par défaut)."""
    return Scenario(
        "Choc uniforme",
        base.volume_eur * (1 - volume_haircut),
        base.daily_vol * vol_mult,
        base.spread * spread_mult,
    )


def exit_metrics(sc: Scenario, position_eur: float, participation: float = 0.20, y: float = 0.7) -> dict:
    """Jours de sortie, part liquidable à 1 / 5 / 20 séances et coût de sortie pour un scénario."""
    daily_capacity = participation * sc.volume_eur  # p · V
    cost = sc.spread / 2 + y * sc.daily_vol * np.sqrt(participation)
    out = {
        "Jours de sortie": position_eur / daily_capacity if daily_capacity > 0 else float("inf"),
        "Coût de sortie (bps)": cost * 1e4,
        "Coût de sortie (€)": cost * position_eur,
    }
    for d in HORIZONS:
        out[f"Liquidable en {d} j"] = min(1.0, daily_capacity * d / position_eur) if position_eur > 0 else 1.0
    out["Position max sortie en 5 j (€)"] = daily_capacity * 5
    return out
