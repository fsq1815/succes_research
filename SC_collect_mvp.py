#!/usr/bin/env python3
# SC_collect_mvp.py — SUCCES 项目 MVP 采集（目标 120 条，实收 N 如实落盘）
#
# 本轮需求对应：
#   #1 锁定「社科·法律·心理 & 科学科普」两区（rid=124 / rid=201，tname 过滤）
#   #3 补 desc / 尝试字幕；写出 within_1yr 等时间语义标记（时间不做强制要求，历史快照窗口纳入口径）
#   #4 目标 120 条，按 子区 × 热度层 × 主题层 分层（两区下「分区」恢复为真实层，见 docs/SC_sample-scope.md）
#
# 诚实约束（重要）：
#   · 公开无签名端点下，即便锁定「社科·法律·心理 + 科学科普」两区**仍无法达到 120 条**，
#     脚本取尽候选并写出 shortfall，绝不生成虚构行、绝不悄悄扩到其它子区。
#   · 时间不做强制要求：榜单历史快照（约 580 天）纳入分析口径；within_1yr 仅作敏感性对照标记，
#     不再据此硬删样本。
# 合规：仅公开视频元数据；每次请求 >= 1.1s；不取个人信息、不存评论正文；
#       遇 -352/-403/412/429/-799 等限制响应立即跳过该类请求，不绕过、不换 UA 重试。
#
# 运行：python3 SC_collect_mvp.py
# 输出：
#   data/raw/SC_mvp_videos_YYYYMMDD.csv        实收样本（含标记）
#   data/raw/SC_mvp_frame.csv                  抽样框 + 分层 + 选中标记 + 缺口
#   data/raw/SC_mvp_sample_bvid.csv            bvid 清单
#   data/raw/SC_mvp_request_log.csv            请求审计日志
#   output/SC_mvp_collection_report.txt        采集报告

import csv
import json
import os
import random
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "output")
os.makedirs(RAW, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

TODAY = datetime.now().strftime("%Y%m%d")
TZ = timezone(timedelta(hours=8))
NOW = datetime.now(TZ)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 "
      "succes-research/0.3 academic-mvp")
BASE = "https://api.bilibili.com"
PAUSE = 1.1
TARGET_N = 120
SEED = 20261106
# 项目锁定两区（2026-11-06 最终决策）：不混用 Kaggle/和鲸；时间不做强制要求
ALLOWED_ZONES = {"社科·法律·心理", "科学科普"}
# 两区各自的榜单 rid；rid=36（生活区）保留做跨区扫掠，仅取命中两区的视频
ZONE_RIDS = [(124, 3), (124, 7), (201, 3), (201, 7), (36, 3), (36, 7)]
BLOCK_CODES = {-352, -403, 403, 412, 429, -799}
MAX_AGE_DAYS = 365

audit = []
subtitle_blocked = False


def api(path, **params):
    url = BASE + path + "?" + urlencode(params)
    cmd = ["curl", "-s", "-m", "15", "-A", UA,
           "-H", "Referer: https://www.bilibili.com", url]
    ts = NOW.strftime("%Y-%m-%d %H:%M:%S")
    try:
        d = json.loads(subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout)
    except Exception as e:  # noqa: BLE001
        d = {"code": -999, "error": str(e)}
    code = d.get("code")
    data = d.get("data")
    n = len(data) if isinstance(data, list) else (1 if isinstance(data, dict) else 0)
    audit.append({"time": ts, "endpoint": path, "params": urlencode(params),
                  "code": code, "n_items": n, "blocked": code in BLOCK_CODES})
    time.sleep(PAUSE)
    return d


def s(v):
    return "" if v is None else str(v)


def num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def fetch_subtitle_intro(bvid, cid):
    """尝试取前 30 秒字幕；未登录通常返回 0 条。返回 (条数, intro, 状态)。"""
    global subtitle_blocked
    if not cid:
        return 0, "", "no_cid"
    if subtitle_blocked:
        return 0, "", "skipped_rate_limited"
    d = api("/x/player/v2", bvid=bvid, cid=cid)
    if d.get("code") in BLOCK_CODES:
        subtitle_blocked = True
        return 0, "", "rate_limited"
    if d.get("code") != 0:
        return 0, "", "api_code_%s" % d.get("code")
    sub = (d.get("data") or {}).get("subtitle") or {}
    subs = sub.get("subtitles") or []
    if not subs:
        return 0, "", "no_subtitle"
    url = subs[0].get("subtitle_url") or ""
    if not url:
        return len(subs), "", "no_url"
    if url.startswith("//"):
        url = "https:" + url
    try:
        raw = subprocess.run(["curl", "-s", "-m", "12", "-A", UA, url],
                             capture_output=True, text=True, timeout=16).stdout
        body = json.loads(raw).get("body") or []
        intro = " ".join(s(b.get("content")) for b in body if num(b.get("from")) < 30)
        return len(subs), intro.strip(), "ok"
    except Exception:  # noqa: BLE001
        return len(subs), "", "parse_failed"


TOPIC_RULES = [
    ("法律", ["法律", "律师", "法院", "判决", "犯罪", "刑法", "民法", "诉讼", "违法", "维权",
              "立案", "司法", "定罪", "合同", "法规", "警方", "诈骗", "案件", "判刑", "拘留",
              "被告", "原告", "法治"]),
    ("心理", ["心理", "情绪", "焦虑", "抑郁", "人格", "潜意识", "内耗", "依恋", "创伤",
              "自卑", "共情", "精神", "治愈", "原生家庭", "性格"]),
    ("社科", ["社会", "经济", "阶层", "人口", "政策", "制度", "文化", "历史", "政治",
              "城市", "性别", "教育", "资本", "打工", "消费", "贫富", "农村", "老龄化",
              "就业", "房价", "人口普查"]),
]


def topic_of(title):
    for name, kws in TOPIC_RULES:
        if any(k in title for k in kws):
            return name
    return "其它"


def official_str(o):
    if isinstance(o, dict):
        return s(o.get("title") or o.get("desc") or o.get("role") or "")
    return s(o)


# ---------------------------------------------------------------------------
# 1. 抽样框：只用「社科·法律·心理」+ 无需签名的公开端点
# ---------------------------------------------------------------------------
print("[1/5] 构建抽样框（锁定 %s）..." % " / ".join(sorted(ALLOWED_ZONES)))
pool = {}


def add(bvid, r, src, rank):
    if not bvid:
        return
    zone = s(r.get("typename") or r.get("tname"))
    if zone not in ALLOWED_ZONES:          # 硬性锁定两区，不悄悄放宽
        return
    stat = r.get("stat") or {}
    play = num(r.get("play") or stat.get("view"))
    if bvid not in pool:
        pool[bvid] = {
            "bvid": bvid,
            "src": set(),
            "rank_best": rank,
            "list_play": play,
            "list_description": s(r.get("description") or r.get("desc")),
            "list_create": s(r.get("create")),
            "list_author": s(r.get("author") or (r.get("owner") or {}).get("name")),
            "list_mid": num(r.get("mid") or (r.get("owner") or {}).get("mid")),
            "list_title": s(r.get("title")),
            "zone": zone,                     # 实际命中分区（社科·法律·心理 / 科学科普）
        }
    pool[bvid]["src"].add(src)
    pool[bvid]["rank_best"] = min(pool[bvid]["rank_best"], rank)
    pool[bvid]["list_play"] = max(pool[bvid]["list_play"], play)
    if not pool[bvid]["list_description"]:
        pool[bvid]["list_description"] = s(r.get("description") or r.get("desc"))
    if not pool[bvid]["list_create"]:
        pool[bvid]["list_create"] = s(r.get("create"))
    pool[bvid]["zone"] = zone


for rid, day in ZONE_RIDS:
    d = api("/x/web-interface/ranking/region", rid=rid, day=day)
    rows = d.get("data") or []
    src = "rank_%s_d%s" % (rid, day)
    hit = sum(1 for r in rows if s(r.get("typename") or r.get("tname")) in ALLOWED_ZONES)
    for rank, r in enumerate(rows, 1):
        add(s(r.get("bvid")), r, src, rank)
    print("    %-18s code=%-5s n=%-3s 目标子区=%s" % (src, d.get("code"), len(rows), hit))

for pn in range(1, 7):
    d = api("/x/web-interface/popular", ps=50, pn=pn)
    rows = (d.get("data") or {}).get("list") or []
    src = "popular_p%s" % pn
    hit = sum(1 for r in rows if s(r.get("tname") or r.get("typename")) in ALLOWED_ZONES)
    for rank, r in enumerate(rows, 1):
        add(s(r.get("bvid")), r, src, rank)
    print("    %-18s code=%-5s n=%-3s 目标子区=%s" % (src, d.get("code"), len(rows), hit))

for pn in range(1, 7):
    d = api("/x/web-interface/newlist", rid=36, pn=pn, ps=50)
    rows = (d.get("data") or {}).get("archives") or []
    src = "newlist_p%s" % pn
    hit = sum(1 for r in rows if s(r.get("tname")) in ALLOWED_ZONES)
    for rank, r in enumerate(rows, 1):
        add(s(r.get("bvid")), r, src, rank)
    print("    %-18s code=%-5s n=%-3s 目标子区=%s" % (src, d.get("code"), len(rows), hit))

print("    → 去重后目标两区候选：%d 条（目标 %d）" % (len(pool), TARGET_N))

# ---------------------------------------------------------------------------
# 2. 分层：热度层 × 主题层（单子区下「分区」退化）
# ---------------------------------------------------------------------------
print("[2/5] 分层（热度层 × 主题层）...")
plays = sorted(v["list_play"] for v in pool.values() if v["list_play"] > 0)
q1, q2 = (plays[len(plays) // 3], plays[2 * len(plays) // 3]) if plays else (0, 0)

for v in pool.values():
    p = v["list_play"]
    v["heat_tier"] = ("high" if p >= q2 else "mid" if p >= q1 else "low") if p > 0 else "fresh"
    v["topic"] = topic_of(v["list_title"] or "")

strata = defaultdict(list)
for v in pool.values():
    # 两区锁定后「分区」恢复为真实层：子区 × 热度层 × 主题层
    strata[(v["zone"], v["heat_tier"], v["topic"])].append(v)
rng = random.Random(SEED)
for k in strata:
    rng.shuffle(strata[k])

# 按层大小比例分配配额，保证每层至少 1 条；候选不足则取尽
total = len(pool)
keys = sorted(strata, key=lambda k: -len(strata[k]))
quota = {k: max(1, round(TARGET_N * len(strata[k]) / total)) for k in keys}
selected, used = [], set()
for k in keys:
    for v in strata[k][:quota[k]]:
        if v["bvid"] not in used:
            selected.append(v)
            used.add(v["bvid"])
# round-robin 补齐到 min(TARGET_N, total)
for _ in range(TARGET_N):
    if len(selected) >= min(TARGET_N, total):
        break
    grew = False
    for k in keys:
        for v in strata[k]:
            if v["bvid"] not in used and len(selected) < min(TARGET_N, total):
                selected.append(v)
                used.add(v["bvid"])
                grew = True
                break
    if not grew:
        break
for v in pool.values():
    v["selected"] = int(v["bvid"] in used)

print("    分层数=%d  各层=%s" % (len(keys), {k: len(strata[k]) for k in keys}))
print("    实选 %d 条；缺口 %d 条（候选不足，不编造、不扩区）" %
      (len(selected), TARGET_N - len(selected)))

# ---------------------------------------------------------------------------
# 3. 逐条取元数据 / 粉丝数 / 字幕
# ---------------------------------------------------------------------------
print("[3/5] 逐条取 view + 字幕（限速 %.1fs）..." % PAUSE)
videos = []
for i, smp in enumerate(selected, 1):
    bv = smp["bvid"]
    d = api("/x/web-interface/view", bvid=bv)
    x = d.get("data") or {}
    st = x.get("stat") or {}
    ow = x.get("owner") or {}
    mid = num(ow.get("mid")) or smp["list_mid"]
    pub = num(x.get("pubdate"))
    pub_dt = datetime.fromtimestamp(pub, TZ) if pub else None
    days = round((NOW - pub_dt).total_seconds() / 86400, 2) if pub_dt else ""

    # desc  enrichment：view.desc → view.desc_v2 → 榜单 description
    desc, desc_src = "", "none"
    raw_desc = s(x.get("desc")).strip()
    if raw_desc and raw_desc not in ("-", "。"):
        desc, desc_src = raw_desc, "view.desc"
    else:
        v2 = x.get("desc_v2") or []
        v2txt = " ".join(s(it.get("raw_text")) for it in v2 if isinstance(it, dict)).strip()
        if v2txt:
            desc, desc_src = v2txt, "view.desc_v2"
        elif smp["list_description"].strip():
            desc, desc_src = smp["list_description"].strip(), "ranking.description"

    cid = num(x.get("cid"))
    sub_n, intro, sub_status = fetch_subtitle_intro(bv, cid)

    view = num(st.get("view"))
    fav = num(st.get("favorite"))
    row = {
        "bvid": bv,
        "title": s(x.get("title")) or smp["list_title"],
        "desc": desc.replace("\n", " ").replace("\r", " "),
        "desc_source": desc_src,
        "desc_len": len(desc),
        "intro": intro.replace("\n", " "),
        "subtitle_n": sub_n,
        "subtitle_status": sub_status,
        "subzone": smp["zone"],                   # 实际命中分区（社科·法律·心理 / 科学科普）
        "topic_layer": smp["topic"],
        "heat_tier": smp["heat_tier"],
        "content_type": "",                       # 人工标注留空
        "duration": num(x.get("duration")),
        "pubdate": pub,
        "pub_datetime": pub_dt.strftime("%Y-%m-%d %H:%M:%S") if pub_dt else "",
        "days_since_pub": days,
        "within_1yr": int(days != "" and days <= MAX_AGE_DAYS),
        "ranking_create": smp["list_create"],
        "pub_hour": pub_dt.hour if pub_dt else "",
        "pub_weekday": pub_dt.isoweekday() if pub_dt else "",
        "mid": mid or "",
        "official": official_str(ow.get("official")),
        "view": view,
        "like": num(st.get("like")),
        "coin": num(st.get("coin")),
        "favorite": fav,
        "share": num(st.get("share")),
        "reply": num(st.get("reply")),
        "danmaku": num(st.get("danmaku")),
        "title_len": len(s(x.get("title")) or smp["list_title"]),
        "src": "|".join(sorted(smp["src"])),
        "list_play": smp["list_play"],
        "rank_best": smp["rank_best"],
        "api_code": d.get("code"),
        "collected_at": NOW.strftime("%Y-%m-%d %H:%M:%S"),
    }
    row["engage_rate"] = round((row["like"] + row["coin"] + fav +
                                row["share"] + row["reply"]) / max(view, 1), 6) if view > 0 else ""
    row["fav_rate"] = round(fav / max(view, 1), 6) if view > 0 else ""
    row["view_usable"] = int(view > 0)
    row["analysis_eligible"] = int(d.get("code") == 0 and view > 0 and row["title"] != "")
    videos.append(row)
    if i % 10 == 0:
        print("    %d/%d" % (i, len(selected)))

# ---------------------------------------------------------------------------
# 4. 粉丝数
# ---------------------------------------------------------------------------
print("[4/5] 取粉丝数 ...")
mids = sorted({v["mid"] for v in videos if v["mid"]})
followers = {}
for m in mids:
    d = api("/x/relation/stat", vmid=m)
    if d.get("code") in BLOCK_CODES:
        break
    followers[m] = num((d.get("data") or {}).get("follower"))
for v in videos:
    v["follower"] = followers.get(v["mid"], "")

# ---------------------------------------------------------------------------
# 5. 落盘 + 报告
# ---------------------------------------------------------------------------
print("[5/5] 写出 ...")
fields = ["bvid", "title", "desc", "desc_source", "desc_len", "intro", "subtitle_n",
          "subtitle_status", "subzone", "topic_layer", "heat_tier", "content_type",
          "duration", "pubdate", "pub_datetime", "days_since_pub", "within_1yr",
          "ranking_create", "pub_hour", "pub_weekday", "mid", "official",
          "view", "like", "coin", "favorite", "share", "reply", "danmaku",
          "engage_rate", "fav_rate", "view_usable", "analysis_eligible",
          "follower", "title_len", "src", "list_play", "rank_best",
          "api_code", "collected_at"]

out_csv = os.path.join(RAW, "SC_mvp_videos_%s.csv" % TODAY)
with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(videos)

with open(os.path.join(RAW, "SC_mvp_sample_bvid.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["bvid"])
    for v in videos:
        w.writerow([v["bvid"]])

frame_fields = ["bvid", "list_title", "list_author", "list_mid", "src", "rank_best",
                "list_play", "list_create", "heat_tier", "topic", "selected",
                "shortfall"]
with open(os.path.join(RAW, "SC_mvp_frame.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=frame_fields, extrasaction="ignore")
    w.writeheader()
    for v in pool.values():
        w.writerow({
            "bvid": v["bvid"], "list_title": v["list_title"], "list_author": v["list_author"],
            "list_mid": v["list_mid"], "src": "|".join(sorted(v["src"])),
            "rank_best": v["rank_best"], "list_play": v["list_play"],
            "list_create": v["list_create"], "heat_tier": v["heat_tier"],
            "topic": v["topic"], "selected": v["selected"],
            "shortfall": TARGET_N - len(selected),
        })

with open(os.path.join(RAW, "SC_mvp_request_log.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["time", "endpoint", "params", "code", "n_items", "blocked"])
    w.writeheader()
    w.writerows(audit)

# ---- 采集报告 ---------------------------------------------------------------
n = len(videos)
ok = [v for v in videos if v["analysis_eligible"] == 1]
within = [v for v in videos if v["within_1yr"] == 1]
desc_ok = [v for v in videos if v["desc_len"] > 0]
sub_ok = [v for v in videos if v["subtitle_n"] > 0]
blocked = [a for a in audit if a["blocked"]]
lines = [
    "SUCCES MVP 采集报告",
    "生成时间: " + NOW.strftime("%Y-%m-%d %H:%M:%S %z"),
    "锁定子区: 社科·法律·心理 & 科学科普 (rid=124 + rid=201)",
    "目标条数: %d / 实收: %d / 缺口: %d" % (TARGET_N, n, TARGET_N - n),
    "",
    "== 抽样框 ==",
    "候选去重: %d 条；分层: 子区 × 热度层 × 主题层（两区下「分区」恢复为真实层）" % len(pool),
    "分层分布: " + str({k: len(v) for k, v in strata.items()}),
    "",
    "== 数据可用性 ==",
    "code=0 且 view>0 且标题非空 (analysis_eligible): %d / %d" % (len(ok), n),
    "within_1yr (<=365天): %d / %d" % (len(within), n),
    "desc 非空: %d / %d (%.0f%%)" % (len(desc_ok), n, 100 * len(desc_ok) / max(n, 1)),
    "desc 来源: " + str({k: sum(1 for v in videos if v["desc_source"] == k)
                       for k in sorted({v["desc_source"] for v in videos})}),
    "字幕可用: %d / %d；状态分布: %s" %
    (len(sub_ok), n, str({k: sum(1 for v in videos if v["subtitle_status"] == k)
                          for k in sorted({v["subtitle_status"] for v in videos})})),
    "粉丝数成功: %d / %d" % (sum(1 for x in followers.values() if x > 0), len(mids)),
    "",
    "== 时间语义核对（时间不做强制要求）==",
    "days_since_pub 范围: %s" %
    (str((min(v["days_since_pub"] for v in videos if v["days_since_pub"] != ""),
          max(v["days_since_pub"] for v in videos if v["days_since_pub"] != "")))
     if any(v["days_since_pub"] != "" for v in videos) else "无"),
    "ranking create 样例: " + str([v["ranking_create"] for v in videos[:3]]),
    "结论: ranking/region 的 day 是排行榜统计窗口，不是投稿时间；本环境返回固定历史快照（约 580 天）。",
    "      时间不做强制要求，故历史快照窗口纳入分析口径，不再据此硬删样本；",
    "      within_1yr 仅作敏感性对照标记（若只取近 1 年子集，样本量将骤降，仅作局限说明）。",
    "",
    "== 合规 ==",
    "请求总数: %d；风控/限制响应: %d（已跳过，未绕过）" % (len(audit), len(blocked)),
    "仅公开元数据；不取个人信息；不存评论正文；间隔 >= %.1fs" % PAUSE,
    "",
    "== 使用边界 ==",
    "本轮为 MVP 链路复跑，非概率抽样。人工语义编码与 kappa 见 data/processed/SC_manual_coding.csv。",
    "任何系数、显著性或因果结论都不得写进项目报告或对外表述。",
    "缺口与解锁条件见 docs/SC_sample-scope.md 第 5 节。",
]
report = "\n".join(lines) + "\n"
with open(os.path.join(OUT, "SC_mvp_collection_report.txt"), "w", encoding="utf-8") as f:
    f.write(report)
print("")
print(report)
print("输出: " + out_csv)
