"""Режимы бурения 16A(78)-32 с шагом 10 с -> показатели по каждому футу проходки и MSE.

Фут считается пробуренным, когда «Total Depth» (забой) впервые превысил его. Для каждого фута: время бурения, средние
нагрузка, обороты ротора, момент, обороты долота, давление и режим (ротор или слайд), отсюда механическая скорость и MSE.
MSE по Тиле (Teale, 1965), psi: WOB/A + 120·π·N·T / (A·ROP), WOB — фунты, A — площадь забоя, дюйм², N — об/мин,
T — момент на роторе, фут·фунт, ROP — фут/ч. Энергия забойного двигателя не учтена (момента на долоте с двигателем нет).
-> data/feet.parquet
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def load():
    d = pd.read_parquet(ROOT / "data/raw/time_10s.parquet")
    d = d.rename(columns={"Total Depth": "depth", "Weight on Bit": "wob", "Top Drive RPM": "rpm", "Top Drive Torque (ft-lbs)": "tq",
                          "Bit RPM": "bit_rpm", "On Bottom": "on_bottom", "Slips Set": "slips", "Bit Diameter": "bit", "Pump Pressure": "spp",
                          "Differential Pressure": "dp", "Flow In": "flow", "Drill Mode": "mode", "Hookload": "hookload", "Block Position": "block",
                          "MWD Inclination": "inc", "ROP Depth/Hour": "rop_rig", "Downhole Torque": "dht"})
    d = d.reset_index(drop=True)
    # метки времени записаны с точностью до минуты, в минуте 6 строк по 10 с: восстанавливаем секунды по порядку строк
    d["Time"] = d.Time + pd.to_timedelta(d.groupby("Time").cumcount() * 10, unit="s")
    d = d.sort_values("Time", kind="stable").reset_index(drop=True)
    d.loc[(d.depth <= 0) | (d.depth > 11500), "depth"] = np.nan
    d["depth"] = d.depth.ffill()
    return d


def feet(d):
    # забой: накопленный максимум, чтобы шумы и откаты значения не давали «повторного» бурения
    hd = d.depth.cummax()
    d = d.assign(hd=hd, dt=d.Time.diff().dt.total_seconds().fillna(10).clip(0, 60))
    drill = d[(d.on_bottom == 1) & (d.wob > 1)]
    drill = drill.assign(ft=np.floor(drill.hd))
    g = drill.groupby("ft")
    f = pd.DataFrame({"t_start": g.Time.min(), "secs": g.dt.sum(), "wob": g.wob.mean(), "rpm": g.rpm.mean(), "tq": g.tq.mean(),
                      "bit_rpm": g.bit_rpm.median(), "spp": g.spp.mean(), "dp": g.dp.mean(), "flow": g.flow.mean(), "bit": g.bit.median(),
                      "slide": g["mode"].apply(lambda s: (s == 2).mean()), "inc": g.inc.median(), "dht": g.dht.median()}).reset_index()
    # время на фут — между первыми отметками соседних футов, если бурение шло непрерывно; иначе сумма шагов на забое
    f = f.sort_values("ft")
    f["rop"] = 3600 / f.secs.clip(lower=10)
    f = f[(f.rop < 400) & (f.wob > 2)]
    bit = f.bit.where(f.bit > 5).ffill().bfill()
    area = np.pi * bit ** 2 / 4
    f["mse"] = f.wob * 1000 / area + 120 * np.pi * f.rpm * f.tq / (area * f.rop)
    # MSE на долоте: момент двигателя (Pason считает его по перепаду давления) и обороты долота (ротор + двигатель)
    dht = f.dht.where((f.dht > 0) & (f.dht < 30000))
    f["mse_bit"] = f.wob * 1000 / area + 120 * np.pi * f.bit_rpm.where(f.bit_rpm < 400) * dht / (area * f.rop)
    f["section"] = np.where(f.ft < 1629, "17½ in", np.where(f.ft < 5113, "12¼ in", "8¾ in"))
    return f


def main():
    d = load()
    f = feet(d)
    f.to_parquet(ROOT / "data/feet.parquet", index=False)
    print(len(f), f.ft.min(), f.ft.max())
    print(f.groupby("section").agg(ft=("ft", "size"), hrs=("secs", lambda s: s.sum() / 3600), rop=("rop", "median"), wob=("wob", "median"),
                                    rpm=("rpm", "median"), tq=("tq", "median"), mse=("mse", "median"), slide=("slide", "mean")).round(1))
    print(f.describe().T.round(1).to_string())


if __name__ == "__main__":
    main()
