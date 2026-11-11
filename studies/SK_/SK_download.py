#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SK_download.py — 从 Kaggle 公开下载端点获取本项目的两个数据源（免登录）.

用法：
    python3 SK_download.py            # 已存在则跳过
    python3 SK_download.py --force    # 强制重下

两个数据集均为公开且许可明确（MIT / Apache 2.0）；脚本只用 Kaggle 的公开下载端点，
不使用 API token、不绕过任何访问控制。原始 zip 不提交仓库（见 .gitignore），
由本脚本重建；清单 data/external/SK_download_manifest.csv 记录 URL、时间与 SHA-256。
"""
import argparse
import csv
import datetime as dt
import hashlib
import os
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
EXTERNAL = os.path.join(ROOT, "data", "external")

DATASETS = [
    dict(
        key="D1",
        ref="sylviawyon/bilibili-2025-top-100-creators-video-dataset",
        license="MIT",
        note="2025 TOP100 creators, 5,759 videos, xlsx",
        expect_file="video_details.xlsx",
    ),
    dict(
        key="D2",
        ref="calefctinpan/bilibili-zhang-xuefeng-video-records",
        license="Apache-2.0",
        note="education-topic videos, 1,881 rows, csv",
        expect_file="bilibili_zhangxuefeng_videos.csv",
    ),
]

UA = "succes-kaggle/0.1 academic-reproduction (public dataset download)"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="覆盖已存在的 zip")
    args = ap.parse_args()
    os.makedirs(EXTERNAL, exist_ok=True)
    rows = []
    for d in DATASETS:
        url = "https://www.kaggle.com/api/v1/datasets/download/" + d["ref"]
        dest = os.path.join(EXTERNAL, "SK_%s_%s.zip" % (d["key"], d["ref"].split("/")[-1]))
        if os.path.exists(dest) and not args.force:
            print("[skip] %s 已存在：%s" % (d["key"], os.path.relpath(dest, ROOT)))
        else:
            print("[get ] %s ← %s" % (d["key"], url))
            try:
                download(url, dest)
            except Exception as e:
                print("  下载失败：%s: %s" % (type(e).__name__, e), file=sys.stderr)
                print("  可手动从 https://www.kaggle.com/datasets/%s 下载并放到 %s"
                      % (d["ref"], dest), file=sys.stderr)
                return 1
            if not zipfile.is_zipfile(dest):
                print("  返回内容不是 zip，已删除", file=sys.stderr)
                os.remove(dest)
                return 1
        with zipfile.ZipFile(dest) as z:
            names = z.namelist()
        ok = d["expect_file"] in names
        print("  %6.2f MB | sha256=%s | 预期文件 %s: %s"
              % (os.path.getsize(dest) / 1e6, sha256(dest)[:16], d["expect_file"],
                 "OK" if ok else "未找到（内容：" + ", ".join(names[:4]) + "）"))
        rows.append(dict(
            dataset=d["key"], ref=d["ref"], license=d["license"], url=url,
            file=os.path.relpath(dest, ROOT), bytes=os.path.getsize(dest),
            sha256=sha256(dest), downloaded_at=dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            note=d["note"], expected_file=d["expect_file"], expected_file_present=int(ok),
        ))
    mpath = os.path.join(EXTERNAL, "SK_download_manifest.csv")
    with open(mpath, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("清单：", os.path.relpath(mpath, ROOT))
    return 0 if all(r["expected_file_present"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
