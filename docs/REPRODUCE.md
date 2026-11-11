# 复现、发布与隐私检查

本页说明在**不破坏已归档数据**的前提下如何复跑、各脚本的副作用，以及发布到 GitHub 前的检查清单。
面向读者的系列整合叙述见仓库根目录 [`REPORT.md`](../REPORT.md)：主体为独立的 `SK_` Kaggle 项目、延伸为 `SW_` 项目，本仓库（`SC_`）为前序方法学工作；报告中的实证系数不属于本仓库产出。
同一内容的网页呈现见根目录 [`index.html`](../index.html)：单文件、无外部资源、浅色排版，可直接作为 GitHub Pages 首页；`.gitignore` 中的 `!/index.html` 例外是为它设置的，勿删除。

---

## 1. 环境

| 用途 | 依赖 |
|---|---|
| 两个核心 R 脚本 | **R ≥ 4.0，仅 base R**。`R/SC_mvp.R` 与 `R/SC_kappa.R` 不加载任何包、不联网、不写系统目录 |
| 采集脚本 | Python ≥ 3.9 标准库 + 系统 `curl`（脚本用 `subprocess` 调 curl，未使用 requests） |
| 编码表导出 / 交回校验 | Python 标准库 + `openpyxl ≥ 3.1`（`pip install openpyxl`） |
| 报告层骨架（未渲染） | `R/00_setup.R` 会检测缺失包并调用 `install.packages()` 安装一整套 tidyverse / 建模包；**只读复现不需要运行它** |

所有路径都相对脚本自身位置解析（`__file__` / `--file=`），clone 到任意目录都能跑，无需改路径。

## 2. 路线 A：只读复现（推荐）

```bash
Rscript R/SC_mvp.R
Rscript R/SC_kappa.R
```

| 脚本 | 读入 | 写出 |
|---|---|---|
| `R/SC_mvp.R` | `data/raw/SC_mvp_videos_*.csv`（取字典序最新）、`data/processed/SC_manual_coding.csv`（仅审计留痕） | `data/processed/SC_mvp_coded.csv`、`output/SC_mvp_summary.txt` |
| `R/SC_kappa.R` | `data/processed/SC_double_coding_template.csv`、`SC_kappa_demo_SIMULATED.csv` | `output/SC_kappa_report.txt` |

两次写出都是确定性覆盖：只要输入不变，重新运行得到的编码结果与报告应与仓库内一致（`SC_kappa_report.txt` 顶部的生成时间除外）。`R/SC_kappa.R` 还支持 `--input=<csv> --output=<txt>`，可在临时副本上做非正式预演而不触碰真实数据。

**预期结果**：`output/SC_mvp_summary.txt` 末尾 `合计: 11 / 11 PASS`；`output/SC_kappa_report.txt` 第 1 节给出正式 kappa 与 2000 次 bootstrap CI，并明确写出「本轮未达到预注册信度目标」与「路径 C / 变更 G：人工指标正式不采用」。

### 11 项自检分别检查什么

字段齐全 · 两区锁定 · 存在有效播放量 · 六维得分无 NA · 因变量无 NA · `s4` 与 `c4` 不再重复 · 逐行记录 `n_valid_items` · 20% 双编码标记数正确 · 至少一维有变异 · 字幕覆盖如实标注 · **人工指标未进入分析口径**。最后一项是路径 C 的技术护栏：即使主表里保留了人工原始列，也不允许它们进入 `s_*` 得分。

## 3. 路线 B：从头采集（会改变仓库数据）

```bash
python3 SC_probe.py        # 只读接口体检：rid / 时间语义 / 翻页 / 字幕
python3 SC_probe2.py
python3 SC_probe3.py
python3 SC_collect_mvp.py  # 正式采集
python3 SC_make_coding_sheets.py
```

⚠️ 采集脚本会**覆盖** `data/raw/SC_mvp_videos_<日期>.csv`、`SC_mvp_frame.csv`、`SC_mvp_request_log.csv` 与 `output/SC_mvp_collection_report.txt`。公开端点在不同时间返回不同快照和风控状态，重跑几乎不可能复现仓库里这 64 条样本；`SC_make_coding_sheets.py` 更会**清空**已填的人工编码。

如需重跑，请先整体备份 `data/` 与 `output/`，或在一个临时副本目录里操作。采集脚本对 `-352 / -403 / 403 / 412 / 429 / -799` 一律跳过并记录在请求审计里，**不绕过风控、不使用登录态**。

## 4. 路线 C：双人编码留痕脚本（只作为流程证据，勿执行）

| 脚本 | 当时作用 |
|---|---|
| `SC_export_coderB.py` | 生成两轮 A / B 盲法填写表（xlsx + csv + 说明 + zip），表内不含对方答案、判定理由与播放/排名数据 |
| `SC_import_coderB.py` | 校验交回表：`--role A\|B`、`--dry-run`、值域 `0/1/9`、素材三列一致性、`coder_id`、写入前自动备份且只写本角色列 |
| `SC_sync_coderA_to_main.py` | 把真人 A 的 13 条 v0.3 判定同步回 64 行主编码表（写入前备份） |
| `SC_fill_coderA.py` | 第一轮**流程演示**：由脚本代填 coderA。它不构成信度证据，且会覆盖真人判定，已标记为 deprecated |

这四支脚本共同证明「盲法交付 → 独立填写 → 校验合并 → 归档」的流程真实存在。路径 C 结案后**无需再运行**；再运行会覆盖 `data/processed/handoff/` 下两轮交回原件与备份，破坏审计链。

## 5. 数据文件约定

- CSV 使用 **UTF-8**，部分由表格软件导出的文件带 BOM；R 脚本统一以 `fileEncoding = "UTF-8-BOM"` 读取，Python 用 `encoding="utf-8-sig"`。
- `SC_kappa_demo_SIMULATED.csv` 与 kappa 报告第 2 节是**模拟自检**，只验证公式实现，与任何真实一致性无关。
- `data/processed/SC_mvp_coded.csv` 中：人工语义列名为 `*_NOT_ADOPTED`；含人工项的混合口径列名为 `*_DIAGNOSTIC_ONLY`；只有 `s_*` 是允许进入模型的口径。
- `data/processed/handoff/` 下的 xlsx 已移除办公软件写入的账户昵称与账号标识元数据（creator / lastModifiedBy 改为 `anonymous`，custom properties 置空），编码值原样保留；两位编码人仅以代号 `R2` / `coderB` 出现。其中两个第一轮文件原本带有 WPS 生成的空 `<fill/>`，已修复为合法样式以便 openpyxl / Excel 直接打开。
- `data/raw/SC_mvp_request_log.csv` 记录每次请求的端点、参数、返回码与是否被风控拦截，可用于核对「0 次绕过」。

## 6. 报告层的当前状态

`R/03_eda.Rmd`、`R/04_model.Rmd`、`writeup/report.Rmd` 都是**预定分析方案的骨架**，从未渲染，也不含任何结果。`writeup/report.Rmd` 顶部有状态横幅，正文中的 `___` 是刻意保留的占位符——在样本量达标前不得填写。`R/00_setup.R` 会在 `source()` 时尝试安装整包依赖，仅在将来真正跑报告层时才需要。

## 7. 常见故障

| 现象 | 原因与处理 |
|---|---|
| `TypeError: expected <class 'openpyxl.styles.fills.Fill'>` | 用 Excel / WPS 另存过的 xlsx 会写出空 `<fill/>`。`SC_import_coderB.py` 的 `read_back()` 已内置样式消毒兜底，原件不动 |
| `Rscript` 报找不到 `data/raw/SC_mvp_videos_*.csv` | 请在仓库根目录运行，或确认 `data/raw/` 未被清空 |
| 采集返回 `-352` / `-799` | 平台风控。脚本会跳过并记入审计日志；这是预期行为，不要加 cookie 或改签名绕过 |
| 重跑后编码表与仓库不一致 | 检查是否误跑了 `SC_make_coding_sheets.py`；从 `data/processed/archive_*` 的备份恢复 |

## 8. 发布到 GitHub

仓库已完成本地提交，只需绑定远程并推送（把 `<your-name>` / `<your-repo>` 换成自己的）：

```bash
cd succes-bilibili-public
git remote add origin https://github.com/<your-name>/<your-repo>.git
git branch -M main
git push -u origin main
```

GitHub Pages：仓库 **Settings → Pages → Deploy from a branch → `main` / `/ (root)` → Save**，稍后访问 `https://<your-name>.github.io/<your-repo>/`。

`.gitignore` 排除 `.DS_Store`、`R_libs/`、`__pycache__`、`*.xlsx` / `*.zip`、双编码交回原件与归档备份、旧版网页存档，以及 `studies/` 下的原始数据、评论正文与个体级编码表；`!/index.html` 例外保证 Pages 首页被跟踪。上传后建议在 GitHub 仓库页补一句 description 与 topics，例如 `inter-coder-reliability`、`pre-registration`、`content-analysis`、`reproducible-research`。

### 公开文件边界

| 随仓库分发 | 不随仓库分发（仅本地工作区留存） |
|---|---|
| 脚本、预注册、编码手册、方法文档、判定汇总、`output/` 聚合结果、`data/raw/` 公开视频元数据 | 双编码交回原件与导入前备份（`data/processed/handoff/`、`archive_*`）、`SC_coderB_handoff.zip`、Kaggle 原始 zip、`studies/` 下的评论正文与个体级 `SK_coded_*.csv` / `SW_analysis.csv` |

文档中出现的 `handoff/` 路径是**流程留痕**，说明当时发生过盲法交付与交回校验，不代表仓库内存在该文件。`SW_` 数据源许可 Unknown，因此只发布聚合统计；`SK_` 的 D1 MIT / D2 Apache-2.0 允许再分发，但同样按 manifest 重建以保持仓库精简。

## 9. 发布前检查清单

- [ ] 如需 GitHub 引用卡片，在 `CITATION.cff` 补上作者名与 `repository-code`（当前为去标识化的集体作者，无占位符）
- [ ] `grep -rInE '(SESSDATA|bili_jct|Cookie:|/Users/)' .` 无真实命中；`token` / `Cookie` 命中若存在，只能是「不使用 token / Cookie」这类合规声明
- [ ] 全仓无 `*.xlsx` / `*.zip`、`handoff/`、`archive_*`、`__pycache__`、评论正文与个体级编码表
- [ ] README 与 `docs/SC_mvp.md` 的样本数一致：64 条，两区 30 / 34
- [ ] `SC_` 部分没有任何文件声称「一致性达标」「主模型已运行」；`output/SC_kappa_report.txt` 明确写的是未达标与不采用
- [ ] `Rscript R/SC_mvp.R` 输出 `11 / 11 PASS`；`Rscript R/SC_kappa.R` 仍按路径 C 输出正式报告
- [ ] `REPORT.md` 与网页的 `SK_` / `SW_` 系数、q 值与 `studies/*/output/` 结果文件一致，且标注为各自 R 脚本产出，没有被读成 `SC_` 的结果
- [ ] 仓库内链接均为相对路径，不指向本机文件；`git status` 干净，无意外大文件
- [ ] 若启用 GitHub Pages：`index.html` 已被跟踪（`!/index.html` 例外生效），页面无 CDN / 外链资源、无绝对路径
