# R/SK_analyze.R — 按 docs/SK_preregistration.md v1.0 执行的推断分析
#
# 依赖：仅 base R（lm / p.adjust / qr），不装包、不联网
# 输入：data/processed/SK_coded_D1.csv, SK_coded_D2.csv（由 SK_prepare.py 生成）
# 输出：output/SK_results.txt, SK_coefficients.csv, SK_robustness.csv
#
# ⚠️ 本文件只在预注册冻结之后运行；任何口径改动必须先在预注册第 9 节登记。
#    全篇只做关联解释，不写因果。

args <- commandArgs(trailingOnly = FALSE)
fp <- sub("^--file=", "", args[grep("^--file=", args)])
ROOT <- if (length(fp)) dirname(dirname(normalizePath(fp))) else getwd()
setwd(ROOT)

DIMS <- c("s_simple", "s_unexpected", "s_concrete", "s_credible", "s_emotional", "s_stories")
HNAMES <- c("H1 Simple", "H2 Unexpected", "H3 Concrete", "H4 Credible", "H5 Emotional", "H6 Stories")
PROC <- "data/processed"; OUT <- "output"
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

# ---- 读取 -------------------------------------------------------------------
load_ds <- function(key) {
  p <- file.path(PROC, paste0("SK_coded_", key, ".csv"))
  d <- read.csv(p, stringsAsFactors = FALSE, check.names = FALSE, fileEncoding = "UTF-8-BOM")
  num <- c(DIMS, "s_credible_cr4zero", "engage_rate", "fav_rate", "share_rate",
           "view", "duration", "title_len", "pub_hour", "pub_weekday")
  for (c0 in num) d[[c0]] <- as.numeric(d[[c0]])
  d$log_view <- log(pmax(d$view, 1))
  d$log_duration <- log1p(d$duration)
  d$up_mid <- as.character(d$up_mid)
  d$pub_month <- as.character(d$pub_month)
  d
}

# ---- 按 up_mid 聚类的稳健标准误（base R 三明治）-----------------------------
# 用 summary(fit)$cov.unscaled 作为 (X'X)^-1，自动避开 aliased 列，
# 不调用 solve(crossprod(X))，因此在高维固定效应下也稳定。
cluster_vcov <- function(fit, cl) {
  co <- coef(fit)
  keep <- !is.na(co)
  X <- model.matrix(fit)[, keep, drop = FALSE]
  u <- residuals(fit)
  n <- nrow(X); k <- ncol(X); G <- length(unique(cl))
  V0 <- summary(fit)$cov.unscaled
  meat <- matrix(0, k, k)
  for (g in unique(cl)) {
    i <- which(cl == g)
    s <- colSums(X[i, , drop = FALSE] * u[i])
    meat <- meat + outer(s, s)
  }
  adj <- (G / (G - 1)) * ((n - 1) / (n - k))
  V <- adj * (V0 %*% meat %*% V0)
  list(V = V, G = G, n = n, k = k)
}

build_formula <- function(y, fe = TRUE) {
  rhs <- c(DIMS, "log_view", "log_duration", "title_len", "pub_hour",
           "factor(pub_weekday)", "factor(pub_month)")
  if (fe) rhs <- c(rhs, "factor(up_mid)")
  as.formula(paste(y, "~", paste(rhs, collapse = " + ")))
}

fit_model <- function(d, y = "log(engage_rate)", fe = TRUE, label = "M") {
  dd <- d
  dd$yvar <- eval(parse(text = y), dd)          # 允许 log(fav_rate) 等
  # 次因变量含 0 → log 为 -Inf，按预注册 3b「log 因变量要求为正」剔除并记数
  before <- nrow(dd)
  dd <- dd[is.finite(dd$yvar), , drop = FALSE]
  dropped <- before - nrow(dd)
  f <- build_formula("yvar", fe)
  fit <- lm(f, data = dd, x = TRUE)
  cr <- cluster_vcov(fit, dd$up_mid)
  se <- sqrt(diag(cr$V))
  b <- coef(fit)
  ok <- !is.na(b)
  b <- b[ok]; se <- se[seq_len(sum(ok))]
  idx <- match(DIMS, names(b))
  beta <- b[idx]; s <- se[idx]
  tval <- beta / s
  dfree <- max(cr$G - 1, 1)
  p <- 2 * pt(-abs(tval), df = dfree)
  q <- p.adjust(p, method = "BH")               # 六条假设内校正
  ci_lo <- beta - qt(0.975, dfree) * s
  ci_hi <- beta + qt(0.975, dfree) * s
  verdict <- ifelse(beta > 0 & q < 0.05, "获得支持",
             ifelse(beta > 0, "方向一致但不显著",
             ifelse(q < 0.05, "方向相反（显著负）", "方向相反且不显著")))
  data.frame(
    model = label, dataset = unique(dd$dataset)[1], y = y, fe = fe,
    N = nrow(dd), G = cr$G, k = cr$k, dropped_for_log = dropped,
    hypothesis = HNAMES, dim = DIMS,
    beta = as.numeric(beta), se = as.numeric(s), t = as.numeric(tval),
    p = as.numeric(p), q_BH = as.numeric(q),
    ci_lo = as.numeric(ci_lo), ci_hi = as.numeric(ci_hi),
    pct_per_0.1 = 100 * (exp(0.1 * as.numeric(beta)) - 1),
    verdict = verdict, stringsAsFactors = FALSE
  )
}

# ---- 共线性诊断（VIF）--------------------------------------------------------
vif_table <- function(d) {
  vars <- c(DIMS, "log_view", "log_duration", "title_len", "pub_hour")
  z <- d[, vars]
  z <- z[complete.cases(z), , drop = FALSE]
  out <- numeric(length(vars))
  for (i in seq_along(vars)) {
    f <- as.formula(paste(vars[i], "~", paste(vars[-i], collapse = " + ")))
    r2 <- summary(lm(f, data = z))$r.squared
    out[i] <- 1 / max(1 - r2, 1e-8)
  }
  data.frame(variable = vars, VIF = round(out, 2))
}

# ---- 组织输出 ---------------------------------------------------------------
lines <- c(
  "SUCCES-Kaggle · 推断分析结果",
  paste("生成时间:", format(Sys.time(), "%Y-%m-%d %H:%M:%S")),
  "预注册: docs/SK_preregistration.md v1.0（在看任何关联结果之前冻结）",
  "推断: OLS + 按 UP 主聚类稳健标准误（base R 手写三明治）| 双侧 t 检验 | 六条假设 BH-FDR 校正",
  "⚠️ 全篇只作关联解释；观察性数据，无因果识别策略。",
  ""
)
all_coef <- list(); robust_rows <- list()

d1 <- load_ds("D1"); d2 <- load_ds("D2")
lines <- c(lines, "== 0. 样本 ==",
           sprintf("D1 (MIT, 2025 TOP100 创作者) N=%d, UP 主聚类数 G=%d", nrow(d1), length(unique(d1$up_mid))),
           sprintf("D2 (Apache-2.0, 教育话题)   N=%d, UP 主聚类数 G=%d", nrow(d2), length(unique(d2$up_mid))),
           "")

# ---- 主模型 M1 (D1) ----------------------------------------------------------
m1 <- fit_model(d1, "log(engage_rate)", TRUE, "M1_主模型_D1")
all_coef[["M1"]] <- m1
lines <- c(lines, "== 1. 主模型 M1：D1，log(engage_rate)，含 UP 主 / 年月固定效应 ==",
           sprintf("N=%d | 聚类 G=%d | 参数 k=%d | 自由度 df=G-1", m1$N[1], m1$G[1], m1$k[1]),
           sprintf("%-17s %9s %9s %8s %9s %9s %-24s", "假设/维度", "beta", "SE", "p", "q_BH", "每+0.1", "判定"))
for (i in seq_len(nrow(m1))) {
  r <- m1[i, ]
  lines <- c(lines, sprintf("%-17s %9.4f %9.4f %8.4f %9.4f %+8.2f%% %-24s",
                            r$hypothesis, r$beta, r$se, r$p, r$q_BH, r$pct_per_0.1, r$verdict))
}
lines <- c(lines, "",
           "95% CI 与效应量（得分 0→1 的全量程变化；每 +0.1 见上表）:")
for (i in seq_len(nrow(m1))) {
  r <- m1[i, ]
  lines <- c(lines, sprintf("  %-17s beta=%+.4f  95%%CI [%+.4f, %+.4f]  全量程 %+.1f%%",
                            r$hypothesis, r$beta, r$ci_lo, r$ci_hi,
                            100 * (exp(r$beta) - 1)))
}
lines <- c(lines, "")

# ---- VIF --------------------------------------------------------------------
v <- vif_table(d1)
lines <- c(lines, "== 2. 共线性诊断（D1 主样本 VIF）==",
           sprintf("  %-16s %s", "变量", "VIF"))
for (i in seq_len(nrow(v))) lines <- c(lines, sprintf("  %-16s %.2f", v$variable[i], v$VIF[i]))
lines <- c(lines, "  注：VIF>5 的维度系数需谨慎解读；按预注册不从模型中删除该维。", "")

# ---- 稳健性 S1–S6 -----------------------------------------------------------
q01 <- quantile(d1$engage_rate, 0.01, names = FALSE)
q99 <- quantile(d1$engage_rate, 0.99, names = FALSE)
d1_trim <- d1[d1$engage_rate >= q01 & d1$engage_rate <= q99, ]
d1_cr4 <- d1; d1_cr4$s_credible <- d1_cr4$s_credible_cr4zero

specs <- list(
  list(id = "S1_fav",   d = d1,      y = "log(fav_rate)",   fe = TRUE,  lab = "S1 换收藏率"),
  list(id = "S2_share", d = d1,      y = "log(share_rate)", fe = TRUE,  lab = "S2 换分享率"),
  list(id = "S3_trim",  d = d1_trim, y = "log(engage_rate)",fe = TRUE,  lab = "S3 去两端1%"),
  list(id = "S4_noFE",  d = d1,      y = "log(engage_rate)",fe = FALSE, lab = "S4 去UP主固定效应"),
  list(id = "S5_cr4",   d = d1_cr4,  y = "log(engage_rate)",fe = TRUE,  lab = "S5 cr4设0"),
  list(id = "S6_D2",    d = d2,      y = "log(engage_rate)",fe = TRUE,  lab = "S6 D2同规格")
)
lines <- c(lines, "== 3. 稳健性与外部效度（顺序按预注册第 7 节冻结）==",
           sprintf("%s  %s", "各设定下六维 beta（* 表示 q_BH<0.05）", ""))
header <- sprintf("%-24s %7s %7s %7s %7s %7s %7s", "设定", "Simple", "Unexp", "Concr", "Credib", "Emot", "Stories")
lines <- c(lines, header)
for (sp in specs) {
  m <- fit_model(sp$d, sp$y, sp$fe, sp$id)
  all_coef[[sp$id]] <- m
  stars <- ifelse(m$q_BH < 0.05, "*", " ")
  cells <- sprintf("%+6.3f%s", m$beta, stars)
  lines <- c(lines, sprintf("%-24s %s", sp$lab, paste(cells, collapse = " ")))
  lines <- c(lines, sprintf("    N=%d | 聚类G=%d | 参数k=%d | 因 log 因变量剔除 %d 行",
                            m$N[1], m$G[1], m$k[1], m$dropped_for_log[1]))
  for (i in seq_len(nrow(m))) {
    robust_rows[[length(robust_rows) + 1]] <- data.frame(
      spec = sp$id, label = sp$lab, N = m$N[i], G = m$G[i],
      hypothesis = m$hypothesis[i], beta = m$beta[i], q_BH = m$q_BH[i],
      verdict = m$verdict[i], stringsAsFactors = FALSE)
  }
}
lines <- c(lines, "")
m2 <- all_coef[["S6_D2"]]
lines <- c(lines, "== 4. RQ3 跨数据集方向一致性（M1 D1 vs S6 D2）==",
           sprintf("  %-17s %10s %10s %-10s", "假设", "D1 beta", "D2 beta", "方向一致"))
same <- 0
for (i in seq_len(nrow(m1))) {
  ok <- sign(m1$beta[i]) == sign(m2$beta[i]); same <- same + ok
  lines <- c(lines, sprintf("  %-17s %+10.4f %+10.4f %-10s",
                            m1$hypothesis[i], m1$beta[i], m2$beta[i], ifelse(ok, "是", "否")))
}
lines <- c(lines, sprintf("  方向一致: %d / 6", same))
sig1 <- which(m1$q_BH < 0.05)
if (length(sig1)) {
  lines <- c(lines, "  D1 中达显著的维度在 D2 的表现：")
  for (i in sig1) {
    lines <- c(lines, sprintf("    %-17s D1 q=%.4f %+.4f | D2 q=%.4f %+.4f | %s",
                              m1$hypothesis[i], m1$q_BH[i], m1$beta[i],
                              m2$q_BH[i], m2$beta[i], m2$verdict[i]))
  }
} else {
  lines <- c(lines, "  D1 中无维度在 BH 校正后达显著。")
}
lines <- c(lines, "")

# ---- 预注册的判定规则汇总 ----------------------------------------------------
lines <- c(lines, "== 5. 假设判定（规则：beta>0 且 q_BH<0.05 才算获得支持）==")
for (i in seq_len(nrow(m1))) {
  lines <- c(lines, sprintf("  %-17s %s", m1$hypothesis[i], m1$verdict[i]))
}
lines <- c(lines, "",
           "== 6. 必须写进报告的边界 ==",
           "  · 观察性关联，不是因果；互动率受推荐流、封面、流量池与反向因果干扰。",
           "  · 六维测的是标题/简介的文本特征，不是 SUCCES 构念本身，更不是内容质量。",
           "  · Credible / Stories 在两组样本中零命中比例极高（见 SK_data_health.txt），",
           "    相应假设实质上是「缺乏变异、难以检验」，不解读为「该维度无效」。",
           "  · D1 为头部创作者样本、D2 为单一教育话题；采集口径由 Kaggle 上传者决定且未知。",
           "  · 两数据集领域、时间窗与原项目 succes-bilibili 不同，属外部效度检验而非复现。",
           "")

writeLines(lines, file.path(OUT, "SK_results.txt"), useBytes = TRUE)
co <- do.call(rbind, all_coef)
write.csv(co, file.path(OUT, "SK_coefficients.csv"), row.names = FALSE, fileEncoding = "UTF-8")
rb <- do.call(rbind, robust_rows)
write.csv(rb, file.path(OUT, "SK_robustness.csv"), row.names = FALSE, fileEncoding = "UTF-8")

cat(paste(lines, collapse = "\n"), "\n")
cat("\n写出：output/SK_results.txt / SK_coefficients.csv / SK_robustness.csv\n")
