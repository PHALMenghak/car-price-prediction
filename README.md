# 🚗 Cambodia Car Price Prediction & Market Intelligence Engine

[![CI Tests](https://github.com/PHALMenghak/car-price-prediction/actions/workflows/run_tests.yml/badge.svg)](https://github.com/PHALMenghak/car-price-prediction/actions/workflows/run_tests.yml)
[![Daily Scraper Pipeline](https://github.com/PHALMenghak/car-price-prediction/actions/workflows/daily_scraper.yml/badge.svg)](https://github.com/PHALMenghak/car-price-prediction/actions/workflows/daily_scraper.yml)
[![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Package Manager](https://img.shields.io/badge/uv-fast%20python-purple.svg)](https://github.com/astral-sh/uv)
[![dbt DuckDB](https://img.shields.io/badge/dbt--duckdb-1.11.0-orange.svg)](https://docs.getdbt.com/)
[![Test Suite](https://img.shields.io/badge/pytest-9%2F9%20passing-brightgreen.svg)](https://docs.pytest.org/)
[![dbt Tests](https://img.shields.io/badge/dbt%20tests-51%2F51%20passing-brightgreen.svg)](https://docs.getdbt.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Production-Grade ELT Lakehouse & Machine Learning Feature Store for Automotive Valuation in Cambodia**  
> An automated end-to-end data intelligence platform that captures raw market feeds from **Khmer24** (Feed API + concurrent Detail Pages), stores untouched raw snapshots in a **Bronze Layer**, executes SQL-based multilingual NLP & specification cleaning in a **Silver Layer (dbt + DuckDB)**, and models analytics & training matrices in a **Gold Star Schema & ML Feature Store**.

---

## 📌 Table of Contents

- [Executive Summary](#-executive-summary)
- [System Architecture](#-system-architecture)
- [Medallion Lakehouse Architecture](#-medallion-lakehouse-architecture)
  - [Bronze Layer (Untouched Raw Storage)](#-bronze-layer-raw-ingestion)
  - [Silver Layer (Cleaned & Conformed)](#-silver-layer-conformed--cleaned)
  - [Gold Layer (Star Schema & ML Feature Store)](#-gold-layer-star-schema--ml-feature-store)
- [Multilingual NLP & SQL Transformation Macros](#-multilingual-nlp--sql-transformation-macros)
- [Repository Structure](#-repository-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Configuration](#environment-configuration)
- [Pipeline Execution](#-pipeline-execution)
  - [1. Full End-to-End ELT Execution](#1-full-end-to-end-elt-execution)
  - [2. Individual Ingestion (Extract & Load)](#2-individual-ingestion-extract--load)
  - [3. Running dbt Transformations (DuckDB)](#3-running-dbt-transformations-duckdb)
  - [4. Running Verification Tests](#4-running-verification-tests)
- [CI/CD & Cloud Infrastructure](#-cicd--cloud-infrastructure)
- [Project Roadmap](#-project-roadmap)
- [Author & Internship Info](#-author--internship-info)

---

## 🌟 Executive Summary

Cambodia’s automotive secondary market is fast-growing but characterized by:
1. **High Pricing Asymmetry**: Unstandardized dealer vs. private seller asking prices.
2. **Multilingual & Unstructured Listings**: Free-text titles mixing Khmer (`ឡានលក់ Prius 07`), Chinese (`腾势D9`, `全新GN8`), and local colloquialisms (`ស្រីម៉ៅ` $\rightarrow$ Lexus RX300).
3. **Spec Omission**: Key pricing drivers (mileage, engine cc, fuel type, tax registration) are scattered across unstructured titles and detail descriptions.

This project delivers a scalable **Extract-Load-Transform (ELT)** architecture that **ingests 100% raw data without premature loss**, transforms it into an analytical **Star Schema**, and materializes a governed **ML Feature Store** for predictive price valuation models.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph 1. Python Bronze Ingestion (Raw & Untouched)
        A[Khmer24 Feed API] --> B[Khmer24Client]
        C[Detail API & Nuxt HTML] -->|ThreadPoolExecutor Concurrent| B
        B -->|Zero-Loss Ingestion| D[(data/bronze/cars_YYYY-MM-DD.parquet)]
    end

    subgraph 2. dbt DuckDB Transformations (Silver)
        D --> E[stg_khmer24_cars\nSnapshot Deduplication & Time-Series Dynamics]
        E --> F[int_cars_cleaned\nSQL Regex Cleaning, Translations & Sanity Bounds]
        F --> G[(data/silver/cars_cleaned.parquet)]
    end

    subgraph 3. Gold Serving (Star Schema & ML Feature Store)
        F --> H[dim_car_model]
        F --> I[dim_location]
        F --> J[dim_seller]
        F --> K[dim_powertrain]
        H & I & J & K --> L[fct_car_listings]
        F --> M[fct_cars_ml_features]

        H --> N[(data/gold/dim_car_model.parquet)]
        I --> O[(data/gold/dim_location.parquet)]
        J --> P[(data/gold/dim_seller.parquet)]
        K --> Q[(data/gold/dim_powertrain.parquet)]
        L --> R[(data/gold/fct_car_listings.parquet)]
        M --> S[(data/gold/fct_cars_ml_features.parquet)]
    end
```

---

## 💎 Medallion Lakehouse Architecture

### 🥉 Bronze Layer (Raw Ingestion)
* **Path**: `data/bronze/cars_YYYY-MM-DD.parquet`
* **Zero-Loss Guarantee**: Captures all untouched raw fields (`raw_title`, `raw_price`, `raw_spec_*`, `raw_description`, `raw_feed_payload`, `raw_detail_payload`).
* **Concurrency**: Scrapes feed listings and pulls full detail specifications concurrently across threads (`ThreadPoolExecutor`) without static detail caching.

### 🥈 Silver Layer (Conformed & Cleaned)
* **Path**: `data/silver/cars_cleaned.parquet`
* **Model**: [`dbt/models/intermediate/int_cars_cleaned.sql`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/models/intermediate/int_cars_cleaned.sql)
* **Time-Series Tracking**: Computes longitudinal signals across snapshot dates (`days_on_market`, `initial_price`, `price_drop_amount`, `has_price_drop`, `view_velocity`).
* **Deterministic Cleaning**: Standardizes vehicle brands, canonical models, Khmer/English color names, fuel types, and transmissions.
* **Sanity Bounds**: Enforces realistic automotive constraints ($500 \le \text{price} \le \$300,000$, $1990 \le \text{year} \le \text{current\_year} + 1$).

### 🥇 Gold Layer (Star Schema & ML Feature Store)
* **Path**: `data/gold/`
* **Star Schema Dimensions & Fact Table**:
  * [`dim_car_model.parquet`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/models/marts/core/dim_car_model.sql): Make, canonical model, body type, and market segment (`Luxury`, `Mass_Market`, `Chinese_EV`).
  * [`dim_location.parquet`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/models/marts/core/dim_location.sql): Province, district, and market liquidity tier (`Tier_1` = Phnom Penh).
  * [`dim_seller.parquet`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/models/marts/core/dim_seller.sql): Seller ID, store vs. individual tiering, and contact info.
  * [`dim_powertrain.parquet`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/models/marts/core/dim_powertrain.sql): Fuel classification, gearbox transmission, and engine cc.
  * [`fct_car_listings.parquet`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/models/marts/core/fct_car_listings.sql): Central fact table with surrogate MD5 foreign keys and core transaction measures.
* **ML Feature Store Table**:
  * [`fct_cars_ml_features.parquet`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/models/marts/ml/fct_cars_ml_features.sql): Implements window-function hierarchical median imputations (`Year/Brand median` $\to$ `Global median`), log-target scaling ($\ln(1 + \text{price})$), registration status (`is_plate_number`), and NLP option flags (`has_full_option`, `is_urgent_sale`).

---

## 🗣️ Multilingual NLP & SQL Transformation Macros

All regex, entity parsing, and domain translations have been ported directly into reusable **dbt SQL macros**:

| Macro File | Key Capabilities |
| :--- | :--- |
| [`brand_model_macro.sql`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/macros/brand_model_macro.sql) | Resolves vehicle brand aliases (Khmer `តូយ៉ូតា`, Chinese `腾势`, English) and infers canonical models. |
| [`brand_tier_macro.sql`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/macros/brand_tier_macro.sql) | Categorizes brands into `Luxury`, `Mass_Market`, `Chinese_EV`, and `Other`. |
| [`clean_specs_macro.sql`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/macros/clean_specs_macro.sql) | Normalizes multilingual colors, fuel types (Petrol, Diesel, Hybrid, Electric, LPG), transmissions, and numeric units (km, cc). |
| [`nlp_options_macro.sql`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/macros/nlp_options_macro.sql) | Extracts binary feature signals from free-text listing titles (e.g. `has_full_option`, `is_urgent_sale`). |

---

## 📂 Repository Structure

```
Car_price_prediction/
├── .github/
│   └── workflows/
│       ├── daily_scraper.yml      # Automated daily scraping & git-push at 09:00 AM ICT
│       └── run_tests.yml          # Automated CI pytest & dbt verification on push and PR
├── cloudflare/
│   └── worker.js                  # Cloudflare Worker relay script (IP unblocking bridge)
│
├── data/
│   ├── bronze/                    # Untouched raw Parquet snapshots (cars_YYYY-MM-DD.parquet)
│   ├── silver/                    # Conformed cleaned dataset (cars_cleaned.parquet, cars_cleaned.csv)
│   ├── gold/                      # Star Schema tables & ML Feature Store (dim_*, fct_*)
│   └── duckdb/                    # Local DuckDB analytical warehouse (khmer24.duckdb)
│
├── dbt/                           # Data Build Tool Transformation Layer
│   ├── dbt_project.yml            # Medallion materialization configs
│   ├── profiles.yml               # DuckDB connection profile
│   ├── packages.yml               # dbt-utils dependency
│   ├── macros/                    # Modular SQL parsing & cleaning macros
│   ├── models/
│   │   ├── staging/               # Bronze view & longitudinal signals
│   │   ├── intermediate/          # Silver conformed view & data contracts
│   │   └── marts/
│   │       ├── core/              # Gold Star Schema dimensions & fact table
│   │       └── ml/                # Gold ML training matrix
│   └── tests/                     # Custom singular price sanity SQL tests
│
├── pipeline/                      # Orchestration & Execution Pipelines
│   ├── extract_load.py            # Bronze extraction & quality logging
│   ├── backfill_details.py        # Detail backfill & enrichment runner
│   └── dbt_runner.py              # Programmatic dbt DuckDB orchestrator
│
├── src/                           # Shared Ingestion Modules
│   ├── client.py                  # TLS-impersonated HTTP client + Nuxt HTML fallback
│   ├── schemas.py                 # Structured RawCarListing Pydantic schema
│   ├── storage.py                 # Parquet / CSV I/O, manifests & historical tracking
│   └── config.py                  # Central paths & project configuration
│
├── notebooks/                     # Exploratory Data Analysis & Modeling
│   ├── 01_data_understanding.ipynb
│   ├── 02_eda_exploration.ipynb
│   └── 04_model_training.ipynb
│
├── tests/                         # Pytest Verification Suite
│   ├── test_backfill.py
│   ├── test_client.py
│   ├── test_pipeline.py
│   └── test_storage.py
│
├── pyproject.toml                 # Single source of truth for Python dependencies
└── uv.lock                        # Deterministic package lockfile
```

---

## 🚀 Getting Started

### Prerequisites
* **Python 3.11+** installed
* **[uv](https://github.com/astral-sh/uv)** installed (Ultra-fast Python package installer & resolver)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/PHALMenghak/car-price-prediction.git
cd car-price-prediction

# 2. Create virtual environment and install dependencies
uv sync
```

### Environment Configuration

Create a `.env` file in the root directory:

```ini
KHMER24_DEVICE_ID=ds-intern-device-f4b8c10a
TARGET_CATEGORY=cars-for-sale
TARGET_PROVINCE=
MAX_PAGES=20
PYTHONUTF8=1

# Optional: Cloudflare Worker relay for GitHub Actions or restricted environments
POSTS_API_BASE=https://car-price-scraper.<your-worker>.workers.dev/
RELAY_KEY=your_secret_relay_key
ENRICH_DETAILS=true
```

---

## ⚡ Pipeline Execution

### 1. Full End-to-End ELT Execution
Scrapes listings, enriches details, persists to Bronze, and triggers dbt transformations & tests:

```bash
uv run python main.py --max-pages 20 --enrich-details --transform --dbt-test
```

### 2. Individual Ingestion (Extract & Load)
Scrapes active vehicle listings and writes raw Parquet files to `data/bronze/`:

```bash
uv run python main.py --max-pages 20 --enrich-details
```

### 3. Running dbt Transformations (DuckDB)
Executes Bronze $\rightarrow$ Silver $\rightarrow$ Gold data transformations and exports Parquet/CSV artifacts:

```bash
# Run all models
uv run python pipeline/dbt_runner.py run

# Run all 51 data quality contract tests
uv run python pipeline/dbt_runner.py test

# Run build (run + test)
uv run python pipeline/dbt_runner.py all
```

### 4. Running Verification Tests
Execute the Pytest test suite:

```bash
uv run pytest tests/ -v --tb=short
```

---

## ☁️ CI/CD & Cloud Infrastructure

### 🔄 GitHub Actions Daily Scraper ([`daily_scraper.yml`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/.github/workflows/daily_scraper.yml))
* **Schedule**: Triggers daily at `02:00 UTC` (`09:00 AM ICT`).
* **Workflow**: Sets up Python 3.11 with `uv`, connects via Cloudflare Worker relay, executes end-to-end ELT, and commits new Bronze snapshots and Gold feature matrices back to GitHub.

### 🛡️ Cloudflare Worker Relay ([`cloudflare/worker.js`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/cloudflare/worker.js))
* Routes API requests securely through an edge Worker proxy with `X-Relay-Key` authentication to bypass Cloudflare Bot Protection on CI cloud runner IP ranges.

---

## 🗺️ Project Roadmap

| Phase | Milestone | Status |
| :--- | :--- | :--- |
| **Phase 1** | Automated Zero-Loss Raw Ingestion (Bronze Layer) & Daily CI/CD | ✅ **Completed** |
| **Phase 2** | dbt & DuckDB Medallion Transformation (Silver & Gold Star Schema) | ✅ **Completed** |
| **Phase 3** | Data Quality Governance (51 dbt Data Contract Tests) | ✅ **Completed** |
| **Phase 4** | Exploratory Data Analysis & Market Segmentation Insights | 🔄 **In Progress** |
| **Phase 5** | High-Precision ML Valuation Models (LightGBM, XGBoost, CatBoost) | 🔲 **Next Up** |
| **Phase 6** | Model Interpretability & Pricing Drivers (SHAP Values) | 🔲 Planned |
| **Phase 7** | Real-Time FastAPI Valuation Service (`/predict`) | 🔲 Planned |
| **Phase 8** | Interactive Market Dashboard (Streamlit / Next.js) | 🔲 Planned |

---

## 👤 Author & Internship Info

* **Author**: **Phal Menghak**
* **Institution**: **Institute of Technology of Cambodia (ITC)**
* **Department**: Applied Mathematics and Statistics (AMS) — Year 4
* **Role**: Data Science & Machine Learning Engineer Intern
* **GitHub**: [@PHALMenghak](https://github.com/PHALMenghak)

---

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
