# R/SC_kappa.R — 随机 20% 双人编码的 Cohen's kappa
#
# 依赖：仅 R base（不装包），可直接 Rscript R/SC_kappa.R
# 输入：data/processed/SC_double_coding_template.csv    （真人双编码）
#       data/processed/SC_kappa_demo_SIMULATED.csv      （模拟自检，绝不充作真实结果）
# 输出：output/SC_kappa_report.txt
#
# 诚实约束（务必保留）：
#   · kappa 只在两位**真实编码人**都填完后计算；coderB 为空时状态为 PENDING，不编造数字。
#   · coderB 必须来自 data/processed/handoff/ 的盲法交付表（SC_export_coderB.py），
#     经 SC_import_coderB.py 校验后合并；不要把含 coderA 答案的主模板直接发给第二编码人。
#   · 模拟自检只证明公式实现正确，其数值不得写进任何对外报告。
#   · n 很小时（本轮 13 条）kappa 的置信区间极宽，只能作为流程检查，不能作为信度证据。
#   · 两位真人都填完后须同时看点估计与 CI：点估计 >= 0.70 但 CI 跨 0 不能声称达标。

args <- commandArgs(trailingOnly = FALSE)
fp <- sub("^--file=", "", args[grep("^--file=", args)])
ROOT <- if (length(fp)) dirname(dirname(normalizePath(fp))) else getwd()
setwd(ROOT)
PROC <- "data/processed"
OUT <- "output"
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

# 可选：--input=<双编码 csv> --output=<报告 txt>
# 用于在临时副本上做「非正式预演」，不触碰 data/processed/ 下的真实数据。
cli <- commandArgs(trailingOnly = TRUE)
opt <- function(flag, default) {
  i <- grep(paste0("^", flag, "="), cli)
  if (length(i)) sub(paste0("^", flag, "="), "", cli[i[1]]) else default
}
DBL_PATH <- opt("--input", file.path(PROC, "SC_double_coding_template.csv"))
OUT_PATH <- opt("--output", file.path(OUT, "SC_kappa_report.txt"))
IS_PREVIEW <- OUT_PATH != file.path(OUT, "SC_kappa_report.txt")

IND <- c("s1", "u3", "c3", "cr1", "st3", "e4")

# ---- Cohen's kappa（无第三方依赖，支持 0/1/9 多类别）------------------------
cohen_kappa <- function(a, b) {
  ok <- !is.na(a) & !is.na(b)
  a <- a[ok]; b <- b[ok]
  n <- length(a)
  if (n < 2) return(list(kappa = NA, po = NA, pe = NA, n = n, note = "有效配对 < 2"))
  lev <- sort(unique(c(a, b)))
  tab <- table(factor(a, levels = lev), factor(b, levels = lev))
  po <- sum(diag(tab)) / n
  pe <- sum(rowSums(tab) * colSums(tab)) / (n * n)
  if (is.na(pe) || pe >= 1 - 1e-12) {
    return(list(kappa = NA, po = po, pe = pe, n = n,
                note = "边际全集中在一类，pe≈1，kappa 不可定义（高同意率但无法校正机遇一致）"))
  }
  list(kappa = (po - pe) / (1 - pe), po = po, pe = pe, n = n, note = "")
}

# bootstrap 百分位 CI（小样本下比正态近似更稳妥）
kappa_ci <- function(a, b, B = 2000, seed = 20261106) {
  set.seed(seed)
  ok <- !is.na(a) & !is.na(b)
  a <- a[ok]; b <- b[ok]
  n <- length(a)
  if (n < 3) return(c(NA, NA))
  vals <- replicate(B, {
    i <- sample.int(n, n, replace = TRUE)
    cohen_kappa(a[i], b[i])$kappa
  })
  vals <- vals[is.finite(vals)]
  if (length(vals) < B * 0.5) return(c(NA, NA))
  as.numeric(quantile(vals, c(0.025, 0.975), na.rm = TRUE))
}

band <- function(k) {
  if (is.na(k)) return("不可计算")
  if (k < 0) "差(poor)" else if (k < 0.21) "轻微(slight)" else
  if (k < 0.41) "一般(fair)" else if (k < 0.61) "中等(moderate)" else
  if (k < 0.81) "较高(substantial)" else "几乎完全一致(almost perfect)"
}

as_num <- function(x) suppressWarnings(as.numeric(as.character(x)))
read_utf8 <- function(p) read.csv(p, check.names = FALSE, fileEncoding = "UTF-8-BOM",
                                  stringsAsFactors = FALSE)

report <- c()
add <- function(...) report <<- c(report, sprintf(...))
add("SUCCES 项目 · 双人编码一致性（Cohen's kappa）报告")
if (IS_PREVIEW) add("*** PREVIEW / 非正式预演：在临时副本上运行，仅供诊断，不得写进任何对外报告 ***")
add("生成时间: %s", format(Sys.time(), "%Y-%m-%d %H:%M:%S"))
add("指标: %s", paste(IND, collapse = ", "))
add("判读阈值: Landis & Koch；目标 kappa >= 0.70；CI 为 2000 次 bootstrap 百分位区间")
add("")

# ---- 1. 真实双编码状态 -------------------------------------------------------
dbl_path <- DBL_PATH
add("== 1. 真实双人编码（本轮状态）==")
if (!file.exists(dbl_path)) {
  add("  模板不存在，请先运行 SC_make_coding_sheets.py")
} else {
  d <- read_utf8(dbl_path)
  main_path <- file.path(PROC, "SC_manual_coding.csv")
  n_all <- if (file.exists(main_path)) nrow(read_utf8(main_path)) else NA_integer_
  add("  双编码样本: %d 条（全样本 %d × 20%%，固定种子 20261106）", nrow(d), n_all)
  coder_ids <- function(col, fallback) {
    if (!(col %in% names(d))) return(fallback)
    v <- unique(trimws(as.character(d[[col]])))
    v <- v[!is.na(v) & v != ""]
    if (length(v)) paste(v, collapse = ", ") else fallback
  }
  add("  编码员 A: %s", coder_ids("coderA_id", "未登记"))
  add("  编码员 B: %s", coder_ids("coderB_id", "待第二位真人独立填写"))
  add("")
  status <- character(length(IND))
  kappas <- rep(NA_real_, length(IND))
  ci_lo <- rep(NA_real_, length(IND))
  ci_hi <- rep(NA_real_, length(IND))
  const_margin <- rep(FALSE, length(IND))
  add("  %-6s %-8s %-8s %-8s %-8s %s", "指标", "A填", "B填", "配对n", "同意率", "状态")
  for (i in seq_along(IND)) {
    ca <- paste0(IND[i], "_coderA"); cb <- paste0(IND[i], "_coderB")
    if (!(ca %in% names(d)) || !(cb %in% names(d))) {
      status[i] <- "缺列"; next
    }
    a <- as_num(d[[ca]]); b <- as_num(d[[cb]])
    na <- sum(!is.na(a)); nb <- sum(!is.na(b))
    pair <- sum(!is.na(a) & !is.na(b))
    agree <- if (pair > 0) mean(a[!is.na(a) & !is.na(b)] == b[!is.na(a) & !is.na(b)]) else NA
    if (nb == 0) {
      status[i] <- "PENDING"
      add("  %-6s %-8d %-8d %-8d %-8s %s", IND[i], na, nb, pair,
          if (is.na(agree)) "-" else sprintf("%.0f%%", 100 * agree), "PENDING：coderB 未填")
    } else {
      k <- cohen_kappa(a, b)
      ci <- kappa_ci(a, b)
      ci_lo[i] <- ci[1]; ci_hi[i] <- ci[2]
      av <- a[!is.na(a) & !is.na(b)]; bv <- b[!is.na(a) & !is.na(b)]
      const_margin[i] <- (length(unique(av)) == 1L) || (length(unique(bv)) == 1L)
      status[i] <- if (is.na(k$kappa)) "不可计算" else sprintf("kappa=%.3f [%.2f, %.2f] %s",
                                                              k$kappa, ci[1], ci[2], band(k$kappa))
      kappas[i] <- k$kappa
      add("  %-6s %-8d %-8d %-8d %-8s %s", IND[i], na, nb, pair,
          sprintf("%.0f%%", 100 * agree), status[i])
      if (k$note != "") add("         说明: %s", k$note)
      add("         po=%.3f pe=%.3f", k$po, k$pe)
      if (const_margin[i]) {
        add("        注意: 至少一位编码人该列取值恒定（常量边际），po≈pe 使 kappa 结构性趋近 0；")
        add("              这反映边际分布退化，不能解读为「两人分歧严重」。")
      }
    }
  }
  add("")
  if (all(status == "PENDING")) {
    add("  >>> 结论：真实 kappa = PENDING（尚未产生）。")
    add("  >>> 必须由第二位真人独立填写 *_coderB 六列后重跑本脚本，才会输出一致性数值。")
    add("  >>> 这一状态本身就是正确结果：没有第二位编码员时，不存在可报告的信度系数。")
  } else {
    kk <- kappas[is.finite(kappas)]
    if (length(kk)) add("  >>> 六指标 kappa 中位数 = %.3f（预注册目标 >= 0.70）", median(kk))
    pt <- IND[!is.na(kappas) & kappas >= 0.70]
    strict <- IND[!is.na(kappas) & kappas >= 0.70 & !is.na(ci_lo) & ci_lo > 0]
    add("  >>> 点估计 >= 0.70 的指标: %s", if (length(pt)) paste(pt, collapse = ", ") else "无")
    add("  >>> 且 95%% CI 下限 > 0 的指标: %s", if (length(strict)) paste(strict, collapse = ", ") else "无")
    if (!length(strict)) {
      add("  >>> 正式结论: 本轮**未达到**预注册信度目标，编码一致性证据不足。")
      add("  >>> 最终决策（2026-11-07 路径 C / 预注册变更 G）：六个人工语义指标**正式不采用**，")
      add("  >>> 排除出分析口径；六维得分只用规则项，混合口径另存 *_DIAGNOSTIC_ONLY。")
      add("  >>> 两轮数据全部保留归档；codebook 冻结 v0.3，不再重编。见 docs/SC_coding-adoption.md。")
      add("  >>> 项目报告不得写成「编码一致性达标」，不得只报点估计或写入任何 kappa 数值。")
    } else {
      add("  >>> 正式结论: %s 达到信度目标；其余指标仍需校准/修订后重编。", paste(strict, collapse = ", "))
    }
  }
  add("")
  add("  小样本提醒：本轮双编码 n=%d，kappa 的抽样误差很大；即使填完也应报告 CI，", nrow(d))
  add("  且只能作为流程检查。正式研究建议双编码 >= 30 条（或 >= 20%% 且不少于 30 条）。")
  if (any(const_margin))
    add("  常量边际指标：%s（见上方逐项注意）。", paste(IND[const_margin], collapse = ", "))
}
add("")

# ---- 2. 公式自检（SIMULATED，不得引用）--------------------------------------
add("== 2. 公式自检：模拟数据（SIMULATED — 以下数字不得写入任何对外报告）==")
demo_path <- file.path(PROC, "SC_kappa_demo_SIMULATED.csv")
if (file.exists(demo_path)) {
  dm <- read_utf8(demo_path)
  add("  模拟样本 n=%d；两名「编码员」由脚本按约 12%% 分歧率生成，非真人", nrow(dm))
  add("  %-6s %-10s %-18s %s", "指标", "kappa", "95% CI", "判读")
  for (ind in IND) {
    k <- cohen_kappa(as_num(dm[[paste0(ind, "_coderA")]]),
                     as_num(dm[[paste0(ind, "_coderB")]]))
    ci <- kappa_ci(as_num(dm[[paste0(ind, "_coderA")]]),
                   as_num(dm[[paste0(ind, "_coderB")]]))
    add("  %-6s %-10.3f %-18s %s", ind, k$kappa,
        sprintf("[%.2f, %.2f]", ci[1], ci[2]), band(k$kappa))
  }
  # 常量情形：检验 pe≈1 时是否被正确识别为不可定义
  kconst <- cohen_kappa(rep(1, 20), rep(1, 20))
  add("  边界用例（两编码员全判 1）: kappa=%s, 说明=%s",
      if (is.na(kconst$kappa)) "NA" else sprintf("%.3f", kconst$kappa), kconst$note)
  add("  >>> 本节仅验证 kappa/pe/CI/常量处理实现正确，不代表本项目任何真实一致性。")
} else {
  add("  模拟数据文件不存在，跳过。")
}
add("")

# ---- 3. 使用边界 -------------------------------------------------------------
add("== 3. 使用边界 ==")
add("  · 报告「编码一致性」一节应据本文件第 1 节如实报告 kappa 与 CI，并说明 n 小、CI 宽；")
add("    未达 0.70 或 CI 跨 0 时必须明确写「信度未达标、本轮结果不采用」，不得只报点估计。")
add("  · 不得把第 2 节模拟数值当作信度证据；不得写「kappa 达标」而无真实双人数据。")
add("  · 低 kappa 的处理：回 docs/codebook.md 做共同校准 → 修订判定细则 → 重编 → 记录修订过程，")
add("    这是研究设计素养的体现，不是需要掩盖的缺陷。")

writeLines(report, OUT_PATH)
cat(paste(report, collapse = "\n"), "\n")
