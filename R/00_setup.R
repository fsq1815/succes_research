# 00_setup.R — 依赖、路径、统一图形主题
# 运行方式：source("R/00_setup.R")

pkgs <- c("httr", "jsonlite", "dplyr", "readr", "stringr", "tidyr",
          "ggplot2", "scales", "corrplot", "sandwich", "lmtest", "broom")
missing <- pkgs[!pkgs %in% rownames(installed.packages())]
if (length(missing)) install.packages(missing)
invisible(lapply(pkgs, library, character.only = TRUE))

DIR_RAW      <- "data/raw"
DIR_PROC     <- "data/processed"
DIR_FIG      <- "output/figures"
FILE_CODED   <- file.path(DIR_PROC, "coded.csv")

theme_succes <- function() {
  theme_minimal(base_size = 12, base_family = "sans") +
    theme(
      plot.title = element_text(face = "plain", size = 14),
      plot.subtitle = element_text(color = "grey40", size = 11),
      plot.caption = element_text(color = "grey50", size = 9),
      panel.grid.minor = element_blank(),
      legend.position = "bottom"
    )
}
theme_set(theme_succes())

save_fig <- function(name, width = 8, height = 5) {
  ggsave(file.path(DIR_FIG, paste0(name, ".png")),
         width = width, height = height, dpi = 300, bg = "white")
}
