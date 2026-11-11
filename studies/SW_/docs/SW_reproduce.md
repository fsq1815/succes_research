# 复现指南

## 环境

| 项 | 要求 |
|---|---|
| Python | 3.9+，**仅标准库**（`csv` / `urllib` / `zipfile` / `re` / `json`） |
| R | ≥ 4.0，**仅 base R**（`lm` / `p.adjust` / `pt`），不装包 |
| 网络 | 需能访问 Kaggle 公开下载端点与 B 站公开评论接口 |
| 凭据 | **不需要**：无 Kaggle token、无 B 站 Cookie、无 WBI 签名 |

## 四步复现

```bash
python3 SW_download.py                 # 1. 下载每周必看 zip + 写 SHA-256 manifest
python3 SW_collect.py --split dev      # 2a. 词典开发集（60 个 bvid）
python3 SW_collect.py --split main     # 2b. 主样本（939 个 bvid）
python3 SW_collect.py --split control  # 2c. 非知识类对照（150 个 bvid）
python3 SW_collect.py --verify-bvid    # 2d.（可选）抽样核验 bvid ↔ aid
python3 SW_prepare.py                  # 3. 清洗 + 六维编码 + 因变量编码 + 描述性体检
Rscript R/SW_analyze.R                 # 4. 主模型 + S1–S6 + VIF + 结果输出
```

**只读复现**：如果原始数据与采集结果已在 `data/`，只需第 3、4 步；这两步**不联网、不改输入**。
如果只需要核对结论，直接看 `output/SW_results.txt` 与三份机器可读结果即可。

## 脚本副作用矩阵

| 脚本 | 联网 | 覆盖已有输出 | 说明 |
|---|---|---|---|
| `SW_download.py` | ✅ | `--force` 时覆盖 zip、总是重写 manifest | 只写 `data/external/` |
| `SW_collect.py` | ✅ | **追加** `SW_comments_<split>.csv` | 断点续跑：已存在的 bvid 自动跳过；日志 append |
| `SW_collect.py --verify-bvid` | ✅ | 覆盖 `output/SW_bvid_aid_check.csv` | 20 个请求，约 25 秒 |
| `SW_prepare.py` | ❌ | 覆盖 `data/processed/SW_analysis.csv`、`output/SW_data_health.txt` | 幂等，可由原始数据完全重建 |
| `R/SW_analyze.R` | ❌ | 覆盖 `output/SW_results.txt`、`output/SW_coefficients.csv`、`output/SW_robustness.csv` | 幂等 |

**采集耗时**：1,149 个请求 × 1.1 s ≈ 21 分钟（dev 60 + main 939 + control 150）。
`output/SW_collect_log.txt` 逐 50 条记录进度与 `code` 分布。

## 隐私与合规

- 采集器**不携带任何凭据**，不绕过 `-352`（WBI 风控）、不换 IP、不重试失败请求。
- 只保存评论正文、点赞数、时间、公开评论 ID 与位置；**不保存用户名 / mid / 头像 / 签名**。
- 评论正文与逐行分析表被 `.gitignore` 排除，不随仓库分发。
- 公开接口 `sort=2` 恒返回 **3 条热评**，这是上限；`reply/main` 需 WBI，本项目不调用。
- Kaggle 数据集许可 **Unknown**：原始 CSV 不分发，复现者自行确认使用权利。

## 输出文件

| 文件 | 内容 |
|---|---|
| `output/SW_data_health.txt` | 各 split 的样本量、因变量基础率、六维稀疏度（**不含任何关联结果**） |
| `output/SW_results.txt` | 主模型六维系数、VIF、S1–S6 稳健性、方向一致性、结论边界 |
| `output/SW_coefficients.csv` | 主模型机器可读系数（β / SE / p / q_BH / CI / 判定） |
| `output/SW_robustness.csv` | 6 组稳健性 × 6 维的机器可读系数 |
| `output/SW_pilot.txt`、`output/SW_pilot_knowledge.txt` | 两次接口/基础率试点的原始记录 |
| `output/SW_dev_dictionary_audit.txt` | `dev` 集 180 条评论的词典逐条审计（为何窄口径不可用） |
| `output/SW_collect_log.txt` | 逐请求日志与接口返回码分布 |

## 检查清单（发布前）

- [ ] `git status` 中不含 `*.zip`、`data/raw/SW_comments_*.csv`、`data/processed/SW_analysis.csv`
- [ ] 全仓无绝对路径、用户名、Cookie、token
- [ ] Markdown 链接与内联路径引用无断链
- [ ] `Rscript R/SW_analyze.R` 可从干净状态复跑，结果与已提交 `output/` 一致
- [ ] README / 报告中没有因果动词、「观众获取了信息」、「SUCCES 有效」等越界表述
