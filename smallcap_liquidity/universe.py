"""Univers étudié : small & mid caps françaises cotées sur Euronext Paris (tickers Yahoo, suffixe .PA).

Liste indicative, modifiable : la classification « Mid » / « Small » est approximative et sert
seulement à regrouper les résultats. Quelques large caps servent de référence de liquidité.
"""

UNIVERSE = {
    # ticker: (nom, segment)
    "SOI.PA": ("Soitec", "Mid"),
    "NEX.PA": ("Nexans", "Mid"),
    "SOP.PA": ("Sopra Steria", "Mid"),
    "ATE.PA": ("Alten", "Mid"),
    "ELIS.PA": ("Elis", "Mid"),
    "GTT.PA": ("GTT", "Mid"),
    "RUI.PA": ("Rubis", "Mid"),
    "VK.PA": ("Vallourec", "Mid"),
    "ERA.PA": ("Eramet", "Mid"),
    "IPS.PA": ("Ipsos", "Mid"),
    "COFA.PA": ("Coface", "Mid"),
    "TRI.PA": ("Trigano", "Mid"),
    "VIRP.PA": ("Virbac", "Mid"),
    "FNAC.PA": ("Fnac Darty", "Small"),
    "BEN.PA": ("Bénéteau", "Small"),
    "LSS.PA": ("Lectra", "Small"),
    "MAU.PA": ("Maurel & Prom", "Small"),
    "MRN.PA": ("Mersen", "Small"),
    "KOF.PA": ("Kaufman & Broad", "Small"),
    "AUB.PA": ("Aubay", "Small"),
    "BOI.PA": ("Boiron", "Small"),
    "JCQ.PA": ("Jacquet Metals", "Small"),
    "CRI.PA": ("Chargeurs", "Small"),
    "LBIRD.PA": ("Lumibird", "Small"),
    "EXA.PA": ("Exail Technologies", "Small"),
    # Références large caps
    "CAP.PA": ("Capgemini", "Référence"),
    "BNP.PA": ("BNP Paribas", "Référence"),
}


# Univers fictif du mode démo : des données simulées ne doivent pas porter le nom de vraies sociétés.
DEMO_UNIVERSE = {
    **{f"DEMO-R{i:02d}": (f"Référence fictive {i}", "Référence") for i in range(1, 3)},
    **{f"DEMO-M{i:02d}": (f"Mid cap fictive {i}", "Mid") for i in range(1, 14)},
    **{f"DEMO-S{i:02d}": (f"Small cap fictive {i}", "Small") for i in range(1, 13)},
}

_ALL = {**UNIVERSE, **DEMO_UNIVERSE}


def name(ticker: str) -> str:
    return _ALL.get(ticker, (ticker, ""))[0]


def segment(ticker: str) -> str:
    return _ALL.get(ticker, ("", "Small"))[1]
