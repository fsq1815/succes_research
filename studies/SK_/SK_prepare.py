#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SK_prepare.py — Kaggle 原始数据 → 统一字段 → 剔除 → SUCCES 规则项编码.

严格按 docs/SK_preregistration.md 第 4/5 节执行。本脚本**只做描述性体检**，
不计算六维得分与互动率之间的任何关联或回归；推断在 R/SK_analyze.R 里做。

用法：python3 SK_prepare.py
输入：data/external/SK_D1_*.zip, SK_D2_*.zip（先跑 SK_download.py）
输出：data/processed/SK_coded_D1.csv, SK_coded_D2.csv
      output/SK_data_health.txt
"""
import csv
import datetime as dt
import io
import os
import re
import sys
import zipfile
from collections import Counter

from SK_codebook import DIM_MAP, ITEMS, code_row, code_row_cr4_zero

ROOT = os.path.dirname(os.path.abspath(__file__))
EXTERNAL = os.path.join(ROOT, "data", "external")
PROCESSED = os.path.join(ROOT, "data", "processed")
OUT = os.path.join(ROOT, "output")

D1_MAP = {
    "BV号": "bvid", "标题": "title", "视频简介": "desc", "UP主": "up_name",
    "UP主ID": "up_mid", "精确播放数": "view", "弹幕数": "danmaku",
    "点赞数": "like", "投币数": "coin", "收藏数": "favorite",
    "分享数": "share", "评论数": "reply", "发布时间": "pub_time",
    "时长(秒)": "duration",
}
NUM_COLS = ["view", "like", "coin", "favorite", "share", "reply", "danmaku", "duration"]


def parse_cn_count(v):
    """把 '40.6万' / '1,234' / 1234 / '-' / None 解析为 float；失败返回 None。"""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace(",", "").replace("，", "")
    if not s or s in {"-", "--", "None", "nan", "NaN", "NULL"}:
        return None
    mult = 1.0
    for suf, m in (("亿", 1e8), ("万", 1e4), ("千", 1e3)):
        if s.endswith(suf):
            mult, s = m, s[:-1]
            break
    try:
        return float(s) * mult
    except ValueError:
        return None


def parse_time(v):
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    s = str(v or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            pass
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def clean_cell(v):
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s in {"-", "--", "None", "nan", "NaN"} else s


def read_d1():
    import openpyxl
    path = [p for p in sorted(os.listdir(EXTERNAL)) if p.startswith("SK_D1_") and p.endswith(".zip")]
    if not path:
        raise SystemExit("缺少 D1 zip，请先运行 python3 SK_download.py")
    with zipfile.ZipFile(os.path.join(EXTERNAL, path[0])) as z:
        wb = openpyxl.load_workbook(io.BytesIO(z.read("video_details.xlsx")),
                                    read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = ws.iter_rows(values_only=True)
        header = [clean_cell(x) for x in next(rows)]
        idx = {c: i for i, c in enumerate(header)}
        missing = [k for k in D1_MAP if k not in idx]
        if missing:
            raise SystemExit("D1 缺少列：" + ", ".join(missing))
        out = []
        for r in rows:
            if all(x is None for x in r):
                continue
            out.append({eng: r[idx[zh]] for zh, eng in D1_MAP.items()})
        wb.close()
    return out


def read_d2():
    path = [p for p in sorted(os.listdir(EXTERNAL)) if p.startswith("SK_D2_") and p.endswith(".zip")]
    if not path:
        raise SystemExit("缺少 D2 zip，请先运行 python3 SK_download.py")
    with zipfile.ZipFile(os.path.join(EXTERNAL, path[0])) as z:
        raw = z.read("bilibili_zhangxuefeng_videos.csv")
    text = raw.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def normalize(rows):
    """统一字段类型，返回 (list of dict, 数值解析失败计数)。"""
    bad = Counter()
    out = []
    for r in rows:
        d = {
            "bvid": clean_cell(r.get("bvid")),
            "title": clean_cell(r.get("title")),
            "desc": clean_cell(r.get("desc")),
            "up_mid": clean_cell(r.get("up_mid")),
            "up_name": clean_cell(r.get("up_name")),
            "pub_time_raw": clean_cell(r.get("pub_time")),
        }
        for c in NUM_COLS:
            v = parse_cn_count(r.get(c))
            if v is None:
                bad[c] += 1
            d[c] = v
        t = parse_time(r.get("pub_time"))
        d["pub_dt"] = t
        out.append(d)
    return out, bad


def quantile(xs, q):
    if not xs:
        return float("nan")
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def fmt(x, nd=4):
    return "NA" if x is None else ("%.*f" % (nd, x))


def prepare(key, rows, health):
    raw_n = len(rows)
    norm, bad = normalize(rows)
    steps = []

    def keep(pred, label):
        nonlocal norm
        before = len(norm)
        norm = [r for r in norm if pred(r)]
        steps.append((label, before - len(norm)))

    # 剔除规则（预注册第 5 节，顺序固定）
    seen = set()
    def dedup(r):
        k = r["bvid"] or ("row:" + str(id(r)))
        if k in seen:
            return False
        seen.add(k)
        return True
    keep(dedup, "1. 按视频 ID 去重")
    keep(lambda r: all(r[c] is not None for c in NUM_COLS), "2a. 数值字段可解析")
    keep(lambda r: r["view"] >= 1000, "2b. view >= 1000")
    keep(lambda r: all(r[c] >= 0 for c in NUM_COLS), "3a. 计数非负")
    keep(lambda r: (r["like"] + r["coin"] + r["favorite"] + r["share"] + r["reply"]) > 0,
         "3b. 互动计数之和 > 0（log 因变量要求）")
    keep(lambda r: r["duration"] > 0 and bool(r["title"]), "4. duration > 0 且标题非空")

    coded = []
    for r in norm:
        t = r["pub_dt"]
        if t is None:
            # 时间不可解析时不臆造；用缺失标记，模型里以 "" 水平处理
            pub_hour, pub_weekday, pub_month, pub_date = "", "", "", ""
        else:
            pub_hour, pub_weekday = t.hour, t.weekday()
            pub_month, pub_date = t.strftime("%Y-%m"), t.strftime("%Y-%m-%d")
        view = max(r["view"], 1)
        engage = (r["like"] + r["coin"] + r["favorite"] + r["share"] + r["reply"]) / view
        fav = r["favorite"] / view
        share = r["share"] / view
        row = {
            "dataset": key, "bvid": r["bvid"], "title": r["title"], "desc": r["desc"],
            "up_mid": r["up_mid"] or "UNKNOWN", "up_name": r["up_name"],
            "pub_date": pub_date, "pub_hour": pub_hour, "pub_weekday": pub_weekday,
            "pub_month": pub_month or "UNKNOWN", "duration": r["duration"],
            "view": view, "like": r["like"], "coin": r["coin"], "favorite": r["favorite"],
            "share": r["share"], "reply": r["reply"], "danmaku": r["danmaku"],
            "engage_rate": engage, "fav_rate": fav, "share_rate": share,
            "title_len": len(r["title"]),
        }
        row.update(code_row(r["title"], r["desc"], r["duration"]))
        row["s_credible_cr4zero"] = code_row_cr4_zero(r["title"], r["desc"], r["duration"])["s_credible"]
        # None → 空（CSV 中即 NA，R 读取为 NA）
        coded.append({k: ("" if v is None else v) for k, v in row.items()})

    path = os.path.join(PROCESSED, "SK_coded_%s.csv" % key)
    fields = list(coded[0].keys()) if coded else []
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(coded)

    h = []
    h.append("=== %s 数据体检（描述性，不含任何关联/回归结果）===" % key)
    h.append("原始行数: %d" % raw_n)
    h.append("数值解析失败计数: %s" % (dict(bad) or "无"))
    for label, n in steps:
        h.append("  %-46s 剔除 %4d 条" % (label, n))
    h.append("最终分析样本 N = %d" % len(coded))
    h.append("UP 主聚类数 (up_mid 唯一值): %d" % len({r["up_mid"] for r in coded}))
    dates = [r["pub_date"] for r in coded if r["pub_date"]]
    h.append("发布时间范围: %s ~ %s" % (min(dates) if dates else "NA", max(dates) if dates else "NA"))
    h.append("简介非空: %d / %d (%.1f%%)" % (
        sum(1 for r in coded if r["desc"]), len(coded),
        100 * sum(1 for r in coded if r["desc"]) / max(len(coded), 1)))
    views = [r["view"] for r in coded]
    ers = [r["engage_rate"] for r in coded]
    h.append("view 分位数 0/25/50/75/100: %s" % " / ".join(
        "%.0f" % quantile(views, q) for q in (0, .25, .5, .75, 1)))
    h.append("engage_rate 分位数 0/25/50/75/100: %s" % " / ".join(
        "%.5f" % quantile(ers, q) for q in (0, .25, .5, .75, 1)))
    h.append("六维规则项得分（均值 / sd / 零比例 / 有效项数）:")
    for dim in DIM_MAP:
        vals = [r[dim] for r in coded]
        m = sum(vals) / len(vals) if vals else 0
        sd = (sum((v - m) ** 2 for v in vals) / len(vals)) ** .5 if vals else 0
        zero = sum(1 for v in vals if v == 0) / len(vals) if vals else 0
        nvalid = Counter(r["n_" + dim] for r in coded)
        h.append("  %-14s mean=%s sd=%s zero=%.1f%% n_valid=%s" % (
            dim, fmt(m, 3), fmt(sd, 3), 100 * zero, dict(nvalid)))
    health.extend(h + [""])


def main():
    os.makedirs(PROCESSED, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    health = [
        "SUCCES-Kaggle · 数据体检报告",
        "生成脚本: SK_prepare.py（描述性统计；关联与回归见 R/SK_analyze.R）",
        "预注册: docs/SK_preregistration.md v1.0（在看任何关联结果之前冻结）",
        "",
    ]
    prepare("D1", read_d1(), health)
    prepare("D2", read_d2(), health)
    with open(os.path.join(OUT, "SK_data_health.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(health) + "\n")
    print("\n".join(health))
    print("编码表：data/processed/SK_coded_D1.csv / SK_coded_D2.csv")


if __name__ == "__main__":
    main()
