#!/usr/bin/env python3
# SC_probe2.py — 抽样框扩量体检（第二轮，只读，可复现）
#
# 第一轮结论：ranking/region rid=124 只有 15 条去重候选、全部约 580 天前；
#             newlist 传子区 rid 返回 0；字幕接口未登录拿不到。
# 本轮要回答：锁定「社科·法律·心理」+ 近 1 年，能否凑到 120 条？
#   1) 榜单自带 create 字段的时间语义；
#   2) newlist 传「知识区大区 rid=36」翻页，按 tname 过滤目标子区的产出率；
#   3) dynamic/region、popular 等其它公开端点能否补充抽样框；
#   4) newlist 取到的视频逐条 view 是否带可用计数与 pubdate。
# 合规：仅公开元数据；间隔 >= 1.1s；遇风控跳过，不绕过。

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
TARGET = "社科·法律·心理"
log = []


def api(path, **params):
    url = BASE + path + "?" + urlencode(params)
    cmd = ["curl", "-s", "-m", "15", "-A", UA,
           "-H", "Referer: https://www.bilibili.com", url]
    try:
        d = json.loads(subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout)
    except Exception as e:  # noqa: BLE001
        d = {"code": -999, "error": str(e)}
    c = d.get("code")
    log.append((path, urlencode(params), c))
    time.sleep(PAUSE)
    return d


def human(pub):
    try:
        return datetime.fromtimestamp(int(pub), TZ).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return "?"


def days(pub):
    try:
        return round((datetime.now(TZ) - datetime.fromtimestamp(int(pub), TZ)).total_seconds() / 86400, 1)
    except (TypeError, ValueError):
        return "?"


print("本机时间:", datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %z"), "| 目标子区:", TARGET)
print("=" * 74)

# ---- 1. 榜单 create 字段语义 ------------------------------------------------
print("\n[1] ranking/region rid=124 的 create 字段（榜单自带投稿时间？）")
rank_pool = {}
for day in (3, 7):
    d = api("/x/web-interface/ranking/region", rid=124, day=day)
    rows = d.get("data") or []
    for r in rows:
        rank_pool[r.get("bvid")] = r
    for r in rows[:2]:
        print("    day=%s bvid=%s create=%r typename=%r play=%s" %
              (day, r.get("bvid"), r.get("create"), r.get("typename"), r.get("play")))
print("    榜单去重候选:", len(rank_pool))

# ---- 2. newlist 传大区 rid=36 翻页 ------------------------------------------
print("\n[2] newlist rid=36（知识区大区）翻页 ps=50")
new_pool = {}
for pn in range(1, 11):
    d = api("/x/web-interface/newlist", rid=36, pn=pn, ps=50)
    rows = (d.get("data") or {}).get("archives") or []
    if not rows:
        print("    pn=%-2s code=%-5s n=0  → 停止翻页" % (pn, d.get("code")))
        break
    tn = Counter(str(r.get("tname")) for r in rows)
    hit = sum(1 for r in rows if str(r.get("tname")) == TARGET)
    pubs = [r.get("pubdate") for r in rows if r.get("pubdate")]
    for r in rows:
        new_pool[r.get("bvid")] = r
    print("    pn=%-2s code=%-5s n=%-3s 目标子区=%-3s 累计=%-4s pub=%s~%s 分区=%s" %
          (pn, d.get("code"), len(rows), hit, len(new_pool),
           human(min(pubs)) if pubs else "-", human(max(pubs)) if pubs else "-",
           dict(tn.most_common(4))))
target_from_new = {b: r for b, r in new_pool.items() if str(r.get("tname")) == TARGET}
print("    → newlist 池中「%s」: %d 条" % (TARGET, len(target_from_new)))

# ---- 3. 其它公开端点 --------------------------------------------------------
print("\n[3] 其它候选抽样框")
for label, path, params in (
    ("dynamic/region rid=124", "/x/web-interface/dynamic/region", dict(rid=124, ps=50)),
    ("dynamic/region rid=36", "/x/web-interface/dynamic/region", dict(rid=36, ps=50)),
    ("popular ps=50 pn=1", "/x/web-interface/popular", dict(ps=50, pn=1)),
    ("popular ps=50 pn=2", "/x/web-interface/popular", dict(ps=50, pn=2)),
):
    d = api(path, **params)
    data = d.get("data") or {}
    rows = (data.get("archives") or data.get("list") or
            (data if isinstance(data, list) else []))
    tn = Counter(str(r.get("tname") or r.get("typename")) for r in rows)
    hit = sum(1 for r in rows if str(r.get("tname") or r.get("typename")) == TARGET)
    print("    %-26s code=%-5s n=%-3s 目标子区=%s 分区=%s" %
          (label, d.get("code"), len(rows), hit, dict(tn.most_common(4))))

# ---- 4. newlist 目标子区样本逐条 view ---------------------------------------
print("\n[4] newlist 目标子区样本逐条 view（计数 / pubdate / tname / desc）")
sample = list(target_from_new.items())[:5]
for bv, r in sample:
    d = api("/x/web-interface/view", bvid=bv)
    x = d.get("data") or {}
    st = x.get("stat") or {}
    print("    %s code=%s pub=%s (%s 天前) tname=%r view=%s like=%s desc_len=%s" %
          (bv, d.get("code"), human(x.get("pubdate")), days(x.get("pubdate")),
           x.get("tname"), st.get("view"), st.get("like"), len(str(x.get("desc") or ""))))

print("\n" + "=" * 74)
print("请求总数:", len(log), "| 风控次数:", sum(1 for _, _, c in log if c in BLOCK))
print("候选汇总: 榜单", len(rank_pool), "条(均为历史) | newlist 目标子区", len(target_from_new), "条")
