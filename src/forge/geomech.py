"""Геомеханика интервала 8¾" (6 000–10 942 фута) по расчёту Schlumberger (IsoMechPro) и каверномеру.

Градиенты переведены в эквивалентную плотность, ppg: psi/ft / 0,052. Плотность раствора и ECD — по рапортам, FIT — по
рапортам на башмаках колонн. Опубликованный минимальный горизонтальный градиент по DFIT и керну — 0,66–0,78 psi/ft
(Bunger et al., Xing et al.), по каротажу — 0,81: в окне это нижняя граница по поглощению берётся консервативно 0,66.
-> data/geomech.parquet, out/geomech.json
"""
import json
from pathlib import Path

import lasio
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def main():
    m = lasio.read(ROOT / "data/raw/logs/University_of_Utah_Forge_16A_78-32_ThrubitDipole_IsoMechPro_result_6000-10942ft.las").df().reset_index()
    g = pd.DataFrame({"md": m.MD, "ucs_psi": m.UCS, "fang": m.FANG, "pp_ppg": m.PPGI / 0.052, "shmin_ppg": m.TXSG_ISO / 0.052,
                      "sv_ppg": m.TZSG / 0.052, "cal": m.C1_24, "bit": m.BS_RM, "devi": m.DEVI, "ym": m.YME_STA, "pr": m.PR})
    g["enl"] = g.cal - g.bit
    g.to_parquet(ROOT / "data/geomech.parquet", index=False)
    res = dict(ucs_mpa_med=float(g.ucs_psi.median() * 0.006895), ucs_mpa_p10=float(g.ucs_psi.quantile(.1) * 0.006895),
               ucs_mpa_p90=float(g.ucs_psi.quantile(.9) * 0.006895), fang_med=float(g.fang.median()),
               pp_ppg=float(g.pp_ppg.median()), shmin_log_ppg=float(g.shmin_ppg.median()), shmin_dfit_ppg=[0.66 / 0.052, 0.78 / 0.052],
               sv_ppg=float(g.sv_ppg.median()), mw_ppg=9.0, ecd_ppg=9.26, fit_ppg=[9.5, 9.6],
               in_gauge=float((g.enl.abs() <= 0.25).mean()), enlarged_05=float((g.enl > 0.5).mean()), ym_mpsi=float(g.ym.median()), pr=float(g.pr.median()))
    json.dump(res, open(ROOT / "out/geomech.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
