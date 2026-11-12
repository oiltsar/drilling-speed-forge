"""Рейсы долот по рапортам и по режимам: проходка, время на забое, механическая скорость, MSE, причина подъёма.

Источник проходки и часов — таблица DRILL BITS суточного рапорта (последняя запись по долоту). MSE и прочность
породы по рейсу — из data/feet.parquet и каротажа Schlumberger (IsoMechPro). Причина подъёма — по тексту операций
дня окончания рейса.
-> data/runs.parquet, out/runs.csv
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def parse_bits():
    b = pd.read_parquet(ROOT / "data/bits.parquet")
    rows = []
    for r in b.itertuples():
        t = r.raw.split()
        try:
            i = max(k for k, x in enumerate(t) if x in ("Y", "N"))
        except ValueError:
            continue
        nums = [float(x.replace(",", "")) for x in t[i + 1:] if re.fullmatch(r"[\d,]+(\.\d+)?", x)]
        kind = "керн" if re.search(r"core", r.raw, re.I) else "PDC" if "PDC" in r.raw.upper() or re.search(r"TKC|SPL|MDSi|XS6|616|CF613|U613", r.raw) else \
            "шарошка" if re.search(r"TRI-?CONE|MILL TOOTH|Z713", r.raw, re.I) else "PDC"
        rows.append(dict(date=r.date, bit_no=r.bit_no, size=r.size, kind=kind, rerun=t[i] == "Y", nums=nums, raw=r.raw))
    d = pd.DataFrame(rows)
    out = []
    for no, g in d.groupby("bit_no"):
        g = g.sort_values("date")
        best = g[g.nums.map(len) >= 4]
        last = (best if len(best) else g).iloc[-1]
        n = last.nums
        rec = dict(bit_no=no, size=last["size"], kind=last.kind, rerun=last.rerun, start=g.date.min(), end=g.date.max(), raw=last.raw)
        if len(n) >= 4:
            rec.update(depth_in=n[0], depth_out=n[1], feet=n[2], hrs=n[3], wob=n[4] if len(n) > 4 else np.nan,
                       rpm=n[5] if len(n) > 5 else np.nan, rop=n[-1] if len(n) > 6 else np.nan)
        out.append(rec)
    return pd.DataFrame(out)


def main():
    r = parse_bits()
    r = r[r.feet.fillna(0) > 20].copy()
    r.loc[r.wob > 1000, "wob"] = r.wob / 1000
    r["rop_calc"] = r.feet / r.hrs
    f = pd.read_parquet(ROOT / "data/feet.parquet")
    import lasio
    m = lasio.read(ROOT / "data/raw/logs/University_of_Utah_Forge_16A_78-32_ThrubitDipole_IsoMechPro_result_6000-10942ft.las").df().reset_index()
    ucs = m.groupby(np.floor(m.MD)).UCS.mean()
    f["ucs"] = f.ft.map(ucs)
    agg = []
    for x in r.itertuples():
        seg = f[(f.ft >= x.depth_in) & (f.ft < x.depth_out)]
        rot = seg[seg.rpm > 30]
        agg.append(dict(bit_no=x.bit_no, mse_med=rot.mse.median(), ucs_med=seg.ucs.median(), rpm_td=rot.rpm.median(), bit_rpm=seg.bit_rpm.median(),
                        tq=rot.tq.median(), wob10s=seg.wob.median(), share_rotary=len(rot) / max(1, len(seg)),
                        mse_first=rot.head(max(1, len(rot) // 4)).mse.median(), mse_last=rot.tail(max(1, len(rot) // 4)).mse.median()))
    r = r.merge(pd.DataFrame(agg), on="bit_no", how="left")
    r["mse_growth"] = r.mse_last / r.mse_first
    # причина подъёма — текст операций дня окончания рейса и следующего
    o = pd.read_parquet(ROOT / "data/ops.parquet")
    reasons = []
    for x in r.itertuples():
        t = " ".join(o[(o.date >= x.end) & (o.date <= x.end + pd.Timedelta(days=1))].text)
        why = "керн/ГИС/исследования" if re.search(r"\bcor(e|ing)\b|log|temperature build|leak ?off|packer|gyro", t, re.I) else \
            "смена КНБК на набор/стабилизацию" if re.search(r"curve|tangent|build", t, re.I) else \
            "отказ оборудования" if re.search(r"fail|stator|wash ?out|broke|lost", t, re.I) else "износ долота / прочее"
        reasons.append(why)
    r["reason_pooh"] = reasons
    r.to_parquet(ROOT / "data/runs.parquet", index=False)
    cols = ["bit_no", "size", "kind", "depth_in", "depth_out", "feet", "hrs", "rop", "rop_calc", "wob", "rpm", "bit_rpm", "ucs_med", "mse_med", "mse_growth", "reason_pooh"]
    r[cols].round(1).to_csv(ROOT / "out/runs.csv", index=False)
    print(r[cols].round(1).to_string())


if __name__ == "__main__":
    main()
