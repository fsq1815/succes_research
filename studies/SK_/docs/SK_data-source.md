# SUCCES-Kaggle 数据源核查与字段映射

**核查日期** 2026-11-07 ｜ **结论**：换用 Kaggle 是**可行的**，但必须使用本次筛出的、许可明确且字段完整的数据集；
原项目 2026-11-06 的「不用 Kaggle」结论只对当时核查的那一批数据集成立，此处予以更新，而不是推翻。

---

## 1. 与 `succes-bilibili/docs/SC_alt-datasets.md` 的关系

原项目在 2026-11-06 决定「不使用 Kaggle / 和鲸现成数据集」，理由有四条：多为 2019–2023 历史快照、
缺粉丝数、数值是中文「1.3万」字符串、许可多为 Unknown。这几条对当时看到的那批数据集都成立。

本次为独立项目，系统检索了 Kaggle 公开数据集目录后，发现：

| 原核查的顾虑 | 本次的实际情况 |
|---|---|
| 数据太老 | D1 是 **2025 年 TOP100 创作者**视频（发布范围 2024-07 ~ 2025-12），比原项目自采的 2025-04 榜单快照更新 |
| 缺粉丝数 | **依然缺**；本项目改用 **UP 主固定效应**替代，并明确写进局限 |
| 中文数字字符串 | D1 为 xlsx 数值、D2 为阿拉伯数字字符串；清洗层仍保留 `parse_cn_count()` 以防其它版本 |
| 许可不明 | 本次只选 **MIT / Apache-2.0** 两个许可明确的数据集，许可 Unknown 的候选一律排除 |

⚠️ 因此这不是「原项目判断错了」，而是**检索范围扩大后的更新**。两个项目的样本框、领域、时间窗、
采集口径仍完全不同，本项目是外部效度检验，不是对原项目的复现或翻案。

## 2. 检索与获取方式（均免登录、可复现）

```bash
# 列目录
curl "https://www.kaggle.com/api/v1/datasets/list?search=bilibili&pageSize=40"
# 下载（返回 302 到 GCS 签名 URL，随后是 application/zip）
curl -L "https://www.kaggle.com/api/v1/datasets/download/<owner>/<slug>"
```

`SK_download.py` 用 Python `urllib` 复现同一链路，不使用 API token、不绕过任何访问控制，
并把 URL、下载时间、字节数与 SHA-256 写入 `data/external/SK_download_manifest.csv`。
本机核查时 `~/.kaggle/kaggle.json` 与 `KAGGLE_*` 环境变量均不存在，Kaggle CLI 也未安装——全部走公开端点。

## 3. 采用的两个数据集

| 编号 | Kaggle ref | 许可 | 原始文件 | 原始行数 | 最终分析 N |
|---|---|---|---|---|---|
| D1 | `sylviawyon/bilibili-2025-top-100-creators-video-dataset` | **MIT** | `video_details.xlsx`（1.5 MB） | 5,759 | **5,717** |
| D2 | `calefctinpan/bilibili-zhang-xuefeng-video-records` | **Apache-2.0** | `bilibili_zhangxuefeng_videos.csv`（0.12 MB） | 1,881 | **962** |

D1：2025 年头部（TOP100）创作者视频，泛领域，含视频简介（覆盖率 81.5%）。
D2：围绕单一教育话题的视频（多 UP 主），时间跨度 2016–2026，简介覆盖率 39.0%，
`tname` / `tags` 两列全空（不用于分析）。

## 4. 被排除的候选（留痕）

| 候选 | 排除原因 |
|---|---|
| `zhuosun03/bilibili-must-watch`（每周必看，8,104 行，字段很全） | 许可 **Unknown**，不引入公开仓库 |
| `pengpengwang1999/blizzard-games-popularity-on-bilibilicomchina` | 许可 Unknown；游戏领域；计数为中文「万」字符串 |
| `beats0/bilibili-user` | 许可 Unknown；1 亿用户个人信息，与本项目无关且涉及隐私 |
| `sherrytp/bilibili-cells-at-work` / `bilibili-spyxfamily` | 影评/评论文本，无视频互动计数字段 |
| `hongbinmiao/kun-bilibili-b` | 910 MB 视频/图像素材，非结构化元数据 |
| `omenkj/social-media-sponsorship-and-engagement` | 下载端点返回 403 |
| `kelvinkeekwongyew/genshin-impact-bilibili-videodataset` | CC BY-NC（非商业限制），且单一游戏领域 |

## 5. 字段映射

**D1（中文表头 → 统一英文）**

| 原始 | 统一 | 原始 | 统一 |
|---|---|---|---|
| BV号 | `bvid` | 精确播放数 | `view` |
| 标题 | `title` | 点赞数 / 投币数 / 收藏数 | `like` / `coin` / `favorite` |
| 视频简介 | `desc`（`-` 视为空） | 分享数 / 评论数 / 弹幕数 | `share` / `reply` / `danmaku` |
| UP主 / UP主ID | `up_name` / `up_mid` | 发布时间 | `pub_time` |
| 时长(秒) | `duration` | 链接 / 视频aid | 不用于分析 |

**D2** 表头已是英文（`bvid,title,up_mid,up_name,pub_time,duration,view,danmaku,reply,like,coin,favorite,share,tname,tags,desc`），直接对齐。

**派生字段**：`engage_rate=(like+coin+favorite+share+reply)/view`；`fav_rate`、`share_rate`；
`title_len`、`log_view`、`log_duration`、`pub_hour`、`pub_weekday`、`pub_month`；18 个规则项 + 6 个维度得分 + 6 个 `n_valid_items`。

## 6. 已知数据质量问题（已处理并留痕）

| 现象 | 处理 |
|---|---|
| D1 有 42 条重复 BV 号、D2 有 894 条重复 | 按 `bvid` 去重，逐条记入 `output/SK_data_health.txt` |
| D1 简介用 `-` 表示空 | 统一转空串，覆盖率 81.5% |
| D2 的 `tname` / `tags` 全空 | 不纳入分析，不猜测填充 |
| D2 `view < 1000` 有 25 条 | 按预注册剔除 |
| `fav_rate=0`（D1 1 条）/ `share_rate=0`（D2 3 条） | 稳健性换 `log` 因变量时按「log 要求为正」剔除并记数 |
| 两个数据集都**没有**字幕、粉丝数、UP 主认证 | `u4` / `cr4` 记 NA，不补 0（预注册 SK-变更 A/B） |
| D2 时间跨度 10 年，`pub_month` 达 73 个水平 | 年月固定效应吸收长期趋势；模型参数偏高，S6 只作诊断 |

## 7. 合规

- 原始 zip 与逐行编码表**不提交仓库**（`.gitignore` 排除），由 `SK_download.py` / `SK_prepare.py` 重建；
  仓库只保留聚合结果与脚本。
- D1 为 MIT、D2 为 Apache-2.0；`LICENSE` 中保留来源与许可声明。
- 不采集任何个人信息、不使用 cookie / token、不绕过访问控制、不对平台发起请求（数据来自 Kaggle 静态文件）。
- UP 主 ID 为平台公开标识，仅用于聚类与固定效应，不做身份识别，也不与任何外部数据关联。
