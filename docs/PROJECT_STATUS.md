# 🚗 Cambodia Car Price Prediction — Project Status Report

> **Project**: Cambodia Used Car Price Prediction & Market Intelligence  
> **Student**: Phal Menghak  
> **Institution**: Institute of Technology of Cambodia (ITC) — Department of Applied Mathematics and Statistics (AMS)  
> **Role**: Data Scientist & Machine Learning Engineer Intern  
> **Last Updated**: September 2, 2026  
> **Test Status**: [![Pytest](https://img.shields.io/badge/pytest-9%2F9%20passing-brightgreen.svg)](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/tests) [![dbt Tests](https://img.shields.io/badge/dbt%20tests-51%2F51%20passing-brightgreen.svg)](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt)  
> **Current Stage**: **Phase 4 in Progress** (Phases 1, 2, and 3 fully completed and operational)

---

## 📑 Table of Contents
1. [Milestone Progress Summary](#1-milestone-progress-summary)
2. [What We Have Built & Completed](#2-what-we-have-built--completed)
3. [Current Dataset & Quality Metrics](#3-current-dataset--quality-metrics)
4. [Next Steps (Phase 4 & Phase 5)](#4-next-steps-phase-4--phase-5)

---

## 1. Milestone Progress Summary

| Phase | Description | Status |
| :--- | :--- | :--- |
| **Phase 1: Ingestion & Storage** | TLS-spoofed HTTP scraper, concurrent detail extraction, daily Bronze Parquet files. | ✅ **Completed** |
| **Phase 2: Cleaning & Translations** | dbt DuckDB SQL macros for multilingual brand/model extraction, color/fuel/transmission cleaning. | ✅ **Completed** |
| **Phase 3: Medallion Architecture** | Silver conformed layer, Gold Star Schema (`dim_*`, `fct_*`), and 51 automated quality tests. | ✅ **Completed** |
| **Phase 4: EDA & Market Insights** | Exploratory data analysis, depreciation curves, and market liquidity segmentation. | 🔄 **In Progress** |
| **Phase 5: ML Valuation Models** | Baseline and ensemble models (LightGBM, XGBoost, CatBoost, Random Forest). | 🔲 **Next Up** |
| **Phase 6: Model Explainability** | SHAP values, feature importance, and pricing driver analysis. | 🔲 Planned |
| **Phase 7: Real-Time Valuation API** | FastAPI REST endpoint for instant car valuation (`/predict`). | 🔲 Planned |
| **Phase 8: Web Dashboard** | Interactive user interface (Streamlit / Next.js). | 🔲 Planned |

---

## 2. What We Have Built & Completed

### A. Raw Data Ingestion (Bronze Layer)
* **High-Speed Scraper**: Uses `curl-cffi` to mimic browser TLS fingerprints, preventing Cloudflare blocks.
* **Concurrent Detail Extraction**: Scrapes full specifications across 4 threads without static cache dependencies.
* **Storage**: Saves daily compressed Parquet snapshots to `data/bronze/cars_YYYY-MM-DD.parquet` and full review CSV to `data/bronze/khmer24_cars.csv`.

### B. SQL Transformations (Silver Layer)
* **Deduplication**: Resolves multi-day snapshots, keeping the newest record while tracking historical initial price and days on market.
* **Multilingual Macros**: Reusable dbt SQL macros parse Khmer, Chinese, and English listing text.
* **Sanity Bounds**: Removes price errors ($<\$500$ or $>\$300,000$) and invalid years ($<1990$).

### C. Star Schema & Feature Store (Gold Layer)
* **Star Schema**: Built 4 Dimension tables (`dim_car_model`, `dim_location`, `dim_seller`, `dim_powertrain`) and 1 central Fact table (`fct_car_listings`).
* **ML Feature Store**: Hierarchical median imputations for mileage and engine cc, log-transformed target $\ln(1 + \text{price})$, and 51 automated data tests.

---

## 3. Current Dataset & Quality Metrics

* **Total Daily Snapshots Collected**: 16 daily runs (August 17 – September 2, 2026).
* **Cumulative Marketplace Listings Tracked**: Over 7,000 car records.
* **Data Test Success Rate**: 100% (51 of 51 dbt tests passing).
* **Python Test Suite**: 100% (9 of 9 unit tests passing).

---

## 4. Next Steps (Phase 4 & Phase 5)

1. **Phase 4: Exploratory Data Analysis (Notebooks 02 & 03)**:
   * Analyze price depreciation by car model and vehicle age.
   * Compare asking price differences between Phnom Penh and regional provinces.
   * Evaluate the market premium for registered plate numbers vs. tax paper cars.
2. **Phase 5: Machine Learning Model Training (Notebook 04)**:
   * Train regression models on `data/gold/fct_cars_ml_features.parquet`.
   * Compare LightGBM, XGBoost, CatBoost, and Random Forest using 5-fold cross-validation.
   * Evaluate Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) in USD.
