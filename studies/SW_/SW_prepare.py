#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SW_prepare.py — 视频元数据 + 高赞评论 → 分析表（只做清洗与编码，不做任何推断）.

严格按 docs/SW_preregistration.md v1.0 第 3/5 节执行。
**本脚本不计算六维与因变量之间的任何关联、相关或回归**；推断只在 R/SW_analyze.R 里做。

输入：data/raw/SW_videos.csv, SW_comments_{dev,main,control}.csv
输出：data/processed/SW_analysis.csv（评论级，每行一条高赞评论）
      output/SW_data_health.txt（描述性体检）
"""
import csv
import os
import re
from collections import Counter

from SW_succes import DIM_MAP, ITEMS, code_row, code_row_cr4_zero
from SW_info_markers import clean, code_comment

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "processed")
OUT = os.path.join(ROOT, "output")
os.makedirs(PROC, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

NUM_VIDEO = ["view", "like", "coin", "favorite", "share", "reply", "danmaku", "duration"]


def num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("，", "")
    if not s or s in {"-", "--", "None", "nan", "NaN", "NULL"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def build_video_index():
    p = os.path.join(RAW, "SW_videos.csv")
    d = {}
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for c in NUM_VIDEO:
                r[c] = num(r.get(c))
            pub = r.get("pub_time") or ""
            m = re.match(r"(\d{4})", pub)
            r["pub_year"] = m.group(1) if m else "UNKNOWN"
            r["title_len"] = len(r.get("title") or "")
            r["blurb_len"] = len(r.get("blurb") or "")
            d[r["bvid"]] = r
    return d


def main():
    vids = build_video_index()
    rows = []
    for split in ("dev", "main", "control"):
        p = os.path.join(RAW, "SW_comments_%s.csv" % split)
        if not os.path.exists(p):
            print("[skip] 缺少 %s" % os.path.relpath(p, ROOT))
            continue
        with open(p, encoding="utf-8") as f:
            for c in csv.DictReader(f):
                v = vids.get(c["bvid"])
                if v is None:
                    continue
                if not clean(c.get("message", "")):
                    continue
                if not (v["view"] and v["view"] > 0 and v["duration"] and v["duration"] > 0 and v["title"]):
                    continue
                six = code_row(v["title"], v["blurb"], v["duration"])
                if any(six[d] is None for d in DIM_MAP):
                    continue
                marks = code_comment(c["message"], v["title"], v["blurb"])
                rec = {
                    "split": split, "bvid": c["bvid"], "aid": c["aid"],
                    "rank": int(c["rank"]), "rpid": c["rpid"],
                    "comment_like": float(c["like"] or 0), "ctime": c["ctime"],
                    "up_mid": v["up_mid"] or "UNKNOWN", "zone": v["zone"] or "UNKNOWN",
                    "issue": v["issue"], "pub_year": v["pub_year"], "pub_time": v["pub_time"],
                    "title_len": v["title_len"], "blurb_len": v["blurb_len"],
                    "duration": v["duration"], "view": v["view"],
                    "video_like": v["like"], "coin": v["coin"], "favorite": v["favorite"],
                    "share": v["share"], "video_reply": v["reply"], "danmaku": v["danmaku"],
                    "title": v["title"], "blurb": v["blurb"],
                }
                rec.update(marks)
                rec.update(six)
                rec["s_credible_cr4zero"] = code_row_cr4_zero(v["title"], v["blurb"], v["duration"])["s_credible"]
                rows.append(rec)

    fields = list(rows[0].keys()) if rows else []
    path = os.path.join(PROC, "SW_analysis.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # ---- 描述性体检（禁止出现任何关联/回归结果）----
    L = ["SUCCES-Weekly · 数据体检（描述性，不含任何关联或回归结果）",
         "预注册: docs/SW_preregistration.md v1.0", ""]
    for split in ("dev", "main", "control"):
        s = [r for r in rows if r["split"] == split]
        if not s:
            L.append("=== %s: 无数据 ===" % split)
            continue
        bv = {r["bvid"] for r in s}
        L.append("=== %s ===" % split)
        L.append("  视频 %d | 高赞评论 %d | 每视频评论数分布 %s" %
                 (len(bv), len(s), dict(sorted(Counter(
                     sum(1 for x in s if x["bvid"] == b) for b in bv).items()))))
        L.append("  UP 主聚类数 %d | 分区数 %d | 年份 %s" %
                 (len({r["up_mid"] for r in s}), len({r["zone"] for r in s}),
                  sorted({r["pub_year"] for r in s})))
        for k in ("info_discussion", "info_learn", "ask", "explain", "fact"):
            h = sum(r[k] for r in s)
            L.append("  %-18s 命中 %4d/%d (%.1f%%)" % (k, h, len(s), 100 * h / len(s)))
        e = [r["info_echo"] for r in s]
        L.append("  %-18s 均值 %.4f 中位 %.4f 非零 %d/%d" %
                 ("info_echo", sum(e) / len(e), sorted(e)[len(e) // 2],
                  sum(1 for x in e if x > 0), len(e)))
        L.append("  六维规则项得分（均值 / 零比例 / 唯一取值数）:")
        for d in DIM_MAP:
            v = [r[d] for r in s]
            L.append("    %-16s %.3f / %5.1f%% / %d" %
                     (d, sum(v) / len(v), 100 * sum(1 for x in v if x == 0) / len(v),
                      len(set(v))))
        L.append("")
    L.append("说明：dev 集只用于词典开发，整体排除出所有推断分析；control 仅用于 S5。")
    L.append("本文件不含任何六维与因变量的关联结果。")
    with open(os.path.join(OUT, "SW_data_health.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("已写出 %s (%d 行) 与 output/SW_data_health.txt" %
          (os.path.relpath(path, ROOT), len(rows)))


if __name__ == "__main__":
    main()
