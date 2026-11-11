#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SW_collect.py — 按 bvid 抓取「每周必看」视频下的高赞公开评论.

数据源：Kaggle `zhuosun03/bilibili-must-watch`（许可标记 Unknown，仅作分析输入、不随仓库分发）。
样本框：data/raw/SW_sample_frame.csv（固定随机种子，split = dev / main / control）。

接口与合规边界
--------------
* 只用公开免登录端点 `GET /x/v2/reply?type=1&oid=<aid>&sort=2&pn=1&ps=20`。
* 不带任何 Cookie / token / WBI 签名；`/x/v2/reply/main` 返回 -352 时**直接放弃**，不绕过风控。
* 固定限速 1.1 秒/请求；非 200 或 code != 0 只记录、不重试、不换 IP、不加凭据。
* 只保存评论正文、点赞数、时间、公开评论 ID；**不保存用户名、mid、头像、签名等身份字段**。
* 未登录公开接口在 sort=2 下**最多返回 3 条热评**（实测 `data.replies` 恒为 3 条，
  `pn=2` / `sort=0` 返回空，`main` 系列需 WBI）。故 TOP_N=3，不是需求里期望的 10 条；
  这一限制如实写入日志与报告，不用楼中楼冒充高赞评论。

用法
----
    python3 SW_collect.py --split dev        # 词典开发集（不进入主分析）
    python3 SW_collect.py --split main       # 主分析样本
    python3 SW_collect.py --split control    # 非知识类对照
    python3 SW_collect.py --split main --limit 50   # 调试用
    python3 SW_collect.py --verify-bvid      # 抽样核验 bvid ↔ aid 一致性

断点续跑：已写入 SW_comments_<split>.csv 的 bvid 自动跳过。
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
import io

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")
EXTERNAL = os.path.join(ROOT, "data", "external")
OUT = os.path.join(ROOT, "output")
os.makedirs(RAW, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

ZIP_NAME = "SW_weekly-must-watch.zip"
CSV_IN_ZIP = "B_231009_1696842727.csv"
FRAME = os.path.join(RAW, "SW_sample_frame.csv")
VIDEOS = os.path.join(RAW, "SW_videos.csv")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
REPLY_URL = "https://api.bilibili.com/x/v2/reply?type=1&oid={aid}&sort=2&pn=1&ps=20"
VIEW_URL = "https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
SLEEP = 1.1
TOP_N = 3
SEED = 20261107

# 知识传播类白名单：与 SC_/SK_ 项目的知识传播框架对齐，且提高信息获取信号的基础率。
# 只看「视频类型」字段，不用标题关键词挑样本（避免按结果挑样本）。
KNOWLEDGE_ZONES = {
    "科学科普", "社科·法律·心理", "人文历史", "人文·历史", "数码", "校园学习",
    "财经商业", "科工机械", "计算机技术", "软件应用", "极客DIY",
    "野生技能协会", "音乐教学", "职业职场", "社会",
}
DEV_N = 60
CONTROL_N = 150

VIDEO_FIELDS = ["bvid", "aid", "split", "issue", "issue_desc", "title", "blurb",
                "zone", "up_mid", "duration", "view", "like", "coin", "favorite",
                "share", "reply", "danmaku", "pub_time"]
COMMENT_FIELDS = ["bvid", "aid", "split", "rank", "rpid", "like", "ctime", "message"]


def log(msg):
    line = "[%s] %s" % (dt.datetime.now().strftime("%H:%M:%S"), msg)
    print(line)
    with open(os.path.join(OUT, "SW_collect_log.txt"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def http_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return e.code, {"code": "HTTP%d" % e.code, "message": str(e)}
    except Exception as e:
        return "ERR", {"code": "ERR", "message": "%s: %s" % (type(e).__name__, e)}


def load_source():
    zp = os.path.join(EXTERNAL, ZIP_NAME)
    if not os.path.exists(zp):
        raise SystemExit("缺少 %s，请先运行 SW_download.py" % zp)
    with zipfile.ZipFile(zp) as z:
        raw = z.read(CSV_IN_ZIP)
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    bv = re.compile(r"(BV[0-9A-Za-z]{10})")
    out, seen = [], set()
    for r in rows:
        m = bv.search(r.get("视频链接") or "")
        if not m:
            continue
        bvid = m.group(1)
        if bvid in seen:            # 同一 bvid 可能出现在多期，保留首次出现
            continue
        seen.add(bvid)
        out.append({
            "bvid": bvid,
            "aid": (r.get("aid") or "").strip(),
            "issue": (r.get("期数") or "").strip(),
            "issue_desc": (r.get("期数描述") or "").strip(),
            "title": (r.get("标题") or "").strip(),
            "blurb": (r.get("视频标签") or "").strip(),   # 实际是榜单一句话推荐语，非标签
            "zone": (r.get("视频类型") or "").strip(),
            "up_mid": (r.get("up主_id") or "").strip(),
            "duration": (r.get("视频时长") or "").strip(),
            "view": (r.get("播放数") or "").strip(),
            "like": (r.get("点赞数") or "").strip(),
            "coin": (r.get("投币数") or "").strip(),
            "favorite": (r.get("收藏数") or "").strip(),
            "share": (r.get("分享数") or "").strip(),
            "reply": (r.get("评论数") or "").strip(),
            "danmaku": (r.get("弹幕数") or "").strip(),
            "pub_time": (r.get("发布时间") or "").strip(),
        })
    return out


def build_frame(rows):
    """固定种子划分 dev / main / control，写样本框；已存在则直接读取。"""
    if os.path.exists(FRAME):
        with open(FRAME, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    rng = random.Random(SEED)
    kn = [r for r in rows if r["zone"] in KNOWLEDGE_ZONES]
    non = [r for r in rows if r["zone"] not in KNOWLEDGE_ZONES]
    rng.shuffle(kn)
    rng.shuffle(non)
    frame = []
    for r in kn[:DEV_N]:
        frame.append(dict(r, split="dev"))
    for r in kn[DEV_N:]:
        frame.append(dict(r, split="main"))
    for r in non[:CONTROL_N]:
        frame.append(dict(r, split="control"))
    with open(FRAME, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=VIDEO_FIELDS)
        w.writeheader()
        w.writerows(frame)
    with open(VIDEOS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=VIDEO_FIELDS)
        w.writeheader()
        w.writerows(frame)
    log("样本框: dev=%d main=%d control=%d (种子 %d)" %
        (DEV_N, len(kn) - DEV_N, CONTROL_N, SEED))
    return frame


def read_done(path):
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {r["bvid"] for r in csv.DictReader(f)}


def collect(split, limit=None):
    frame = build_frame(load_source())
    target = [r for r in frame if r["split"] == split]
    if limit:
        target = target[:limit]
    path = os.path.join(RAW, "SW_comments_%s.csv" % split)
    done = read_done(path)
    todo = [r for r in target if r["bvid"] not in done]
    new_file = not os.path.exists(path)
    f = open(path, "a", encoding="utf-8", newline="")
    w = csv.DictWriter(f, fieldnames=COMMENT_FIELDS)
    if new_file:
        w.writeheader()
    log("开始 split=%s 目标=%d 已完成=%d 待采=%d" % (split, len(target), len(done), len(todo)))
    stats = {"ok": 0, "empty": 0, "fail": 0, "comments": 0}
    codes = {}
    try:
        for i, r in enumerate(todo, 1):
            status, j = http_json(REPLY_URL.format(aid=r["aid"]))
            code = str(j.get("code"))
            codes[code] = codes.get(code, 0) + 1
            if status != 200 or code != "0":
                stats["fail"] += 1
                log("  [%d/%d] %s code=%s %s" %
                    (i, len(todo), r["bvid"], code, str(j.get("message"))[:50]))
            else:
                reps = (j.get("data") or {}).get("replies") or []
                rows = []
                for rank, x in enumerate(reps[:TOP_N], 1):
                    msg = str((x.get("content") or {}).get("message", "") or "").strip()
                    if not msg:
                        continue
                    rows.append({
                        "bvid": r["bvid"], "aid": r["aid"], "split": split,
                        "rank": rank, "rpid": x.get("rpid", ""),
                        "like": x.get("like", 0), "ctime": x.get("ctime", ""),
                        "message": msg.replace("\r", " ").replace("\n", " "),
                    })
                w.writerows(rows)
                stats["comments"] += len(rows)
                stats["ok"] += bool(rows)
                stats["empty"] += (not rows)
            if i % 50 == 0:
                f.flush()
                log("  进度 %d/%d | 成功 %d | 评论 %d | code=%s" %
                    (i, len(todo), stats["ok"], stats["comments"], codes))
            time.sleep(SLEEP)
    finally:
        f.close()
    log("完成 split=%s | 成功视频 %d | 空 %d | 失败 %d | 评论 %d | code=%s" %
        (split, stats["ok"], stats["empty"], stats["fail"], stats["comments"], codes))
    return stats


def verify_bvid(n=20):
    """抽样用公开 view 接口核对数据集里的 aid 是否与 bvid 对应（不绕过任何风控）。"""
    frame = build_frame(load_source())
    rng = random.Random(SEED + 1)
    sample = rng.sample(frame, min(n, len(frame)))
    ok = bad = err = 0
    lines = ["bvid,aid_in_kaggle,aid_from_view,match"]
    for r in sample:
        status, j = http_json(VIEW_URL.format(bvid=r["bvid"]))
        if status == 200 and str(j.get("code")) == "0":
            av = str((j.get("data") or {}).get("aid", ""))
            m = (av == r["aid"])
            ok += m
            bad += (not m)
            lines.append("%s,%s,%s,%s" % (r["bvid"], r["aid"], av, int(m)))
        else:
            err += 1
            lines.append("%s,%s,ERR_%s,0" % (r["bvid"], r["aid"], j.get("code")))
        time.sleep(SLEEP)
    p = os.path.join(OUT, "SW_bvid_aid_check.csv")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log("bvid↔aid 核验: 一致 %d / 不一致 %d / 接口错误 %d → %s" %
        (ok, bad, err, os.path.relpath(p, ROOT)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "main", "control"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--verify-bvid", action="store_true")
    a = ap.parse_args()
    if a.verify_bvid:
        verify_bvid()
    elif a.split:
        collect(a.split, a.limit)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
