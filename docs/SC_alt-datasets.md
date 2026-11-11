# 现成 B 站数据集调研（2026-11-06）

> **【最终决策 2026-11-06】不使用 Kaggle / 和鲸现成数据集作为本项目的样本来源。**
> 理由：① 现成数据集多为 2019–2023 年历史快照，比本项目接口采集的 2025-04 样本更老，
> 「近 1 年」不仅没解决反而更不成立；② 普遍缺粉丝数、数值为中文「1.3万」字符串、许可多为 Unknown；
> ③ 项目已明确「时间不做强制要求」，历史快照窗口本身即可纳入口径，因此「补时间窗」这唯一现实动机消失；
> ④ 项目锁定「社科·法律·心理 & 科学科普」两区，且坚持不混用外部数据集。
> 故本文件仅作**可复现的方法学核查记录**保留，主流程继续走 B 站公开接口（见 `SC_collect_mvp.py`）。
> 若未来确实需要外部对照，仍须按 `SC_preregistration.md` 第 8 节登记一组口径变更后再启用。

---

> 触发：`SC_sample-scope.md` §5 第 3 条把「换 Kaggle / 和鲸现成数据集」列为解锁 120 条的最现实路径，
> 并称「能同时解决『近 1 年』与样本量」。本文件为**实测核实**，结论是后半句不成立。
> 方法：Kaggle 公开 `datasets/list` API 检索 → 公开 `datasets/download` 下载 3 个数据集 →
> 解压读取真实表头与样例行 → 统计目标分区/时间跨度；和鲸与 GitHub 侧核对官网数据字典。
> 全部为只读核实，未把任何外部数据接入主流程。

---

## 1. 一句话结论

现成数据集是**个人爬虫项目留下的静态 CSV 快照**，不是为研究设计的样本。
它们能给你**样本量**和**单区标签**，但普遍是 **2019–2023 年**的历史数据，
比你当前从接口采到的 33 条（2025-04）**更老**，因此「近 1 年」这一条不但没解决，反而更差。

**同时更正上一轮的判断**：`SC_sample-scope.md` §5-3 与 `data-source.md` 里
「能同时解决近 1 年与样本量」的说法**已被本文件推翻**，见 §6 的更正记录。

---

## 2. 它们长什么样：通用字段结构

把 4 个平台的样本对齐后，字段高度同质。括号内为与本项目 `codebook.md` 的对应关系：

| 类别 | 常见字段 | 覆盖率 | 对本项目的作用 |
|---|---|---|---|
| 内容文本 | 标题 `title` | **几乎 100%** | ✅ 六维规则编码的主素材 |
| 内容文本 | 简介 `desc`/`description`/`视频介绍` | 不稳定（0%–83%） | ⚠️ Concrete / Credible / Stories 依赖它 |
| 内容文本 | 标签 `tags` | 部分有 | ⚠️ 有时其实是「平台推荐语」，见 §4 |
| 互动计数 | 播放、点赞、投币、收藏、分享、评论、弹幕 | **几乎 100%** | ✅ 可算 `engage_rate` 与 `fav_rate` |
| 时间 | 发布时间 `pub_time`/`upload_date`/`发布时间` | 几乎 100% | ✅ 可算 `days_since_pub` |
| 时间 | **采集时间 `collected_at`** | **多数没有** | ❌ 累计互动量的口径无法核验 |
| 主体 | UP 主昵称 + `mid` | 几乎 100% | ✅ 可做聚类/固定效应 |
| 主体 | **粉丝数 `follower`** | **几乎都没有** | ❌ 关键控制变量缺失；当下的粉丝数无法回溯历史 |
| 分区 | `tname` / `视频类型` / `channel_title` / `tid` | 部分有 | ⚠️ 决定了能否锁定单一子区 |
| 时长 | `duration` / `视频时长`（秒） | 部分有 | ✅ 控制变量 |
| 其它 | 字幕、评论正文、封面图（另附 jpg） | 基本没有 | ❌ Stories 维度仍然测不了 |

**结构性缺口**：粉丝数与采集时间几乎普遍缺失，而这正是 `04_model.Rmd` 里最重要的两个控制/口径变量。

---

## 3. 真实案例清单（已核实）

### Kaggle（用 `datasets/list?search=bilibili` 等 6 个检索词，共 25 个去重结果）

| 数据集 ref | 规模 / 年份 | 内容 | 关键字段 | 许可 |
|---|---|---|---|---|
| **`zhuosun03/bilibili-must-watch`** | **8,104 条，2019-03→2023-10** | 每周必看精选榜，237 期 | 18 列：标题、**视频类型**、视频标签(推荐语)、视频时长、up主_id、aid、投币/弹幕/收藏/点赞/评论/分享/播放、发布时间 | **Unknown**（Usability 1.18） |
| `calefctinpan/bilibili-zhang-xuefeng-video-records` | 1,881 条，2016→**2026-05**（60% 在近 1 年） | 搜索「张雪峰」的结果，489 个 UP 主 | 19 列，几乎与 B 站 `view` 接口一致（bvid/aid/cid/duration/view/danmaku/reply/like/coin/favorite/share/desc…） | Apache 2.0 |
| `taylorhtl/biliblili-info-with-video-info-and-ai-summary` | 3,070 条，2024 | 首页视频 + AI 摘要 + 封面情绪标注 | 27–274 列，xlsx 为主 | MIT |
| `pengpengwang1999/blizzard-games-popularity-on-bilibilicomchina` | 5 个 CSV / 2,865 条，2017→2022 | 16 个暴雪游戏的搜索结果 | `game_name,title,view,dm,like,coin,collect,share,upload_date,url` | Unknown |
| `hexsyro/creator-economy-and-monetisation-trends` | 1,420 行 / **327 列**，其中 bilibili 163 条 | 多平台社媒「规则生成」的 enrichment 数据 | 有 title/content/views/likes/engagement_rate/author_followers | Social Intel Commercial v1 |
| `beats0/bilibili-user` | 2.5 GB，1 亿用户，2022 | **用户信息**，不是视频 | — | Unknown |

> 提醒：`hexsyro` 那份字段看似最完美（连 `author_followers` 都有），但方法论写明所有 enrichment 信号
> 由确定性规则生成，属于**合成/加工数据**，不适合作为实证项目的主样本；
> `bilibili-user` 是用户个人信息，合规上不碰。

### 和鲸社区（Heywhale）

| 数据集 | 规模 / 采集时间 | 字段 | 许可 |
|---|---|---|---|
| [B站美食类视频详情](https://www.heywhale.com/mw/dataset/600649817ed5ab0015f06f1f) | **近 3 万条，4 个 CSV**，采集于 2021-01-11~19 | 12 列：标题/总播放数/总弹幕数/发布时间/发布者/点赞数/金币数/收藏量/分享数/视频介绍/标签/评论数 | **CC0** |
| [B站美食区数据集](https://www.heywhale.com/mw/dataset/60e05360be5f09001760a6ec) | 9,628 行 × 12 列，UTF-8，4.5 MB | 同上 | 未标注 |
| 四专区视频数据 `62a45d28…` | 每个 CSV 约 110 条，2022 | `title, duration, publisher, descriptions, pub_time, view, comments, praise, coins, favors, forwarding` | 未标注 |
| 「每周必看」notebook 数据 | 6,750 条 × 17 列，2019 起 | 期数/标题/视频类型/标签/链接/up主_id/aid/各类计数/发布时间 | 未标注 |

### GitHub（补充，字段最完整的一个）

[zhaisc2001/dataset_bilibili](https://github.com/zhaisc2001/dataset_bilibili) — Bilibili Daily Hot Videos，
**1,500 流行 + 9,786 普通**，2022 年，另有 11,273 张封面图。
字段：`video_bv, tid, title, channel_title, publish_time, authors, views, danmaku, likes, coins,
shares, tags, comment_counts, description, favorite, duration, pop`。
**Apache 2.0**。有 `channel_title` 与 `description`，是结构上最贴近 `codebook.md` 的一份；
但数据托管在 Google Drive，且是「单日分区流行/普通视频」，未验证是否含目标子区。

---

## 4. 实测样例行（不是看页面描述猜的）

```
# zhuosun03/bilibili-must-watch  (UTF-8, 8,104 行, 18 列)
HEADER: 期数 | 期数描述 | 标题 | 视频类型 | 视频标签 | 视频链接 | 视频时长 |
        up主 | up主_id | aid | 投币数 | 弹幕数 | 收藏数 | 点赞数 | 评论数 | 分享数 | 播放数 | 发布时间
ROW   : 1 | 2019第1期 03.22 - 03.28 | the real suger baby已知最高画质 | 音乐综合 |
        (空) | https://b23.tv/BV16b411b71j | 29 | 一嗷垚 | 30194033 | ... | 29236360 | 2019-03-01

# pengpengwang1999/blizzard-games  (GBK, 541 行)
HEADER: game_name | title | view | dm | like | coin | collect | share | upload_date | url
ROW   : 冰封王座 | 魔兽争霸：冰封王座【电影版】 | '40.6万 ' | 6452 | '1.3万' | 7712 | '1.1万' | 1054 | 2020-02-26 | ...

# calefctinpan/zhang-xuefeng  (UTF-8, 1,881 行, 19 列)
HEADER: bvid | aid | cid | title | up_mid | up_name | pub_time | duration | view | danmaku |
        reply | like | coin | favorite | share | tname | tags | desc
ROW   : BV1EcL36KEtW | ... | 为什么曾经备受尊敬的张雪峰，现如今被恶搞群嘲？ | ... |
        2026-05-16 | 265 | 3825504 | ... | tname='' | tags='' | desc=''
```

**三个真实存在的坑**：

1. **数值是中文网页字符串**：`'40.6万 '`、`'1.3万'` 带尾空格；和鲸美食更把
   `1.3万播放 · 79弹幕` 塞进同一格。直接 `as.numeric()` 会全变 `NA`，必须先正则解析。
   → `LS_01_load.R` / `02_code_succes.R` 都要加 `parse_cn_count()`。
2. **编码混乱**：同一 Kaggle 数据集内 5 个 CSV，部分是 GBK、部分已编码损坏
   （`Hearthstone.csv` / `Warcraft.csv` 用 GBK/GB18030 都解不开）。
3. **「视频标签」名不副实**：`bilibili-must-watch` 里它存的是**平台编辑写的每周必看推荐语**
   （如「看了这个视频，又想重读一遍《山海经》了。」），不是 UP 主简介，也不是标签。
   拿它当 `desc` 用，测到的是**平台包装话术**而非创作者包装，构念效度要重新界定并写进报告。

---

## 5. 与本项目 8 项需求的适配度（重点）

**最有价值的发现**：`bilibili-must-watch` 的 `视频类型` 里，
`社科·法律·心理` 恰好有 **156 条** —— 正是你锁定的子区，且超过 120 条 MVP 目标。
另有 `科学科普` 230、`人文历史` 165、`校园学习` 49 可作异质性对照。

这 156 条的实测画像：

| 指标 | 值 |
|---|---|
| 时间范围 | 2019-06-23 → 2023-09-29（2019:8 / 2020:60 / 2021:43 / 2022:25 / 2023:20） |
| 播放数 | 中位数 374 万，最小 **60.6 万**，最大 2,445 万 |
| 互动率 | 中位数 0.1388，范围 0.0438–0.3762 |
| 时长 | 中位数 575.5 秒，**无 <60 秒**（现有剔除规则几乎不生效） |
| 标签/推荐语 | 空率 1.3% |

| 项目需求 | 现成数据集 | 说明 |
|---|---|---|
| 扩到 120 条 | ✅ **156 条** | 一次到位，且静态文件可存档、完全可复现 |
| 锁定社科·法律·心理 | ✅ `视频类型` 直接过滤 | 不需要靠标题关键词派生主题层 |
| 近 1 年内发布 | ❌ **2019–2023，比现状更老** | 唯一近 1 年占比高的（张雪峰）`tname` 100% 为空、是单一话题搜索结果 |
| 补字幕素材 | ❌ 全都没有 | 与现状一致，H6 仍可能测不了 |
| 补简介素材 | ⚠️ 只有平台推荐语 | 构念从「创作者包装」变成「平台包装」，须写进 codebook |
| 互动率计算 | ✅ 7 项计数齐全、**纯数字** | 比现采数据还干净（无「万」字符串） |
| 粉丝数控制变量 | ❌ 无 | 有 `up主_id` 可回补**当下**粉丝数，但历史粉丝数不可回溯 |
| 时长 / 发布时间 / 分区 | ✅ 全有 | 控制变量齐全 |
| **选择偏差** | ⚠️ **比现状更严重** | 「每周必看」是平台精选爆款榜，全样本播放 ≥ 60 万 —— 属于**对结果变量截断**，比一般非概率样本更难辩护 |
| 许可 | ⚠️ **Unknown** | 公开发布 ≠ 可自由再利用；正式引用前需确认或改用 CC0 / Apache 2.0 来源 |
| 累计互动量可比性 | ⚠️ | 跨 5 个年份的采集日快照，且无 `collected_at`；`days_since_pub` 线性控制不够 |

---

## 6. 三条可选路径（需要你拍板）

**A. 换主样本为「每周必看」156 条（样本量优先）**
立刻能跑主模型、能做异质性。代价是要一次性登记一组**大口径变更**：
- 抽样框：公开接口榜单 → Kaggle 静态数据集（`04_model.Rmd` 全部路径改读外部数据）
- 时间窗：「近 1 年」→ **2019–2023 历史窗口**（`within_1yr` 标记作废）
- 编码素材：`desc` → 平台推荐语，构念效度重新界定
- 控制变量：`follower` 缺失，须降级为「UP 主固定效应」或另找来源
- 选择偏差：必须新增「爆款榜截断」一节，主结论只说「在入选每周必看的知识类视频内部」
- 现有 33 条实时数据**保留但不合并建模**，作为「当代样本 / 外部效度」对照 —— 这个对照本身
  是很好的方法学亮点（历史爆款 vs 当下实时），对研究设计讨论反而加分。

**B. 只当外部效度对照 / 清洗练习**
和鲸美食 3 万条（CC0、许可干净）用来演示 `parse_cn_count()` 与跨数据集稳健性，
主样本不动。工作量小，但解决不了 120 条。

**C. 不换，走回采清单**
对 `newlist` 的当天新稿建 bvid 清单，2–4 周后回采累计互动量。
这是**唯一能同时满足「近 1 年 + 互动量可比 + 单区锁定」**的路径，但需要 2–4 周回采窗口。

> **核查结论（当时倾向 A，最终未采用）**：换数据源后，项目叙事要从
> 「调用公开接口采集并编码了 B 站知识区视频」改成
> 「整理了一个公开数据集、重新清洗编码并检验了它的适用边界」。
> 两者侧重不同，但都必须把「为什么换、换了之后哪些结论不能说」写清楚。
> 最终决策为**不使用外部数据集**，见本文件开头与 `docs/SC_preregistration.md`。

---

## 7. 更正记录（对既有文档）

| 文件 | 原表述 | 更正 |
|---|---|---|
| `SC_sample-scope.md` §5-3 | 「改用现成数据集……**能同时解决『近 1 年』与样本量**」 | 只能解决样本量与单区锁定；年代普遍更早，「近 1 年」不成立 |
| `data-source.md` 降级方案 | 同上暗示 | 明确标注需核实年代与许可 |
| `SC_preregistration.md` §8 | 尚无数据源变更条目 | **若采用 A，必须新增一条完整变更记录**（抽样框、时间窗、素材定义、控制变量、选择偏差五项） |

---

## 8. 复现

```bash
# Kaggle 公开 API 检索
curl -s "https://www.kaggle.com/api/v1/datasets/list?search=bilibili&page=1"

# 下载三个已核实的数据集（无需登录）
for r in zhuosun03/bilibili-must-watch \
         calefctinpan/bilibili-zhang-xuefeng-video-records \
         pengpengwang1999/blizzard-games-popularity-on-bilibilicomchina; do
  curl -sL "https://www.kaggle.com/api/v1/datasets/download/$r" -o "$(echo $r | tr / _).zip"
done
# 注意：blizzard 系列 CSV 为 GBK，且部分文件编码已损坏；must-watch 为 UTF-8-BOM。
```

**本轮未把任何外部数据复制进项目仓库**：`bilibili-must-watch` 许可为 Unknown，
在确认可再利用前只做本地评估，不入库、不上传。
