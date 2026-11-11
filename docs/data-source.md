# 数据来源、抽样与合规

## 为什么选 B 站而不是抖音

| 维度 | B 站 | 抖音 |
|---|---|---|
| 公开元数据 | 有稳定公开接口，字段完整（播放/投币/收藏/分享/弹幕） | 反爬强，推荐流数据不可复现 |
| 知识内容界定 | 有明确知识区与分区体系，样本框清晰 | 知识类与泛娱乐混杂，抽样框模糊 |
| 编码素材 | 标题 + 简介 + 时长，中长视频有叙事结构 | 标题短、信息少，Stories 维度几乎无法编码 |
| 可复现性 | 高 | 低 |

**结论**：主线做 B 站；抖音仅作为"外部效度讨论"里的一句话，不进数据。若后续有余力，可用蝉妈妈/新抖等第三方公开榜单做小样本对照，但不与主线合并。

## 接口与字段

| 用途 | 端点 | 关键返回字段 |
|---|---|---|
| 视频元数据 | `https://api.bilibili.com/x/web-interface/view?bvid=<BVID>` | `bvid`, `title`, `desc`, `duration`, `pubdate`, `tname`(分区), `owner.mid`, `stat.{view,danmaku,reply,favorite,coin,share,like}` |
| UP 主粉丝数 | `https://api.bilibili.com/x/relation/stat?vmid=<MID>` | `follower` |
| 认证信息 | 同上 view 接口的 `owner` / `official` | 官方认证类型 |
| 排行榜/分区列表（取样框） | `https://api.bilibili.com/x/web-interface/ranking/v2?rid=<RID>&type=all` | 分区榜单 bvid 列表（**需 WBI 签名，实测返回 `-352`；按合规约定不绕过**） |
| 分区榜单（实际使用） | `https://api.bilibili.com/x/web-interface/ranking/region?rid=<RID>&day=3\|7` | bvid、`typename`、`play`、`create`（投稿时间）、`description` |
| 最新投稿（辅助取样框） | `https://api.bilibili.com/x/web-interface/newlist?rid=36&pn=&ps=` | 当天新稿；**`pn` 翻页几乎不生效、`stat` 全 0**，须逐条 `view` 补数 |
| 字幕 | `https://api.bilibili.com/x/player/v2?bvid=&cid=` | 未登录返回 `subtitles=[]`，实测覆盖率 0% |

> 接口可能随平台调整，脚本里已做失败重试与日志；若失效，**降级方案**：改用 Kaggle / 和鲸上现成的
> B 站数据集，并在 README 注明数据来源变更。**该方案已于 2026-11-06 实测核实（见 `docs/SC_alt-datasets.md`），
> 但其「补时间窗」这一唯一现实动机因用户最终决策「时间不做强制要求」而消失，且现成数据集多为 2019–2023 年快照、
> 普遍缺粉丝数、数值为中文「1.3万」字符串、许可多为 Unknown。**【最终决策 2026-11-06：不使用 Kaggle / 和鲸，
> 主流程继续走 B 站公开接口。】** 若未来确需外部对照，仍须按预注册第 8 节登记口径变更后再启用。

## 抽样策略（2026-11-06 第二轮已调整，详见 `SC_sample-scope.md`）

- **领域锁定**：B 站知识区**两区**「社科·法律·心理」(`rid=124`) **& 科学科普**(`rid=201`)；候选与样本均按 `typename` 硬过滤，不混入其它分区、不混用 Kaggle/和鲸外部数据。
- **分层**：两区锁定后「分区」恢复为真实层，原「4 分区 × 3 热度层」改为
  **子区（社科·法律·心理 / 科学科普）× 热度层（榜单 `play` 三分位 `high/mid/low` + 无播放的 `fresh`）× 主题层（法律/心理/社科/其它，标题关键词派生）**，固定种子 `20261106`。
- **样本量**：目标 120 条（MVP）/ 200–300 条（正式）；**公开无签名端点实收 64 条（目标 120，缺口 56）**，分层分布见 `output/SC_mvp_collection_report.txt`。不补造、不悄悄扩区，缺口逐层记在 `data/raw/SC_mvp_frame.csv`。
- **时间窗（不做强制要求）**：`ranking/region` 的 `day` 是**排行榜统计窗口，不是投稿时间窗**；本环境榜单自带 `create` 为 2025-04-03 ~ 04-09（约 580 天）。**项目已决定时间不做强制要求**，故该历史快照窗口直接纳入分析口径；每条样本仍写 `within_1yr` / `view_usable` / `rate_stable` 标记，`within_1yr` 仅作敏感性对照，不再据此硬删样本。
- **剔除**：时长 < 60 秒、重复 bvid、接口失败、自动命名的直播切片（`title_auto`，如 `XXX_2026-11-05_23-14-52_000`）、明显非知识类（人工判定并记录 `exclude_reason`）。`view<1000` 只标记 `rate_stable=0`，**不静默删除**——分母失真与选择偏差要同时写进报告。
- 保留 `days_since_pub` 作控制变量；**注意榜单历史稿（约 580 天）与 `newlist` 当天新稿（0–2 天）的累计互动率不可直接合并比较**。
- 原始设计的「4 分区 × 3 热度层 × 20-25 条 = 240-300 条」为便利设定、非 power analysis，且当前数据源不成立。解锁 120 条的四条路见 `SC_sample-scope.md` 第 5 节。

## 数据字典（字段设计说明）

> 下表是**最初骨架阶段的字段设计**。本轮实际落地的表头以
> `data/raw/SC_mvp_videos_20261106.csv` 为准（多出 `desc_source` / `subtitle_status` /
> `within_1yr` / `view_usable` / `analysis_eligible` / `heat_tier` / `topic_layer` 等标记列）。


| 列 | 类型 | 说明 |
|---|---|---|
| bvid | chr | 视频唯一 ID |
| title / desc | chr | 标题 / 简介（编码素材） |
| subzone | chr | 平台分区 |
| content_type | chr | 人工标注：硬核科普 / 通识·学习方法 |
| view, like, coin, favorite, share, reply, danmaku | int | 平台公开计数 |
| duration | int | 秒 |
| pubdate | int | Unix 时间戳，转 POSIXct |
| mid, follower, official | int/chr | UP 主 ID / 粉丝数 / 认证 |
| collected_at | datetime | 采集时间，必须记录（数据会变动） |

## 合规与工程注意

1. **只取公开视频元数据**，不采集任何用户个人信息、不存储评论正文中的账号与昵称。
2. **限速**：每次请求间隔 ≥ 1 秒，失败指数退避；单日请求量控制在数百级，见 `R/01_collect.R`。
3. 设置可识别的 User-Agent，遵守平台服务条款与 robots；若收到 412/429 立即停止，不绕过风控。
4. 原始数据**不覆盖写**，每次采集另存 `videos_raw_YYYYMMDD.csv`，保证可回溯。
5. 仓库中不提交任何 cookie、token 或认证信息；如接口需要登录态，改用本地环境变量读取，脚本里留占位。
6. 报告中标注：数据为某日快照，平台计数会随时间变化，故所有结论限于该快照。

## 若拿不到字幕（已实测：覆盖率 0%）

`x/player/v2` 在未登录状态返回 `code=0` 但 `subtitles=[]`、`allow_submit=false`，
第二轮 33 条全部 `no_subtitle`，`intro` 全空。因此 `Stories` 维度只能靠标题与简介代理，效度受限：

- **本轮实际采用（保守做法）**：`u4` 标 `NA`、人工 `st3` 按 `docs/codebook.md` 判定细则填写、
  `st4` 保留 `st_weak=1` 弱代理标记；主模型只按有效指标计分并逐行记录 `n_valid_items`。
- **报告必须写明**：「字幕覆盖率 0%，Stories 与 Unexpected 的口语线索无法测量」，
  以及该维在本样本得分近乎全 0 → **H6 无法检验**，不得硬跑模型。
- **进阶做法（需登录态）**：用 `x/player/v2` 取有字幕视频的前 30 秒作 `intro` 列，
  并在报告中说明字幕覆盖率；采集脚本 `SC_collect_mvp.py` 已预留该分支。
