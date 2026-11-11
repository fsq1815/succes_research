#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SW_download.py — 从 Kaggle 公开下载端点获取「每周必看」数据集（免登录）.

用法：python3 SW_download.py [--force]

数据集：zhuosun03/bilibili-must-watch
        B_231009_1696842727.csv，8,104 行 / 8,064 唯一 bvid，2019-2023 共 237 期。
        ⚠️ Kaggle 上该数据集的 licenseName 为 **Unknown**，因此原始 CSV 只作本地分析输入，
        不随仓库分发（见 .gitignore）；许可与来源声明见 docs/SW_data-source.md。

只用公开下载端点，不用 API token、不绕过任何访问控制。
原始 zip 不提交仓库；清单 data/external/SW_download_manifest.csv 记录 URL、时间与 SHA-256。
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
REF = "zhuosun03/bilibili-must-watch"
ZIP_NAME = "SW_weekly-must-watch.zip"
URL = "https://www.kaggle.com/api/v1/datasets/download/" + REF
UA = "succes-weekly/0.1 academic-reproduction (public dataset download)"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    os.makedirs(EXTERNAL, exist_ok=True)
    dest = os.path.join(EXTERNAL, ZIP_NAME)
    if os.path.exists(dest) and not a.force:
        print("[skip] 已存在：%s" % os.path.relpath(dest, ROOT))
    else:
        print("[get ] %s" % URL)
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:
            print("下载失败：%s: %s" % (type(e).__name__, e), file=sys.stderr)
            print("可手动从 https://www.kaggle.com/datasets/%s 下载并放到 %s" % (REF, dest),
                  file=sys.stderr)
            sys.exit(1)
    if not zipfile.is_zipfile(dest):
        print("错误：下载内容不是 zip", file=sys.stderr)
        sys.exit(1)
    with zipfile.ZipFile(dest) as z:
        names = z.namelist()
    print("zip 内文件:", names)
    row = {
        "dataset": "weekly-must-watch", "ref": REF, "url": URL,
        "license": "Unknown (Kaggle licenseName)", "file": ZIP_NAME,
        "size_bytes": os.path.getsize(dest), "sha256": sha256(dest),
        "downloaded_at": dt.datetime.now().isoformat(timespec="seconds"),
        "note": "原始 CSV 不随仓库分发；仅作本地分析输入",
    }
    mf = os.path.join(EXTERNAL, "SW_download_manifest.csv")
    with open(mf, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        w.writeheader()
        w.writerow(row)
    print("manifest → %s" % os.path.relpath(mf, ROOT))
    print("sha256: %s" % row["sha256"])


if __name__ == "__main__":
    main()
