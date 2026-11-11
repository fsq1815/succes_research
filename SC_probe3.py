#!/usr/bin/env python3
# SC_probe3.py — 扩量路径体检（第三轮，只读，可复现）
#
# 前两轮结论：
#   · rid=124 = 社科·法律·心理；ranking/region 仅 15 条去重，create 显示均为 2025-04（约 580 天前）；
#   · newlist 翻页 pn 几乎不生效（10 页累计仅 54 条），目标子区仅 8 条且 view≈0（当天新稿）；
#   · popular 几乎不含目标子区；dynamic/region -404；字幕 player/v2 未登录返回 0 条。
# 本轮：测试「种子 UP 主 → 其投稿列表」的滚雪球抽样能否补足近 1 年、有真实播放量的目标子区样本。
# 合规：仅公开元数据；间隔 >= 1.1s；遇 -352/403/412/429 跳过，绝不绕过签名或风控。

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


print("本机时间:", datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %z"), "| 目标:", TARGET)
print("=" * 72)

# 取榜单种子 UP 主
d = api("/x/web-interface/ranking/region", rid=124, day=7)
rows = d.get("data") or []
seeds = [(r.get("mid"), r.get("bvid"), r.get("author")) for r in rows[:5] if r.get("mid")]
print("\n[1] 榜单种子 UP 主:", len(seeds))
for m, bv, a in seeds:
    print("    mid=%s bvid=%s author=%s" % (m, bv, a))

# 测试 space/arc/search（投稿列表）
print("\n[2] x/space/arc/search 投稿列表（是否需要 WBI 签名）")
for mid, _, _ in seeds[:3]:
    d = api("/x/space/arc/search", mid=mid, pn=1, ps=30)
    data = d.get("data") or {}
    vl = (data.get("list") or {}).get("vlist") or []
    print("    mid=%s code=%-5s n=%-3s message=%r" % (mid, d.get("code"), len(vl), d.get("message")))
    if vl:
        for v in vl[:2]:
            print("        bvid=%s pub=%s tname=%r play=%s" %
                  (v.get("bvid"), human(v.get("created")), v.get("tname"), v.get("play")))

# 测试更多 day 取值与 arc_type
print("\n[3] ranking/region rid=124 其它 day / arc_type 组合")
for day in (1, 3, 5, 7, 30):
    d = api("/x/web-interface/ranking/region", rid=124, day=day)
    r = d.get("data") or []
    print("    day=%-3s code=%-5s n=%s" % (day, d.get("code"), len(r)))

# 测试 newlist 是否支持不同 ps / 其它 rid 组合
print("\n[4] newlist 其它参数组合")
for label, kw in (
    ("rid=124 ps=20", dict(rid=124, pn=1, ps=20)),
    ("rid=36 type=1", dict(rid=36, pn=1, ps=50, type=1)),
    ("rid=36 ps=100", dict(rid=36, pn=1, ps=100)),
):
    d = api("/x/web-interface/newlist", **kw)
    r = (d.get("data") or {}).get("archives") or []
    tn = Counter(str(x.get("tname")) for x in r)
    print("    %-16s code=%-5s n=%-3s 目标子区=%s" %
          (label, d.get("code"), len(r), tn.get(TARGET, 0)))

print("\n" + "=" * 72)
print("请求总数:", len(log), "| 风控/签名失败次数:", sum(1 for _, _, c in log if c in BLOCK))
