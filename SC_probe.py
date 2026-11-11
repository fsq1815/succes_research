#!/usr/bin/env python3
# SC_probe.py — 接口体检（可复现，只读，不落盘业务数据）
#
# 目的：在写正式采集脚本之前，把四件事实查清楚：
#   1) 「社科·法律·心理」对应的 rid 与 typename 到底是什么；
#   2) ranking/region 的 day 语义 —— 榜单里的视频究竟是不是近 N 天投稿；
#   3) 单一子区能否凑够 120 条（榜单条数 + newlist 翻页能力）；
#   4) 字幕接口 x/player/v2 在未登录状态下是否可用、desc_v2 能否补简介。
# 合规：仅公开元数据；每次请求间隔 >= 1.1 秒；遇 -352/403/412/429 立即跳过，不绕过。
#
# 运行：python3 SC_probe.py

import json
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

BASE = "https://api.bilibili.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 "
      "succes-research/0.2 academic-probe")
PAUSE = 1.1
TZ = timezone(timedelta(hours=8))
BLOCK = {-352, -403, 403, 412, 429}
log = []


def api(path, **params):
    url = BASE + path + "?" + urlencode(params)
    cmd = ["curl", "-s", "-m", "15", "-A", UA,
           "-H", "Referer: https://www.bilibili.com", url]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
        d = json.loads(out)
    except Exception as e:  # noqa: BLE001
        d = {"code": -999, "error": str(e)}
    code = d.get("code")
    log.append((path, urlencode(params), code))
    time.sleep(PAUSE)
    if code in BLOCK:
        print("    !! 风控响应 %s，按合规要求跳过" % code)
    return d


def ts_human(pub):
    try:
        return datetime.fromtimestamp(int(pub), TZ).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return "?"


def days_ago(pub):
    try:
        return round((datetime.now(TZ) - datetime.fromtimestamp(int(pub), TZ)).total_seconds() / 86400, 1)
    except (TypeError, ValueError):
        return "?"


print("本机时间:", datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %z"))
print("=" * 72)

# ---- 1. 锁定「社科·法律·心理」的 rid ---------------------------------------
print("\n[1] 知识区各 rid 的 typename（确认社科·法律·心理 = ?）")
RIDS = [124, 201, 228, 207, 208, 209, 95, 122]
rid_zone = {}
for rid in RIDS:
    d = api("/x/web-interface/ranking/region", rid=rid, day=7)
    rows = d.get("data") or []
    zones = Counter(str(r.get("typename")) for r in rows)
    rid_zone[rid] = zones.most_common(1)[0][0] if zones else "-"
    print("    rid=%-4s code=%-5s n=%-3s typename=%s" %
          (rid, d.get("code"), len(rows), dict(zones)))

TARGET_ZONE = "社科·法律·心理"
target_rids = [r for r, z in rid_zone.items() if TARGET_ZONE in z]
print("    → 命中「%s」的 rid: %s" % (TARGET_ZONE, target_rids or "无（需回退到 rid=36 全域再按 tname 过滤）"))

# ---- 2. 榜单 day 语义核对 ---------------------------------------------------
print("\n[2] ranking/region day 语义：同一 rid 不同 day 的 bvid 集合与发布时间")
probe_rid = target_rids[0] if target_rids else 36
rank_bv = {}
for day in (3, 7, 30):
    d = api("/x/web-interface/ranking/region", rid=probe_rid, day=day)
    rows = d.get("data") or []
    rank_bv[day] = [r.get("bvid") for r in rows]
    print("    rid=%s day=%-3s code=%-5s n=%s  榜单自带字段=%s" %
          (probe_rid, day, d.get("code"), len(rows),
           sorted(rows[0].keys())[:12] if rows else []))
for a, b in ((3, 7), (7, 30)):
    sa, sb = set(rank_bv[a]), set(rank_bv[b])
    print("    day=%s vs day=%s 交集 %d / 并集 %d" % (a, b, len(sa & sb), len(sa | sb)))

# 从榜单取 4 条，逐条 view 核对真实 pubdate / tname / desc
print("\n[2b] 榜单样本逐条 view → 真实 pubdate 与 tname")
rank_sample = [b for b in rank_bv.get(7, []) if b][:4]
rank_meta = []
for bv in rank_sample:
    d = api("/x/web-interface/view", bvid=bv)
    x = d.get("data") or {}
    st = x.get("stat") or {}
    rank_meta.append(x)
    print("    %s code=%s pub=%s (%s 天前) tname=%s view=%s desc_len=%s desc_v2=%s" %
          (bv, d.get("code"), ts_human(x.get("pubdate")), days_ago(x.get("pubdate")),
           x.get("tname"), (st.get("view")), len(str(x.get("desc") or "")),
           "有" if x.get("desc_v2") else "无"))

# ---- 3. newlist 翻页能力（近 1 年新投稿的抽样框）-----------------------------
print("\n[3] newlist 翻页：rid=%s, ps=50" % probe_rid)
new_bv = []
for pn in (1, 2, 3, 4, 5, 6):
    d = api("/x/web-interface/newlist", rid=probe_rid, pn=pn, ps=50)
    rows = (d.get("data") or {}).get("archives") or []
    ids = [r.get("bvid") for r in rows]
    new_bv.extend(ids)
    tn = Counter(str(r.get("tname")) for r in rows)
    pubs = [r.get("pubdate") for r in rows if r.get("pubdate")]
    print("    pn=%s code=%-5s n=%-3s tname=%s pub=%s~%s" %
          (pn, d.get("code"), len(rows), dict(tn),
           ts_human(min(pubs)) if pubs else "-", ts_human(max(pubs)) if pubs else "-"))
    if not rows:
        break
print("    → 6 页累计候选 %d 条，去重后 %d 条" % (len(new_bv), len(set(new_bv))))

print("\n[3b] newlist 样本逐条 view → 计数是否可用（newlist 自带 stat 全 0）")
new_meta = []
for bv in [b for b in new_bv if b][:4]:
    d = api("/x/web-interface/view", bvid=bv)
    x = d.get("data") or {}
    st = x.get("stat") or {}
    new_meta.append(x)
    print("    %s code=%s pub=%s (%s 天前) tname=%s view=%s like=%s desc_len=%s" %
          (bv, d.get("code"), ts_human(x.get("pubdate")), days_ago(x.get("pubdate")),
           x.get("tname"), st.get("view"), st.get("like"), len(str(x.get("desc") or ""))))

# ---- 4. 字幕与 desc_v2 可用性 ----------------------------------------------
print("\n[4] 字幕接口 x/player/v2（未登录）与简介补充")
for x in (rank_meta[:1] + new_meta[:1]):
    bv, cid = x.get("bvid"), x.get("cid")
    if not (bv and cid):
        continue
    d = api("/x/player/v2", bvid=bv, cid=cid)
    sub = (d.get("data") or {}).get("subtitle") or {}
    subs = sub.get("subtitles") or []
    print("    %s cid=%s code=%s allow_submit=%s 字幕条数=%s %s" %
          (bv, cid, d.get("code"), sub.get("allow_submit"), len(subs),
           [(s.get("lan_doc"), str(s.get("subtitle_url"))[:60]) for s in subs[:2]]))

# ---- 汇总 -------------------------------------------------------------------
print("\n" + "=" * 72)
print("请求总数:", len(log), " | 风控次数:", sum(1 for _, _, c in log if c in BLOCK))
print("结论要点：")
print("  · 目标子区 rid:", target_rids)
print("  · 榜单候选（去重）:", len(set(b for v in rank_bv.values() for b in v if b)))
print("  · newlist 候选（去重）:", len(set(new_bv)))
print("  · 榜单 pubdate 天数:", [days_ago(x.get("pubdate")) for x in rank_meta])
print("  · newlist pubdate 天数:", [days_ago(x.get("pubdate")) for x in new_meta])
