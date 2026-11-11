#!/usr/bin/env python3
# SC_export_coderB.py — 导出第二轮 A / B 两份独立盲法填写表
#
# 版本：Codebook v0.3（第一轮双人编码信度未达标后的判定细则补订，预注册变更 E）
#
# 为什么要两份：
#   规则一改，两位编码人都必须按 v0.3 重编同一 13 条；只让 B 重填会变成
#   「A 用 v0.2、B 用 v0.3」，比较不成立。第一轮 coderA 由脚本代填，
#   不符「两位真实的人独立编码」前提，因此第二轮 A、B 都交给真人。
#
# 盲法约束：
#   data/processed/SC_double_coding_template.csv 含已填答案与判定理由，
#   绝不可直接发给任何编码人。本脚本只导出「素材 + 空白待填列」，
#   并对列名、单元格内容与说明文本做泄露自检（不含任何 bvid 的答案线索）。
#
# 产出（data/processed/handoff/round2/）：
#   SC_round2_coderA_sheet.xlsx / SC_round2_coderB_sheet.xlsx
#   SC_round2_coderA_sheet.csv  / SC_round2_coderB_sheet.csv
#   SC_round2_instructions.md   通用说明（含两份可直接复制的发送文案）
#   SC_round2_handoff.zip       以上打包
#
# 运行：python3 SC_export_coderB.py
# 回收：python3 SC_import_coderB.py <交回文件> --role A    （或 --role B）
#       Rscript R/SC_kappa.R
#
# 历史：第一轮单份 coderB 交付包已归档在 data/processed/handoff/archive_round1/。

import csv
import os
import zipfile

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(ROOT, "data", "processed")
OUT_DIR = os.path.join(PROC, "handoff", "round2")
TEMPLATE = os.path.join(PROC, "SC_double_coding_template.csv")
os.makedirs(OUT_DIR, exist_ok=True)

IND = ["s1", "u3", "c3", "cr1", "st3", "e4"]
ROLES = ("A", "B")
FIELDS = (["序号", "bvid", "title", "desc", "intro"]
          + IND + ["coder_id", "coded_date", "note"])

# 任何含以下片段的列名都不得出现在交付表里（泄露自检用）
FORBIDDEN = ("coderA", "coderB", "view", "like", "coin", "favorite", "share",
             "reply", "danmaku", "engage_rate", "rank", "follower",
             "heat_tier", "play", "s_simple", "s_unexpected", "s_concrete",
             "s_credible", "s_emotional", "s_stories")

# ---------------------------------------------------------------- v0.3 细则
RULES = [
    ("s1", "Simple 简约",
     "标题能用一句话复述一个核心主张；副标题、补充限定不改变主句单一性",
     "两个及以上并列话题、开放式罗列、多个并列设问",
     "长标题 ≠ 多主张；「A 和 B 的差距」是单一比较主张，仍判 1"),
    ("u3", "Unexpected 意外",
     "同一文本内两组数量级明显不同的数字，或 A/B 冲突并置",
     "只有一个数字、同一集合内的数量、量级相近的数字、纯疑问句",
     "疑问句/悬念归规则项 u2；u3 不是「看起来意外」的笼统判断"),
    ("c3", "Concrete 具体",
     "专有名词 / 具体案例：真实人名、机构、产品、期刊、案件名、国名地名",
     "泛指类别、职业、角色、群称、抽象概念、普通物品名",
     "普通物品（煎锅、手机）归规则项 c2，c3 不重复计；能指到「那一个」→1，只能指到「一类」→0"),
    ("cr1", "Credible 可信",
     "简介明确注明数据来源 / 论文 / 报告名 / 机构署名",
     "只写「据说」「有研究表明」而无出处；出现「数据」二字但无出处",
     "与规则项 cr2（依据词）不同，规则未改"),
    ("st3", "Stories 故事",
     "人物 + 障碍 + 结局三者齐全的困境—转折结构",
     "设问式标题、假设前提、事件罗列、活动介绍、纯说明、纯清单",
     "标题讲一个事件 ≠ 叙事；「先/后来/结果」只是 st2，单独出现不能判 1"),
    ("e4", "Emotional 情感",
     "明确情绪唤起意图：直接情绪词、吐槽/诉苦语气、诉诸第二人称的煽动",
     "纯信息设问、事实陈述、实用指导、新闻事实（即使带感叹号）、轻微感受但整体中立",
     "疑问/反差/悬念是信息缺口（U 维度）不是情绪；与规则项 e1 互补但不等同"),
]

HDR_FILL = PatternFill("solid", fgColor="DCE6F1")
NOTE_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="B7C9DC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def intro_lines(role, n):
    return [
        ("SUCCES 项目 · 编码人 %s 填写说明（第二轮）" % role, "title"),
        ("版本：Codebook v0.3 ｜ 2026-11-06 ｜ 样本：%d 条视频 × 6 个指标 = %d 格" % (n, n * 6), "sub"),
        ("", "body"),
        ("一、你要做什么", "h"),
        ("在「编码表」sheet 里，对每条视频的 6 个指标各填一个数字：1 = 符合 / 出现，0 = 不符合 / 未出现，9 = 实在判不准。", "body"),
        ("只依据表内 title + desc + intro 文本判断，不需要、也不要去 B 站搜索或打开原视频。", "body"),
        ("本轮两位编码人（A / B）各拿一份内容相同、互不含对方答案的表，都按 v0.3 独立填写。", "body"),
        ("", "body"),
        ("二、请务必独立作答（这一条比填对更重要）", "h"),
        ("本项目要计算 Cohen's kappa（评分者间一致性），前提是两位真人互不知道对方的判断。", "body"),
        ("这份表已刻意移除对方的全部答案与判定理由，也移除了播放量、点赞、排名等结果数据。", "body"),
        ("· 不要向另一位编码人询问任何一条的判断，也不要讨论具体条目的尺度；", "body"),
        ("· 不要查看视频的播放/点赞/评论数据（会造成「看到爆款就觉得它更 Simple」的后见之明偏差）；", "body"),
        ("· 不要改动 title / desc / intro 三列，也不要增删行；", "body"),
        ("· 判不准就填 9 并在 note 写一句理由，不要猜。9 会作为独立类别计入 kappa，请节制使用。", "body"),
        ("", "body"),
        ("三、编码前先校准", "h"),
        ("先各自通读下方 v0.3 细则，再独立试编 3 条虚构例句；校准阶段允许讨论「规则表述是否清楚」，", "body"),
        ("但进入正式 13 条后不得交流任何一条的判定。若整批某指标判 1 的比例接近 100%，", "body"),
        ("请先回看该指标的反例复核尺度 —— 常量边际会让 kappa 无法估计，即使两人完全一致也算不出信度。", "body"),
        ("", "body"),
        ("四、素材范围", "h"),
        ("编码单元 = 一条视频一行；素材 = 标题 + 简介 + 前 30 秒口播（intro）。", "body"),
        ("本轮字幕覆盖率为 0%，intro 列为空，按 title + desc 判断即可；desc 为空的条目只按 title 判断。", "body"),
        ("本研究测的是「包装特征」，不是内容质量，不需要评价视频好不好。", "body"),
        ("", "body"),
        ("五、六个指标的判定细则（v0.3；例句均为虚构，不来自本表 13 条）", "h"),
    ]


def example_lines(role, n):
    return [
        ("", "body"),
        ("六、示例（全部虚构，仅示范记分口径，不得据此反推本表任何一条的答案）", "h"),
        ("例 1｜标题：「为什么罗翔说张三的案子判了 3 年，隔壁案只判 3 个月？」｜简介：空", "body"),
        ("　s1=1（单一主张） · u3=1（3 年 vs 3 个月，数量级反差） · c3=1（罗翔 / 张三是具体人名）", "body"),
        ("　cr1=0（无出处） · st3=0（无困境—转折叙事） · e4=0（中性设问）", "body"),
        ("例 2｜标题：「我朋友考研三战失败，后来去做了木匠，现在反而活得松弛」→ st3=1（人物+障碍+结局）", "body"),
        ("例 3｜标题：「疯批冷空气要来了，能不能别搞我们啊」→ e4=1（明确吐槽/情绪唤起）", "body"),
        ("例 4｜标题：「职场沟通、时间管理与情绪控制」→ s1=0（并列罗列）", "body"),
        ("", "body"),
        ("七、交回方式", "h"),
        ("1. 填「编码表」sheet 的 s1/u3/c3/cr1/st3/e4 六列，全部 %d 行都要填，不留空格；" % n, "body"),
        ("2. 在 coder_id 填你的代号（昵称即可，请与另一位编码人不同），coded_date 填完成日期 YYYY-MM-DD；", "body"),
        ("3. note 列可选，用来写判 9 的理由或任何边界情形；", "body"),
        ("4. 直接把整个文件发回，不要改文件名、列名、列顺序，不要删除「填写说明」sheet。", "body"),
        ("预计用时约 20–40 分钟。拿不准的按 9 + note 处理，不需要为了「配合」而猜。", "body"),
        ("", "body"),
        ("—— 以下为项目方内部备注，编码人无需操作 ——", "sub"),
        ("本表对应角色 %s；项目方回收后会做值域/完整性校验并合并，两份都到齐后才计算 kappa。" % role, "body"),
        ("若 kappa < 0.70，回编码手册修订判定细则后重编，并在报告写明修订过程——这是研究设计素养，不是需要掩盖的缺陷。", "body"),
    ]


def read_source():
    with open(TEMPLATE, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("主模板为空，请先运行 SC_make_coding_sheets.py")
    out = []
    for i, r in enumerate(rows, 1):
        out.append({
            "序号": i,
            "bvid": r["bvid"],
            "title": r.get("title", ""),
            "desc": r.get("desc", ""),
            "intro": r.get("intro", ""),
            "coder_id": "",
            "coded_date": "",
            "note": "",
            **{k: "" for k in IND},
        })
    return out


def leak_check(rows, texts):
    """列名、单元格、以及发给编码人的说明文本都不得含对方答案或结果变量线索。"""
    for k in FIELDS:
        low = k.lower()
        assert not any(t in low for t in (f.lower() for f in FORBIDDEN)), \
            "泄露风险：列名 %s 含禁用片段" % k
    banned = ("判1", "判0", "assistant-coderA-demo", "数据质量", "PREVIEW-UNVERIFIED")
    blob = "\n".join(str(v) for r in rows for v in r.values())
    for p in banned:
        assert p not in blob, "泄露风险：数据区含判定痕迹「%s」" % p
    blob_text = "\n".join(texts)
    for r in rows:
        assert r["bvid"] not in blob_text, \
            "泄露风险：说明文本出现样本 bvid %s" % r["bvid"]
    for p in ("assistant-coderA-demo", "kappa=0.000", "PREVIEW"):
        assert p not in blob_text, "泄露风险：说明文本含第一轮结果「%s」" % p
    assert len({r["bvid"] for r in rows}) == len(rows), "bvid 有重复"
    print("  盲法自检：列名 / 数据区 / 说明文本均无对方答案、判定痕迹、样本线索或结果变量 ✓")


def write_csv(rows, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def style_instructions(ws, rule_header):
    """A 列是内部 tag（隐藏）；可见文字放在 B:F 合并区，避免长句被窄列截断。"""
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].hidden = True
    for col, width in zip("BCDEF", (13, 34, 46, 46, 48)):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows():
        tag = row[0].value or ""
        lead = row[1]
        r = row[0].row
        for c in row[1:]:
            c.alignment = Alignment(vertical="top", wrap_text=True)
        if tag == "title":
            lead.font = Font(bold=True, size=16, color="1F3864")
        elif tag == "h":
            lead.font = Font(bold=True, size=12, color="1F3864")
            for c in row[1:]:
                c.fill = HDR_FILL
        elif tag == "sub":
            lead.font = Font(italic=True, size=10, color="595959")
        elif tag == "rule":
            for c in row[1:]:
                c.font = Font(size=10, color="222222")
                c.border = BORDER
            if r == rule_header:
                for c in row[1:]:
                    c.fill = HDR_FILL
                    c.font = Font(bold=True, size=10, color="1F3864")
        else:
            lead.font = Font(size=10, color="222222")
        ws.row_dimensions[r].height = (62 if tag == "rule"
                                       else max(20, 17 * (len(str(lead.value or "")) // 85 + 1)))


def build_xlsx(rows, path, role):
    wb = Workbook()
    ws = wb.active
    ws.title = "填写说明"
    for text, tag in intro_lines(role, len(rows)):
        ws.append([tag, text])
        if text:
            ws.merge_cells(start_row=ws.max_row, start_column=2,
                           end_row=ws.max_row, end_column=6)
    # 规则表紧接「五、判定细则」标题
    ws.append(["rule", "指标", "维度", "判 1 的条件", "判 0 的条件", "易错点"])
    rule_header = ws.max_row
    for ind, dim, one, zero, trap in RULES:
        ws.append(["rule", ind, dim, one, zero, trap])
    for text, tag in example_lines(role, len(rows)):
        ws.append([tag, text])
        if text:
            ws.merge_cells(start_row=ws.max_row, start_column=2,
                           end_row=ws.max_row, end_column=6)
    style_instructions(ws, rule_header)

    cd = wb.create_sheet("编码表")
    cd.append(FIELDS)
    for c in cd[1]:
        c.fill = HDR_FILL
        c.font = Font(bold=True, size=10, color="1F3864")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
    cd.row_dimensions[1].height = 30
    for r in rows:
        cd.append([r[k] for k in FIELDS])

    widths = {"序号": 6, "bvid": 17, "title": 44, "desc": 68, "intro": 14,
              "s1": 7, "u3": 7, "c3": 7, "cr1": 7, "st3": 7, "e4": 7,
              "coder_id": 16, "coded_date": 14, "note": 38}
    for i, k in enumerate(FIELDS, 1):
        cd.column_dimensions[get_column_letter(i)].width = widths[k]
    for row in cd.iter_rows(min_row=2):
        for c in row:
            c.border = BORDER
            c.alignment = Alignment(vertical="top", wrap_text=True)
        cd.row_dimensions[row[0].row].height = 46
    for col in range(6, len(FIELDS) + 1):
        for row in range(2, len(rows) + 2):
            cd.cell(row=row, column=col).fill = NOTE_FILL

    dv = DataValidation(type="list", formula1='"0,1,9"', allow_blank=True,
                        showErrorMessage=True, errorTitle="取值不合法",
                        error="只能填 0（未出现）/ 1（出现）/ 9（判不准）")
    dv.errorStyle = "stop"
    cd.add_data_validation(dv)
    dv.add("F2:K%d" % (len(rows) + 1))
    cd.freeze_panes = "C2"
    wb.save(path)


def write_instructions(path, n):
    rules = "\n".join("| `%s` | %s | %s | %s | %s |" % r for r in RULES)
    text = """# SUCCES 项目 · 第二轮双人编码填写说明（A / B 各一份）

版本：**Codebook v0.3** ｜ 2026-11-06 ｜ 样本：{n} 条视频 × 6 个指标 = {cells} 格／人

> 第一轮 20% 双人编码的一致性未达标，按预注册「低 kappa → 修订手册 → 重编」补订了判定细则。
> 本轮 **A、B 两位真人都按 v0.3 重编同一 {n} 条**，各拿一份互不含对方答案的表。
> 规则一改，若只有一方重填，就会变成「A 用旧规则、B 用新规则」，比较不成立。

## 你要做什么

在 `SC_round2_coderA_sheet.xlsx` / `SC_round2_coderB_sheet.xlsx` 的「编码表」sheet 里，
对每条视频的 6 个指标各填一个数字：**1 = 符合 / 出现；0 = 不符合 / 未出现；9 = 实在判不准**。
只依据表内 `title` + `desc` + `intro` 文本判断，不需要、也不要去 B 站搜索或打开原视频。

## 请务必独立作答（这一条比填对更重要）

Cohen's kappa 成立的前提是两位真人互不知道对方的判断。两份表都刻意移除了对方答案、
判定理由与播放/点赞/排名等结果数据。

- 不要向另一位编码人询问任何一条的判断，也不要讨论具体条目的尺度；
- 不要查看视频的播放 / 点赞 / 评论数据；
- 不要改动 `title` / `desc` / `intro` 三列，也不要增删行；
- 判不准填 9 并在 `note` 写一句理由，不要猜。9 会作为独立类别计入 kappa，请节制使用。

**编码前先校准**：两人各自通读 v0.3 细则，独立试编 3 条虚构例句；校准阶段允许讨论
「规则表述是否清楚」，进入正式 {n} 条后不得交流任何一条的判定。
若整批某指标判 1 的比例接近 100%，先回看反例复核尺度 —— 常量边际会让 kappa 无法估计。

**素材范围**：字幕覆盖率为 0%，`intro` 为空；`desc` 为空的条目只按 `title` 判断。
本研究测的是「包装特征」，不是内容质量。

## 六个指标的判定细则（v0.3）

| 指标 | 维度 | 判 1 的条件 | 判 0 的条件 | 易错点 |
|---|---|---|---|---|
{rules}

**例句全部虚构，不来自本表 {n} 条，不得据此反推任何一条的答案**：

- 「为什么罗翔说张三的案子判了 3 年，隔壁案只判 3 个月？」→ `s1=1` `u3=1` `c3=1` `cr1=0` `st3=0` `e4=0`
- 「我朋友考研三战失败，后来去做了木匠，现在反而活得松弛」→ `st3=1`
- 「疯批冷空气要来了，能不能别搞我们啊」→ `e4=1`
- 「职场沟通、时间管理与情绪控制」→ `s1=0`

完整边界与反例见项目内 `docs/codebook.md`「v0.3 判定细则补订」。

## 交回方式

1. 填 `s1/u3/c3/cr1/st3/e4` 六列，全部 {n} 行都要填，不留空格；
2. `coder_id` 填你的代号（昵称即可，**两人必须不同**），`coded_date` 填 `YYYY-MM-DD`；
3. `note` 列可选，用来写判 9 的理由或边界情形；
4. 把整个文件发回，**不要改文件名、列名、列顺序，不要删除「填写说明」sheet**。

预计用时约 20–40 分钟／人。

---

### 可直接复制的发送文案（分别发给两个人）

> 麻烦帮忙做一个独立编码，约 20–40 分钟。附件 Excel 的第一个 sheet 是填写说明，
> 第二个 sheet 是 {n} 条视频，每条填 6 个 0/1（判不准填 9 并写一句理由）。
> 规则刚按上一轮的反馈细化过（v0.3），请先读说明再做。
> 这次是两位编码人各自独立填写、用来算评分者信度的，所以**请不要问另一个人怎么判，
> 也不要去查视频播放数据**；只看标题和简介按说明判断就好。
> 填完把原文件发回给我，并在 `coder_id` 留个代号（昵称即可），谢谢！

### 项目方回收备注（编码人无需操作）

```bash
python3 SC_import_coderB.py <A 交回文件> --role A --dry-run
python3 SC_import_coderB.py <A 交回文件> --role A
python3 SC_import_coderB.py <B 交回文件> --role B
Rscript R/SC_kappa.R          # 两份都到齐后才会产出真实 kappa
```

导入脚本写入前自动备份主模板，且只写本角色的列，不覆盖另一方答案。
若仍有 kappa < 0.70，回 `docs/codebook.md` 修订细则后重编，并在报告写明修订过程。
""".format(n=n, cells=n * len(IND), rules=rules)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    rows = read_source()
    print("导出第二轮 v0.3 双份盲法填写表：%d 条样本 × 2 位编码人" % len(rows))
    texts = []
    for role in ROLES:
        texts += [t for t, _ in intro_lines(role, len(rows)) + example_lines(role, len(rows))]
    leak_check(rows, texts)

    produced = []
    for role in ROLES:
        stem = "SC_round2_coder%s_sheet" % role
        p_xlsx = os.path.join(OUT_DIR, stem + ".xlsx")
        p_csv = os.path.join(OUT_DIR, stem + ".csv")
        write_csv(rows, p_csv)
        build_xlsx(rows, p_xlsx, role)
        produced += [p_xlsx, p_csv]

    p_md = os.path.join(OUT_DIR, "SC_round2_instructions.md")
    p_zip = os.path.join(OUT_DIR, "SC_round2_handoff.zip")
    write_instructions(p_md, len(rows))
    produced += [p_md]
    with zipfile.ZipFile(p_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in produced:
            z.write(p, arcname=os.path.basename(p))

    for p in produced + [p_zip]:
        print("  %-38s %7d bytes" % (os.path.basename(p), os.path.getsize(p)))


if __name__ == "__main__":
    main()
