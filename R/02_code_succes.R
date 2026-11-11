# 02_code_succes.R — SUCCES 六维规则编码
# 规则细节见 docs/codebook.md。词典版本：v0.2（冻结日期 2026-11-06）
# 任何词典改动必须记录 changelog，禁止看到结果后回头加词。
# v0.2 变更：C4 由「标题不含抽象词」（与 S4 完全同一）改定义为「数字+具体单位的可感知量化短语」。
#            详见 docs/SC_preregistration.md 第 8 节变更记录与 docs/SC_mvp.md。
#
# ⚠️ 采用性决策（2026-11-07，路径 C / 预注册变更 G）：
#   两轮 20% 双人编码信度均未达标 → 六个人工语义指标正式不采用。
#   六维得分只用下面的规则项（dim_map 每维 3 项）；s1/u3/c3/cr1/st3/e4 六列
#   保留在输出中仅作占位与审计对齐，**不得回填、不得进入得分或模型**。
#   权威口径见 docs/SC_coding-adoption.md。

source("R/00_setup.R")

# ---- 词典 v0.1 ---------------------------------------------------------------
LEX <- list(
  simple_conclusion = c("一句话", "搞懂", "讲清", "其实就", "只需", "分钟", "本质上是", "说白了"),
  abstract          = c("底层逻辑", "方法论", "认知", "范式", "维度", "体系", "思维模型"),
  unexpected        = c("你以为", "其实不是", "并不是", "错了", "恰恰相反", "颠覆", "真相是"),
  suspense          = c("为什么", "到底", "竟然", "凭什么", "?", "？"),
  concrete_entity   = c("钱", "工资", "手机", "地铁", "一天", "分钟", "一杯", "一张", "块钱", "公里", "小时"),
  credible          = c("研究显示", "实验", "数据", "调查", "论文", "根据", "统计", "报告", "文献"),
  emotional         = c("震惊", "崩溃", "后悔", "焦虑", "扎心", "救命", "细思极恐", "爽", "绝了", "可怕"),
  second_person     = c("你", "你的", "千万别"),
  frame             = c("别再", "错过", "省下", "避免", "少走弯路", "白花", "别被"),
  story_open        = c("我朋友", "有个学生", "曾经", "我当年", "某位", "有个读者"),
  story_time        = c("先", "后来", "结果", "直到", "没想到", "于是"),
  # v0.2 新增：可感知量化短语（数字 + 具体单位），用于替换与 S4 重复的旧 C4
  measured_unit     = c("[0-9]+ ?(元|块|万元|亿元|年|个月|天|小时|分钟|秒|公里|米|人|%|％|次|倍|斤|公斤|度|杯|页|位|万|亿|岁)")
)

hit <- function(x, words) as.integer(str_detect(x, paste(words, collapse = "|")))
hit_count <- function(x, words) str_count(x, paste(words, collapse = "|"))

# ---- 主编码函数 --------------------------------------------------------------
# df 需含 title, desc；可选 intro（字幕前 30 秒）
# 返回：原表 + 24 个指标列 + 6 个维度得分（0-1）
code_succes <- function(df) {
  if (!all(c("title", "desc") %in% names(df))) stop("需要 title 与 desc 列")

  txt <- paste(ifelse(is.na(df$title), "", df$title),
               ifelse(is.na(df$desc),  "", df$desc), sep = " ")
  intro <- if ("intro" %in% names(df)) ifelse(is.na(df$intro), "", df$intro) else rep("", nrow(df))

  out <- df %>%
    mutate(
      txt = txt,
      # S Simple
      s1 = NA_integer_,                                  # 人工：核心主张是否单一
      s2 = as.integer(nchar(title) <= 20),
      s3 = hit(txt, LEX$simple_conclusion),
      s4 = as.integer(hit_count(title, LEX$abstract) == 0),
      # U Unexpected
      u1 = hit(txt, LEX$unexpected),
      u2 = hit(title, LEX$suspense),
      u3 = NA_integer_,                                  # 人工：数字反差 / 冲突并置
      u4 = ifelse(intro == "", NA_integer_,
                  as.integer(str_detect(intro, "\\?|？|为什么") &
                             !str_detect(intro, LEX$simple_conclusion[1]))),
      # C Concrete
      c1 = as.integer(str_detect(txt, "[0-9]")),
      c2 = hit(txt, LEX$concrete_entity),
      c3 = NA_integer_,                                  # 人工：具体案例 / 人名 / 产品名
      # v0.2：C4 不再复用 S4 的抽象词判定（两列曾完全相同，人为制造两维耦合）
      c4 = hit(txt, LEX$measured_unit),
      # Cr Credible
      cr1 = NA_integer_,                                 # 人工：是否注明来源
      cr2 = hit(txt, LEX$credible),
      cr3 = as.integer(str_detect(txt, "https?://|DOI|doi|参考文献|出处")),
      cr4 = as.integer(!is.na(official) & official != ""),
      # E Emotional
      e1 = hit(title, LEX$emotional),
      e2 = hit(title, LEX$second_person),
      e3 = hit(title, LEX$frame),
      e4 = NA_integer_,                                  # 人工(v0.2)：标题/简介是否有明确情绪唤起意图
      # St Stories
      st1 = hit(txt, LEX$story_open),
      st2 = as.integer(hit_count(txt, LEX$story_time) >= 2),
      st3 = NA_integer_,                                 # 人工：困境—转折结构
      st4 = as.integer(!is.na(duration) & duration >= 480 &
                       str_detect(txt, "案例|例子|举例|故事")),
      st_weak = 1L                                      # 标记：本维主要靠文本代理
    )

  # 规则项-only 分析口径（变更 G）：与 R/SC_mvp.R 的 RULE_DIMS 保持一致
  dim_map <- list(
    s_simple     = c("s2", "s3", "s4"),
    s_unexpected = c("u1", "u2", "u4"),
    s_concrete   = c("c1", "c2", "c4"),
    s_credible   = c("cr2", "cr3", "cr4"),
    s_emotional  = c("e1", "e2", "e3"),
    s_stories    = c("st1", "st2", "st4")
  )
  for (nm in names(dim_map)) {
    out[[nm]] <- rowMeans(out[, dim_map[[nm]]], na.rm = TRUE)
  }

  out %>%
    mutate(
      engage_rate = (like + coin + favorite + share + reply) / pmax(view, 1),
      fav_rate    = favorite / pmax(view, 1),
      share_rate  = share    / pmax(view, 1),
      log_follower = log1p(follower),
      log_duration = log1p(duration)
    ) %>%
    select(-txt)
}

# ---- 使用示例 ----------------------------------------------------------------
# source("R/02_code_succes.R")
# videos <- read_csv("data/raw/videos_raw_20261105.csv")
# coded  <- code_succes(videos)
# write_csv(coded, FILE_CODED)
#
# ---- 一致性检验（已结案，报告「局限」必写） -----------------------------------
# 随机 20% 由两位真人独立标注，计算 Cohen's kappa：
#   Rscript R/SC_kappa.R        （读 data/processed/SC_double_coding_template.csv）
# 两轮均未达到预注册目标 0.70 → 项目决策路径 C，**人工语义指标正式不采用**，
# codebook 冻结在 v0.3，不再重编、不再出 v0.4（变更 F / G）。
# 报告须写明「信度未达标、结果不采用」与口径缩小的代价；两轮数据全部保留归档。
# 注意：kappa 必须由两位真实编码人填写后计算；脚本自带「模拟数据自检」，
#       该自检数值仅证明公式跑通，绝不可写进报告（见 output/SC_kappa_report.txt）。

# ---- Changelog ---------------------------------------------------------------
# v0.1 2026-11-05 初始词典与规则，冻结于数据跑出结果之前。pilot 28 条使用的是本版。
# v0.2 2026-11-06 变更一：C4 由「标题不含抽象词」改为「数字+具体单位的可感知量化短语」，
#                 新增词典项 measured_unit。理由：pilot 发现 s4 与 c4 是同一列，
#                 使 Simple 与 Concrete 人为耦合。此改动发生在看到 pilot 描述统计之后、
#                 看到任何回归结果之前；按预注册第 8 节登记为探索性调整，
#                 并保留 v0.1 结果供对照（见 output/SC_mvp_summary.txt 第 6 节）。
#      2026-11-06 变更二：E4 由「评论区情绪均值」改为人工语义判定「是否有明确情绪唤起意图」。
#                 理由：合规约定不采集评论正文，原指标不可得。见 docs/codebook.md。
