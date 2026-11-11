#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SW_info_markers.py — 高赞评论里「信息获取」的三层可复现代理指标.

背景（来自 dev 集 180 条评论的人工审计，见 output/SW_dev_dictionary_audit.txt）
---------------------------------------------------------------------------
每周必看的**高赞热评**被点赞机制筛成神评论 / 玩梗 / 情感共鸣，开发集里
「学到了 / 感谢科普 / 涨知识 / 受益匪浅 / 记笔记」**全部 0 命中**；
「明白了 / 懂了 / 才知道」的 3 条命中经逐条核对均为叙事误报
（例：「才知道那是只义眼」「脑子懂了但手还是不会」）。
因此窄口径 `info_learn` 在样本内近乎恒为 0，**不能用作主模型因变量**，
本项目只把它作为「为什么不能那样测」的报告性证据保留。

三层指标（全部为规则项，不含人工语义判断，不调用任何模型）
--------------------------------------------------------
1. info_learn      窄：显式学习/理解表述。高精度词典，剔除开发集已证误报的模式。
2. info_discussion 主：评论是否包含「信息性讨论」= 求解提问 ∨ 解释性陈述 ∨ 事实复述。
                   只依赖评论自身文本，**不引用标题**，避免与同源派生的六维自变量
                   产生机械相关。构念边界：测的是围绕信息的讨论痕迹，
                   是「获取信息」的必要非充分条件，不等于认知增益。
3. info_echo       次：评论与视频文本的字符 bigram Jaccard。客观连续，
                   但自变量与它都从标题派生，**存在机械相关风险**，
                   仅作稳健性并强制控制 title_len / blurb_len，不作主结论。

⚠️ 三层都是**代理指标**；高赞热评 ≠ 全体观众，词典命中 ≠ 真的学到。
"""
import re

EMOTE = re.compile(r"\[[^\]]{1,12}\]")
URL = re.compile(r"https?://\S+")
SPACE = re.compile(r"\s+")
CJK = re.compile(r"[\u4e00-\u9fff]")

# ---- 1. 窄口径：显式学习/理解表述（开发集校准后剔除误报模式）--------------
LEARN = re.compile(
    r"涨知识|涨姿势|学到了(?:很多|不少)?|学习到了|学到(?:了)?(?:新)?知识|"
    r"受益匪浅|受教了?|感谢(?:科普|讲解|分享|up主?的?(?:科普|讲解))|"
    r"谢谢(?:科普|讲解|分享)|解惑|醍醐灌顶|恍然大悟|原来如此|茅塞顿开|豁然开朗|"
    r"终于(?:懂了|明白了|理解了)|记笔记|做笔记|小本本|马住学|收藏(?:了)?学习|"
    r"讲得(?:很|太)?(?:清楚|明白|透彻)|科普得(?:很)?好|解开(?:了)?(?:我)?(?:的)?疑惑|"
    r"有收获|收获(?:很大|满满|良多)", re.I
)
# 开发集证实为误报、明确排除的词形（保留在此仅为审计留痕，不参与匹配）
_EXCLUDED_AFTER_AUDIT = ["才知道", "现在才知道", "懂了但", "明白了(?!.*视频)", "知道(?:了|啦)"]

# ---- 2. 主口径：信息性讨论 ------------------------------------------------
ASK_STRONG = re.compile(
    r"请问|求解|求科普|求解答|谁能(?:解释|讲讲|说说)|有没有(?:人|大佬|老哥)(?:知道|能|可以)|"
    r"大佬(?:能|可以)?(?:解释|讲讲)|想问(?:一下|个)|不(?:太)?明白(?:为什么|怎么|为何)", re.I
)
ASK_WORD = re.compile(r"怎么|为什么|为何|如何|是不是|能不能|什么原理|有何区别|区别在哪|原因[是何]|原理[是何]", re.I)
QMARK = re.compile(r"[？?]")

EXPLAIN_MARK = re.compile(
    r"因为|所以|其实|原理|指的是|意思是|也就是说|原因在于|这是由于|因此|"
    r"根据[^，。]{0,8}(?:数据|研究|统计|报告|文献)|第一[，,、]|第二[，,、]|"
    r"由此(?:可见|可知)|换句话说|事实上", re.I
)
FACT_NUM = re.compile(
    r"[0-9]+ ?(?:年|月|日|%|％|倍|万|亿|元|块|米|公里|度|人|次|秒|分钟|小时|岁|"
    r"公斤|斤|台|部|个|层|种|条|位|篇|项)"
)

_MIN_EXPLAIN_LEN = 30
_MIN_FACT_LEN = 25


def clean(msg):
    """去表情码 / URL / 多余空白，保留可比对文本。"""
    s = URL.sub(" ", str(msg or ""))
    s = EMOTE.sub(" ", s)
    return SPACE.sub(" ", s).strip()


def cjk_only(s):
    return "".join(CJK.findall(s))


def learn_flag(msg):
    return int(bool(LEARN.search(clean(msg))))


def discussion_parts(msg):
    s = clean(msg)
    n = len(s)
    ask = int(bool(ASK_STRONG.search(s)) or (bool(ASK_WORD.search(s)) and bool(QMARK.search(s))))
    explain = int(n >= _MIN_EXPLAIN_LEN and bool(EXPLAIN_MARK.search(s)))
    fact = int(n >= _MIN_FACT_LEN and bool(FACT_NUM.search(s)))
    return {"ask": ask, "explain": explain, "fact": fact,
            "info_discussion": int(bool(ask or explain or fact))}


def bigrams(s):
    t = cjk_only(s)
    return {t[i:i + 2] for i in range(len(t) - 1)} if len(t) >= 2 else set()


def echo_jaccard(msg, title, blurb):
    """评论与视频文本（标题+推荐语）的 CJK 字符 bigram Jaccard。"""
    a = bigrams(clean(msg))
    b = bigrams(clean((title or "") + " " + (blurb or "")))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def code_comment(msg, title="", blurb=""):
    d = {"info_learn": learn_flag(msg),
         "info_echo": round(echo_jaccard(msg, title, blurb), 6),
         "msg_len": len(clean(msg))}
    d.update(discussion_parts(msg))
    return d


if __name__ == "__main__":
    # 开发集描述性自检：只报各指标基础率，不计算任何与六维的关联
    import csv
    import os
    p = os.path.join(os.path.dirname(__file__), "data", "raw", "SW_comments_dev.csv")
    vp = os.path.join(os.path.dirname(__file__), "data", "raw", "SW_videos.csv")
    if not os.path.exists(p) or not os.path.exists(vp):
        print("缺少 dev 集或视频元数据，跳过自检")
    else:
        vm = {r["bvid"]: r for r in csv.DictReader(open(vp, encoding="utf-8"))}
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        vals = []
        for r in rows:
            v = vm.get(r["bvid"], {})
            vals.append(code_comment(r["message"], v.get("title", ""), v.get("blurb", "")))
        n = len(vals)
        for k in ("info_learn", "info_discussion", "ask", "explain", "fact"):
            print("  %-18s 命中 %3d/%d (%.1f%%)" % (k, sum(v[k] for v in vals), n,
                                                   100 * sum(v[k] for v in vals) / max(n, 1)))
        e = [v["info_echo"] for v in vals]
        print("  %-18s 均值 %.4f 中位 %.4f 非零 %d/%d" %
              ("info_echo", sum(e) / n, sorted(e)[n // 2], sum(1 for x in e if x > 0), n))
