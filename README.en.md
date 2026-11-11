# SUCCES on Bilibili · Pre-registered Measurement and Association Studies (Integrated Repository)

[中文说明](README.md) · [Web version (~3 min)](index.html) · [Integrated report](REPORT.md) · [Main study SK_](studies/SK_/) · [Follow-up SW_](studies/SW_/) · [Reproduction guide](docs/REPRODUCE.md)

> This repository collects the public code, pre-registrations and aggregate results of **three independent studies** that share one rule-based codebook and the rule "fix the measurement before looking at results".
>
> | Stage | Location | Status | Finding |
> |---|---|---|---|
> | Preceding `SC_` | repo root (`R/`, `SC_*.py`) | 64 self-collected videos; subjective semantic items dropped after two failed double-coding rounds; main model **never run** (sample too small) | **No empirical findings reported** |
> | Main `SK_` | [`studies/SK_/`](studies/SK_/) | Two licensed Kaggle datasets; pre-registered main model run | **1 / 6** supported: H3 Concrete beta = +0.0891, q = 0.0292, 95% CI [+0.0274, +0.1508]; not robust to dropping account controls, not replicated in a second domain |
> | Follow-up `SW_` | [`studies/SW_/`](studies/SW_/) | Top-liked comments, different construct level | **0 / 6**; explicit learning statements only 13 / 2,773 |
>
> Samples, sources and units of analysis differ; the studies are **not pooled and do not corroborate each other**. Associations only — no causal claim, no "SUCCES works / does not work". See the [web version](index.html) and [REPORT.md](REPORT.md).

---

## What is here / what is not

| | |
|---|---|
| ✅ Included | 64 real public video records; pre-registration with 7 logged protocol changes (A–G); codebook v0.3; reproducible dictionary/regex coding; the two-round blind double-coding decisions and audit documents; Cohen's kappa with bootstrap CIs; **11/11** pipeline self-checks; scripts, pre-registrations and aggregate outputs for `SK_` / `SW_` under `studies/` |
| ❌ Not included (`SC_`) | A fitted main model; any `SC_` effect estimate, p-value or causal claim; subtitles (0% coverage); findings that generalise beyond this sample |
| ❌ Not included (whole repo) | Comment text, row-level coded tables, double-coding handoff originals, raw dataset zips, credentials or personal data |

The `SC_` part is a documented case of *when to abandon a measurement*. For association results see [`studies/SK_/`](studies/SK_/) and [`studies/SW_/`](studies/SW_/), or the [3-minute web version](index.html).

## Research question

The **SUCCES** framework from *Made to Stick* (Heath & Heath, 2007) — Simple, Unexpected, Concrete, Credible, Emotional, Stories — proposes six features that make messages stick. This project operationalises them for Bilibili knowledge videos and asks how each dimension is associated with audience interaction, whether the associations hold after controlling for account size, and whether they differ between hard-science and general-audience content.

**H1–H6 are all directional positive and were frozen before looking at the data** ([pre-registration](docs/SC_preregistration.md)).

A deliberate design choice: the outcome is **engagement rate**, not view count. Views largely reflect algorithmic distribution; engagement rate — `(likes + coins + favorites + shares + comments) / views` — is closer to audience response, with follower count and duration controlled for.

## The core decision: Path C

| Round | Protocol | Outcome | Action |
|---|---|---|---|
| 1 | Script-filled coderA (flow demo) + a human coderB | Ambiguous boundaries, constant margins | Not imported into the main template; originals archived; codebook revised to v0.3 |
| 2 | Two human coders, each with a blind sheet, independently recoding the same 13 items under v0.3 | Formal kappa below the pre-registered target, no indicator with a CI lower bound > 0; coders drifted in opposite directions on strictness | Imported and formally reported, but judged insufficient |

**Decision: the six human semantic indicators are NOT ADOPTED** (`s1 / u3 / c3 / cr1 / st3 / e4` → `*_NOT_ADOPTED`). They enter no score, no model, and no claim. The six dimension scores use **rule-based items only**; the mixed specification is retained as `*_DIAGNOSTIC_ONLY` for coverage diagnostics. The codebook is frozen at v0.3.

> Why this matters: with n=13, another coding round would not narrow the CI. Adding labour would be an attempt to fix a calibration problem with more labelling. Dropping an unreliable measure *before* seeing any regression output is closer to research design than selecting a flattering coefficient afterwards. See [docs/SC_coding-adoption.md](docs/SC_coding-adoption.md).

⚠️ [`output/SC_kappa_report.txt`](output/SC_kappa_report.txt) is **audit evidence for the non-adoption decision**, not evidence of agreement. `SC_kappa_demo_SIMULATED.csv` exists only to verify the kappa implementation and is unrelated to any real agreement.

## Data

| Item | Value |
|---|---|
| Sample | **64** public videos: "Social Science / Law / Psychology" (`rid=124`) 30 + "Science Popularisation" (`rid=201`) 34 |
| Sampling | subzone × popularity tier × topic tier; target 120, collected 64 — the shortfall of 56 is **not** filled or widened |
| Usability flags | `view_usable` / `analysis_eligible` = 48; `rate_stable` (`view ≥ 1000`) = 41; `within_1yr` = 27 (sensitivity marker only) |
| Material | title + description (description coverage 56%); **subtitle coverage 0%**, so `u4` is `NA` rather than a fake 0 |
| Time | ranking snapshot from April 2025 (≈580 days); `day` is a ranking window, not a publication date — no recency requirement, the snapshot window is declared as a limitation |
| Source | Bilibili public endpoints only; Kaggle / Heywhale datasets were investigated and **rejected** ([record](docs/SC_alt-datasets.md)) |

**Compliance**: public video metadata only; no personal data, no comment text, no cookies/tokens/login state; rate-limited requests; risk-control responses (`-352`, `-799`) were skipped, never bypassed. Double-coding handoff originals and pre-import backups are **not distributed** (local working copies only); the repository keeps the consolidated judgements, the formal kappa report and the two round diagnostics. Paths under `handoff/` appearing in the docs are process records, not files in this repository. Coders appear only as pseudonyms (`R2`, `coderB`).

## Reproduce

Both core R scripts use **base R only** — no packages, no network:

```bash
git clone <your-repo-url> && cd <repo>

# SC_ · preceding study (base R only, no packages, no network)
Rscript R/SC_mvp.R      # rule-only coding + 11 self-checks
Rscript R/SC_kappa.R    # formal kappa + bootstrap CIs

# SK_ · main study (raw data rebuilt from manifest, not distributed)
cd studies/SK_ && python3 SK_download.py && python3 SK_prepare.py && Rscript R/SK_analyze.R

# SW_ · follow-up (comment text not distributed; see studies/SW_/docs/SW_reproduce.md)
cd ../SW_ && python3 SW_prepare.py && Rscript R/SW_analyze.R
```

Expect `11 / 11 PASS`, including an explicit check that human-coded items are outside the analysis specification. Python scripts use the standard library only; sheet export/validation additionally needs `openpyxl` and collection needs a system `curl`. Re-running collection hits live endpoints and **overwrites** the archived sample. See [docs/REPRODUCE.md](docs/REPRODUCE.md) for the full side-effect matrix.

⚠️ These are historical, **do not re-run** them or you will overwrite archived human judgements: `SC_make_coding_sheets.py`, `SC_fill_coderA.py`, `SC_export_coderB.py`, `SC_import_coderB.py`, `SC_sync_coderA_to_main.py`.

## Layout

```
README.md / README.en.md  project overview (zh / en)
index.html                self-contained web narrative (GitHub Pages entry point)
REPORT.md                 series-level integrated report (main: SK_; follow-up: SW_; preceding: SC_)
studies/SK_/              main study: scripts, pre-registration, docs, aggregate outputs
studies/SW_/              follow-up: scripts, pre-registration, docs, aggregate outputs
docs/    pre-registration · codebook · adoption decision · two coding rounds · data source · pilot/MVP logs
SC_*.py  collection · API probes · blind coding sheets · return validation (historical)
R/       SC_mvp.R / SC_kappa.R (reproducible core) · report-layer skeletons (not rendered)
data/    public video metadata (SC_ reproduction input) · consolidated coded tables
output/  self-check report · kappa report · collection report
writeup/ report.Rmd — an unrendered template with `___` placeholders, NOT a finished report
```

## Limitations

1. **Sample size**: 64 observations against roughly 140–240 needed; the main model was never run. `s_credible` and `s_stories` have sparse variation.
2. **Construct validity**: three rule items per dimension after the scope reduction; these are *text features of titles and descriptions*, not the constructs themselves. With 0% subtitle coverage, Stories is proxied by titles alone and `s4` is constant.
3. **Algorithmic endogeneity**: engagement still depends on recommendation, thumbnails and follower activity, with reverse causality (teams rewrite titles based on metrics). Associations only — no causal language.
4. **External validity**: one platform, Chinese-language context, one historical snapshot.
5. **Reliability cost**: human semantic coding failed two rounds and was excluded. This is a documented cost, not a hidden defect.

## What you may / may not claim

> The table constrains the **`SC_` preceding study**. Claim boundaries for `SK_` / `SW_` live in [`studies/SK_/SK_report.md`](studies/SK_/SK_report.md) and [`studies/SW_/SW_report.md`](studies/SW_/SW_report.md); cross-project statements must name their source.

| ✅ May state | ❌ Must not state |
|---|---|
| 64 real public videos, two locked subzones, pre-registration, codebook v0.3, two rounds of blind 20% double coding | "acceptable inter-coder agreement", or any cherry-picked kappa value as an achievement |
| The design judgement: unreliability was detected and the measure was removed in favour of reproducible rule items | `modelled each dimension against engagement rate`, `240 videos`, `cluster-robust SE` — none of these happened |
| 0% subtitles, historical ranking snapshot, 120-target shortfall, main model not run | Any `SC_` coefficient, p-value, CI, causal claim, or "SUCCES works / does not work" |
| Cross-project statements in [REPORT.md](REPORT.md), with each project attributed; coefficients are produced by each study's R script under `studies/` | Reading `SK_` / `SW_` coefficients as `SC_` output, presenting the studies as a replication or a pooled sample, or back-inferring `SC_`'s model from the follow-up |

## License

Code is [MIT](LICENSE); `studies/SK_/` and `studies/SW_/` carry their own source and licence notices. Only scripts, documentation and aggregate outputs are published: `data/raw/` holds public video metadata (including public creator identifiers) for `SC_` reproduction; comment text, row-level coded tables, raw Kaggle zips and double-coding handoff originals are not distributed and can be rebuilt from the download / collection scripts and manifests. The `SW_` source dataset has an **Unknown** licence, so only aggregate statistics are published. The SUCCES framework is from Heath & Heath, *Made to Stick* (2007), referenced solely as an object of academic analysis.
