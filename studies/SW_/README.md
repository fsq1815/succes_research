# SUCCES-Weekly — 每周必看高赞评论 × SUCCES 六要素
> **公开快照说明**：本目录是原工作区项目 `succes-weekly/` 的可公开部分。文档中出现的工作区目录名（`succes-bilibili/`、`succes-kaggle/`、`succes-weekly/`）是历史路径；在**本仓库**内，对应内容分别是根目录（`SC_`，前序）、`studies/SK_/`（主体）、`studies/SW_/`（延伸）。预注册与结果文件保持冻结原文，未随迁移改写。


把 `succes-bilibili` / `succes-kaggle` 的 **SUCCES 六维规则项编码表**原样移植到
Kaggle「B 站每周必看」的 bvid 上，抓取每个视频的**公开高赞评论**，在预注册冻结之后
检验六要素与评论中「信息性讨论」的关联。

> **一句话边界**：高赞热评里几乎不出现「学到了 / 感谢科普 / 涨知识」这类表达
> （词典开发集 180 条中 **0 命中**），所以「观众获取信息」这一构念**不能被直接测量**。
> 本项目诚实报告这一点，并把因变量改为可复现的代理指标「信息性讨论」；
> 结论只针对该代理指标，**不等于「观众真的获取了信息」**。

结果见 [`SW_report.md`](SW_report.md)，机器可读结果见 `output/`。

---

## 文件名前缀怎么区分

工作区里四个项目用不同前缀，**互不覆盖**：

| 前缀 | 目录 | 主题 | 状态 |
|---|---|---|---|
| `SC_` | `succes-bilibili/` | SUCCES × B 站公开接口自采（64 条） | 主模型未运行；方法学与可复现工程 |
| `SK_` | `succes-kaggle/` | SUCCES × Kaggle 二手视频数据（5,717 + 962 条） | 主模型已运行，1/6 假设获支持 |
| **`SW_`** | **`succes-weekly/`** | **SUCCES × 每周必看高赞评论** | **主模型已运行，见 `SW_report.md`** |
| `LS_` | `logistics-satisfaction/` | 物流履约体验与用户评分 | 独立骨架 |

另有 `succes-bilibili-public/`：`SC_` 项目的去隐私 GitHub 公开版。

## 这个项目能呈现什么

| ✅ 有 | ❌ 没有 |
|---|---|
| 按 bvid 抓取的真实公开高赞评论、逐请求日志、bvid↔aid 抽样核验 | 评论正文的再分发（`.gitignore` 排除） |
| 看结果前冻结的预注册（六条正相关假设、模型、控制变量、BH 校正、S1–S7） | 「观众获取了信息」的直接测量 |
| 词典开发集独立排除、逐条审计留痕（解释为何换因变量） | 10 条高赞评论（公开接口上限 **3 条**） |
| 评论级 LPM + 按 UP 主聚类稳健 SE + BH-FDR + 6 组稳健性 | 因果结论 / 「SUCCES 有效」 |
| 一条真实的测量天花板发现 + 六个可报告的关联系数 | 把高赞热评外推到全体观众 |

## 快速开始

```bash
python3 SW_download.py                 # 免登录下载每周必看 zip
python3 SW_collect.py --split dev      # 词典开发集（60 bvid）
python3 SW_collect.py --split main     # 主样本（939 bvid，约 17 分钟）
python3 SW_collect.py --split control  # 非知识类对照（150 bvid）
python3 SW_prepare.py                  # 清洗 + 六维编码 + 因变量编码
Rscript R/SW_analyze.R                 # 主模型 + S1–S6（仅 base R）
```

依赖：Python 3.9+ **仅标准库**；R ≥ 4.0 **仅 base R**。原始数据与评论正文不进仓库，
由前两步重建；`output/` 下的聚合结果已提交。详见 [`docs/SW_reproduce.md`](docs/SW_reproduce.md)。

## 目录

```
succes-weekly/
├── README.md / SW_report.md        说明 / 结果报告（先读这两个）
├── LICENSE / .gitignore            许可（数据许可 Unknown）与忽略规则
├── SW_download.py                  Kaggle 公开端点下载 + SHA-256 manifest
├── SW_collect.py                   ⭐ 按 bvid 抓高赞评论（限速、无凭据、不绕过风控）
├── SW_succes.py                    ⭐ 六维规则项编码表（逐项移植 SK_/SC_ 的 LEX v0.2）
├── SW_info_markers.py              ⭐ 三层信息代理指标 + dev 集审计结论
├── SW_prepare.py                   合并、清洗、编码、描述性体检（不做推断）
├── R/SW_analyze.R                  ⭐ 主模型 / 聚类稳健 SE / BH-FDR / S1–S6
├── docs/
│   ├── SW_preregistration.md       ⭐ 看任何关联结果前冻结的预注册 v1.0
│   ├── SW_data-source.md           数据源、字段语义、接口边界、许可与局限
│   └── SW_reproduce.md             环境、四步复现、副作用矩阵、发布前检查
├── data/raw/                       样本框与评论原文（原文不提交）
├── data/processed/                 逐行分析表（不提交，可重建）
└── output/                        结果、日志、试点与词典审计记录
```

## 口径一致性

- **编码表相同**：`SW_succes.py` 的 `LEX` / `DIM_MAP` 逐项复制自
  `succes-kaggle/SK_codebook.py`（词典 v0.2、路径 C 的规则项-only 口径），不新增词、不改阈值。
- **人工语义指标同样不采用**：原项目两轮盲法双编码信度未达标，`s1/u3/c3/cr1/st3/e4` 不重新引入。
- **两处数据源变更**（预注册第 4 节已登记）：无完整简介 → `视频标签` 实为榜单推荐语，作为 `blurb`；
  无字幕 / 无认证 → `u4=NA`、`cr4=NA`，按有效项均值计分，`cr4=0` 仅作 S6 敏感性。

## 引用边界

可以写：按 bvid 抓取的公开高赞评论、预注册、六条方向性假设、BH-FDR 校正、
按 UP 主聚类稳健标准误、以及「显式学习表述在高赞热评中近乎不可测」这一方法学发现。

不得写：因果动词、「SUCCES 有效」、「观众获取了信息 / 学习效果更好」、
把 3 条高赞热评外推到全体观众、把 `info_echo` 系数当主结论、
隐去窄口径 `info_learn ≈ 0`、隐去不复现或不利的稳健性结果。
完整清单见 `SW_report.md` 与预注册第 8 节。

## 许可

代码 MIT；Kaggle 数据集许可标记 **Unknown**（原始 CSV 不分发），
评论正文不随仓库分发。来源、字段与合规边界见 `LICENSE` 和 `docs/SW_data-source.md`。
