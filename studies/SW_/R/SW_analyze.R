# R/SW_analyze.R — 按 docs/SW_preregistration.md v1.0 执行的推断分析
#
# 依赖：仅 base R（lm / p.adjust / pt），不装包、不联网
# 输入：data/processed/SW_analysis.csv（由 SW_prepare.py 生成）
# 输出：output/SW_results.txt, SW_coefficients.csv, SW_robustness.csv
#
# ⚠️ 本文件只在预注册冻结之后运行；任何口径改动必须先在预注册第 9 节登记。
#    全篇只做关联解释，不写因果；主因变量是「高赞评论中的信息性讨论」，不是认知增益。

args <- commandArgs(trailingOnly = FALSE)
fp <- sub("^--file=", "", args[grep("^--file=", args)])
ROOT <- if (length(fp)) dirname(dirname(normalizePath(fp))) else getwd()
setwd(ROOT)

DIMS <- c("s_simple", "s_unexpected", "s_concrete", "s_credible", "s_emotional", "s_stories")
HNAMES <- c("H1 Simple", "H2 Unexpected", "H3 Concrete", "H4 Credible", "H5 Emotional", "H6 Stories")
OUT <- "output"
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

CTRL <- c("log_view", "log_duration", "title_len", "blurb_len",
          "factor(pub_year)", "factor(zone)", "factor(rank)", "log_comment_like")

load_ds <- function() {
  d <- read.csv("data/processed/SW_analysis.csv", stringsAsFactors = FALSE,
                check.names = FALSE, fileEncoding = "UTF-8-BOM")
  for (c0 in c(DIMS, "s_credible_cr4zero", "info_discussion", "info_learn",
               "info_echo", "ask", "explain", "fact", "msg_len", "view",
               "duration", "title_len", "blurb_len", "comment_like")) {
    d[[c0]] <- as.numeric(d[[c0]])
  }
  d$log_view <- log(pmax(d$view, 1))
  d$log_duration <- log1p(d$duration)
  d$log_comment_like <- log1p(pmax(d$comment_like, 0))
  d$up_mid <- as.character(d$up_mid)
  d$pub_year <- as.character(d$pub_year)
  d$zone <- as.character(d$zone)
  d$rank <- as.character(d$rank)
  d
}

# ---- 聚类稳健三明治（与 SK_analyze.R 同一实现）------------------------------
cluster_vcov <- function(fit, cl) {
  co <- coef(fit); keep <- !is.na(co)
  X <- model.matrix(fit)[, keep, drop = FALSE]
  u <- residuals(fit); n <- nrow(X); k <- ncol(X); G <- length(unique(cl))
  V0 <- summary(fit)$cov.unscaled
  meat <- matrix(0, k, k)
  for (g in unique(cl)) {
    i <- which(cl == g)
    s <- colSums(X[i, , drop = FALSE] * u[i])
    meat <- meat + outer(s, s)
  }
  adj <- (G / (G - 1)) * ((n - 1) / (n - k))
  list(V = adj * (V0 %*% meat %*% V0), G = G, n = n, k = k)
}

fit_spec <- function(d, label, y = "yvar", rhs = c(DIMS, CTRL), cl = "up_mid",
                     dataset_tag = NA) {
  dd <- d[is.finite(d[[y]]), , drop = FALSE]
  f <- as.formula(paste(y, "~", paste(rhs, collapse = " + ")))
  fit <- lm(f, data = dd, x = TRUE)
  cr <- cluster_vcov(fit, dd[[cl]])
  se <- sqrt(diag(cr$V)); b <- coef(fit); ok <- !is.na(b)
  b <- b[ok]; se <- se[seq_len(sum(ok))]
  idx <- match(DIMS, names(b)); estimable <- !is.na(idx)
  beta <- unname(as.numeric(b[idx])); s <- unname(as.numeric(se[idx]))
  tval <- beta / s
  dfree <- max(cr$G - 1, 1)
  p <- 2 * pt(-abs(tval), df = dfree)
  q <- p.adjust(p, method = "BH")
  ci_lo <- as.numeric(beta - qt(0.975, dfree) * s)
  ci_hi <- as.numeric(beta + qt(0.975, dfree) * s)
  verdict <- as.character(ifelse(!estimable | !is.finite(beta), "不可估（共线/稀疏）",
              ifelse(beta > 0 & q < 0.05, "获得支持",
              ifelse(beta > 0, "方向一致但不显著",
              ifelse(q < 0.05, "方向相反（显著负）", "方向相反且不显著")))))
  data.frame(
    model = label, dataset = if (is.na(dataset_tag)) unique(dd$split)[1] else dataset_tag,
    y = y, cluster = cl, N = nrow(dd), G = cr$G, k = cr$k,
    hypothesis = HNAMES, dim = DIMS, estimable = estimable,
    beta = as.numeric(beta), se = as.numeric(s), t = as.numeric(tval),
    p = as.numeric(p), q_BH = as.numeric(q),
    ci_lo = ci_lo, ci_hi = ci_hi,
    verdict = verdict, stringsAsFactors = FALSE
  )
}

vif_table <- function(d) {
  vars <- c(DIMS, "log_view", "log_duration", "title_len", "blurb_len", "msg_len")
  z <- d[, vars]
  z <- z[complete.cases(z), , drop = FALSE]
  out <- numeric(length(vars))
  for (i in seq_along(vars)) {
    f <- as.formula(paste(vars[i], "~", paste(vars[-i], collapse = " + ")))
    out[i] <- 1 / max(1 - summary(lm(f, data = z))$r.squared, 1e-8)
  }
  data.frame(variable = vars, VIF = round(out, 2))
}

d_all <- load_ds()
d <- d_all[d_all$split == "main", , drop = FALSE]
d$yvar <- d$info_discussion
dc <- d_all[d_all$split == "control", , drop = FALSE]
dc$yvar <- dc$info_discussion

L <- c(
  "SUCCES-Weekly · 推断分析结果",
  paste("生成时间:", format(Sys.time(), "%Y-%m-%d %H:%M:%S")),
  "预注册: docs/SW_preregistration.md v1.0（主样本采集期间冻结，未看过任何关联结果）",
  "因变量: info_discussion = 高赞评论中是否出现信息性讨论（求解提问/解释性陈述/事实复述）",
  "推断: 评论级 LPM + 按 UP 主聚类稳健标准误（base R 手写三明治）| 双侧 t | 六条假设 BH-FDR",
  "⚠️ 全篇只作关联解释；高赞热评 ≠ 全体观众；规则项命中 ≠ 真实认知增益；无因果识别策略。",
  ""
)

# ---- 0. 样本与窄口径报告 ----------------------------------------------------
L <- c(L, "== 0. 样本与测量体检 ==",
       sprintf("主样本 main: %d 条高赞评论 / %d 个视频 / %d 个 UP 主 / %d 个分区",
               nrow(d), length(unique(d$bvid)), length(unique(d$up_mid)), length(unique(d$zone))),
       sprintf("对照 control: %d 条评论 / %d 个视频", nrow(dc), length(unique(dc$bvid))),
       sprintf("dev 集（仅词典开发，已排除）: %d 条评论", sum(d_all$split == "dev")),
       sprintf("info_discussion 基础率: %.1f%% | info_learn 命中: %d 条 (%.2f%%), 唯一取值: %s",
               100 * mean(d$info_discussion), sum(d$info_learn),
               100 * mean(d$info_learn), paste(sort(unique(d$info_learn)), collapse = "/")),
       sprintf("info_echo 均值 %.4f | 非零 %d/%d",
               mean(d$info_echo), sum(d$info_echo > 0), nrow(d)),
       "→ S7：若 info_learn 近乎恒 0，则该构念在公开高赞热评中不可测，不强行建模。",
       "")

# ---- 1. 主模型 --------------------------------------------------------------
main <- fit_spec(d, "M0 主模型")
L <- c(L, "== 1. 主模型 M0（main, y=info_discussion, cluster=up_mid）==",
       sprintf("N=%d | G=%d | k=%d | 六条假设内 BH-FDR", main$N[1], main$G[1], main$k[1]))
L <- c(L, sprintf("%-16s %10s %9s %9s %9s  %-22s %s", "假设", "beta", "se", "p", "q_BH", "95% CI", "判定"))
for (i in seq_len(nrow(main)))
  L <- c(L, sprintf("%-16s %+10.4f %9.4f %9.4f %9.4f  [%+.4f,%+.4f]  %s",
                    main$hypothesis[i], main$beta[i], main$se[i], main$p[i], main$q_BH[i],
                    main$ci_lo[i], main$ci_hi[i], main$verdict[i]))
L <- c(L, sprintf("主模型获得支持的假设: %d / 6%s", sum(main$verdict == "获得支持", na.rm = TRUE),
                  if (sum(main$verdict == "获得支持", na.rm = TRUE)) paste(" →", paste(main$hypothesis[main$verdict == "获得支持"], collapse = ", ")) else ""),
       "", "VIF（六维 + 连续控制）:")
vt <- vif_table(d)
for (i in seq_len(nrow(vt))) L <- c(L, sprintf("  %-16s %6.2f", vt$variable[i], vt$VIF[i]))
L <- c(L, "")

# ---- 2. 稳健性 --------------------------------------------------------------
specs <- list()

# S1 按 bvid 聚类
specs[["S1 cluster=bvid"]] <- fit_spec(d, "S1 cluster=bvid", cl = "bvid")

# S2 视频级经验 logit
bv <- unique(d$bvid)
vid <- do.call(rbind, lapply(bv, function(b) {
  s <- d[d$bvid == b, , drop = FALSE]
  h <- sum(s$info_discussion); n <- nrow(s)
  base <- data.frame(
    bvid = b, split = "main", up_mid = s$up_mid[1], zone = s$zone[1],
    pub_year = s$pub_year[1], rank = "1",
    log_view = s$log_view[1], log_duration = s$log_duration[1],
    title_len = s$title_len[1], blurb_len = s$blurb_len[1],
    log_comment_like = mean(s$log_comment_like),
    yvar = log((h + 0.5) / (n - h + 0.5)),
    stringsAsFactors = FALSE)
  for (nm in DIMS) base[[nm]] <- as.numeric(s[[nm]][1])
  base
}))
specs[["S2 视频级比例"]] <- fit_spec(vid, "S2 视频级比例",
                                     rhs = c(DIMS, CTRL[!CTRL %in% c("factor(rank)", "log_comment_like")]),
                                     dataset_tag = "main")

# S3 info_echo（注明机械相关风险，不作主结论）
d3 <- d; d3$yvar <- d3$info_echo
specs[["S3 info_echo"]] <- fit_spec(d3, "S3 info_echo")

# S4 去掉 rank / comment_like
specs[["S4 去热评排序控制"]] <- fit_spec(d, "S4 去热评排序控制",
                                          rhs = c(DIMS, CTRL[!CTRL %in% c("factor(rank)", "log_comment_like")]))

# S5 control（非知识类）
specs[["S5 非知识类对照"]] <- fit_spec(dc, "S5 非知识类对照", dataset_tag = "control")

# S6 cr4 = 0
d6 <- d; d6$s_credible <- d6$s_credible_cr4zero; d6$yvar <- d6$info_discussion
specs[["S6 cr4=0"]] <- fit_spec(d6, "S6 cr4=0")

# S5 稀疏诊断（标记必须在输出表格之前设置）
nz_st <- sum(dc$s_stories > 0, na.rm = TRUE)
nz_cr <- sum(dc$s_credible > 0, na.rm = TRUE)
bv_st <- length(unique(dc$bvid[dc$s_stories > 0]))
up_st <- length(unique(dc$up_mid[dc$s_stories > 0]))
for (nm in names(specs)) {
  specs[[nm]]$sparse_flag <- FALSE
  specs[[nm]]$note <- ""
}
s5 <- specs[["S5 非知识类对照"]]
s5$sparse_flag[s5$dim %in% c("s_stories", "s_credible")] <- TRUE
s5$note[s5$dim == "s_stories"] <- sprintf(
  "仅 %d/%d 条非零、%d 视频、%d UP 主：稀疏伪估计，不可解读", nz_st, nrow(dc), bv_st, up_st)
s5$note[s5$dim == "s_credible"] <- "该组 s_credible 恒为 0，系数被 aliased，不可估"
specs[["S5 非知识类对照"]] <- s5

L <- c(L, "== 2. 稳健性 S1–S6（各设定下六维 beta / q_BH）==")
for (nm in names(specs)) {
  s <- specs[[nm]]
  L <- c(L, sprintf("--- %s | N=%d G=%d ---", nm, s$N[1], s$G[1]),
         sprintf("    %-16s %9s %9s  %s", "假设", "beta", "q_BH", "判定"))
  for (i in seq_len(nrow(s)))
    L <- c(L, sprintf("    %-16s %+9.4f %9.4f  %s%s",
                      s$hypothesis[i], s$beta[i], s$q_BH[i], s$verdict[i],
                      if (isTRUE(s$sparse_flag[i])) "  ⚠ 稀疏伪估计，不可解读" else ""))
  L <- c(L, "")
}

L <- c(L, "== 2b. S5 稀疏诊断（防止把伪估计当发现）==",
       sprintf("control: s_stories 非零 %d/%d 条（%d 视频 / %d UP 主）；s_credible 非零 %d/%d 条",
               nz_st, nrow(dc), bv_st, up_st, nz_cr, nrow(dc)),
       "→ S5 的 H6「获得支持」与 H4「不可估」都是稀疏/共线产物，不得作为发现、不得与 main 比较。",
       "")

# ---- 3. 方向一致性 ----------------------------------------------------------
L <- c(L, "== 3. 各稳健性设定与主模型的方向一致性 ==")
for (nm in names(specs)) {
  s <- specs[[nm]]
  agree <- sum(sign(s$beta) == sign(main$beta), na.rm = TRUE)
  sig <- sum(s$verdict == "获得支持" & !s$sparse_flag, na.rm = TRUE)
  L <- c(L, sprintf("  %-22s 方向一致 %d/6 | 该设定下支持 %d/6", nm, agree, sig))
}
L <- c(L, "",
       "== 4. 结论边界 ==",
       "· 支持判定写死为 beta>0 且 q_BH<0.05；稳健性只判断主结论是否脆弱，不替换主结果。",
       "· S3 info_echo 与六维同源派生自标题，存在机械相关，只作方向参考，不作主结论。",
       "· S5 非知识类与 S2 视频级若出现极端系数，须先检查稀疏/自由度，不得当作负向发现。",
       "· 不得写因果动词、「SUCCES 有效」、「观众获取了信息」、把 3 条高赞热评外推到全体观众。",
       "")

writeLines(L, file.path(OUT, "SW_results.txt"))
main_out <- main
write.csv(main_out, file.path(OUT, "SW_coefficients.csv"), row.names = FALSE)
rob <- do.call(rbind, specs)
write.csv(rob, file.path(OUT, "SW_robustness.csv"), row.names = FALSE)
cat("已写出 output/SW_results.txt, SW_coefficients.csv, SW_robustness.csv\n")
cat(sprintf("主模型获得支持: %d/6\n", sum(main$verdict == "获得支持", na.rm = TRUE)))
