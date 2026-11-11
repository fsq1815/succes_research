#!/usr/bin/env python3
# SC_make_coding_sheets.py — 生成人工编码表 / 20% 双人编码模板 / kappa 模拟自检数据
#
# 需求 #2：补 6 个人工语义指标 + 随机 20% 双人编码算 Cohen's kappa
# 需求 #3：素材覆盖度（desc / intro / subtitle）随编码表带出，便于核对
#
# 盲法：编码表**不含** view/like/favorite/engage_rate/粉丝数/热度层/榜单排名，
#       避免"看到爆款就觉得它更 Simple"的后见之明偏差。
# 诚实约束：kappa 必须由两位真实编码人产生；本脚本生成的 SIMULATED 数据只用于验证公式，
#           文件内与报告里都明确标注，绝不充作真实一致性证据。
#
# 运行：python3 SC_make_coding_sheets.py
# ⚠️ 重跑会**覆盖并清空**人工编码表、双编码模板里已填的 coderA / coderB 判定。
#    采集结果或样本范围没变时不要重跑；确需重跑先备份 data/processed/。
#    找第二位真人编码请用 SC_export_coderB.py 生成盲法交付包，
#    回收用 SC_import_coderB.py（不要把本脚本产出的模板直接发给对方：含 A 的答案与判定理由）。

import csv
import os
import random
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "processed")
os.makedirs(PROC, exist_ok=True)

SRC = os.path.join(RAW, "SC_mvp_videos_20261106.csv")
SEED = 20261106
KAPPA_FRACTION = 0.20
INDICATORS = ["s1", "u3", "c3", "cr1", "st3", "e4"]

rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))

AUTO_PAT = re.compile(r"_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_|_\d{3}$|^[\W_]{0,3}$")


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def flags(r):
    v = num(r["view"])
    rate_stable = int(v >= 1000)          # 互动率分母稳定（仅标记，不硬删）
    title_auto = int(bool(AUTO_PAT.search(r["title"] or "")))
    reason = ""
    if title_auto:
        reason = "直播切片/自动命名标题，非策划型知识视频"
    elif v < 1000:
        reason = "view<1000，互动率分母不稳定"
    return rate_stable, title_auto, reason


for r in rows:
    r["rate_stable"], r["title_auto"], r["exclude_reason"] = flags(r)

# ---- 1. 主编码表（盲法）------------------------------------------------------
main_fields = (["bvid", "title", "desc", "intro", "subtitle_n", "desc_source",
                "subzone", "topic_layer", "within_1yr", "rate_stable",
                "title_auto", "exclude_reason", "kappa_flag", "content_type"]
               + INDICATORS + ["coder_id", "coded_date", "note"])

# 20% 抽签：以全样本为分母取整，但只在 rate_stable 且非自动命名的行中抽，
# 避免把编码精力浪费在 view<=5 的直播切片上（该决定写入报告）。
eligible = [r["bvid"] for r in rows
            if r["rate_stable"] == 1 and r["title_auto"] == 0]
n_kappa = max(1, round(len(rows) * KAPPA_FRACTION))
rng = random.Random(SEED)
kappa_set = set(rng.sample(eligible, min(n_kappa, len(eligible))))
print("编码样本(rate_stable & 非自动命名): %d 条" % len(eligible))
print("双人编码抽签: 全样本 %d × 20%% = %d 条（固定种子 %d）" % (len(rows), n_kappa, SEED))

with open(os.path.join(PROC, "SC_manual_coding.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=main_fields, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        rec = {k: r.get(k, "") for k in main_fields}
        rec["kappa_flag"] = int(r["bvid"] in kappa_set)
        for ind in INDICATORS:
            rec[ind] = ""            # 留给编码员 A
        rec["coder_id"] = rec["coded_date"] = rec["note"] = ""
        w.writerow(rec)

# ---- 2. 双人编码模板 --------------------------------------------------------
dbl_fields = ["bvid", "title", "desc", "intro"]
for ind in INDICATORS:
    dbl_fields += [ind + "_coderA", ind + "_coderB"]
dbl_fields += ["coderA_id", "coderB_id", "coded_date", "note"]

kappa_rows = [r for r in rows if r["bvid"] in kappa_set]
kappa_rows.sort(key=lambda r: r["bvid"])
with open(os.path.join(PROC, "SC_double_coding_template.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=dbl_fields, extrasaction="ignore")
    w.writeheader()
    for r in kappa_rows:
        rec = {"bvid": r["bvid"], "title": r["title"],
               "desc": r["desc"], "intro": r["intro"]}
        for ind in INDICATORS:
            rec[ind + "_coderA"] = ""   # 由编码员 A 填（本轮由助手按 codebook 代填示例，见文件）
            rec[ind + "_coderB"] = ""   # 必须由第二位真人独立填写
        rec["coderA_id"] = rec["coderB_id"] = rec["coded_date"] = rec["note"] = ""
        w.writerow(rec)

# ---- 3. 模拟双编码（仅验证公式，明确标注 SIMULATED）--------------------------
# 用一条独立生成的伪双编码数据，检验 SC_kappa.R 在「完全一致 / 部分不一致 / 常量」
# 三种情况下都能给出正确数值。真实 kappa 不得引用这里的任何数字。
demo = []
sim = random.Random(999)
for i in range(30):
    rec = {"item_id": "SIM_%02d" % (i + 1), "simulated": 1}
    for j, ind in enumerate(INDICATORS):
        a = 1 if sim.random() < (0.35 + 0.06 * j) else 0
        # 人为注入约 12% 分歧，使 kappa 落在 0.7-0.9 区间以便观察输出
        b = a if sim.random() > 0.12 else 1 - a
        rec[ind + "_coderA"] = a
        rec[ind + "_coderB"] = b
    demo.append(rec)
demo_fields = ["item_id", "simulated"] + [i + "_" + c for i in INDICATORS for c in ("coderA", "coderB")]
with open(os.path.join(PROC, "SC_kappa_demo_SIMULATED.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=demo_fields)
    w.writeheader()
    w.writerows(demo)

# ---- 输出核对信息 -----------------------------------------------------------
print("\n抽中双人编码的 %d 条（供填写 coderA / coderB）：" % len(kappa_rows))
for r in kappa_rows:
    print("  %s | %s" % (r["bvid"], r["title"][:46]))
    print("       desc: %s" % (r["desc"][:80] or "(空)"))
print("\n素材覆盖：desc 非空 %d/%d；intro 非空 %d/%d；字幕 %d/%d" %
      (sum(1 for r in rows if r["desc"].strip()), len(rows),
       sum(1 for r in rows if (r["intro"] or "").strip()), len(rows),
       sum(1 for r in rows if num(r["subtitle_n"]) > 0), len(rows)))
print("\n产物：")
for p in ("SC_manual_coding.csv", "SC_double_coding_template.csv", "SC_kappa_demo_SIMULATED.csv"):
    print("  data/processed/" + p)
