"""Наращивания при бурении по режимам с шагом 10 с: время «в клиньях» и «от нагрузки до нагрузки».

Наращивание — эпизод «клинья установлены» между двумя интервалами бурения, если за него забой не изменился и он короче 60 мин.
Слипс-слипс (в клиньях) — длительность эпизода; от нагрузки до нагрузки — от последней секунды на забое до первой.
-> data/connections.parquet
"""
from pathlib import Path

import numpy as np
import pandas as pd

from forge.drilling import load

ROOT = Path(__file__).resolve().parents[2]


def main():
    d = load()
    d["hd"] = d.depth.cummax()
    d["onb"] = (d.on_bottom == 1) & (d.wob > 1)
    s = (d.slips == 1).astype(int)
    grp = (s.diff() != 0).cumsum()
    ep = d.assign(g=grp)[s == 1].groupby("g").agg(t0=("Time", "min"), t1=("Time", "max"), hd=("hd", "max"), n=("Time", "size"))
    ep["slips_min"] = (ep.t1 - ep.t0).dt.total_seconds() / 60 + 10 / 60
    onb_t = d.loc[d.onb, ["Time", "hd"]]
    times = onb_t.Time.values
    rows = []
    for e in ep.itertuples():
        i = np.searchsorted(times, np.datetime64(e.t0))
        if i == 0 or i >= len(times):
            continue
        prev, nxt = pd.Timestamp(times[i - 1]), pd.Timestamp(times[i])
        w2w = (nxt - prev).total_seconds() / 60
        if w2w > 90 or e.slips_min > 60:
            continue
        rows.append(dict(t0=e.t0, depth=e.hd, slips_min=e.slips_min, w2w_min=w2w))
    c = pd.DataFrame(rows)
    c["section"] = np.where(c.depth < 1629, "17½ in", np.where(c.depth < 5113, "12¼ in", "8¾ in"))
    c.to_parquet(ROOT / "data/connections.parquet", index=False)
    print(len(c)); print(c.groupby("section")[["slips_min", "w2w_min"]].describe(percentiles=[.25, .5, .75]).round(1).T.to_string())


if __name__ == "__main__":
    main()
