#!/usr/bin/env python3
# SC_sync_coderA_to_main.py — 把「真人 coderA 的 v0.3 判定」同步回 64 行主编码表
#
# 背景：第一轮 13 条双编码样本里，coderA 由脚本按 v0.2 代填
#       （coder_id = assistant-coderA-demo）。第二轮按 v0.3 由真人 R2 重编后，
#       双编码模板 SC_double_coding_template.csv 的 *_coderA 已更新，但主编码表
#       SC_manual_coding.csv 仍是旧值 —— 若不同步，R/SC_mvp.R 会用错六维得分。
#
# 用法：python3 SC_sync_coderA_to_main.py           # 校验并写入（自动备份）
#       python3 SC_sync_coderA_to_main.py --dry-run # 只校验
#
# 约束：只改双编码样本那 13 行；其余 51 行一个字不动；写入前整表备份。
#       不生成、不推测任何一格答案，只搬运真人已填的值。

import argparse
import csv
import os
import shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(ROOT, "data", "processed")
DBL = os.path.join(PROC, "SC_double_coding_template.csv")
MAIN = os.path.join(PROC, "SC_manual_coding.csv")
ARCHIVE = os.path.join(PROC, "archive_main_sync")
IND = ["s1", "u3", "c3", "cr1", "st3", "e4"]
VALID = {"0", "1", "9"}
BANNED = ("assistant-coderA-demo", "PREVIEW-UNVERIFIED")
NOTE = ("v0.3 真人 coderA 重编（13 条双编码样本）；v0.2 脚本代填理由已作废，"
        "原件见 data/processed/archive_main_sync/")


def read(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        return list(rd.fieldnames or []), list(rd)


def main():
    ap = argparse.ArgumentParser(description="同步真人 coderA 判定到主编码表")
    ap.add_argument("--dry-run", action="store_true", help="只校验不写入")
    a = ap.parse_args()

    df, dbl = read(DBL)
    mf, main = read(MAIN)
    need = ["bvid", "coderA_id", "coderA_date"] + [k + "_coderA" for k in IND]
    miss = [c for c in need if c not in df]
    if miss:
        raise SystemExit("双编码模板缺列：%s" % ", ".join(miss))
    miss = [c for c in ["bvid", "coder_id", "coded_date", "note"] + IND if c not in mf]
    if miss:
        raise SystemExit("主编码表缺列：%s" % ", ".join(miss))

    dmap = {r["bvid"]: r for r in dbl}
    ids = sorted({r["coderA_id"].strip() for r in dbl} - {""})
    if len(ids) != 1:
        raise SystemExit("coderA_id 应为单一真人代号，实际：%s" % (ids or "空"))
    if any(b in ids[0] for b in BANNED):
        raise SystemExit("coderA_id 仍是脚本代填标识，拒绝同步：%s" % ids[0])

    # 先全量校验，任何一格不合格就整体退出，绝不半写入
    changes = {}
    for bv, d in dmap.items():
        vals = {}
        for k in IND:
            v = d[k + "_coderA"].strip()
            if v not in VALID:
                raise SystemExit("值域错误：%s 的 %s = %r" % (bv, k, v))
            vals[k] = v
        changes[bv] = vals
    missing = sorted(set(changes) - {r["bvid"] for r in main})
    if missing:
        raise SystemExit("双编码样本有 %d 条 bvid 不在主编码表：%s" % (len(missing), missing[:4]))

    print("校验通过：%d 条双编码样本、%d 格，coderA = %s，值域全在 0/1/9"
          % (len(changes), len(changes) * len(IND), ids[0]))
    changed = [r["bvid"] for r in main if r["bvid"] in changes]
    others = [r for r in main if r["bvid"] not in changes]
    print("主编码表：%d 行，将更新 %d 行，其余 %d 行不动" % (len(main), len(changed), len(others)))
    if a.dry_run:
        print("--dry-run：未写入。")
        return

    os.makedirs(ARCHIVE, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(ARCHIVE, "SC_manual_coding_before_%s.csv" % stamp)
    shutil.copy2(MAIN, backup)

    for r in main:
        vals = changes.get(r["bvid"])
        if not vals:
            continue
        for k, v in vals.items():
            r[k] = v
        r["coder_id"] = ids[0]
        r["coded_date"] = dmap[r["bvid"]]["coderA_date"].strip()
        r["note"] = NOTE

    tmp = MAIN + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=mf, extrasaction="ignore")
        w.writeheader()
        w.writerows(main)
    os.replace(tmp, MAIN)
    print("✓ 已同步：%s" % os.path.relpath(MAIN, ROOT))
    print("  写入前备份：%s" % os.path.relpath(backup, ROOT))
    print("  下一步：Rscript R/SC_mvp.R（六维得分会随真人 A 判定变化）")


if __name__ == "__main__":
    main()
