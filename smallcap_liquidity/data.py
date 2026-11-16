"""Données journalières : Yahoo Finance (réelles) ou simulées (démo et tests).

Format commun : DataFrame indexé par date, colonnes ``open, high, low, close, volume``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[COLUMNS].dropna(subset=["close"])
    df["volume"] = df["volume"].fillna(0.0)
    return df[df["high"] >= df["low"]]


def load_yahoo(tickers: list[str], period: str = "5y") -> dict[str, pd.DataFrame]:
    """Télécharge les données journalières non ajustées (les plus hauts / plus bas réels servent au spread)."""
    import yfinance as yf

    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        df = yf.download(t, period=period, interval="1d", auto_adjust=False, progress=False)
        if df is not None and not df.empty:
            out[t] = _normalize(df)
    if not out:
        raise ValueError("Aucune donnée Yahoo téléchargée : vérifie la connexion internet et les tickers.")
    return out


def simulate_stock(
    n_days: int = 1260,
    price: float = 40.0,
    daily_vol: float = 0.02,
    adv_eur: float = 2e6,
    spread: float = 0.002,
    zero_volume_prob: float = 0.0,
    stress: tuple[int, int] | None = (700, 760),
    seed: int | None = 0,
    steps_per_day: int = 2000,
) -> pd.DataFrame:
    """Une action simulée, avec un épisode de stress (volatilité ×2,5, volumes ×0,5, spread ×2,5).

    Le prix milieu suit une marche aléatoire intraday ; chaque transaction se fait au prix
    acheteur ou vendeur (mid ± spread/2), ce qui gonfle les plus hauts / plus bas du spread.
    Pour les titres peu liquides, certaines séances n'ont aucune transaction (volume nul).

    Paramètres : n_days (séances), price (prix initial en €), daily_vol (volatilité journalière),
    adv_eur (volume moyen journalier en €), spread (spread relatif), zero_volume_prob
    (probabilité d'une séance sans échange), stress (début, fin) de l'épisode de stress.
    """
    rng = np.random.default_rng(seed)
    vol_mult = np.ones(n_days)
    volu_mult = np.ones(n_days)
    spr_mult = np.ones(n_days)
    if stress is not None:
        a, b = stress
        vol_mult[a:b], volu_mult[a:b], spr_mult[a:b] = 2.5, 0.5, 2.5

    dates = pd.bdate_range(end=pd.Timestamp("2026-11-13"), periods=n_days)
    shocks = rng.normal(0.0, 1.0, (n_days, steps_per_day)) * (daily_vol * vol_mult / np.sqrt(steps_per_day))[:, None]
    log_mid = np.log(price) + np.cumsum(shocks.ravel()).reshape(n_days, steps_per_day)
    mid = np.exp(log_mid)
    side = rng.choice([-1.0, 1.0], size=(n_days, steps_per_day))
    trades = mid * (1 + side * (spread * spr_mult)[:, None] / 2)

    close = trades[:, -1]
    # volume en titres tel que le montant moyen échangé reste ≈ adv_eur quel que soit le cours
    volume = adv_eur / close * volu_mult * rng.lognormal(-0.5 * 0.5**2, 0.5, n_days)
    df = pd.DataFrame(
        {"open": trades[:, 0], "high": trades.max(axis=1), "low": trades.min(axis=1), "close": close,
         "volume": np.round(volume)},
        index=dates,
    )
    if zero_volume_prob > 0:
        no_trade = rng.random(n_days) < zero_volume_prob
        prev_close = df["close"].shift(1).fillna(df["open"])
        for col in ("open", "high", "low", "close"):
            df.loc[no_trade, col] = prev_close[no_trade]
        df.loc[no_trade, "volume"] = 0.0
    return df


def simulate_universe(tickers: list[str], seed: int = 2026) -> dict[str, pd.DataFrame]:
    """Univers simulé : liquidité très dispersée, des références (≈ 100 M€/j) aux petites valeurs (≈ 50 k€/j).

    Le spread et la volatilité baissent quand la liquidité augmente, comme sur le marché réel.
    """
    from smallcap_liquidity.universe import segment

    rng = np.random.default_rng(seed)
    out = {}
    for i, t in enumerate(tickers):
        seg = segment(t)
        log_adv = {"Référence": rng.uniform(18.0, 19.5), "Mid": rng.uniform(14.5, 17.0)}.get(seg, rng.uniform(10.8, 14.5))
        adv_eur = float(np.exp(log_adv))  # ≈ 50 k€ à 300 M€
        illiq = (19.5 - log_adv) / 8.7  # 0 (très liquide) → 1 (peu liquide)
        out[t] = simulate_stock(
            price=float(rng.uniform(8, 250)),
            daily_vol=0.012 + 0.018 * illiq + rng.uniform(-0.002, 0.002),
            adv_eur=adv_eur,
            spread=float(np.exp(np.log(0.0004) + illiq * np.log(0.025 / 0.0004))),  # 4 bps → 250 bps
            zero_volume_prob=max(0.0, (illiq - 0.75) * 0.3),
            seed=seed + i,
        )
    return out
