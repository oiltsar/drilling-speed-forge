"""Графики отчёта. Серый — основной цвет, оранжевый — главная мысль. Заголовок графика — вывод."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "reports" / "figures"
INK, INK2, GREY, LIGHT = "#151917", "#4f5753", "#9aa09c", "#e1e4df"
ACCENT, CALM, BG = "#e8590c", "#b9beba", "#fcfcfb"
SRC = "Utah FORGE, скважина 16A(78)-32, 30.10.2020–03.01.2021"


def setup():
    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "figure.dpi": 110, "savefig.dpi": 160, "savefig.bbox": "tight",
        "font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "axes.edgecolor": GREY, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK, "xtick.major.size": 0, "ytick.major.size": 0,
        "legend.frameon": False})


def head(fig, title, sub):
    fig.text(0.0, 1.07, title, fontsize=13, fontweight="bold", color=INK, ha="left", va="bottom")
    fig.text(0.0, 1.015, sub, fontsize=9, color=INK2, ha="left", va="bottom")


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)


def n(x, d=0):
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def balance():
    b = pd.read_csv(ROOT / "out/balance_by_kind.csv", index_col=0)
    b = b[b.суток >= 0.5].sort_values("суток")
    fig, ax = plt.subplots(figsize=(9, 4.2))
    col = [ACCENT if k in ("СПО и смена КНБК",) else INK2 if k == "Исследования FORGE" else CALM for k in b.index]
    ax.barh(b.index, b.суток, color=col, height=0.66)
    for i, (d, s) in enumerate(zip(b.суток, b.доля)):
        ax.text(d + 0.2, i, f"{n(d, 1)} сут · {n(s * 100)}%", va="center", fontsize=9, color=INK)
    ax.set_xticks([]); ax.spines["bottom"].set_visible(False)
    head(fig, "СПО и смена КНБК заняли больше времени, чем само бурение",
         f"Баланс календарного времени от забуривания до цементирования хвостовика, сутки. Тёмным — программа исследований FORGE. {SRC}, суточные рапорты")
    save(fig, "01_balance")


def depth_time():
    d = pd.read_parquet(ROOT / "data/raw/time_10s.parquet", columns=["Time", "Total Depth"])
    d["Time"] = d.Time + pd.to_timedelta(d.groupby("Time").cumcount() * 10, unit="s")
    d = d[(d["Total Depth"] > 0) & (d["Total Depth"] < 11500)].sort_values("Time")
    d["hd"] = d["Total Depth"].cummax() * 0.3048
    spud = pd.Timestamp("2020-10-30 13:00")
    d = d[d.Time >= spud]
    d["day"] = (d.Time - spud).dt.total_seconds() / 86400
    d = d.iloc[::30]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.plot(d.day, d.hd, color=INK, lw=1.8)
    ax.invert_yaxis()
    for y, t in [(1629 * .3048, "башмак 13⅜\""), (5113 * .3048, "башмак 9⅝\"")]:
        ax.axhline(y, color=LIGHT, lw=1, zorder=0); ax.text(0.5, y - 40, t, fontsize=8, color=INK2)
    ax.axvspan((pd.Timestamp("2020-11-24") - spud).days, (pd.Timestamp("2020-12-01") - spud).days, color=ACCENT, alpha=.12, lw=0)
    ax.text((pd.Timestamp("2020-11-24") - spud).days + .3, 3300, "набор кривизны\nдо 65°", fontsize=8.5, color=ACCENT)
    ax.set_xlabel("сутки от забуривания"); ax.set_ylabel("глубина по стволу, м")
    ax.grid(axis="y", color=LIGHT, lw=.6)
    head(fig, "3 349 м за 61 сутки: в граните проходка шла ступеньками между рейсами",
         f"Глубина забоя по данным станции с шагом 10 с. {SRC}")
    save(fig, "02_depth_time")


def rop_runs():
    r = pd.read_csv(ROOT / "out/runs.csv")
    r = r[(r["size"] < 9) & (r.kind == "PDC")]
    r["rop_m"] = r.rop_calc * 0.3048
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = np.arange(len(r))
    col = [ACCENT if d >= 8020 else CALM for d in r.depth_in]
    ax.bar(x, r.rop_m, color=col, width=.66)
    for i, (v, f_) in enumerate(zip(r.rop_m, r.feet)):
        ax.text(i, v + .3, n(v, 1), ha="center", fontsize=9, color=INK)
        ax.text(i, -1.4, f"{n(f_ * .3048)} м", ha="center", fontsize=7.5, color=INK2)
    ax.set_xticks(x, [f"№{int(b)}\n{n(d * .3048)} м" for b, d in zip(r.bit_no, r.depth_in)], fontsize=8)
    ax.set_yticks([]); ax.set_ylim(-2.2, r.rop_m.max() * 1.15)
    head(fig, "В тангенсе каждый рейс давал 11–15 м/ч, до него — от 2,5 до 11",
         f"Средняя механическая скорость рейса PDC 8¾\", м/ч; подпись — проходка за рейс. Оранжевым — тангенс 65°. {SRC}, рапорты")
    save(fig, "03_rop_runs")


def rop_ucs():
    res = json.load(open(ROOT / "out/results.json"))["rop"]
    u = pd.DataFrame(res["by_ucs"])
    labels = ["до 103", "103–114", "114–124", "124–134", "больше 134"]
    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(len(u))
    ax.bar(x - .18, u.early_rop * .3048, width=.34, color=CALM, label=f"набор кривизны, 1 795–2 440 м: ротор {n(res['early_td_rpm'])} об/мин, долото {n(res['early_bit_rpm'])}, нагрузка {n(res['early_wob'] * .4536, 1)} т")
    ax.bar(x + .18, u.late_rop * .3048, width=.34, color=ACCENT, label=f"тангенс, 2 444–3 339 м: ротор {n(res['late_td_rpm'])} об/мин, долото {n(res['late_bit_rpm'])}, нагрузка {n(res['late_wob'] * .4536, 1)} т")
    for i, (a, b) in enumerate(zip(u.early_rop * .3048, u.late_rop * .3048)):
        ax.text(i - .18, a + .3, n(a, 1), ha="center", fontsize=8.5, color=INK2)
        ax.text(i + .18, b + .3, n(b, 1), ha="center", fontsize=9, color=INK, fontweight="bold")
    ax.set_xticks(x, [f"UCS {l} МПа" for l in labels], fontsize=8.5)
    ax.set_yticks([]); ax.legend(loc="upper center", bbox_to_anchor=(.5, -.12), fontsize=8.5)
    head(fig, "При той же прочности гранита роторное бурение в тангенсе шло в 1,5 раза быстрее",
         f"Механическая скорость роторного бурения, м/ч, по классам прочности породы (UCS по каротажу Schlumberger). {SRC}")
    save(fig, "04_rop_ucs")


def bit14():
    f = pd.read_parquet(ROOT / "data/feet.parquet")
    seg = f[(f.ft >= 5505) & (f.ft < 5846)].sort_values("ft")
    t = seg.secs.clip(upper=900).cumsum() / 3600
    h = (seg.ft - 5505) * .3048
    bp = pd.read_csv(ROOT / "out/bit_pull.csv").set_index("bit_no").loc[14]
    k = int(bp.opt_ft) - 1
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(t, h, color=INK, lw=2)
    ax.plot(t.iloc[k:], h.iloc[k:], color=ACCENT, lw=2.4)
    ax.scatter([t.iloc[k]], [h.iloc[k]], color=ACCENT, zorder=3, s=40)
    ax.annotate(f"оптимальный подъём: {n(h.iloc[k])} м за {n(t.iloc[k], 1)} ч", (t.iloc[k], h.iloc[k]), (t.iloc[k] + 2, h.iloc[k] - 25),
                fontsize=9, color=ACCENT, arrowprops=dict(arrowstyle="-", color=ACCENT))
    ax.text(t.iloc[-1], h.iloc[-1] + 3, f"фактически {n(h.iloc[-1])} м\nза {n(t.iloc[-1], 1)} ч", fontsize=9, color=INK, ha="right", va="bottom")
    ax.set_xlabel("время на забое, ч"); ax.set_ylabel("проходка рейса, м"); ax.grid(axis="y", color=LIGHT, lw=.6)
    head(fig, f"Рейс №14 бурили изношенным долотом ещё {n(bp.tail_h)} ч при скорости {n(bp.rop_end * .3048, 1)} м/ч",
         f"Проходка рейса №14 (8¾\", 1 678–1 782 м). Износ по IADC 8/2 CR, причина подъёма — низкая скорость. Новое долото с СПО дали бы экономию {n(bp.saving_h, 1)} ч. {SRC}")
    save(fig, "05_bit14")


def mse():
    f = pd.read_parquet(ROOT / "data/feet.parquet")
    g = pd.read_parquet(ROOT / "data/geomech.parquet")
    f["ucs"] = f.ft.map(g.groupby(np.floor(g.md)).ucs_psi.mean())
    f = f[(f.ft >= 6000) & (f.rpm > 30) & f.ucs.notna()].copy()
    f["r_surf"], f["r_bit"] = f.mse / f.ucs, f.mse_bit / f.ucs
    f["bin"] = (f.ft // 100) * 100
    a = f.groupby("bin")[["r_surf", "r_bit", "tq"]].median().rolling(3, center=True, min_periods=1).median()
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(a.index * .3048, a.r_surf, color=GREY, lw=1.6, label="MSE по поверхностным параметрам (ротор, момент на роторе)")
    ax.plot(a.index * .3048, a.r_bit, color=ACCENT, lw=2.2, label="MSE на долоте (обороты долота, момент двигателя по перепаду)")
    ax.axhline(1, color=INK, lw=.8, ls=":")
    ax.text(1830, 1.08, "MSE = UCS", fontsize=8, color=INK2)
    ax.set_ylim(0, 5.5); ax.set_xlabel("глубина по стволу, м"); ax.set_ylabel("MSE / UCS, раз")
    ax.grid(axis="y", color=LIGHT, lw=.6); ax.legend(fontsize=8.5, loc="upper left")
    med_bit = f.r_bit.median()
    head(fig, f"На долоте MSE держится около {n(med_bit, 1)} UCS, а рост по поверхности — трение в наклонном стволе",
         f"Отношение MSE к прочности породы, медиана по 30 м, роторное бурение 8¾\". КПД долота ≈ UCS/MSE ≈ {n(100 / med_bit)}%. Момент на роторе вырос "
         f"с {n(a.tq.iloc[0] / 1000, 1)} до {n(a.tq.iloc[-1] / 1000, 1)} тыс. фут·фунт. {SRC}")
    save(fig, "06_mse")


def connections():
    c = pd.read_parquet(ROOT / "data/connections.parquet")
    c = c[c.depth >= 1629]
    r = json.load(open(ROOT / "out/results.json"))["connections"]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    bins = np.arange(0, 56, 2.5)
    ax.hist(c.w2w_min.clip(upper=55), bins=bins, color=CALM, edgecolor=BG)
    ax.axvline(r["w2w_p25"], color=ACCENT, lw=2); ax.axvline(r["w2w_med"], color=INK, lw=1.2, ls="--")
    ax.text(r["w2w_p25"] + .5, ax.get_ylim()[1] * .9, f"лучшая четверть: {n(r['w2w_p25'], 1)} мин", color=ACCENT, fontsize=9)
    ax.text(r["w2w_med"] + .5, ax.get_ylim()[1] * .75, f"медиана: {n(r['w2w_med'], 1)} мин", color=INK, fontsize=9)
    ax.set_xlabel("от снятия нагрузки до её возврата, мин"); ax.set_yticks([])
    head(fig, f"В клиньях — {n(r['slips_med'])} мин, а нагрузку на долото возвращали через {n(r['w2w_med'], 1)} мин",
         f"{r['n']} наращиваний при бурении ниже башмака 13⅜\": время от нагрузки до нагрузки. {SRC}, данные станции с шагом 10 с")
    save(fig, "07_connections")


def geomech():
    g = pd.read_parquet(ROOT / "data/geomech.parquet").iloc[::5]
    r = json.load(open(ROOT / "out/geomech.json"))
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(9, 4.6), sharey=True, gridspec_kw={"width_ratios": [3, 1.3]})
    y = g.md * .3048
    ax.fill_betweenx(y, r["pp_ppg"], r["shmin_dfit_ppg"][0], color=LIGHT, lw=0)
    ax.plot(g.pp_ppg, y, color=INK2, lw=1.2, label="поровое давление")
    ax.axvline(r["mw_ppg"] * 1.0, color=ACCENT, lw=2.2, label="плотность раствора 9,0 ppg (1,08 г/см³)")
    ax.axvline(r["shmin_dfit_ppg"][0], color=INK, lw=1.2, ls="--", label="мин. горизонтальное напряжение по DFIT и керну")
    ax.plot(g.shmin_ppg, y, color=GREY, lw=1, label="мин. горизонтальное напряжение по каротажу")
    ax.plot(g.sv_ppg, y, color=CALM, lw=1, label="горное давление")
    ax.invert_yaxis(); ax.set_xlabel("эквивалентная плотность, ppg"); ax.set_ylabel("глубина по стволу, м")
    ax.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(.6, -.13), ncol=2)
    ax2.plot(g.enl, y, color=INK2, lw=.8)
    ax2.axvline(0, color=ACCENT, lw=1.2); ax2.set_xlabel("каверна, дюйм"); ax2.set_xlim(-.6, 1.2)
    head(fig, f"Окно плотности широкое, ствол устойчив: {n(r['in_gauge'] * 100)}% интервала в номинале",
         f"Интервал 8¾\" 1 829–3 335 м. Напряжения и UCS — расчёт Schlumberger по акустике и плотности; DFIT и керн — 0,66–0,78 psi/ft. {SRC}")
    save(fig, "08_geomech")


def waterfall():
    res = json.load(open(ROOT / "out/results.json"))
    a, p, pot = res["actual"], res["production_like"], res["potential"]
    rows = [("Факт: от забуривания до цементирования хвостовика", a["days"], "total", f"{n(a['comm_speed'])} м/ст.-мес."),
            ("Исследования FORGE: керн, ГИС, термометрия, DFIT", -(a["days"] - p["days"]), "science", ""),
            ("Как производственная скважина", p["days"], "sub", f"{n(p['comm_speed'])} м/ст.-мес.")]
    names = ["Механическая скорость в граните — режим тангенса сразу (только ротор)", "Отработка долот — подъём рейса №14 в оптимуме",
             "Наращивания — до лучшей четверти", "НПВ по ремонту оборудования — вдвое меньше", "Проходка на рейс как у трёх лучших — меньше СПО"]
    for nm, l in zip(names, res["levers"]):
        rows.append((nm, -l["days"], "lever", ""))
    rows.append(("Потенциал", pot["days"], "final", f"{n(pot['comm_speed'])} м/ст.-мес."))
    fig, ax = plt.subplots(figsize=(9, 4.6))
    cur = 0
    for i, (lab, v, kind, sp) in enumerate(rows):
        y = len(rows) - 1 - i
        if kind in ("total", "sub", "final"):
            ax.barh(y, v, color={"total": INK2, "sub": CALM, "final": ACCENT}[kind], height=.62)
            cur = v
            ax.text(v + .4, y, f"{n(v, 1)} сут · {sp}", va="center", fontsize=9, color=INK, fontweight="bold" if kind == "final" else "normal")
        else:
            ax.barh(y, -v, left=cur + v, color=GREY if kind == "science" else ACCENT, height=.62, alpha=.9)
            ax.text(cur + .4, y, f"−{n(-v, 1)} сут", va="center", fontsize=9, color=INK2)
            cur += v
    ax.set_yticks(range(len(rows)), [r[0] for r in rows][::-1], fontsize=8.5)
    ax.set_xticks([]); ax.spines["bottom"].set_visible(False); ax.set_xlim(0, a["days"] * 1.35)
    head(fig, f"Как производственная скважина 16A прошла бы за {n(pot['days'], 1)} сут вместо {n(p['days'], 1)}: +{n((pot['comm_speed'] / p['comm_speed'] - 1) * 100)}% к коммерческой скорости",
         f"Сутки от забуривания до цементирования хвостовика; коммерческая скорость — метров на станко-месяц (720 ч). {SRC}")
    save(fig, "09_waterfall")


def main():
    setup()
    for f in (balance, depth_time, rop_runs, rop_ucs, bit14, mse, connections, geomech, waterfall):
        f()
        print("ok", f.__name__)


if __name__ == "__main__":
    main()
