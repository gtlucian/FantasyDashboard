# 🏈 FantasyPros 3-Hour Draft Intelligence Pipeline & BI Dashboard

A **100% Free, Zero-Cost Data Engineering & BI Platform** for Fantasy Football draft preparation and live draft decision-support, powered by the **FantasyPros Model Context Protocol (MCP)** server, **DuckDB** in-process OLAP engine, and **Streamlit / Web UI**.

---

## ⚡ Key Highlights
* **Zero Subscription Costs**: $0 database fees, $0 cloud hosting fees, $0 API costs.
* **3-Hour Automated Sync**: Captures training camp reports, depth chart updates, and ADP momentum shifts every 3 hours.
* **Smart Analytics**:
  * **Dynamic VORP (Value Over Replacement Player)**: Dynamically calibrated to your league size (8, 10, 12, 14, 16) and format (1-QB, Superflex).
  * **Market Arbitrage Index**: $\text{ADP} - \text{ECR}$ (Instantly flags draft steals vs. overdrafted traps).
  * **Positional Scarcity & Tier Drop-off Alerts**: Warns when the next best player at a position drops off steeply.
* **Dual Serving Mode**:
  1. **Interactive Streamlit BI Dashboard** (Live draft cross-off mode, dynamic formulas).
  2. **Zero-Dependency Offline HTML Sheet** (`index.html`) (Opens anywhere on laptops/tablets with zero internet required).

---

## 🏗️ Architecture & Data Flow

```
 [FantasyPros MCP Endpoint] (https://api.fantasypros.com/mcp)
            │
            ▼ (Every 3 Hours via GitHub Actions / Local Cron)
 ┌────────────────────────────────────────────────────────┐
 │ 1. Ingestion (`pipeline.py`)                           │
 │    - Ingests ECR, ADP, Projections, Injuries           │
 └──────────────────────────┬─────────────────────────────┘
                            │
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ 2. Atomic Staging & DuckDB (`draft_vault.duckdb`)      │
 │    - Writes to staging -> Atomic OS swap               │
 │    - Multi-layer schema (Bronze -> Silver -> Gold)     │
 └──────────────────────────┬─────────────────────────────┘
                            │
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ 3. Analytical Calculations (Gold Layer SQL)            │
 │    - VORP, Arbitrage Delta, Tier Drop-off Cliffs       │
 └──────────────────────────┬─────────────────────────────┘
                            │
                            ▼
 ┌────────────────────────────────────────────────────────┐
 │ 4. Dual Serving Layer                                  │
 │    ├── Streamlit Dashboard (`streamlit run dashboard.py│
 │    └── Offline Browser View (`index.html`)             │
 └────────────────────────────────────────────────────────┘
```

---

## 📖 Data Dictionary

### Table: `gold_draft_board`
| Column | Type | Description |
| :--- | :--- | :--- |
| `player_id` | `VARCHAR` | Unique player identifier |
| `player_name` | `VARCHAR` | Player's full name |
| `position` | `VARCHAR` | Primary fantasy position (`QB`, `RB`, `WR`, `TE`, `DST`, `K`) |
| `pos_rank` | `INT` | Positional rank by projected points |
| `team` | `VARCHAR` | NFL team abbreviation |
| `bye_week` | `INT` | NFL Bye week |
| `current_injury_status` | `VARCHAR` | Injury designation (`Healthy`, `Questionable`, `PUP`, `IR`) |
| `ecr_rank` | `INT` | Expert Consensus Rank |
| `adp_rank` | `DOUBLE` | Average Draft Position across platforms |
| `arbitrage_delta` | `DOUBLE` | $\text{ADP} - \text{ECR}$ (Positive = Sleeper Target, Negative = Overvalued) |
| `projected_fantasy_points` | `DOUBLE` | Total season projected fantasy points |
| `vorp` | `DOUBLE` | Value Over Replacement Player vs. positional baseline |
| `tier` | `INT` | Positional expert consensus tier |
| `expert_volatility` | `DOUBLE` | Standard deviation among expert rankings (risk index) |
| `latest_insight` | `TEXT` | Practice note, camp report, or depth chart update |
| `last_updated` | `VARCHAR` | Timestamp of latest 3-hour refresh cycle |

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Ingestion & Transformation Pipeline
```bash
python3 pipeline.py
```
*Outputs: `draft_vault.duckdb` and `draft_data.json`*

### 3. Launch the Interactive BI Dashboard
```bash
streamlit run dashboard.py
```

### 4. Or Open the Standalone Web Sheet
Simply open `index.html` in Safari, Chrome, or Firefox.

---

## ⏰ Automated Scheduling

### Option A: Free GitHub Actions (Recommended)
Push this repository to GitHub. The workflow in [`.github/workflows/fantasy_refresh_3h.yml`](.github/workflows/fantasy_refresh_3h.yml) will automatically run every 3 hours (`0 */3 * * *`) and commit updated snapshots for free.

### Option B: Local Mac Cron
```bash
crontab -e
# Add:
0 */3 * * * /usr/bin/python3 /Users/kareemgoddard/Documents/FprosMCPTest/pipeline.py
```
