#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SK_codebook.py — SUCCES 六维「规则项-only」编码表（移植自 succes-bilibili）.

来源：succes-bilibili/R/02_code_succes.R 的 LEX v0.2 与 dim_map（路径 C / 变更 G）。
规则与词典**逐项照抄**，不新增词、不改阈值。差异只有两处，均为工程实现或数据可用性，
已在 docs/SK_preregistration.md 第 4 节登记：
  · 字面词统一 re.escape 后拼接（原 R 实现把 "?" 直接拼进正则；此处按字面问号匹配，语义更正确）；
  · u4（字幕开场疑问）与 cr4（UP 主认证）在两个 Kaggle 数据源均不可得 → 返回 None（NA），
    不猜测、不补 0。六维得分按有效项均值，并逐行记录 n_valid_items。

人工语义指标 s1/u3/c3/cr1/st3/e4 按原项目路径 C 的结论**不采用**，本模块不予实现。
"""
import re

# ---- 词典 v0.2（冻结 2026-11-06）-------------------------------------------
LEX = {
    "simple_conclusion": ["一句话", "搞懂", "讲清", "其实就", "只需", "分钟", "本质上是", "说白了"],
    "abstract":          ["底层逻辑", "方法论", "认知", "范式", "维度", "体系", "思维模型"],
    "unexpected":        ["你以为", "其实不是", "并不是", "错了", "恰恰相反", "颠覆", "真相是"],
    "suspense":          ["为什么", "到底", "竟然", "凭什么", "?", "？"],
    "concrete_entity":   ["钱", "工资", "手机", "地铁", "一天", "分钟", "一杯", "一张", "块钱", "公里", "小时"],
    "credible":          ["研究显示", "实验", "数据", "调查", "论文", "根据", "统计", "报告", "文献"],
    "emotional":         ["震惊", "崩溃", "后悔", "焦虑", "扎心", "救命", "细思极恐", "爽", "绝了", "可怕"],
    "second_person":     ["你", "你的", "千万别"],
    "frame":             ["别再", "错过", "省下", "避免", "少走弯路", "白花", "别被"],
    "story_open":        ["我朋友", "有个学生", "曾经", "我当年", "某位", "有个读者"],
    "story_time":        ["先", "后来", "结果", "直到", "没想到", "于是"],
}
# v0.2 新增：可感知量化短语（数字 + 具体单位），替换曾与 S4 重复的旧 C4
MEASURED_UNIT = re.compile(
    r"[0-9]+ ?(元|块|万元|亿元|年|个月|天|小时|分钟|秒|公里|米|人|%|％|次|倍|斤|公斤|度|杯|页|位|万|亿|岁)"
)
CREDIBLE_SOURCE = re.compile(r"https?://|DOI|doi|参考文献|出处")
STORY_LONG = re.compile(r"案例|例子|举例|故事")

_LITERAL = {k: re.compile("|".join(re.escape(w) for w in v)) for k, v in LEX.items()}


def _hit(text, key):
    return int(bool(_LITERAL[key].search(text)))


def _hit_count(text, key):
    return len(_LITERAL[key].findall(text))


# 六维 → 规则项（与原 R 脚本 dim_map 完全一致）
DIM_MAP = {
    "s_simple":     ("s2", "s3", "s4"),
    "s_unexpected": ("u1", "u2", "u4"),
    "s_concrete":   ("c1", "c2", "c4"),
    "s_credible":   ("cr2", "cr3", "cr4"),
    "s_emotional":  ("e1", "e2", "e3"),
    "s_stories":    ("st1", "st2", "st4"),
}

ITEMS = [i for cols in DIM_MAP.values() for i in cols]


def code_row(title, desc, duration, official=None):
    """对单条视频返回 18 个规则项 + 6 个维度得分 + 6 个 n_valid_items。

    title / desc 为字符串（空串表示缺失）；duration 为秒（数值或 None）。
    official 参数保留仅为接口对齐：两个 Kaggle 数据源均无认证字段，恒不使用。
    """
    title = title or ""
    desc = desc or ""
    txt = title + " " + desc
    items = {
        # S Simple
        "s2": int(len(title) <= 20),
        "s3": _hit(txt, "simple_conclusion"),
        "s4": int(_hit_count(title, "abstract") == 0),
        # U Unexpected
        "u1": _hit(txt, "unexpected"),
        "u2": _hit(title, "suspense"),
        "u4": None,                       # SK-变更 A：无字幕
        # C Concrete
        "c1": int(bool(re.search(r"[0-9]", txt))),
        "c2": _hit(txt, "concrete_entity"),
        "c4": int(bool(MEASURED_UNIT.search(txt))),
        # Cr Credible
        "cr2": _hit(txt, "credible"),
        "cr3": int(bool(CREDIBLE_SOURCE.search(txt))),
        "cr4": None,                      # SK-变更 B：无 UP 主认证字段
        # E Emotional
        "e1": _hit(title, "emotional"),
        "e2": _hit(title, "second_person"),
        "e3": _hit(title, "frame"),
        # St Stories
        "st1": _hit(txt, "story_open"),
        "st2": int(_hit_count(txt, "story_time") >= 2),
        "st4": int(bool(duration is not None and duration >= 480 and STORY_LONG.search(txt))),
    }
    out = dict(items)
    for dim, cols in DIM_MAP.items():
        vals = [items[c] for c in cols if items[c] is not None]
        out[dim] = sum(vals) / len(vals) if vals else None
        out["n_" + dim] = len(vals)
    return out


def code_row_cr4_zero(title, desc, duration):
    """稳健性 S5：把 cr4 强制设 0（Credible 恢复 3 项），其余不变。"""
    out = code_row(title, desc, duration)
    out["cr4"] = 0
    vals = [out[c] for c in DIM_MAP["s_credible"] if out[c] is not None]
    out["s_credible"] = sum(vals) / len(vals)
    out["n_s_credible"] = len(vals)
    return out


if __name__ == "__main__":
    # 与 docs/codebook.md 的示例一致性自检（不联网、不读数据）
    demo = code_row("为什么罗翔说张三的案子判了 3 年？", "根据判决书", 600)
    print("示例规则项:", {k: demo[k] for k in ITEMS})
    print("六维得分:", {k: round(demo[k], 3) for k in DIM_MAP})
    print("有效项数:", {k: demo["n_" + k] for k in DIM_MAP})
