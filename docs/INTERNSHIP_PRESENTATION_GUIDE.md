# 🎓 Internship Project Presentation & Technical Guide

> **Project**: Cambodia Used Car Price Prediction & Market Intelligence Engine  
> **Student**: Phal Menghak  
> **Institution**: Institute of Technology of Cambodia (ITC)  
> **Department**: Applied Mathematics and Statistics (AMS) — Year 4 Internship  

---

## 🎯 Project Overview at a Glance

This project builds an automated end-to-end Machine Learning and Data Engineering platform for second-hand vehicle valuation in Cambodia.

```
   Raw Scraping (Bronze)          dbt SQL Cleaning (Silver)          Star Schema & ML Matrix (Gold)
┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────────────┐
│ • Khmer24 Feed API      │ ───► │ • Deduplicate snapshots │ ───► │ • Star Schema (dim_*, fct_*)    │
│ • Concurrent details    │      │ • SQL regex translation │      │ • Hierarchical median impute    │
│ • Zero raw data loss    │      │ • Sanity bounds filters │      │ • Log-price regression target   │
└─────────────────────────┘      └─────────────────────────┘      └─────────────────────────────────┘
```

---

## 📽️ Recommended Slide-by-Slide Defense Presentation

### Slide 1: Title & Introduction
* **Title**: Automotive Price Intelligence & Machine Learning Valuation Engine for Cambodia
* **Presenter**: Phal Menghak (Year 4 AMS Intern)
* **Key Message**: Transforming unstructured online car ads into accurate, real-time market valuations.

### Slide 2: The Problem in Cambodia's Car Market
1. **Price Uncertainty**: Large differences between dealer asking prices and private seller prices.
2. **Multilingual Listings**: Titles mix Khmer (`ឡានលក់ Prius 07`), Chinese (`腾势D9`), and English nicknames (`ស្រីម៉ៅ` = Lexus RX300).
3. **Missing Specs**: Odometer and engine size are frequently missing or buried in free-text descriptions.

### Slide 3: Solution & System Architecture
* **Extract-Load-Transform (ELT)**:
  * **Bronze Layer**: Python scraper collects raw posts without altering data.
  * **Silver Layer**: dbt + DuckDB cleans and standardizes text using reusable SQL regex macros.
  * **Gold Layer**: Star Schema for business analysis + ML Feature Store for valuation models.

### Slide 4: Data Pipeline & Anti-Bot Protection
* **Fast HTTP Scraping**: Uses `curl-cffi` to mimic browser TLS fingerprints, preventing Cloudflare blocks.
* **Concurrent Detail Extraction**: Pulls full specifications across 4 threads without blocking.
* **Daily Snapshots**: Stored as compressed Parquet files in `data/bronze/`.

### Slide 5: Data Transformation (dbt + DuckDB)
* **Why dbt?**: Transforms data with version-controlled SQL, automated lineage (DAG), and 51 automated quality tests.
* **Multilingual Macros**:
  * `brand_model_macro.sql`: Extracts make and model from Khmer/English text.
  * `clean_specs_macro.sql`: Translates colors, fuels (Petrol, Diesel, Hybrid, Electric, LPG), and transmissions.

### Slide 6: Gold Star Schema
* **Central Fact Table (`fct_car_listings`)**: Measures prices, price drops, days on market, and view velocity.
* **Dimension Tables**: `dim_car_model`, `dim_location`, `dim_seller`, `dim_powertrain`.
* **Business Value**: Allows instant slicing of the market by brand segment (Luxury vs Mass Market) or region (Phnom Penh vs provinces).

### Slide 7: Machine Learning Feature Store
* **Target**: $\ln(1 + \text{price})$ for symmetrical error handling.
* **Smart Imputation**: Fills missing numbers using specific Brand/Model medians with binary indicator flags.
* **Models Tested**: LightGBM, XGBoost, Random Forest, Ridge Regression.

### Slide 8: Results & Next Steps
* **Completed**: Full automated daily scraping, dbt transformations, 51 automated data tests, and Star Schema.
* **Next Steps**: Train production gradient boosting models, compute feature importance (SHAP), and build a valuation web interface.

---

## ❓ Common Defense Questions & How to Answer

**Q1: Why use an ELT approach instead of cleaning data inside Python?**  
*Answer*: In traditional ETL, if your Python regex makes a mistake, the raw data is lost forever. In ELT, we store 100% of the raw data in Bronze. If we improve our cleaning rules later, we can re-run dbt transformations over all historical data in seconds without re-scraping.

**Q2: Why use DuckDB instead of pandas for transformations?**  
*Answer*: DuckDB runs SQL directly on compressed Parquet files with multi-threading and low memory usage. It executes complex window functions (like deduplication and median imputations) much faster and with strict data type safety.

**Q3: How do you handle listings with missing mileage or engine displacement?**  
*Answer*: We use hierarchical window median imputation in SQL (taking the median of that specific car model, falling back to brand median). We also add a binary flag `is_mileage_missing = 1` so tree models understand that the value was imputed.
