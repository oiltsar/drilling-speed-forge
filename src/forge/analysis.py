"""Резерв времени и коммерческая скорость 16A(78)-32: что дала бы проводка «как на лучших рейсах».

Рычаги, каждый считается отдельно и без двойного счёта:
1. Механическая скорость в граните. Рейсы 8¾" до выхода на устойчивый режим (5 505–8 004 фута) против медианы рейсов в
   тангенсе (8 024–10 955 футов) при той же прочности породы (UCS по каротажу).
2. Отработка долот. Для каждого рейса — момент подъёма, при котором минимально время на фут с учётом СПО
   ((t_бурения + t_СПО) / проходка). Экономия — если время бурения изношенным долотом после этой точки больше, чем СПО
   плюс бурение того же интервала новым долотом со скоростью начала рейса.
3. Наращивания: время от снятия нагрузки до её возврата сверх лучшей четверти.
4. НПВ по ремонту бурового оборудования — по рапортам.
Время СПО: 2·глубина / 2 100 фут/ч (медиана чистого спуска по рапортам) + 3 ч на смену КНБК.
-> out/results.json, out/levers.csv
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FT_M = 0.3048
TRIP_FTH, BHA_H = 2100, 3.0


def trip_hours(depth):
    return 2 * depth / TRIP_FTH + BHA_H


def main():
    f = pd.read_parquet(ROOT / "data/feet.parquet")
    r = pd.read_parquet(ROOT / "data/runs.parquet")
    b = pd.read_parquet(ROOT / "data/balance.parquet")
    c = pd.read_parquet(ROOT / "data/connections.parquet")
    b = b[b.stage == "после забуривания"]
    res = {}
    total_h = b.hrs.sum()
    depth_ft = 10987
    res["actual"] = dict(days=total_h / 24, depth_m=depth_ft * FT_M, comm_speed=depth_ft * FT_M / total_h * 720,
                         science_h=float(b[b.kind == "Исследования FORGE"].hrs.sum()))
    prod_h = total_h - res["actual"]["science_h"]
    res["production_like"] = dict(days=prod_h / 24, comm_speed=depth_ft * FT_M / prod_h * 720)

    # 1. скорость в граните: только роторное бурение (на наборе кривизны ориентированное бурение медленнее по природе),
    #    интервал 5 892–8 004 фута (рейс 14 в вертикали учтён в рычаге 2), сравнение в одинаковых классах прочности
    import lasio
    m = lasio.read(ROOT / "data/raw/logs/University_of_Utah_Forge_16A_78-32_ThrubitDipole_IsoMechPro_result_6000-10942ft.las").df().reset_index()
    f["ucs"] = f.ft.map(m.groupby(np.floor(m.MD)).UCS.mean())
    f["secs_c"] = f.secs.clip(upper=900)
    rot = f[(f.rpm > 30) & f.ucs.notna()].copy()
    rot["ub"] = pd.cut(rot.ucs, [0, 15000, 16500, 18000, 19500, 1e6])
    early = rot[(rot.ft >= 5892) & (rot.ft < 8010)]
    late = rot[(rot.ft >= 8020) & (rot.ft < 10955)]
    late_rop = late.groupby("ub", observed=True).apply(lambda d: len(d) / (d.secs_c.sum() / 3600), include_groups=False)
    e = early.groupby("ub", observed=True).agg(ft=("ft", "size"), h=("secs_c", lambda x: x.sum() / 3600))
    e["h_best"] = e.ft / late_rop.reindex(e.index)
    lever1 = float((e.h - e.h_best).clip(lower=0).sum())
    pdc = r[(r["size"] < 9) & (r.kind == "PDC")].copy()
    res["rop"] = dict(early_rop=float(len(early) / (early.secs_c.sum() / 3600)), late_rop=float(len(late) / (late.secs_c.sum() / 3600)),
                      early_ucs=float(early.ucs.median()), late_ucs=float(late.ucs.median()), early_bit_rpm=float(early.bit_rpm.median()),
                      late_bit_rpm=float(late.bit_rpm.median()), early_td_rpm=float(early.rpm.median()), late_td_rpm=float(late.rpm.median()),
                      early_wob=float(early.wob.median()), late_wob=float(late.wob.median()), saving_h=lever1,
                      by_ucs=[dict(ucs=str(i), early_rop=float(row.ft / row.h), late_rop=float(late_rop.get(i, np.nan)), ft=int(row.ft)) for i, row in e.iterrows()])

    # 2. отработка долот
    rows = []
    for x in pdc.itertuples():
        seg = f[(f.ft >= x.depth_in) & (f.ft < x.depth_out)].sort_values("ft")
        if len(seg) < 50:
            continue
        t = seg.secs.clip(upper=900).cumsum() / 3600
        h = np.arange(1, len(seg) + 1)
        T = trip_hours(x.depth_in)
        cost = (t.values + T) / h
        k = int(np.argmin(cost[len(seg) // 5:])) + len(seg) // 5
        rop0 = seg.head(max(20, len(seg) // 5)).pipe(lambda s: len(s) / (s.secs.clip(upper=900).sum() / 3600))
        tail_h = float(t.values[-1] - t.values[k])
        tail_ft = len(seg) - k - 1
        alt = T + tail_ft / rop0
        rows.append(dict(bit_no=x.bit_no, depth_in=x.depth_in, feet=len(seg), hrs=float(t.values[-1]), opt_ft=k + 1, rop_start=rop0,
                         rop_end=len(seg.tail(max(20, len(seg) // 5))) / (seg.tail(max(20, len(seg) // 5)).secs.clip(upper=900).sum() / 3600),
                         tail_h=tail_h, alt_h=alt, saving_h=max(0.0, tail_h - alt), trip_h=T))
    bo = pd.DataFrame(rows)
    bo.round(2).to_csv(ROOT / "out/bit_pull.csv", index=False)
    lever2 = float(bo.saving_h.sum())

    # 3. наращивания
    c8 = c[c.depth >= 1629]
    p25 = c8.w2w_min.quantile(0.25)
    lever3 = float((c8.w2w_min - p25).clip(lower=0).sum() / 60)
    res["connections"] = dict(n=int(len(c8)), slips_med=float(c8.slips_min.median()), w2w_med=float(c8.w2w_min.median()), w2w_p25=float(p25), saving_h=lever3)

    # 4. НПВ (ремонт оборудования): половина — реалистичная цель планово-предупредительного ремонта
    npt = float(b[b.kind == "НПВ: ремонт и аварии"].hrs.sum())
    lever4 = npt * 0.5
    res["npt"] = dict(hours=npt, saving_h=lever4)

    # 5. проходка на рейс 8¾": как у трёх лучших рейсов. В производственной скважине нет подъёмов на точки отбора керна,
    #    поэтому рейсы ограничивает только износ и смена КНБК под профиль
    d8 = pdc[pdc.feet > 0]
    best3 = float(d8.feet.nlargest(3).mean())
    n_new = int(np.ceil(d8.feet.sum() / best3))
    trip_avg = float(trip_hours(d8.depth_in.mean()))
    lever5 = (len(d8) - n_new) * trip_avg
    res["runs"] = dict(n=int(len(d8)), feet_avg=float(d8.feet.mean()), best3=best3, n_new=n_new, trip_h=trip_avg, saving_h=lever5)

    levers = pd.DataFrame([
        ("Механическая скорость в граните: режим тангенса с начала интервала (только ротор)", lever1),
        ("Отработка долот: подъём в точке минимума времени на фут", lever2),
        ("Наращивания: время от нагрузки до нагрузки на уровне лучшей четверти", lever3),
        ("НПВ по ремонту оборудования: вдвое меньше за счёт ППР", lever4),
        ("Проходка на рейс 8¾\" как у трёх лучших рейсов: меньше СПО", lever5)], columns=["lever", "hours"])
    levers["days"] = levers.hours / 24
    levers.to_csv(ROOT / "out/levers.csv", index=False)
    save_h = levers.hours.sum()
    res["levers"] = levers.to_dict("records")
    res["potential"] = dict(save_days=save_h / 24, days=(prod_h - save_h) / 24, comm_speed=depth_ft * FT_M / (prod_h - save_h) * 720)
    json.dump(res, open(ROOT / "out/results.json", "w"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(res, ensure_ascii=False, indent=1, default=lambda v: round(float(v), 2)))
    print(bo.round(1).to_string())


if __name__ == "__main__":
    main()
