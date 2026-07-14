#!/usr/bin/env python3
"""
IDX80 universe definition.

IDX80 = the 80 most liquid IDX stocks with large market cap and strong
fundamentals. IDX rebalances constituents at its major evaluations
(effective early Feb / early Aug, with minor evaluations in between).

IMPORTANT: Update this list when IDX announces a new evaluation result:
https://www.idx.co.id/en/market-data/stock-index/
"""

# LQ45 subset (kept in sync with STOCK_INDICES["LQ45"] in stock_api_server.py)
_LQ45 = [
    "AADI", "ACES", "ADMR", "ADRO", "AKRA",
    "AMMN", "AMRT", "ANTM", "ASII",
    "BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRPT", "BUMI",
    "CPIN", "CTRA",
    "DSSA",
    "EMTK", "EXCL",
    "GOTO",
    "HEAL",
    "ICBP", "INCO", "INDF", "INKP", "ISAT", "ITMG",
    "JPFA",
    "KLBF",
    "MAPI", "MBMA", "MDKA", "MEDC",
    "NCKL",
    "PGAS", "PGEO", "PTBA",
    "SCMA", "SMGR",
    "TLKM", "TOWR",
    "UNTR", "UNVR"
]

# IDX80 members beyond LQ45 (35 stocks)
_IDX80_EXTRA = [
    "ARTO", "BREN", "BRMS", "BSDE", "BTPS",
    "BUKA", "CMRY", "CUAN", "DSNG",
    "ELSA", "ENRG", "ERAA", "ESSA",
    "HRTA", "HRUM", "INDY", "INTP",
    "JSMR", "KIJA", "KPIG",
    "MAPA", "MIKA", "MTEL", "MYOR",
    "PANI", "PNLF", "PTRO", "PWON",
    "RAJA", "RATU", "SIDO", "SMRA",
    "SSIA", "TAPG", "WIFI"
]

IDX80 = sorted(set(_LQ45 + _IDX80_EXTRA))

assert len(IDX80) == 80, f"IDX80 universe must have 80 members, got {len(IDX80)}"
