# 01_collect.R — B 站公开视频元数据采集（骨架，非成品）
# 运行前请先阅读 docs/data-source.md；确认遵守平台条款后再执行。
# 输入：data/raw/sample_bvid.csv（按 docs/data-source.md 的分层策略自行生成，一列 bvid）
# 输出：data/raw/videos_raw_YYYYMMDD.csv、followers_YYYYMMDD.csv

source("R/00_setup.R")

BASE  <- "https://api.bilibili.com"
UA    <- "succes-research/0.1 (academic coursework)"
PAUSE <- 1.2   # 礼貌限速：每次请求间隔秒数，不要调小
TODAY <- format(Sys.Date(), "%Y%m%d")

nz <- function(x) if (is.null(x) || length(x) == 0) NA_character_ else as.character(x)
nz_num <- function(x) if (is.null(x) || length(x) == 0) NA_integer_ else as.integer(x)

safe_get <- function(url, pause = PAUSE, max_retry = 2) {
  for (i in seq_len(max_retry)) {
    Sys.sleep(pause * i)
    res <- tryCatch(GET(url, user_agent(UA), timeout(10)), error = function(e) NULL)
    if (is.null(res)) next
    code <- status_code(res)
    if (code %in% c(412, 429, 403)) {
      message("Rate limited or blocked (HTTP ", code, "). Stop. Do NOT bypass.")
      return(NULL)
    }
    if (code == 200) {
      parsed <- tryCatch(fromJSON(content(res, as = "text", encoding = "UTF-8"),
                                  simplifyVector = FALSE), error = function(e) NULL)
      if (!is.null(parsed)) return(parsed)
    }
  }
  NULL
}

fetch_video <- function(bvid) {
  url <- paste0(BASE, "/x/web-interface/view?bvid=", bvid)
  res <- safe_get(url)
  if (is.null(res) || is.null(res$data)) return(NULL)
  d <- res$data
  st <- if (is.null(d$stat)) list() else d$stat
  tibble(
    bvid        = bvid,
    title       = nz(d$title),
    desc        = nz(d$desc),
    subzone     = nz(d$tname),
    duration    = nz_num(d$duration),
    pubdate     = nz_num(d$pubdate),
    mid         = nz_num(if (is.null(d$owner)) NULL else d$owner$mid),
    official    = nz(if (is.null(d$owner)) NULL else d$owner$official),
    view        = nz_num(st$view),
    like        = nz_num(st$like),
    coin        = nz_num(st$coin),
    favorite    = nz_num(st$favorite),
    share       = nz_num(st$share),
    reply       = nz_num(st$reply),
    danmaku     = nz_num(st$danmaku),
    collected_at = as.character(Sys.time())
  )
}

fetch_follower <- function(mid) {
  if (is.na(mid)) return(tibble(mid = NA_integer_, follower = NA_integer_))
  url <- paste0(BASE, "/x/relation/stat?vmid=", mid)
  res <- safe_get(url)
  tibble(mid = mid,
         follower = if (is.null(res) || is.null(res$data)) NA_integer_
                    else nz_num(res$data$follower))
}

# ---- 主流程 -----------------------------------------------------------------
sample_file <- file.path(DIR_RAW, "sample_bvid.csv")
if (!file.exists(sample_file)) {
  stop("缺少 data/raw/sample_bvid.csv：请先按 docs/data-source.md 的分层策略生成 bvid 清单。")
}
bvid_list <- unique(read_csv(sample_file, show_col_types = FALSE)$bvid)
message("待采集视频数：", length(bvid_list))

raw <- list()
for (i in seq_along(bvid_list)) {
  row <- fetch_video(bvid_list[i])
  if (!is.null(row)) raw[[length(raw) + 1L]] <- row
  if (i %% 25 == 0) message("  进度 ", i, "/", length(bvid_list))
}
videos <- bind_rows(raw)

mids <- unique(na.omit(videos$mid))
followers <- bind_rows(lapply(mids, fetch_follower))

videos <- left_join(videos, followers, by = "mid") %>%
  mutate(
    pub_datetime    = as.POSIXct(pubdate, origin = "1970-01-01", tz = "Asia/Shanghai"),
    days_since_pub  = as.numeric(difftime(Sys.time(), pub_datetime, units = "days")),
    pub_hour        = as.integer(format(pub_datetime, "%H")),
    pub_weekday     = format(pub_datetime, "%u"),
    title_len       = nchar(title)
  )

write_csv(videos,    file.path(DIR_RAW, paste0("videos_raw_", TODAY, ".csv")))
write_csv(followers, file.path(DIR_RAW, paste0("followers_", TODAY, ".csv")))
message("完成：", nrow(videos), " 条视频。原始数据已按日期存档，请勿覆盖。")

# TODO
# 1) 人工标注 content_type（硬核科普 / 通识·学习方法），写回 processed 表
# 2) 记录剔除样本及原因（时长 < 60s、播放 < 1000、非知识类）
# 3) 若接口变更，降级使用公开数据集，并在 README 注明来源变化
# 4) 采集时间写入报告：平台计数为快照，会随时间变化
