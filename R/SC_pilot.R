# R/SC_pilot.R — pilot 编码与链路自检
#
# 目的：验证「CSV → 六维规则编码 → 因变量 → 描述统计」能否跑通，并暴露字段/口径问题。
# 依赖：R base + stringr（系统已装）；不 source 00_setup.R，避免触发整包安装。
# 口径：人工语义指标（s1,u3,c3,cr1,e4,st3）尚未标注，本版**只用规则项**计分，
#       并逐行记录每维 n_valid_items，避免各维计分项数不同造成得分不可比。
# 运行：在项目根目录执行 Rscript R/SC_pilot.R

args <- commandArgs(trailingOnly = FALSE)
fp <- sub("^--file=", "", args[grep("^--file=", args)])
ROOT <- if (length(fp)) dirname(dirname(normalizePath(fp))) else getwd()
setwd(ROOT)

RAW <- "data/raw"
PROC <- "data/processed"
OUT <- "output"
dir.create(PROC, showWarnings = FALSE, recursive = TRUE)
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

f <- list.files(RAW, pattern = "^SC_pilot_videos_.*\\.csv$", full.names = TRUE)
if (!length(f)) stop("未找到 data/raw/SC_pilot_videos_*.csv，请先运行 SC_pilot_collect.py")
src <- f[order(f, decreasing = TRUE)][1]
d <- read.csv(src, stringsAsFactors = FALSE, fileEncoding = "UTF-8-BOM", check.names = FALSE)

num_cols <- c("view", "like", "coin", "favorite", "share", "reply", "danmaku",
              "follower", "duration", "title_len", "days_since_pub", "pub_hour",
              "pub_weekday", "mid", "list_play")
for (cl in num_cols) if (cl %in% names(d)) d[[cl]] <- as.numeric(as.character(d[[cl]]))

n_raw <- nrow(d)
d <- d[!is.na(d$view) & d$view > 0, ]
n_valid <- nrow(d)

# ---- 词典 v0.1（与 R/02_code_succes.R 保持一致；问号需转义）----------------
LEX <- list(
  simple_conclusion = c("一句话", "搞懂", "讲清", "其实就", "只需", "分钟", "本质上是", "说白了"),
  abstract          = c("底层逻辑", "方法论", "认知", "范式", "维度", "体系", "思维模型"),
  unexpected        = c("你以为", "其实不是", "并不是", "错了", "恰恰相反", "颠覆", "真相是"),
  suspense          = c("为什么", "到底", "竟然", "凭什么", "\\?", "？"),
  concrete_entity   = c("钱", "工资", "手机", "地铁", "一天", "分钟", "一杯", "一张", "块钱", "公里", "小时"),
  credible          = c("研究显示", "实验", "数据", "调查", "论文", "根据", "统计", "报告", "文献"),
  emotional         = c("震惊", "崩溃", "后悔", "焦虑", "扎心", "救命", "细思极恐", "爽", "绝了", "可怕"),
  second_person     = c("你", "你的", "千万别"),
  frame             = c("别再", "错过", "省下", "避免", "少走弯路", "白花", "别被"),
  story_open        = c("我朋友", "有个学生", "曾经", "我当年", "某位", "有个读者"),
  story_time        = c("先", "后来", "结果", "直到", "没想到", "于是")
)

pat <- function(w) paste(w, collapse = "|")
hit <- function(x, w) as.integer(grepl(pat(w), x, perl = TRUE))
hit_count <- function(x, w) stringr::str_count(x, pat(w))
blank <- function(x) ifelse(is.na(x), "", as.character(x))

title <- blank(d$title)
desc <- blank(d$desc)
txt <- paste(title, desc)

coded <- data.frame(
  bvid = blank(d$bvid), title = title, subzone = blank(d$subzone),
  s2 = as.integer(nchar(title) <= 20),
  s3 = hit(txt, LEX$simple_conclusion),
  s4 = as.integer(hit_count(title, LEX$abstract) == 0),
  u1 = hit(txt, LEX$unexpected),
  u2 = hit(title, LEX$suspense),
  c1 = as.integer(grepl("[0-9]", txt)),
  c2 = hit(txt, LEX$concrete_entity),
  c4 = as.integer(hit_count(title, LEX$abstract) == 0),
  cr2 = hit(txt, LEX$credible),
  cr3 = as.integer(grepl("https?://|DOI|doi|参考文献|出处", txt)),
  cr4 = as.integer(!is.na(d$official) & d$official != ""),
  e1 = hit(title, LEX$emotional),
  e2 = hit(title, LEX$second_person),
  e3 = hit(title, LEX$frame),
  st1 = hit(txt, LEX$story_open),
  st2 = as.integer(hit_count(txt, LEX$story_time) >= 2),
  st4 = as.integer(!is.na(d$duration) & d$duration >= 480 &
                     grepl("案例|例子|举例|故事", txt)),
  stringsAsFactors = FALSE
)

dims <- list(
  s_simple     = c("s2", "s3", "s4"),
  s_unexpected = c("u1", "u2"),
  s_concrete   = c("c1", "c2", "c4"),
  s_credible   = c("cr2", "cr3", "cr4"),
  s_emotional  = c("e1", "e2", "e3"),
  s_stories    = c("st1", "st2", "st4")
)
for (nm in names(dims)) {
  m <- as.matrix(coded[, dims[[nm]]])
  coded[[nm]] <- rowMeans(m, na.rm = TRUE)
  coded[[paste0("n_", nm)]] <- rowSums(!is.na(m))
}

coded$engage_rate <- (d$like + d$coin + d$favorite + d$share + d$reply) / pmax(d$view, 1)
coded$fav_rate    <- d$favorite / pmax(d$view, 1)
coded$share_rate  <- d$share / pmax(d$view, 1)
coded$view        <- d$view
coded$duration    <- d$duration
coded$follower    <- d$follower
coded$days_since_pub <- d$days_since_pub
coded$desc_empty  <- as.integer(desc == "")

write.csv(coded, file.path(PROC, "SC_pilot_coded.csv"), row.names = FALSE, fileEncoding = "UTF-8")

# ---- 链路自检报告 -----------------------------------------------------------
sink(file.path(OUT, "SC_pilot_summary.txt"))
cat("SUCCES pilot · 链路自检报告\n")
cat("生成时间:", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n")
cat("输入文件:", basename(src), "\n\n")

cat("== 1. 样本 ==\n")
cat("采集条数:", n_raw, " | view>0 有效:", n_valid, " | 剔除:", n_raw - n_valid, "\n")
cat("分区分布:\n"); print(table(coded$subzone))
cat("来源榜单分布:\n"); print(table(d$src))
cat("desc 为空:", sum(coded$desc_empty), "/", n_valid,
    sprintf("(%.0f%%)\n", 100 * mean(coded$desc_empty)))
cat("follower 缺失:", sum(is.na(coded$follower)), "\n")

cat("\n== 2. 六维得分（仅规则项）==\n")
res <- t(sapply(names(dims), function(nm) {
  x <- coded[[nm]]
  c(mean = mean(x, na.rm = TRUE), sd = sd(x, na.rm = TRUE),
    min = min(x, na.rm = TRUE), max = max(x, na.rm = TRUE),
    n_items = mean(coded[[paste0("n_", nm)]]))
}))
print(round(res, 3))
cat("提示：sd=0 表示该维在本 pilot 样本中缺乏变异，正式样本需检查词典覆盖。\n")

cat("\n== 3. 因变量 ==\n")
cat("engage_rate 分位数:\n"); print(round(quantile(coded$engage_rate, c(0, .25, .5, .75, 1), na.rm = TRUE), 4))
cat("fav_rate 中位数:", round(median(coded$fav_rate, na.rm = TRUE), 4), "\n")
cat("view 中位数:", median(coded$view, na.rm = TRUE),
    " | days_since_pub 范围:", paste(round(range(coded$days_since_pub, na.rm = TRUE), 1), collapse = " - "), "\n")

cat("\n== 4. 六维间相关（样本小，仅作链路检查）==\n")
D <- coded[, names(dims)]
const <- apply(D, 2, sd, na.rm = TRUE) == 0
if (any(const)) cat("  （以下维度在本样本无变异，相关记为 NA：",
                    paste(names(dims)[const], collapse = ", "), "）\n", sep = "")
CM <- suppressWarnings(cor(D, use = "pairwise.complete.obs"))
CM[const, ] <- NA
CM[, const] <- NA
print(round(CM, 2))

cat("\n== 5. 链路自检 ==\n")
checks <- c(
  "字段齐全" = all(c("title", "view", "like", "favorite", "follower") %in% names(d)),
  "存在有效播放量" = n_valid > 0,
  "六维得分无 NA" = all(complete.cases(coded[, names(dims)])),
  "因变量无 NA" = all(is.finite(coded$engage_rate)),
  "至少 20 条" = n_valid >= 20,
  "至少一维有变异" = any(apply(coded[, names(dims)], 2, sd, na.rm = TRUE) > 0)
)
for (k in names(checks)) cat(sprintf("  [%s] %s\n", if (checks[k]) "PASS" else "FAIL", k))

cat("\n== 6. 示例（前 5 条标题 + 六维得分）==\n")
show <- coded[seq_len(min(5, n_valid)), c("title", names(dims))]
show$title <- substr(show$title, 1, 34)
print(format(show, digits = 2), row.names = FALSE)

cat("\n== 7. 使用边界 ==\n")
cat("本文件只用于验证采集与编码链路。pilot 样本来自公开榜单、非分层概率样本，\n")
cat("且人工语义指标尚未标注、字幕未取，任何系数或结论都不得写进最终报告。\n")
cat("正式分析前需：补齐人工编码与 kappa、扩大样本至 200-300 条、按 SC_preregistration.md 执行。\n")
sink()

cat("完成：", n_valid, "条 → ", file.path(PROC, "SC_pilot_coded.csv"), "\n")
cat("自检报告：", file.path(OUT, "SC_pilot_summary.txt"), "\n")
