"""Rapports : classeur Excel (tableaux) et page HTML (graphiques interactifs)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from jinja2 import Template
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

CLASS_COLORS = {
    "A — très liquide": "#1a7f4b",
    "B — liquide": "#7cb342",
    "C — peu liquide": "#f0a202",
    "D — illiquide": "#c0392b",
}

SYNTHESIS_COLUMNS = [
    "Nom", "Segment", "Classe", "Score de liquidité", "ADV 60 j (€)", "Spread estimé (bps)",
    "Amihud (bps / M€)", "Séances sans volume", "Jours de sortie — Normal",
    "Jours de sortie — Stress historique", "Jours de sortie — Choc uniforme", "Jours de sortie — Pire scénario",
    "Coût de sortie (bps) — Pire scénario", "Liquidable en 5 j — Stress historique",
]

METHODOLOGY = [
    ("Notations", "X : position (€) · V : volume journalier de référence (€) · p : taux de participation · "
                  "σ : volatilité journalière · s : spread relatif · Y : constante d'impact · d : nombre de séances"),
    ("Jours de sortie", "D = X / (p · V)"),
    ("Part liquidable en d séances", "min(1, p · V · d / X)"),
    ("Coût de sortie", "s/2 + Y · σ · √p (demi-spread + impact en racine carrée)"),
    ("Amihud", "moyenne de |r_t| / (P_t · N_t), en bps par M€ échangé (r_t : rendement, P_t : cours, N_t : volume en titres)"),
    ("Spread", "estimateur de Corwin-Schultz (2012) sur 6 mois, plancher 2 bps"),
    ("Scénario normal", "montant médian échangé sur 60 séances, σ sur 60 séances, spread sur 6 mois"),
    ("Stress historique", "10e centile du volume médian glissant 20 j, 90e centile de σ glissante 20 j et du spread glissant 60 j"),
    ("Choc uniforme", "scénario normal avec volume −50 %, volatilité ×2, spread ×2"),
    ("Score", "moyenne des rangs centiles de l'ADV, d'Amihud, du spread, des séances sans volume et des jours de sortie en stress (100 = plus liquide)"),
    ("Classes", "A ≥ 75, B ≥ 50, C ≥ 25, D < 25 — classement relatif à l'univers étudié"),
]


def _fmt(col: str) -> str:
    if "(€)" in col:
        return '#,##0'
    if col in ("Séances sans volume",) or col.startswith("Liquidable") or col == "Volatilité annualisée":
        return '0%'
    if col.startswith("Volatilité j"):
        return '0.00%'
    return '0.0'


def write_excel(table: pd.DataFrame, params: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    detail = table.drop(columns=["Nom", "Segment"]).copy()
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        table[SYNTHESIS_COLUMNS].to_excel(xl, sheet_name="Synthèse")
        detail.to_excel(xl, sheet_name="Détail par scénario")
        pd.DataFrame(list(params.items()), columns=["Paramètre", "Valeur"]).to_excel(xl, sheet_name="Paramètres", index=False)
        pd.DataFrame(METHODOLOGY, columns=["Élément", "Définition"]).to_excel(xl, sheet_name="Méthodologie", index=False)

        header_fill = PatternFill("solid", fgColor="1F4E79")
        for ws in xl.book.worksheets:
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = header_fill
                cell.alignment = Alignment(wrap_text=True, vertical="center")
            ws.row_dimensions[1].height = 45
            ws.freeze_panes = "B2"
            for i, col_cells in enumerate(ws.columns, start=1):
                header = str(col_cells[0].value or "")
                width = 60 if ws.title == "Méthodologie" and i == 2 else max(12, min(26, len(header) * 0.9))
                ws.column_dimensions[get_column_letter(i)].width = width
                for c in col_cells[1:]:
                    if isinstance(c.value, (int, float)):
                        c.number_format = _fmt(header)
                    if header == "Classe" and c.value in CLASS_COLORS:
                        c.fill = PatternFill("solid", fgColor=CLASS_COLORS[c.value].lstrip("#"))
                        c.font = Font(color="FFFFFF", bold=True)
    return path


def _charts(table: pd.DataFrame) -> list[str]:
    t = table.reset_index()
    t["Libellé"] = t["Nom"] + " (" + t["Ticker"] + ")"
    figs = []

    f1 = px.scatter(
        t, x="ADV 60 j (€)", y="Amihud (bps / M€)", color="Classe", hover_name="Libellé", log_x=True, log_y=True,
        color_discrete_map=CLASS_COLORS, category_orders={"Classe": list(CLASS_COLORS)},
        hover_data={"Spread estimé (bps)": ":.1f", "Score de liquidité": True},
        title="Volume moyen et illiquidité d'Amihud",
    )
    f1.update_traces(marker_size=11)
    figs.append(f1)

    s = t.sort_values("Jours de sortie — Pire scénario")
    f2 = go.Figure()
    for col, color in [("Jours de sortie — Normal", "#1f4e79"), ("Jours de sortie — Stress historique", "#c0392b"),
                       ("Jours de sortie — Choc uniforme", "#f0a202")]:
        f2.add_bar(y=s["Libellé"], x=s[col], name=col.split("— ")[1], orientation="h", marker_color=color)
    f2.update_layout(barmode="group", xaxis_type="log", title="Jours nécessaires pour sortir de la position",
                     height=max(500, 28 * len(s)), xaxis_title="Séances (échelle logarithmique)")
    # Repères 1 semaine / 1 mois. Sur un axe log, les lignes se placent en valeur, les annotations en log10.
    for days, label in [(5, "1 semaine"), (20, "1 mois")]:
        f2.add_shape(type="line", x0=days, x1=days, y0=0, y1=1, yref="paper", line=dict(dash="dash", color="grey"))
        f2.add_annotation(x=np.log10(days), y=1.0, yref="paper", text=label, showarrow=False, yanchor="bottom")
    figs.append(f2)

    cols = [c for c in t.columns if c.startswith("Liquidable en") and c.endswith("Stress historique")]
    h = t.set_index("Libellé")[cols].rename(columns=lambda c: c.split(" — ")[0])
    f3 = px.imshow(h, text_auto=".0%", color_continuous_scale="RdYlGn", zmin=0, zmax=1, aspect="auto",
                   title="Part de la position liquidable en stress historique")
    f3.update_layout(height=max(500, 24 * len(h)), coloraxis_showscale=False)
    figs.append(f3)

    for f in figs:
        f.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=60, b=10), legend_title_text="")
    # Plotly est intégré une seule fois dans la page : le rapport fonctionne hors connexion.
    return [f.to_html(full_html=False, include_plotlyjs=(i == 0)) for i, f in enumerate(figs)]


_HTML = Template("""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>Étude de liquidité — small & mid caps françaises</title>
<style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:1150px;margin:32px auto;padding:0 20px;color:#1d2733}
h1{color:#1f4e79;margin-bottom:4px} .sub{color:#5c6b7a;margin-top:0}
.kpis{display:flex;gap:14px;margin:24px 0}.kpi{flex:1;background:#f4f7fa;border-radius:8px;padding:14px}
.kpi b{display:block;font-size:26px;color:#1f4e79}.note{background:#fff8e6;border-left:4px solid #f0a202;padding:10px 14px}
table{border-collapse:collapse;width:100%;font-size:13px;margin:12px 0}th,td{padding:6px 8px;border-bottom:1px solid #e3e8ee;text-align:right}
th{background:#1f4e79;color:#fff}td:first-child,th:first-child,td:nth-child(2){text-align:left}
.badge{color:#fff;padding:2px 8px;border-radius:10px;font-size:12px;white-space:nowrap}
</style></head><body>
<h1>Étude de liquidité — small & mid caps françaises</h1>
<p class="sub">{{ today }} · source : {{ source }} · position étudiée : {{ position }} · participation : {{ participation }}</p>
{% if demo %}<p class="note">Données simulées (mode démo). Relancer sans <code>--demo</code> pour les données Yahoo Finance.</p>{% endif %}
<div class="kpis">
<div class="kpi"><b>{{ n }}</b>titres étudiés</div>
<div class="kpi"><b>{{ n_week }}</b>sortables en moins d'une semaine en stress</div>
<div class="kpi"><b>{{ n_month }}</b>nécessitent plus d'un mois en stress</div>
<div class="kpi"><b>{{ median_cost }}</b>coût de sortie médian (pire scénario)</div>
</div>
{% for c in charts %}{{ c }}{% endfor %}
<h2>Synthèse</h2>
<table><tr><th>Titre</th><th>Classe</th><th>Score</th><th>ADV 60 j</th><th>Spread</th><th>Amihud</th><th>Sortie normale</th><th>Sortie stress</th><th>Coût pire cas</th></tr>
{% for r in rows %}<tr><td>{{ r.label }}</td><td><span class="badge" style="background:{{ r.color }}">{{ r.cls }}</span></td>
<td>{{ r.score }}</td><td>{{ r.adv }}</td><td>{{ r.spread }}</td><td>{{ r.amihud }}</td><td>{{ r.d_norm }}</td><td>{{ r.d_stress }}</td><td>{{ r.cost }}</td></tr>{% endfor %}
</table>
<h2>Méthodologie</h2><table>{% for k, v in methodology %}<tr><td><b>{{ k }}</b></td><td style="text-align:left">{{ v }}</td></tr>{% endfor %}</table>
<p class="sub">Étude indicative à partir de données publiques gratuites : ne constitue pas un conseil d'investissement.</p>
</body></html>""")


def _eur(x: float) -> str:
    return f"{x / 1e6:,.1f} M€".replace(",", " ") if x >= 1e6 else f"{x / 1e3:,.0f} k€".replace(",", " ")


def _days(x: float) -> str:
    return "> 250 j" if x > 250 else f"{x:.1f} j"


def write_html(table: pd.DataFrame, params: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        dict(label=f"{r['Nom']} ({t})", cls=r["Classe"], color=CLASS_COLORS[r["Classe"]], score=f"{r['Score de liquidité']:.0f}",
             adv=_eur(r["ADV 60 j (€)"]), spread=f"{r['Spread estimé (bps)']:.0f} bps", amihud=f"{r['Amihud (bps / M€)']:.0f}",
             d_norm=_days(r["Jours de sortie — Normal"]), d_stress=_days(r["Jours de sortie — Stress historique"]),
             cost=f"{r['Coût de sortie (bps) — Pire scénario']:.0f} bps")
        for t, r in table.iterrows()
    ]
    worst = table["Jours de sortie — Stress historique"]
    html = _HTML.render(
        today=date.today().strftime("%d/%m/%Y"), source=params["Source"], demo=params["Source"].startswith("Démo"),
        position=_eur(params["Position (€)"]), participation=f"{params['Participation p']:.0%}",
        n=len(table), n_week=int((worst <= 5).sum()), n_month=int((worst > 20).sum()),
        median_cost=f"{np.median(table['Coût de sortie (bps) — Pire scénario']):.0f} bps",
        charts=_charts(table), rows=rows, methodology=METHODOLOGY,
    )
    path.write_text(html, encoding="utf-8")
    return path
