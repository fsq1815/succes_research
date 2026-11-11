# SUCCES-Kaggle — 换数据源后能不能跑出结论？
> **公开快照说明**：本目录是原工作区项目 `succes-kaggle/` 的可公开部分。文档中出现的工作区目录名（`succes-bilibili/`、`succes-kaggle/`、`succes-weekly/`）是历史路径；在**本仓库**内，对应内容分别是根目录（`SC_`，前序）、`studies/SK_/`（主体）、`studies/SW_/`（延伸）。预注册与结果文件保持冻结原文，未随迁移改写。


把 `succes-bilibili` 的 **SUCCES 六维框架与规则项编码表**原样搬到两个 Kaggle 公开数据集上，
在预注册冻结之后真跑了一次主模型。答案：**能跑出结论，但结论是有边界的**。

> 5,717 条真实视频里，六条正相关假设只有 **Concrete** 一条在 BH-FDR 校正后获得支持
> （β=+0.0891, q=0.0292, 95%CI [+0.0274, +0.1508]）；换到另一领域 962 条样本后方向一致仅 2/6，
> 该关联未复现。同时发现：样本量放大 90 倍也救不了 Credible / Stories 两维（95%+ 为零）——
> **瓶颈在「只靠标题/简介」的操作化，不在样本量。**

完整结果见 [`SK_report.md`](SK_report.md)，机器可读结果见 `output/`。

---

## 文件名前缀怎么区分

工作区里三个项目用不同前缀，**互不覆盖**：

| 前缀 | 目录 | 主题 | 状态 |
|---|---|---|---|
| `SC_` | `succes-bilibili/` | SUCCES × B 站公开接口自采（64 条） | 主模型未运行；方法学与可复现工程 |
| `SK_` | **`succes-kaggle/`** | **SUCCES × Kaggle 二手数据（5,717 + 962 条）** | **主模型已运行，有结论与局限** |
| `LS_` | `logistics-satisfaction/` | 物流履约体验与用户评分 | 独立骨架 |

另有 `succes-bilibili-public/`：`SC_` 项目的去隐私 GitHub 公开版。

## 这个项目能呈现什么

| ✅ 有 | ❌ 没有 |
|---|---|
| 两个许可明确（MIT / Apache-2.0）的真实公开数据集、免登录可复现下载与 SHA-256 清单 | 因果结论 |
| 看结果前冻结的预注册（假设、公式、剔除规则、BH 校正、稳健性清单） | 「SUCCES 有效」或六维全正相关 |
| OLS + 按 UP 主聚类稳健标准误 + BH-FDR + VIF + 6 组稳健性 + 跨数据集方向一致性 | 跨领域稳定复现（方向一致仅 2/6） |
| 一条可报告的样本内关联、一条外部效度边界、一条方法学诊断 | 字幕、粉丝数、认证字段（两个数据源都没有，已记 NA） |

## 快速开始

```bash
python3 SK_download.py      # 免登录下载两个 Kaggle 数据集（约 1.6 MB）
python3 SK_prepare.py       # 清洗 → 规则项编码 → 描述性体检
Rscript R/SK_analyze.R      # 主模型 + S1–S6（仅 base R，不装包、不联网）
```

依赖：Python 3.9+ 标准库 + `openpyxl`（读 D1 的 xlsx）；R ≥ 4.0 仅 base R。
原始 zip 与逐行编码表不进仓库（`.gitignore`），由前两步重建；`output/` 下的聚合结果已提交。

## 目录

```
succes-kaggle/
├── README.md / SK_report.md        说明 / 结果报告（先读这两个）
├── LICENSE / .gitignore            许可与忽略规则
├── SK_codebook.py                  ⭐ 六维规则项编码表（移植自 SC_ 项目词典 v0.2）
├── SK_download.py                  Kaggle 公开端点下载 + SHA-256 清单
├── SK_prepare.py                   字段映射、中文数字解析、剔除、编码、体检
├── R/SK_analyze.R                  ⭐ 主模型 / 聚类稳健 SE / BH-FDR / 稳健性（仅 base R）
├── R/SK_explore_comment_proxies.R  ⚠️ 事后探索（非预注册）：评论计数代理诊断
├── docs/
│   ├── SK_preregistration.md       ⭐ 看结果前冻结的预注册 v1.0
│   ├── SK_data-source.md           数据源核查、许可、字段映射、质量留痕
│   └── SK_comment-feasibility.md   评论文本可行性核查（含 Kaggle 候选逐个核验）
├── data/external/                  下载的 zip + manifest（zip 不提交）
├── data/processed/                 逐行编码表（不提交，可重建）
└── output/
    ├── SK_data_health.txt          描述性体检（不含任何关联结果）
    ├── SK_results.txt              ⭐ 完整推断结果
    ├── SK_coefficients.csv         各模型 × 六维系数
    ├── SK_robustness.csv           S1–S6 稳健性明细
    └── SK_exploratory_comment_proxies.txt  ⚠️ 事后探索，非结论
```

## 口径一致性

- **编码表相同**：`SK_codebook.py` 的 `LEX` 与 `DIM_MAP` 逐项复制自
  `succes-bilibili/R/02_code_succes.R`（词典 v0.2、路径 C 的规则项-only 口径），不新增词、不改阈值。
- **人工语义指标同样不采用**：原项目两轮盲法双编码信度未达标，`s1/u3/c3/cr1/st3/e4` 在本项目不重新引入。
- **两处数据源变更**（已在预注册登记）：无字幕 → `u4=NA`；无 UP 主认证 → `cr4=NA`。
  两者都不猜值、不补 0；`cr4=0` 只作为稳健性 S5 单独检验。

## 评论文本：可行性核查（非预注册）

两个数据源**都没有评论正文**，只有 `reply`（评论数）与 `danmaku`（弹幕数）两个计数。
Kaggle 上另外 6 个带评论文本的数据集已逐个下载核验，结论见
[`docs/SK_comment-feasibility.md`](docs/SK_comment-feasibility.md)：唯一有大规模真实中文评论的
原神数据集，评论只能配到「动态 Post」，视频表无 ID 字段，**无法与本项目已编码的视频级指标拼接**；
其余为单部番剧长评或明显合成数据。

更根本的是方法学问题：六维编码的是**创作者生产侧**的标题/简介特征，评论是**受众反应侧**，
套同一套词典得到的不是「同样的六个系数」；且 `engage_rate` 分子含 `reply`，用评论文本构造自变量会与因变量机械相关。
想用评论补的 `Credible` / `Stories` 恰好是最依赖主观语义判断的两维，会退回路径 C 已否定的方向。

`R/SK_explore_comment_proxies.R` 用现有计数做了一组**事后探索性**诊断（⚠️ 写在看过主模型结果之后，
不属于预注册、不得当结论或写进对外报告）：剔除评论分量后 H3 仍为 β=+0.0889 / q=0.0316，
说明主结论不是被评论数机械驱动；但拆成单一行为因变量后 H3 均不显著，且六维零比例完全不变——
**计数不含语义，救不了测量天花板**。

## 引用边界

可以写：5,717 条真实公开视频、预注册、六条方向性假设、BH-FDR 校正、按 UP 主聚类稳健标准误；
「六条中一条获得支持，且该关联对因变量与极端值稳健、依赖账号层控制」；
「换到另一领域后方向一致仅 2/6，未复现」；「扩大样本后两维仍近乎常数 → 瓶颈在操作化」。

不得写：任何因果动词、「SUCCES 有效」、「六个维度都正相关」、把 S6 的极端系数当负向发现、
隐去不复现或隐去「去掉 UP 主固定效应后结论改变」。清单见 `SK_report.md` 第 6 节。

## 许可

代码 MIT；数据来自 Kaggle（D1 MIT、D2 Apache-2.0），原始文件不随仓库分发，
来源与许可声明见 `LICENSE` 和 `docs/SK_data-source.md`。
