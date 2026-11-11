# R/SK_explore_comment_proxies.R — 评论「计数」代理的事后探索性诊断
#
# ⚠️ 性质：POST-HOC / EXPLORATORY。本脚本写在看过 SK_analyze.R 主模型结果之后，
#    不属于 docs/SK_preregistration.md v1.0 的任何预注册假设或稳健性清单。
#    输出只用于回答「评论数能否替代/补救评论文本测量」这一可行性问题，
#    **不得作为假设检验结论、不得写进结果摘要或对外报告**。
#
# 依赖：仅 base R
# 输入：data/processed/SK_coded_D1.csv, SK_coded_D2.csv
# 输出：output/SK_exploratory_comment_proxies.txt

args <- commandArgs(trailingOnly = FALSE)
fp <- sub("^--file=", "", args[grep("^--file=", args)])
ROOT <- if (length(fp)) dirname(dirname(normalizePath(fp))) else getwd()
setwd(ROOT)

DIMS <- c("s_simple", "s_unexpected", "s_concrete", "s_credible", "s_emotional", "s_stories")
HNAMES <- c("H1 Simple", "H2 Unexpected", "H3 Concrete", "H4 Credible", "H5 Emotional", "H6 Stories")
OUT <- "output"
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

load_ds <- function(key) {
  d <- read.csv(file.path("data/processed", paste0("SK_coded_", key, ".csv")),
                stringsAsFactors = FALSE, check.names = FALSE, fileEncoding = "UTF-8-BOM")
  num <- c(DIMS, "engage_rate", "fav_rate", "share_rate", "view", "duration",
           "title_len", "pub_hour", "pub_weekday", "like", "coin", "favorite",
           "share", "reply", "danmaku")
  for (c0 in num) d[[c0]] <- as.numeric(d[[c0]])
  d$log_view <- log(pmax(d$view, 1))
  d$log_duration <- log1p(d$duration)
  d$up_mid <- as.character(d$up_mid)
  d$pub_month <- as.character(d$pub_month)
  # 四个替代因变量（均为 rate，取 log）
  d$engage_noreply <- (d$like + d$coin + d$favorite + d$share) / d$view
  d$like_rate      <- d$like / d$view
  d$reply_rate     <- d$reply / d$view
  d$danmaku_rate   <- d$danmaku / d$view
  d
}

# 与主分析完全一致的按 up_mid 聚类稳健标准误
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

fit_one <- function(d, ycol, fe = TRUE) {
  dd <- d
  dd$yvar <- log(dd[[ycol]])
  before <- nrow(dd)
  dd <- dd[is.finite(dd$yvar), , drop = FALSE]
  dropped <- before - nrow(dd)
  rhs <- c(DIMS, "log_view", "log_duration", "title_len", "pub_hour",
           "factor(pub_weekday)", "factor(pub_month)")
  if (fe) rhs <- c(rhs, "factor(up_mid)")
  fit <- lm(as.formula(paste("yvar ~", paste(rhs, collapse = " + "))), data = dd, x = TRUE)
  cr <- cluster_vcov(fit, dd$up_mid)
  se <- sqrt(diag(cr$V)); b <- coef(fit); ok <- !is.na(b)
  b <- b[ok]; se <- se[seq_len(sum(ok))]
  idx <- match(DIMS, names(b)); beta <- b[idx]; s <- se[idx]
  p <- 2 * pt(-abs(beta / s), df = max(cr$G - 1, 1))
  q <- p.adjust(p, method = "BH")
  data.frame(y = ycol, N = nrow(dd), G = cr$G, dropped = dropped,
             hypothesis = HNAMES, dim = DIMS,
             beta = as.numeric(beta), se = as.numeric(s),
             p = as.numeric(p), q_BH = as.numeric(q), stringsAsFactors = FALSE)
}

YCOLS <- c("engage_rate", "engage_noreply", "like_rate", "reply_rate", "danmaku_rate")
YLAB  <- c("engage_rate (基线，含 reply)", "engage_noreply (剔除评论分量)",
           "like_rate (纯点赞)", "reply_rate (评论数/view)",
           "danmaku_rate (弹幕数/view)")

L <- c(
  "SUCCES-Kaggle · 评论「计数」代理探索性诊断",
  paste("生成时间:", format(Sys.time(), "%Y-%m-%d %H:%M:%S")),
  "⚠️ POST-HOC / EXPLORATORY：写在看过主模型结果之后，非预注册分析。",
  "⚠️ 用途仅限于评估「用评论数替代评论文本」的可行性；不得当作假设检验结论引用。",
  "方法：与主分析相同的 OLS + 按 UP 主聚类稳健标准误 + 双侧 t + 六条假设内 BH-FDR。",
  "数据集内不含任何评论正文；本脚本只使用评论数 reply、弹幕数 danmaku 两个计数。",
  ""
)

all_rows <- list()
for (key in c("D1", "D2")) {
  d <- load_ds(key)
  L <- c(L, sprintf("=== %s（N=%d, UP 主=%d）===", key, nrow(d), length(unique(d$up_mid))))

  # 1) 评论分量在主因变量里的占比
  share <- d$reply / (d$like + d$coin + d$favorite + d$share + d$reply)
  L <- c(L, "--- 1. 评论数在 engage_rate 分子中的占比（描述性）",
         sprintf("    中位数 %.3f  |  均值 %.3f  |  >=10%% 的视频 %d/%d (%.1f%%)",
                 median(share, na.rm = TRUE), mean(share, na.rm = TRUE),
                 sum(share >= 0.10, na.rm = TRUE), sum(is.finite(share)),
                 100 * mean(share >= 0.10, na.rm = TRUE)),
         sprintf("    reply=0: %d 条 | danmaku=0: %d 条（log 后会被剔除）",
                 sum(d$reply == 0), sum(d$danmaku == 0)), "")

  # 2) 六维稀疏度：计数不提供任何文本，故零比例与基线完全相同
  L <- c(L, "--- 2. 六维规则项零比例（编码表的输入只有标题/简介，与评论数无关）")
  for (i in seq_along(DIMS))
    L <- c(L, sprintf("    %-16s 零比例 %5.1f%%  |  唯一取值数 %d",
                      DIMS[i], 100 * mean(d[[DIMS[i]]] == 0, na.rm = TRUE),
                      length(unique(d[[DIMS[i]]]))))
  L <- c(L, "")

  # 3) 各替代因变量下的六个系数
  for (j in seq_along(YCOLS)) {
    r <- fit_one(d, YCOLS[j])
    r$dataset <- key
    all_rows[[length(all_rows) + 1]] <- r
    L <- c(L, sprintf("--- 3.%d %s：N=%d, G=%d, log 剔除 %d 条",
                      j, YLAB[j], r$N[1], r$G[1], r$dropped[1]))
    L <- c(L, sprintf("    %-16s %9s %9s %9s  %s", "假设", "beta", "p", "q_BH", "判定"))
    for (i in seq_len(nrow(r)))
      L <- c(L, sprintf("    %-16s %+9.4f %9.4f %9.4f  %s",
                        r$hypothesis[i], r$beta[i], r$p[i], r$q_BH[i],
                        if (r$beta[i] > 0 && r$q_BH[i] < 0.05) "正且 FDR 显著" else
                        if (r$beta[i] > 0) "正、不显著" else
                        if (r$q_BH[i] < 0.05) "负且 FDR 显著" else "负、不显著"))
    L <- c(L, "")
  }
  L <- c(L, "")
}

# 4) 跨因变量 H3 汇总（唯一在预注册中获得支持的假设）
L <- c(L, "=== 跨因变量汇总：H3 Concrete 的 beta / q_BH（探索性）")
pooled <- do.call(rbind, all_rows)
for (key in c("D1", "D2")) {
  for (j in seq_along(YCOLS)) {
    h3 <- pooled[pooled$dataset == key & pooled$y == YCOLS[j] & pooled$dim == "s_concrete", ]
    L <- c(L, sprintf("  %s  %-34s beta=%+.4f  q=%.4f  N=%d",
                      key, YCOLS[j], h3$beta, h3$q_BH, h3$N))
  }
}

L <- c(L, "", "=== 解读边界",
       "1. 评论数/弹幕数只是计数，不含语义，无法给 Credible / Stories 等维度补充任何文本证据。",
       "2. engage_rate 分子含 reply；若把评论文本-derived 指标当自变量，会与因变量机械相关。",
       "3. 本表所有 p / q 值均为事后探索，未做多重分析族校正，不得作为发现或写进对外报告。",
       "")

writeLines(L, file.path(OUT, "SK_exploratory_comment_proxies.txt"))
cat("已写出", file.path(OUT, "SK_exploratory_comment_proxies.txt"), "\n")
