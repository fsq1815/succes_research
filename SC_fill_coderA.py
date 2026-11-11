#!/usr/bin/env python3
# SC_fill_coderA.py — 按 docs/codebook.md v0.2 的判定细则，代填编码员 A 的 20% 双编码样本
#
# 用途：让 kappa 模板有真实可读的 coderA 列，编码员 B（真人）只需独立填 *_coderB。
# 诚实约束：
#   · 这 13 条是**单编码员的语义判定**，不是双人一致性证据；
#   · coderB 全部留空，真实 kappa 必须由第二位真人填写后才计算；
#   · 边界判定写进 note，供双人讨论与 codebook 修订。
#
# 运行：python3 SC_fill_coderA.py

import csv
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(ROOT, "data", "processed")
IND = ["s1", "u3", "c3", "cr1", "st3", "e4"]

# bvid -> (六项判定, 边界说明)
# 判定依据见 docs/codebook.md「六个人工语义指标：判定细则」
# 编码素材仅 title + desc（字幕覆盖率 0%，intro 实际为空；盲法：未看 view/like 等结果变量）
# 样本为锁定两区（社科·法律·心理 + 科学科普）后重新 20% 抽签所得（全样本 64 条，固定种子 20261106）
JUDGEMENTS = {
    "BV16WZJY3Enq": ((1, 0, 0, 0, 0, 0),
                     "s1: 标题单一主张(婚内出轨证据)，desc 罗列3种取证但主句单一，判1；"
                     "u3: 仅单一数字，无两组数量级反差，判0；c3: 法官/原配均泛指角色，无具体人名/案名，判0；"
                     "cr1: 无出处，判0；st3: 无叙事，判0；e4: '必看避坑指南'为中性指导，非情绪唤起，判0"),
    "BV1XhfgYBEqg": ((1, 0, 0, 0, 0, 0),
                     "s1: 单问，判1；u3: '年年'与'晚期'非两组数量级数字，判0；"
                     "c3: 无具体实体，判0；cr1: 无出处，判0；st3: 无叙事，判0；"
                     "e4: '无异常却是晚期'为反差设问而非情绪唤起，判0"),
    "BV1YqZJYaE7L": ((1, 0, 1, 0, 0, 0),
                     "s1: 单一事件(马斯克摇摆州发钱)，判1；u3: 仅'200万美元'单个数字，判0；"
                     "c3: '马斯克'(人名)/'民主党'(机构)为具体指称，判1；cr1: 无出处，判0；"
                     "st3: 无叙事，判0；e4: '大撒币'为戏谑措辞，非明确情绪唤起，判0"),
    "BV1bSZ9YHEQG": ((1, 0, 0, 0, 0, 0),
                     "s1: 物理论题单一(最速曲线)，判1；u3: '三个小球'为同一集合，无两组数量级，判0；"
                     "c3: 小球/物理学均泛指，判0；cr1: 无出处，判0；st3: 无叙事，判0；"
                     "e4: '看似简单却藏深层法则'为惊喜式包装，非情绪唤起，判0"),
    "BV1cgdWYSEfv": ((1, 0, 1, 0, 0, 1),
                     "s1: 单一话题(冷空气)，判1；u3: '十几/二十度'量级相近，判0；"
                     "c3: '东北'(地名)/'周五周六'(具体日)为具体指称，判1；cr1: 无出处，判0；"
                     "st3: 无叙事，判0；e4: '疯批冷空气''能不能别搞我们啊'明显情绪/吐槽唤起，判1"),
    "BV1ewRUYMEG7": ((1, 0, 1, 0, 0, 0),
                     "s1: 单一话题(日本米饭神器)，判1；u3: 无两组数字，判0；"
                     "c3: '日本'(国名)为具体指称，判1；cr1: 无出处，判0；st3: 无叙事，判0；"
                     "e4: '智商税还是高科技'为中性设问，判0"),
    "BV1pEdNYaExa": ((1, 0, 1, 0, 0, 0),
                     "s1: 单一话题(加征关税)，判1；u3: 仅'50%'单个数字，判0；"
                     "c3: '美国'(国名)为具体指称，判1；cr1: 无出处，判0；st3: 无叙事，判0；"
                     "e4: '强硬反制！'为表态性新闻标题，非情绪唤起，判0"),
    "BV1w6ZEYrEsb": ((1, 0, 0, 0, 0, 0),
                     "s1: 单一文化设问(为何'下饭'是最高评价)，判1；u3: 无两组数字，判0；"
                     "c3: '中国人'/'一道菜'均泛指，判0；cr1: 无出处，判0；st3: 无叙事，判0；e4: 中性设问，判0"),
    "BV1wAfKYGEkj": ((1, 0, 1, 1, 0, 0),
                     "s1: 单一话题(和尚如何补蛋白)，判1；u3: 无两组数字，判0；"
                     "c3: desc 含'孙建琴''杨月欣'(具体人名)与'母子健康'(期刊)，判1；"
                     "cr1: desc 以'参考资料：…[J].母子健康，2016'明确注明出处，判1；"
                     "st3: 无叙事，判0；e4: 中性设问，判0；"
                     "⚠ 数据质量：desc 似错贴(讲牛奶/乳糖不耐受，与标题和尚/蛋白质无关)，仍按字段如实编码并标记待核查"),
    "BV1wFZ8YBEt4": ((1, 0, 0, 0, 0, 0),
                     "s1: 单一设问(人为何需吃盐而动物不用)，判1；u3: 无两组数字，判0；"
                     "c3: '人类'/'动物们'泛指，判0；cr1: 无出处，判0；st3: 无叙事，判0；e4: 中性设问，判0"),
    "BV1wGdWYEE48": ((1, 0, 1, 0, 0, 0),
                     "s1: 单一设问(冰块清煎锅)，判1；u3: 无两组数字，判0；"
                     "c3: '煎锅'为具体物品，判1；cr1: 无出处，判0；st3: 无叙事，判0；e4: 中性设问，判0"),
    "BV1x1x96aEGM": ((1, 0, 0, 0, 0, 0),
                     "s1: 单一设问(虚假亲子鉴定是否违法)，判1；u3: 无两组数字，判0；"
                     "c3: '虚假亲子鉴定机构'为类别而非具体机构名，判0；cr1: 无出处，判0；"
                     "st3: 仅为前提式设问，无人物障碍—转折叙事，判0；"
                     "e4: '听起来就很烧心'为轻微感受，非明确情绪唤起，判0"),
    "BV1ymdWYWEXr": ((1, 0, 1, 0, 0, 0),
                     "s1: 单一话题(无穷小亮寻'三傻')，判1；u3: 无两组数字，判0；"
                     "c3: '无穷小亮'/'小王'/'皮克桃'/'呱唧鸭'(人名)、'王者荣耀'(产品)、'藏狐/雪豹/兔狲'(物种)为具体指称，判1；"
                     "cr1: 无出处，判0；st3: 为活动描述非叙事弧，判0；e4: 中性/热情描述，判0"),
}

# ---- 1. 双人模板：填 coderA，coderB 保持空白 --------------------------------
dbl_path = os.path.join(PROC, "SC_double_coding_template.csv")
rows = list(csv.DictReader(open(dbl_path, encoding="utf-8-sig")))
fields = list(rows[0].keys())
for r in rows:
    if r["bvid"] in JUDGEMENTS:
        j, note = JUDGEMENTS[r["bvid"]]
        for ind, val in zip(IND, j):
            r[ind + "_coderA"] = val
            r[ind + "_coderB"] = ""       # 必须由第二位真人独立填写
        r["coderA_id"] = "assistant-coderA-demo"
        r["coderB_id"] = ""
        r["coded_date"] = "2026-11-06"
        r["note"] = note
    else:
        # 模板中的 bvid 不在本判定表内（不应发生），留空并提示
        for ind in IND:
            r[ind + "_coderA"] = r[ind + "_coderB"] = ""
        r["coderA_id"] = r["coderB_id"] = r["coded_date"] = r["note"] = ""
with open(dbl_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

# ---- 2. 主编码表：同步这 13 行，其余行留空待填 -----------------------------
main_path = os.path.join(PROC, "SC_manual_coding.csv")
mrows = list(csv.DictReader(open(main_path, encoding="utf-8-sig")))
mfields = list(mrows[0].keys())
for r in mrows:
    if r["bvid"] in JUDGEMENTS:
        j, note = JUDGEMENTS[r["bvid"]]
        for ind, val in zip(IND, j):
            r[ind] = val
        r["coder_id"] = "assistant-coderA-demo"
        r["coded_date"] = "2026-11-06"
        r["note"] = note
    else:
        r["coder_id"] = r["coded_date"] = r["note"] = ""
with open(main_path, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=mfields, extrasaction="ignore")
    w.writeheader()
    w.writerows(mrows)

print("已填编码员 A：%d / %d 行（20%% 双编码样本，锁定两区后重新抽签）" % (len(JUDGEMENTS), len(mrows)))
print("编码员 B：全部留空，待真人独立填写后运行 Rscript R/SC_kappa.R")
print("边界判定说明已写入 note 列，共 %d 条备注" % sum(1 for r in rows if r["note"]))
