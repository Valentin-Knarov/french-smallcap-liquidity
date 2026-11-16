"""Indicateurs de liquidité d'un titre.

Notations :
    P_t : cours de clôture du jour t (€)
    N_t : volume échangé le jour t (titres)
    r_t : rendement logarithmique du jour t, ln(P_t / P_{t-1})
    H_t, L_t : plus haut et plus bas du jour t
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252
_K = 3 - 2 * np.sqrt(2)
SPREAD_FLOOR = 0.0002  # 2 bps : en dessous, l'estimateur ne distingue plus le spread du bruit


def turnover_eur(df: pd.DataFrame) -> pd.Series:
    """Montant échangé chaque jour : P_t × N_t (€)."""
    return df["close"] * df["volume"]


def adv_eur(df: pd.DataFrame, window: int = 60) -> float:
    """Volume moyen journalier en euros sur ``window`` séances."""
    return float(turnover_eur(df).tail(window).mean())


def median_turnover_eur(df: pd.DataFrame, window: int = 60) -> float:
    """Montant médian échangé : plus représentatif qu'une moyenne tirée par quelques gros jours."""
    return float(turnover_eur(df).tail(window).median())


def daily_volatility(df: pd.DataFrame, window: int = 60) -> float:
    """σ : écart-type des rendements journaliers r_t sur la fenêtre."""
    return float(np.log(df["close"]).diff().dropna().tail(window).std(ddof=1))


def amihud(df: pd.DataFrame, window: int = 250) -> float:
    """Ratio d'illiquidité d'Amihud (2002), en points de base par million d'euros échangé.

        ILLIQ = moyenne sur les jours échangés de  |r_t| / (P_t × N_t)

    Lecture : variation de prix moyenne provoquée par 1 M€ échangé. Plus il est élevé,
    moins le titre est liquide. Les séances sans volume sont exclues du calcul.
    """
    d = df.tail(window + 1)
    r = np.log(d["close"]).diff().abs()
    t = turnover_eur(d)
    mask = (t > 0) & r.notna()
    if not mask.any():
        return float("nan")
    return float((r[mask] / t[mask]).mean() * 1e6 * 1e4)


def zero_volume_share(df: pd.DataFrame, window: int = 250) -> float:
    """Part des séances sans aucun échange."""
    return float((df["volume"].tail(window) <= 0).mean())


def corwin_schultz(df: pd.DataFrame, window: int = 120) -> float:
    """Spread relatif estimé (Corwin & Schultz, 2012) sur les ``window`` dernières séances.

    β = [ln(H_t/L_t)]² + [ln(H_{t+1}/L_{t+1})]²,  γ = [ln(max(H_t,H_{t+1}) / min(L_t,L_{t+1}))]²
    α = (√(2β̄) − √β̄) / (3 − 2√2) − √(γ̄ / (3 − 2√2)),  S = 2(e^α − 1) / (1 + e^α)

    β̄ et γ̄ sont les moyennes de β et γ sur la fenêtre (plus robuste que de moyenner des
    estimations journalières tronquées à 0). Les séances sans échange sont exclues.
    Un plancher de 2 bps est appliqué : sur les titres liquides, la volatilité domine
    l'amplitude journalière et l'estimation devient trop bruitée pour descendre plus bas.
    """
    d = df[df["volume"] > 0].tail(window + 1)
    h, l = d["high"].to_numpy(float), d["low"].to_numpy(float)
    if len(h) < 10:
        return float("nan")
    hl = np.log(h / l) ** 2
    beta = np.mean(hl[:-1] + hl[1:])
    gamma = np.mean(np.log(np.maximum(h[:-1], h[1:]) / np.minimum(l[:-1], l[1:])) ** 2)
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / _K - np.sqrt(gamma / _K)
    return float(max(2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha)), SPREAD_FLOOR))


def rolling_median_turnover_eur(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Montant médian échangé sur des fenêtres glissantes de ``window`` séances."""
    return turnover_eur(df).rolling(window).median().dropna()


def rolling_volatility(df: pd.DataFrame, window: int = 20) -> pd.Series:
    return np.log(df["close"]).diff().rolling(window).std().dropna()


def rolling_spread(df: pd.DataFrame, window: int = 60, step: int = 5) -> pd.Series:
    """Spread Corwin-Schultz glissant (fenêtres de ``window`` séances, recalculé tous les ``step`` jours)."""
    values, idx = [], []
    for end in range(window, len(df) + 1, step):
        values.append(corwin_schultz(df.iloc[end - window:end], window))
        idx.append(df.index[end - 1])
    return pd.Series(values, index=idx).dropna()
