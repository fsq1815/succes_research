#!/usr/bin/env python3
# SC_import_coderB.py — 校验并合并 A / B 任一位编码人交回的填写表
#
# 用法（第二轮 v0.3）：
#   python3 SC_import_coderB.py <交回文件.xlsx|csv> --role A     # 写入 *_coderA 六列
#   python3 SC_import_coderB.py <交回文件.xlsx|csv> --role B     # 写入 *_coderB 六列
#   python3 SC_import_coderB.py <交回文件> --role B --dry-run    # 只校验，不写入
#   python3 SC_import_coderB.py <交回文件> --template <模板.csv> # 测试时指向副本
#
# 设计约束：
#   1. 真实 kappa 只能由两位真实编码人产生；本脚本不生成、不推测任一格答案。
#   2. 写入前自动备份主模板；**只写本角色的列**，另一方的答案、coded_date 与 note
#      一律不覆盖；本角色的日期与备注写入 coder{A,B}_date / note_coder{A,B} 新列。
#   3. 校验失败即退出，绝不「半合并」：bvid 集合、素材一致性、六列值域与完整性都通过才写。
#   4. 交回文件的 coder_id 不得为脚本代填标识（assistant-coderA-demo / PREVIEW-*）。
#
# 两份都写回后运行：Rscript R/SC_kappa.R

import argparse
import csv
import os
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(ROOT, "data", "processed")
DEFAULT_TEMPLATE = os.path.join(PROC, "SC_double_coding_template.csv")
ARCHIVE = os.path.join(PROC, "archive_coderB_import")

IND = ["s1", "u3", "c3", "cr1", "st3", "e4"]
MATERIAL = ["title", "desc", "intro"]
VALID = {"0", "1", "9"}
BANNED_IDS = ("assistant-coderA-demo", "PREVIEW-UNVERIFIED")


def role_cols(role):
    """本角色专属的新列（不覆盖任何既有列）。"""
    return ["coder%s_date" % role, "note_coder%s" % role]


def norm(v):
    """把 Excel 可能给出的 1 / 1.0 / ' 1 ' 统一成 '1'；空值统一成 ''。"""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _sanitize_xlsx(path):
    """WPS / 腾讯文档等编辑器会写出 `<fill/>` 空节点，openpyxl 反序列化样式表时抛
    TypeError: Fill() takes no arguments。把空 fill 补成合法节点后另存**临时副本**，
    绝不改动交回的原件。返回 (可读取路径, 待清理的临时文件路径或 None)。
    """
    try:
        with zipfile.ZipFile(path) as z:
            styles = z.read("xl/styles.xml").decode("utf-8")
    except (KeyError, UnicodeDecodeError, zipfile.BadZipFile):
        return path, None
    if not re.search(r"<fill\s*/>", styles):
        return path, None
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", prefix="SC_coderB_clean_")
    os.close(fd)
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "xl/styles.xml":
                data = re.sub(r"<fill\s*/>", "<fill><patternFill/></fill>",
                              data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)
    return tmp, tmp


def read_back(path):
    if path.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        clean, tmp = path, None
        try:
            try:
                wb = load_workbook(clean, data_only=True)
            except Exception:
                clean, tmp = _sanitize_xlsx(path)
                if tmp is None:
                    raise
                wb = load_workbook(clean, data_only=True)
                print("  注：交回文件的样式表由其它表格软件写出，已用临时副本绕过兼容性问题（原件未改动）")
            if "编码表" not in wb.sheetnames:
                raise ValueError("xlsx 缺少「编码表」sheet（现有：%s）" % ", ".join(wb.sheetnames))
            ws = wb["编码表"]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                raise ValueError("「编码表」sheet 为空")
            header = [norm(c) for c in rows[0]]
            return [dict(zip(header, [norm(c) for c in r])) for r in rows[1:]
                    if any(norm(c) for c in r)]
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k: norm(v) for k, v in r.items()} for r in csv.DictReader(f)]


def check(back, template, role):
    """校验交回表；返回 (coder_id, coded_date, warnings)，失败直接抛 ValueError。"""
    need = ["bvid"] + MATERIAL + IND
    missing = [c for c in need if c not in back[0]]
    if missing:
        raise ValueError("交回文件缺列：%s（请勿改动列名/列顺序）" % ", ".join(missing))

    bmap = {}
    for r in back:
        bv = r["bvid"]
        if not bv:
            continue
        if bv in bmap:
            raise ValueError("bvid 重复：%s（请勿复制粘贴行）" % bv)
        bmap[bv] = r

    exp = {r["bvid"] for r in template}
    got = set(bmap)
    if got != exp:
        lost = sorted(exp - got)
        added = sorted(got - exp)
        raise ValueError("bvid 集合与模板不一致：缺 %d 条 %s；多 %d 条 %s"
                         % (len(lost), lost[:4], len(added), added[:4]))

    tmap = {r["bvid"]: r for r in template}
    warnings = []
    n_ind = 0
    n_9 = 0
    bad_cells = []
    for bv, r in bmap.items():
        for col in MATERIAL:
            a = norm(tmap[bv].get(col, "")).strip()
            b = norm(r.get(col, "")).strip()
            if a != b:
                raise ValueError("素材被改动：%s 的 %s 列与模板不一致（编码单元必须一致）" % (bv, col))
        for ind in IND:
            v = norm(r.get(ind, ""))
            if v not in VALID:
                bad_cells.append("%s 的 %s = %r" % (bv, ind, v))
                continue          # 一次列全，不让用户一格一格地试
            n_ind += 1
            if v == "9":
                n_9 += 1
                if not norm(r.get("note", "")):
                    warnings.append("%s 的 %s 判 9 但 note 未写理由" % (bv, ind))
    if bad_cells:
        raise ValueError("值域/完整性错误（%d 格）：%s。只能是 0 / 1 / 9，不留空格"
                         % (len(bad_cells), "；".join(bad_cells[:12])))

    # 第二轮交付表用通用 coder_id；兼容第一轮的 coderB_id / coderA_id
    id_col = next((c for c in ("coder_id", "coder%s_id" % role) if c in back[0]),
                  "coder%s_id" % role)
    ids = sorted({norm(r.get(id_col, "")) for r in bmap.values()} - {""})
    if not ids:
        raise ValueError("%s 全为空：请填你的代号，用于证明是真人独立编码" % id_col)
    if len(ids) > 1:
        warnings.append("检测到多个 %s：%s（若为一人填写请统一）" % (id_col, ids))
    for bad in BANNED_IDS:
        if bad in ids:
            raise ValueError("coder_id 不能是脚本代填/预演标识「%s」（两位真人独立编码前提）" % bad)

    dates = sorted({norm(r.get("coded_date", "")) for r in bmap.values()} - {""})
    print("  角色：coder%s ｜ 校验通过：%d 条 × %d 指标 = %d 格，全部在 0/1/9 值域内" %
          (role, len(bmap), len(IND), n_ind))
    print("  素材一致性：title / desc / intro 三列与模板逐行一致 ✓")
    print("  编码人：%s ｜ 完成日期：%s ｜ 判 9 的格数：%d" %
          (", ".join(ids), ", ".join(dates) or "(未填)", n_9))
    for w in warnings:
        print("  ⚠ 提醒：" + w)
    return ids[0], (dates[0] if dates else ""), warnings


def main():
    ap = argparse.ArgumentParser(description="校验并合并 A / B 填写表")
    ap.add_argument("file", help="交回的 xlsx 或 csv")
    ap.add_argument("--role", choices=("A", "B"), default="B",
                    help="这份表属于哪位编码人（默认 B；决定写入 *_coderA 还是 *_coderB）")
    ap.add_argument("--dry-run", action="store_true", help="只校验不写入")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE, help="主模板路径（测试可指向副本）")
    a = ap.parse_args()

    if not os.path.exists(a.file):
        raise SystemExit("找不到交回文件：%s" % a.file)
    with open(a.template, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        fields = list(rd.fieldnames or [])
        template = list(rd)
    if not template:
        raise SystemExit("主模板为空：%s" % a.template)

    back = read_back(a.file)
    if not back:
        raise SystemExit("交回文件没有数据行")
    n_note = sum(1 for r in back if not norm(r.get("bvid", "")))
    print("读入 %s：%d 行%s" % (
        os.path.basename(a.file), len(back),
        "（其中 %d 行无 bvid，为复制进表的判定细则/备注，已忽略；有效编码行 %d 条）"
        % (n_note, len(back) - n_note) if n_note else ""))

    try:
        coder_id, coded_date, _ = check(back, template, a.role)
    except ValueError as e:
        print("\n✗ 校验失败：%s" % e)
        print("  主模板未做任何改动。请退回编码人修正后重交。")
        sys.exit(1)

    suff = "_coder" + a.role
    bmap = {r["bvid"]: r for r in back}
    new_fields = fields + [c for c in role_cols(a.role) if c not in fields]
    for r in template:
        b = bmap[r["bvid"]]
        for ind in IND:
            r[ind + suff] = norm(b[ind])
        r["coder%s_id" % a.role] = coder_id
        r["coder%s_date" % a.role] = coded_date
        r["note_coder%s" % a.role] = norm(b.get("note", ""))

    if a.dry_run:
        print("\n--dry-run：校验通过，未写入。以上结果可用于确认交回文件是否合格。")
        return

    os.makedirs(ARCHIVE, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(ARCHIVE, "SC_double_coding_template_before_%s_role%s.csv"
                          % (stamp, a.role))
    shutil.copy2(a.template, backup)

    tmp = a.template + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=new_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(template)
    os.replace(tmp, a.template)

    shown = (os.path.relpath(a.template, ROOT)
             if os.path.abspath(a.template).startswith(os.path.abspath(ROOT))
             else os.path.abspath(a.template))
    other = "B" if a.role == "A" else "A"
    print("\n✓ 已合并写回：%s（角色 coder%s）" % (shown, a.role))
    print("  写入前备份：%s" % os.path.relpath(backup, ROOT))
    print("  保留未动：*_coder%s / coder%s_id / coded_date / note（另一方的答案与判定理由）"
          % (other, other))
    print("  下一步：等另一份也导入后运行 Rscript R/SC_kappa.R → 真实 kappa 与 bootstrap CI")


if __name__ == "__main__":
    main()
