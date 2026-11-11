#!/usr/bin/env python3
# SC_pilot_collect.py — SUCCES 项目 pilot 采集（零第三方依赖，调用本机 curl）
#
# 目的：验证「抽样框 → 逐条元数据 → 粉丝数 → 可分析 CSV」整条链路能否跑通，
#       并产出 20-30 条真实公开数据供编码与描述统计使用。
# 合规：仅取公开视频元数据；每次请求间隔 >= 1.1 秒；不采个人信息、不存评论正文；
#       遇到 -352/403/412/429 等风控响应立即跳过，不绕过、不重试换UA。
#
# 运行：python3 SC_pilot_collect.py
# 输出：data/raw/SC_pilot_videos_YYYYMMDD.csv
#       data/raw/sample_bvid.csv           （供 R/01_collect.R 直接复用）
#       data/raw/SC_pilot_request_log.csv （请求审计日志）

import csv
import json
import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")
os.makedirs(RAW, exist_ok=True)

TODAY = datetime.now().strftime("%Y%m%d")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 "
      "succes-research/0.1 academic-pilot")
BASE = "https://api.bilibili.com"
PAUSE = 1.1
TARGET_N = 28
BLOCK_CODES = {-352, -403, 403, 412, 429}

audit = []


def api(path, **params):
    """礼貌地请求一次公开接口，返回解析后的 dict；失败也返回可诊断的结构。"""
    url = BASE + path + "?" + urlencode(params)
    cmd = ["curl", "-s", "-m", "15", "-A", UA,
           "-H", "Referer: https://www.bilibili.com", url]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
        d = json.loads(out)
    except Exception as e:  # noqa: BLE001
        d = {"code": -999, "error": str(e)}
    code = d.get("code")
    n = 0
    data = d.get("data")
    if isinstance(data, list):
        n = len(data)
    elif isinstance(data, dict):
        n = 1
    audit.append({"time": ts, "endpoint": path, "params": urlencode(params),
                  "code": code, "n_items": n,
                  "blocked": code in BLOCK_CODES})
    time.sleep(PAUSE)
    return d


def s(v):
    return "" if v is None else str(v)


def num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


# ---- 1. 抽样框：知识区主榜 + 子分区榜 × 多个时间窗 --------------------------
SPECS = [(36, 3), (36, 7), (36, 30),
         (201, 7), (124, 7), (228, 7), (207, 7), (208, 7), (209, 7),
         (95, 7), (122, 7)]

pool = {}
print("[1/4] 收集抽样框 ...")
for rid, day in SPECS:
    d = api("/x/web-interface/ranking/region", rid=rid, day=day)
    rows = d.get("data") or []
    print("    rid=%-4s day=%-3s code=%-5s n=%s" % (rid, day, d.get("code"), len(rows)))
    if d.get("code") != 0 or not isinstance(rows, list):
        continue
    for rank, r in enumerate(rows, 1):
        bv = s(r.get("bvid"))
        if not bv or bv in pool:
            continue
        pool[bv] = {
            "bvid": bv,
            "src": "%s/%s" % (rid, day),
            "rank": rank,
            "zone": s(r.get("typename")),
            "list_title": s(r.get("title")),
            "description": s(r.get("description")),
            "list_play": num(r.get("play")),
        }
print("    去重后候选 bvid：%d 条" % len(pool))

# 按来源轮流取样，避免只吃某一个榜单的头部
by_src = defaultdict(list)
for v in pool.values():
    by_src[v["src"]].append(v)
for k in by_src:
    by_src[k].sort(key=lambda x: x["rank"])
sample = []
for _ in range(200):
    if len(sample) >= TARGET_N:
        break
    progressed = False
    for k in sorted(by_src):
        if by_src[k] and len(sample) < TARGET_N:
            sample.append(by_src[k].pop(0))
            progressed = True
    if not progressed:
        break
print("    分层交错取样：%d 条" % len(sample))

# ---- 2. 逐条取完整元数据 ----------------------------------------------------
print("[2/4] 逐条请求 view 接口（限速 %.1fs）..." % PAUSE)
TZ = timezone(timedelta(hours=8))
videos = []
for i, smp in enumerate(sample, 1):
    d = api("/x/web-interface/view", bvid=smp["bvid"])
    x = d.get("data") or {}
    st = x.get("stat") or {}
    ow = x.get("owner") or {}
    mid = num(ow.get("mid"))
    pub = num(x.get("pubdate"))
    pub_dt = datetime.fromtimestamp(pub, TZ) if pub else None
    desc = s(x.get("desc")) or smp["description"]
    videos.append({
        "bvid": smp["bvid"],
        "title": s(x.get("title")) or smp["list_title"],
        "desc": desc.replace("\n", " ").replace("\r", " "),
        "subzone": s(x.get("tname")) or s(x.get("tname_v2")) or smp["zone"],
        "content_type": "",                       # 人工标注留空
        "duration": num(x.get("duration")),
        "pubdate": pub,
        "pub_datetime": pub_dt.strftime("%Y-%m-%d %H:%M:%S") if pub_dt else "",
        "days_since_pub": round((datetime.now(TZ) - pub_dt).total_seconds() / 86400, 2) if pub_dt else "",
        "pub_hour": pub_dt.hour if pub_dt else "",
        "pub_weekday": pub_dt.isoweekday() if pub_dt else "",
        "mid": mid or "",
        "official": s(ow.get("official")),
        "view": num(st.get("view")),
        "like": num(st.get("like")),
        "coin": num(st.get("coin")),
        "favorite": num(st.get("favorite")),
        "share": num(st.get("share")),
        "reply": num(st.get("reply")),
        "danmaku": num(st.get("danmaku")),
        "title_len": len(s(x.get("title")) or smp["list_title"]),
        "src": smp["src"],
        "list_play": smp["list_play"],
        "api_code": d.get("code"),
        "collected_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
    })
    if i % 10 == 0:
        print("    %d/%d" % (i, len(sample)))

# ---- 3. 粉丝数 --------------------------------------------------------------
print("[3/4] 请求粉丝数 ...")
mids = sorted({v["mid"] for v in videos if v["mid"]})
followers = {}
for m in mids:
    d = api("/x/relation/stat", vmid=m)
    followers[m] = num((d.get("data") or {}).get("follower"))
for v in videos:
    v["follower"] = followers.get(v["mid"], "")

# ---- 4. 落盘 ----------------------------------------------------------------
print("[4/4] 写出 CSV ...")
fields = ["bvid", "title", "desc", "subzone", "content_type", "duration",
          "pubdate", "pub_datetime", "days_since_pub", "pub_hour", "pub_weekday",
          "mid", "official", "view", "like", "coin", "favorite", "share",
          "reply", "danmaku", "follower", "title_len", "src", "list_play",
          "api_code", "collected_at"]

out_csv = os.path.join(RAW, "SC_pilot_videos_%s.csv" % TODAY)
with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(videos)

with open(os.path.join(RAW, "sample_bvid.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["bvid"])
    for v in videos:
        w.writerow([v["bvid"]])

with open(os.path.join(RAW, "SC_pilot_request_log.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["time", "endpoint", "params", "code", "n_items", "blocked"])
    w.writeheader()
    w.writerows(audit)

ok = [v for v in videos if v["api_code"] == 0 and v["view"] > 0]
blocked = [a for a in audit if a["blocked"]]
print("")
print("完成：%d 条采集，其中 code=0 且 view>0 的 %d 条" % (len(videos), len(ok)))
print("风控响应次数：%d（已跳过，未绕过）" % len(blocked))
print("粉丝数成功：%d / %d" % (sum(1 for x in followers.values() if x > 0), len(mids)))
print("输出：%s" % out_csv)
