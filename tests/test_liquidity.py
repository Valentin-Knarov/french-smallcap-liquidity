import numpy as np
import pytest

from smallcap_liquidity import exit as ex
from smallcap_liquidity import metrics
from smallcap_liquidity.data import simulate_stock, simulate_universe
from smallcap_liquidity.report import write_excel, write_html
from smallcap_liquidity.study import classify, run_study
from smallcap_liquidity.universe import DEMO_UNIVERSE


@pytest.fixture(scope="module")
def liquid():
    return simulate_stock(adv_eur=20e6, spread=0.0010, daily_vol=0.015, seed=1, stress=None)


@pytest.fixture(scope="module")
def illiquid():
    return simulate_stock(adv_eur=150e3, spread=0.015, daily_vol=0.028, zero_volume_prob=0.05, seed=2)


def test_adv_close_to_simulated(liquid):
    assert metrics.adv_eur(liquid, 250) == pytest.approx(20e6, rel=0.25)


def test_spread_estimator_recovers_wide_spread(illiquid):
    assert metrics.corwin_schultz(illiquid, 500) == pytest.approx(0.015, rel=0.3)


def test_spread_floor(liquid):
    assert metrics.corwin_schultz(liquid, 120) >= metrics.SPREAD_FLOOR


def test_amihud_ranks_liquidity(liquid, illiquid):
    assert metrics.amihud(illiquid) > 10 * metrics.amihud(liquid)


def test_zero_volume_share(liquid, illiquid):
    assert metrics.zero_volume_share(liquid) == 0
    assert 0 < metrics.zero_volume_share(illiquid) < 0.2


def test_exit_formulas():
    sc = ex.Scenario("test", volume_eur=1e6, daily_vol=0.02, spread=0.004)
    m = ex.exit_metrics(sc, position_eur=2e6, participation=0.20, y=0.7)
    assert m["Jours de sortie"] == pytest.approx(10.0)  # 2 M€ / (20 % × 1 M€)
    assert m["Liquidable en 1 j"] == pytest.approx(0.10)
    assert m["Liquidable en 20 j"] == 1.0
    assert m["Coût de sortie (bps)"] == pytest.approx((0.002 + 0.7 * 0.02 * np.sqrt(0.2)) * 1e4)


def test_stress_is_worse_than_normal(illiquid):
    normal, stress = ex.normal_scenario(illiquid), ex.historical_stress(illiquid)
    assert stress.daily_vol > normal.daily_vol
    assert stress.spread >= normal.spread


def test_shock_scenario():
    base = ex.Scenario("Normal", 1e6, 0.02, 0.004)
    sh = ex.shock_scenario(base)
    assert (sh.volume_eur, sh.daily_vol, sh.spread) == (5e5, 0.04, 0.008)


def test_classify():
    assert classify(80).startswith("A") and classify(10).startswith("D")


@pytest.fixture(scope="module")
def study():
    tickers = list(DEMO_UNIVERSE)[:8]
    return run_study(simulate_universe(tickers), position_eur=5e6)


def test_study_sorted_and_scored(study):
    s = study["Score de liquidité"]
    assert s.is_monotonic_decreasing
    assert s.between(0, 100).all()
    # les références fictives sont les plus liquides
    assert study.index[0].startswith("DEMO-R")


def test_reports_written(study, tmp_path):
    params = {"Source": "Démo (données simulées)", "Position (€)": 5e6, "Participation p": 0.2}
    assert write_excel(study, params, tmp_path / "r.xlsx").stat().st_size > 5_000
    html = write_html(study, params, tmp_path / "r.html").read_text(encoding="utf-8")
    assert "Étude de liquidité" in html and "plotly" in html.lower()
