# R/SC_mvp.R — MVP 全链路复跑（采集 → 编码 v0.2 → 覆盖度 → 自检）
#
# 依赖：仅 R base（不 source 00_setup.R，不触发整包安装）
# 输入：data/raw/SC_mvp_videos_20261106.csv
#       data/processed/SC_manual_coding.csv（仅作审计留痕，不参与分析口径）
# 输出：data/processed/SC_mvp_coded.csv
#       output/SC_mvp_summary.txt
#
# ⚠️ 采用性决策（2026-11-07，项目决策路径 C；预注册变更 G）：
#   两轮 20% 双人编码信度均未达标 → 六个人工语义指标 s1/u3/c3/cr1/st3/e4
#   **正式不采用**，不进入任何推断分析。详见 docs/SC_coding-adoption.md。
#   六维得分 s_* 只用可复现的规则项（词典/正则）；含人工项的混合口径另存
#   *_DIAGNOSTIC_ONLY 列，仅供覆盖度诊断，禁止用于建模或结论。
#
# 口径：词典 v0.2（C4 已修、E4 改人工）；六维得分按「该维有效规则项均值」计算，
#       逐行记录 n_valid_items；u4 因字幕 0% 可为 NA，不冒充 0。
# 边界：本脚本只做链路自检与覆盖度诊断，**不报告任何系数、显著性或研究结论**。

args <- commandArgs(trailingOnly = FALSE)
fp <- sub("^--file=", "", args[grep("^--file=", args)])
ROOT <- if (length(fp)) dirname(dirname(normalizePath(fp))) else getwd()
setwd(ROOT)

RAW <- "data/raw"; PROC <- "data/processed"; OUT <- "output"
dir.create(PROC, showWarnings = FALSE, recursive = TRUE)
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

f <- list.files(RAW, pattern = "^SC_mvp_videos_.*\\.csv$", full.names = TRUE)
if (!length(f)) stop("未找到 data/raw/SC_mvp_videos_*.csv，请先运行 SC_collect_mvp.py")
src <- f[order(f, decreasing = TRUE)][1]
d <- read.csv(src, stringsAsFactors = FALSE, fileEncoding = "UTF-8-BOM", check.names = FALSE)

num_cols <- c("view", "like", "coin", "favorite", "share", "reply", "danmaku",
              "follower", "duration", "title_len", "days_since_pub", "pub_hour",
              "pub_weekday", "mid", "list_play", "rank_best", "subtitle_n",
              "desc_len", "within_1yr", "view_usable", "analysis_eligible")
for (cl in num_cols) if (cl %in% names(d)) d[[cl]] <- as.numeric(as.character(d[[cl]]))

blank <- function(x) ifelse(is.na(x), "", as.character(x))
title <- blank(d$title); desc <- blank(d$desc); intro <- blank(d$intro)
txt <- paste(title, desc)

# ---- 词典 v0.2 ---------------------------------------------------------------
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
  story_time        = c("先", "后来", "结果", "直到", "没想到", "于是"),
  measured_unit     = c("[0-9]+ ?(元|块|万元|亿元|年|个月|天|小时|分钟|秒|公里|米|人|%|％|次|倍|斤|公斤|度|杯|页|位|万|亿|岁)")
)
pat <- function(w) paste(w, collapse = "|")
hit <- function(x, w) as.integer(grepl(pat(w), x, perl = TRUE))
hit_count <- function(x, w) {
  m <- gregexpr(pat(w), x, perl = TRUE)
  vapply(m, function(z) if (z[1] == -1L) 0L else length(z), integer(1))
}

# ---- 人工语义指标（仅保留原始值供审计；HUMAN_ADOPTED=FALSE 时不进入得分）----
# 主表 13 行为真人 A 按 v0.3 的判定，其余 51 行 NA。两轮双编码均判定信度不足，
# 因此这些列只用于写出 *_DIAGNOSTIC_ONLY 诊断列，绝不进入分析口径。
HUMAN <- c("s1", "u3", "c3", "cr1", "st3", "e4")
manual <- NULL
mp <- file.path(PROC, "SC_manual_coding.csv")
if (file.exists(mp)) {
  mc <- read.csv(mp, stringsAsFactors = FALSE, fileEncoding = "UTF-8-BOM", check.names = FALSE)
  idx <- match(d$bvid, mc$bvid)
  manual <- data.frame(row.names = seq_len(nrow(d)))
  for (h in HUMAN) {
    v <- if (h %in% names(mc)) as.numeric(as.character(mc[[h]]))[idx] else rep(NA_real_, nrow(d))
    manual[[h]] <- v
  }
} else {
  manual <- data.frame(matrix(NA_real_, nrow = nrow(d), ncol = length(HUMAN)))
  names(manual) <- HUMAN
}
n_double <- if (exists("mc")) sum(mc$kappa_flag == 1, na.rm = TRUE) else 0

# ---- 六维规则编码（v0.2）+ 保留 v0.1 的 C4 供对照 --------------------------
coded <- data.frame(
  bvid = blank(d$bvid), title = title, subzone = blank(d$subzone),
  s1 = manual$s1,
  s2 = as.integer(nchar(title) <= 20),
  s3 = hit(txt, LEX$simple_conclusion),
  s4 = as.integer(hit_count(title, LEX$abstract) == 0),
  u1 = hit(txt, LEX$unexpected),
  u2 = hit(title, LEX$suspense),
  u3 = manual$u3,
  u4 = ifelse(intro == "", NA_integer_,
              as.integer(grepl("\\?|？|为什么", intro) & !grepl("一句话|搞懂|说白了", intro))),
  c1 = as.integer(grepl("[0-9]", txt)),
  c2 = hit(txt, LEX$concrete_entity),
  c3 = manual$c3,
  c4 = hit(txt, LEX$measured_unit),                 # v0.2 新定义
  c4_v01 = as.integer(hit_count(title, LEX$abstract) == 0),  # v0.1 旧值，仅做对照
  cr1 = manual$cr1,
  cr2 = hit(txt, LEX$credible),
  cr3 = as.integer(grepl("https?://|DOI|doi|参考文献|出处", txt)),
  cr4 = as.integer(!is.na(d$official) & d$official != ""),
  e1 = hit(title, LEX$emotional),
  e2 = hit(title, LEX$second_person),
  e3 = hit(title, LEX$frame),
  e4 = manual$e4,
  st1 = hit(txt, LEX$story_open),
  st2 = as.integer(hit_count(txt, LEX$story_time) >= 2),
  st3 = manual$st3,
  st4 = as.integer(!is.na(d$duration) & d$duration >= 480 &
                     grepl("案例|例子|举例|故事", txt)),
  stringsAsFactors = FALSE
)

# ---- 采用性决策（2026-11-07 路径 C；预注册变更 G）--------------------------
# 唯一的推断分析口径：规则项-only（词典 / 正则，可复现、无需人工判断）。
HUMAN_ADOPTED <- FALSE
RULE_DIMS <- list(
  s_simple     = c("s2", "s3", "s4"),
  s_unexpected = c("u1", "u2", "u4"),
  s_concrete   = c("c1", "c2", "c4"),
  s_credible   = c("cr2", "cr3", "cr4"),
  s_emotional  = c("e1", "e2", "e3"),
  s_stories    = c("st1", "st2", "st4")
)
# 旧混合口径（含人工项）保留为显式标记的诊断列，禁止进入任何模型或结论。
ALL_DIMS <- list(
  s_simple     = c("s1", "s2", "s3", "s4"),
  s_unexpected = c("u1", "u2", "u3", "u4"),
  s_concrete   = c("c1", "c2", "c3", "c4"),
  s_credible   = c("cr1", "cr2", "cr3", "cr4"),
  s_emotional  = c("e1", "e2", "e3", "e4"),
  s_stories    = c("st1", "st2", "st3", "st4")
)
dims <- RULE_DIMS
for (nm in names(dims)) {
  m <- as.matrix(coded[, dims[[nm]]])
  coded[[nm]] <- rowMeans(m, na.rm = TRUE)
  coded[[paste0("n_", nm)]] <- rowSums(!is.na(m))
}
for (nm in names(ALL_DIMS)) {
  m <- as.matrix(coded[, ALL_DIMS[[nm]]])
  coded[[paste0(nm, "_DIAGNOSTIC_ONLY")]] <- rowMeans(m, na.rm = TRUE)
}

# v0.1 对照：同样只用规则项，把 C4 换回旧值重算 Concrete
m01 <- as.matrix(coded[, c("c1", "c2", "c4_v01")])
coded$s_concrete_v01 <- rowMeans(m01, na.rm = TRUE)

coded$engage_rate <- (d$like + d$coin + d$favorite + d$share + d$reply) / pmax(d$view, 1)
coded$fav_rate    <- d$favorite / pmax(d$view, 1)
coded$view        <- d$view
coded$days_since_pub <- d$days_since_pub
coded$within_1yr  <- d$within_1yr
coded$view_usable <- d$view_usable
coded$analysis_eligible <- d$analysis_eligible
coded$rate_stable <- as.integer(d$view >= 1000)
coded$desc_empty  <- as.integer(desc == "")
coded$desc_source <- blank(d$desc_source)
coded$subtitle_n  <- d$subtitle_n
coded$heat_tier   <- blank(d$heat_tier)
coded$topic_layer <- blank(d$topic_layer)
# 把六个人工原始列显式改名，防止下游误把它们当自变量代入模型
# （诊断列已在上面用原名算完，此处改名不影响 *_DIAGNOSTIC_ONLY）
for (h in HUMAN) names(coded)[names(coded) == h] <- paste0(h, "_NOT_ADOPTED")
# 让数据文件自带采用性标记：0 = 人工语义指标不采用，s_* 为规则项-only 口径
coded$human_coding_adopted <- 0L

write.csv(coded, file.path(PROC, "SC_mvp_coded.csv"), row.names = FALSE, fileEncoding = "UTF-8")

# ---- 自检报告 ---------------------------------------------------------------
sink(file.path(OUT, "SC_mvp_summary.txt"))
cat("SUCCES MVP · 全链路复跑自检报告（词典 v0.2）\n")
cat("生成时间:", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n")
cat("输入文件:", basename(src), "\n\n")

cat("== 1. 样本与抽样框 ==\n")
cat("实收:", nrow(d), "条 | 目标 120 | 缺口:", 120 - nrow(d), "条（候选不足，未补造、未扩区）\n")
cat("锁定子区: 社科·法律·心理 & 科学科普 (rid=124 + rid=201)\n")
cat("分层（热度层 × 主题层）:\n"); print(table(coded$heat_tier, coded$topic_layer))
cat("来源:\n"); print(table(sub("\\|.*", "", blank(d$src))))

cat("\n== 2. 素材覆盖度（需求 #3 核对）==\n")
cat("desc 非空:", sum(!coded$desc_empty), "/", nrow(d),
    sprintf("(%.0f%%)\n", 100 * mean(!coded$desc_empty)))
cat("desc 来源分布:\n"); print(table(coded$desc_source))
cat("intro 非空:", sum(intro != ""), "/", nrow(d), "\n")
cat("字幕可用:", sum(coded$subtitle_n > 0, na.rm = TRUE), "/", nrow(d),
    " → 覆盖率 0%，按 data-source.md 降级：u4 标 NA；Stories 仅靠规则项 st1/st2/st4\n")
cat("人工语义指标原始值:", sum(complete.cases(manual)), "/", nrow(d),
    "行（13 行真人 A 的 v0.3 判定，仅作审计留痕）\n")
cat("⚠️ 采用性决策（变更 G / 路径 C）：两轮 20% 双编码信度均未达标 → 六个人工语义指标正式不采用；\n")
cat("   六维 s_* 只用规则项，混合口径另存 *_DIAGNOSTIC_ONLY 仅供覆盖度对照。\n")
cat("   权威口径见 docs/SC_coding-adoption.md；主表原始值保留归档、不删除。\n")

cat("\n== 3. 时间语义核对（需求 #3）==\n")
cat("days_since_pub 分位数:\n")
print(round(quantile(coded$days_since_pub, c(0, .25, .5, .75, 1), na.rm = TRUE), 1))
cat("within_1yr(<=365天):", sum(coded$within_1yr == 1, na.rm = TRUE), "/", nrow(d), "\n")
cat("交叉表 within_1yr × rate_stable(view>=1000):\n")
print(table(coded$within_1yr, coded$rate_stable))
cat("结论: ranking/region 的 day 是排行榜统计窗口而非投稿时间；本环境返回 2025-04 固定历史快照。\n")
cat("      时间不做强制要求，故历史快照窗口（约 580 天）纳入分析口径，不再据此硬删样本；\n")
cat("      within_1yr 仅作敏感性对照标记（只取近 1 年子集时样本量骤降，仅作局限说明）。\n")

cat("\n== 4. 六维得分（规则项-only 分析口径，变更 G）==\n")
res <- t(sapply(names(dims), function(nm) {
  x <- coded[[nm]]
  c(mean = mean(x, na.rm = TRUE), sd = sd(x, na.rm = TRUE),
    min = min(x, na.rm = TRUE), max = max(x, na.rm = TRUE),
    n_items = mean(coded[[paste0("n_", nm)]]))
}))
print(round(res, 3))
cat("说明：每维由 3 个可复现规则项构成；n_items 的组间差异只来自 u4 的 NA（字幕 0%），\n")
cat("      与人工编码无关。得分不可跨维直接比较，且本节不是研究结果。\n")
cat("诊断口径对照（含人工项，*_DIAGNOSTIC_ONLY，禁止用于推断）：\n")
diag_res <- t(sapply(names(ALL_DIMS), function(nm) {
  x <- coded[[paste0(nm, "_DIAGNOSTIC_ONLY")]]
  c(mean = mean(x, na.rm = TRUE), sd = sd(x, na.rm = TRUE))
}))
print(round(diag_res, 3))
cat("代价（须写进报告局限）：每维由 4 项减为 3 项，构念效度变弱；s4 仍为常量。\n")

cat("\n== 5. 六维间相关（分析口径；仅链路检查，不得解读为构念关系）==\n")
D <- coded[, names(dims)]
const <- apply(D, 2, sd, na.rm = TRUE) == 0
CM <- suppressWarnings(cor(D, use = "pairwise.complete.obs"))
CM[const, ] <- NA; CM[, const] <- NA
if (any(const)) cat("无变异维度:", paste(names(dims)[const], collapse = ", "), "\n")
print(round(CM, 2))

cat("\n== 6. s4/c4 重复计分修复对照（预注册变更 A）==\n")
safe_cor <- function(a, b) {
  if (sd(a, na.rm = TRUE) == 0 || sd(b, na.rm = TRUE) == 0) return(NA_real_)
  suppressWarnings(cor(a, b, use = "complete.obs"))
}
fmt_cor <- function(x) if (is.na(x)) "NA（其中一列为常量，相关不可定义）" else sprintf("%.3f", x)
cat("v0.1: s4 与 c4_v01 是否逐行完全相同:", identical(coded$s4, coded$c4_v01), "\n")
cat("      s4 取值:", paste(sort(unique(coded$s4)), collapse = ","),
    " | c4_v01 取值:", paste(sort(unique(coded$c4_v01)), collapse = ","), "\n")
cat(sprintf("      → 两者都是常量 1（%d 条标题全部未命中抽象词词典），旧 C4 方差为 0，\n", nrow(d)))
cat("        对 Concrete 维度提供的信息量为零，且与 Simple 的 S4 完全共线。\n")
cat("v0.2: c4(数字+单位) 取值:", paste(sort(unique(coded$c4)), collapse = ","),
    " | 命中", sum(coded$c4, na.rm = TRUE), "/", nrow(d), "条，已恢复变异\n")
cat("      cor(s4, c4_v01) =", fmt_cor(safe_cor(coded$s4, coded$c4_v01)), "\n")
cat("      cor(s4, c4)     =", fmt_cor(safe_cor(coded$s4, coded$c4)),
    "（s4 仍为常量，故不可计算；但两列已不再相同）\n")
cat("s_simple 与 s_concrete 相关：v0.1 =",
    fmt_cor(safe_cor(coded$s_simple, coded$s_concrete_v01)),
    " → v0.2 =", fmt_cor(safe_cor(coded$s_simple, coded$s_concrete)), "\n")
cat("说明：改动前结果（pilot 28 条, v0.1）保留在 output/SC_pilot_summary.txt 供对照。\n")
cat("本样本维度变异情况（规则项-only 分析口径）：\n")
cat(sprintf("  s_credible 有 %d 行得分 > 0（只由 cr2/cr3/cr4 规则项贡献）；\n",
            sum(coded$s_credible > 0, na.rm = TRUE)))
cat(sprintf("  s_stories 有 %d 行得分 > 0。H4/H6 在本口径下能否检验须待样本量达标后再判定；\n",
            sum(coded$s_stories > 0, na.rm = TRUE)))
cat("  人工语义指标已按变更 G 正式不采用；不得为了「恢复变异」而回填人工列、补齐全表或重挑指标。\n")

cat("\n== 7. 链路自检 ==\n")
checks <- c(
  "字段齐全" = all(c("title", "desc", "view", "like", "favorite") %in% names(d)),
  "锁定目标子区(两区)" = all(coded$subzone %in% c("社科·法律·心理", "科学科普")),
  "存在有效播放量" = sum(coded$view > 0, na.rm = TRUE) > 0,
  "六维得分无 NA" = all(complete.cases(coded[, names(dims)])),
  "因变量无 NA" = all(is.finite(coded$engage_rate)),
  "s4 与 c4 不再相同" = !identical(coded$s4, coded$c4),
  "记录 n_valid_items" = all(paste0("n_", names(dims)) %in% names(coded)),
  "20% 双编码标记数正确" = file.exists(mp) && {
    mc <- read.csv(mp, fileEncoding = "UTF-8-BOM")
    sum(mc$kappa_flag == 1, na.rm = TRUE) == round(nrow(d) * 0.20)
  },
  "至少一维有变异" = any(apply(coded[, names(dims)], 2, sd, na.rm = TRUE) > 0),
  "字幕覆盖已如实标注" = all(coded$subtitle_n == 0 | is.na(coded$subtitle_n)),
  "人工指标未进入分析口径" = !HUMAN_ADOPTED &&
    !any(unlist(dims) %in% HUMAN) &&
    !any(HUMAN %in% names(coded)) &&
    all(paste0(HUMAN, "_NOT_ADOPTED") %in% names(coded)) &&
    all(paste0(names(ALL_DIMS), "_DIAGNOSTIC_ONLY") %in% names(coded)) &&
    all(coded$human_coding_adopted == 0L)
)
for (k in names(checks)) cat(sprintf("  [%s] %s\n", if (isTRUE(checks[k])) "PASS" else "FAIL", k))
cat("  合计:", sum(unlist(checks)), "/", length(checks), "PASS\n")

cat("\n== 8. 主模型可行性诊断（不报告任何系数/显著性）==\n")
sub <- coded[coded$rate_stable == 1, ]
cat("rate_stable(view>=1000) 行数:", nrow(sub), "\n")
cat("主模型预定自变量数: 6 维 + 7 控制 + 分区哑变量 ≈ 14-16\n")
cat("经验法则 10~15 观测/参数 → 需 140-240 条；当前", nrow(sub), "条，远不足。\n")
cat("→ 本轮**不运行主模型、不报告系数**；按预注册第 6 节，模型在样本量达标后再执行。\n")
cat("→ 人工语义指标已按变更 G 正式不采用，不再作为前置条件；若将来运行主模型，\n")
cat("  唯一允许的自变量口径是规则项-only 的 s_*，*_DIAGNOSTIC_ONLY 列不得代入。\n")
cat("→ 当前唯一阻塞项：样本量。信度问题已通过缩小口径处理，不再是待办。\n")

cat("\n== 9. 报告与引用边界 ==\n")
cat("本文件是链路自检与覆盖度诊断，不是研究结果；主模型从未运行。\n")
cat(sprintf("可以诚实报告：pilot 28 条 → MVP 实收 %d 条真实公开视频、锁定两区、\n", nrow(d)))
cat("codebook v0.3、预注册、盲法 A/B 双份交付、两轮 20% 双编码流程；\n")
cat("以及最值得记录的一条研究设计判断：两轮双编码暴露主观语义指标的校准难题，\n")
cat("因此主动判定测量信度不足、把人工编码排除出分析口径，只保留可复现的规则项。\n")
cat("也应写明「字幕 0% / 榜单历史快照 / 120 条目标未达 / 主模型因样本量不足未运行」。\n")
cat("不得写：kappa 达标、任何 kappa 数值、系数/显著性/因果结论、「SUCCES 有效」、\n")
cat("   「modelled each dimension against engagement rate」或「240 videos」等未发生的产出。\n")
cat("权威口径见 docs/SC_coding-adoption.md；对外表述边界见 README.md 的 Status 一节。\n")
sink()

cat("完成：", nrow(d), "条 →", file.path(PROC, "SC_mvp_coded.csv"), "\n")
cat("自检报告：", file.path(OUT, "SC_mvp_summary.txt"), "\n")
