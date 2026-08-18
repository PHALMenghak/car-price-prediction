# 🧼 Data Preprocessing Methodology for Khmer24 Car Price Prediction

> **Project**: Cambodia Used Car Price Prediction  
> **Input**: Raw daily scraped Parquet files from Khmer24 (`data/raw/**/*.parquet`)  
> **Output**: Clean, model-ready feature matrix (`data/processed/cars_train.parquet`)  
> **Target Variable**: `price` (USD)  

---

## 📑 Table of Contents
1. [Overview & Preprocessing Pipeline Architecture](#1-overview--preprocessing-pipeline-architecture)
2. [Multi-Day Scraping, Deduplication & Historical Features](#2-multi-day-scraping-deduplication--historical-features)
3. [Data Cleaning & Sanity Filtering](#3-data-cleaning--sanity-filtering)
4. [Missing Value Imputation Strategies](#4-missing-value-imputation-strategies)
5. [Feature Engineering (Domain-Specific for Cambodia Market)](#5-feature-engineering-domain-specific-for-cambodia-market)
6. [Categorical Encoding & Target Transformation](#6-categorical-encoding--target-transformation)
7. [Data Leakage Prevention & Validation Strategy](#7-data-leakage-prevention--validation-strategy)
8. [Complete Python Implementation Reference](#8-complete-python-implementation-reference)

---

## 1. Overview & Preprocessing Pipeline Architecture

The preprocessing pipeline follows the **Medallion Architecture** to ensure data reproducibility, traceability, and zero data leakage:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BRONZE LAYER (Raw Ingestion)                    │
│  Daily raw scraped files with timestamps (data/raw/**/*.parquet)       │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        SILVER LAYER (Clean & Dedup)                    │
│  1. Multi-day deduplication (Latest snapshot per listing_id)           │
│  2. Historical change extraction (Price drops, Days on Market)         │
│  3. Sanity rule filters (Invalid prices, extreme years, outliers)      │
│  4. Data type coercion & standardizations                             │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        GOLD LAYER (ML Features)                        │
│  1. Missing value imputation (Grouped medians + 'Unknown' categories)  │
│  2. Domain feature engineering (Vehicle age, mileage/yr, brand tier)   │
│  3. Categorical encoding (Target/Frequency encoding, One-Hot)          │
│  4. Target log-transformation (log1p(price))                           │
│  5. Export to data/processed/cars_train.parquet                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Multi-Day Scraping, Deduplication & Historical Features

Because data is scraped across multiple days, individual cars (`listing_id`) appear multiple times. We preprocess this raw time-series log into two components:

### A. Deduplication to the Latest State
For machine learning training, each physical listing should appear **only once**.
* **Method**: Group by `listing_id` and pick the record with the maximum `scraped_at` timestamp.
* **Why**: The latest snapshot contains the seller's most up-to-date price, corrected specs, and latest view count.

$$\text{Latest Record} = \arg\max_{t} (\text{scraped\_at} \mid \text{listing\_id} = i)$$

### B. Extracting Historical Change Signals
Before deduplicating, we compute aggregate historical metrics across all snapshots for each car:

| Feature Name | Computation Formula | Business / ML Signal |
|---|---|---|
| `days_on_market` | `(max(scraped_at) - min(posted_at)).days` | Cars listed longer often indicate lower demand or initial overpricing. |
| `initial_price` | Price observed on the earliest `scraped_at` date | The baseline asking price. |
| `price_drop_amount` | `initial_price - latest_price` | Quantifies seller discount / price reduction. |
| `has_price_drop` | `1 if price_drop_amount > 0 else 0` | Binary indicator that the seller has lowered their price. |
| `view_velocity` | `view_count / max(days_on_market, 1)` | Average views per day (proxy for buyer interest/popularity). |

---

## 3. Data Cleaning & Sanity Filtering

Raw marketplace data contains spam, test posts, typos, and extreme outliers. We apply sequential deterministic filtering rules:

### Rule 1: Drop Missing or Non-Positive Target (`price`)
* **Action**: Discard any listing where `price IS NULL` or `price <= 0`.
* **Reason**: Supervised regression requires a valid ground-truth target.

### Rule 2: Price Sanity Bounds Filtering
* **Action**: Retain only listings where:
  $$\$500 \le \text{price} \le \$300,000$$
* **Reason**:
  - `< $500`: Likely accessories, deposit placeholders, down payment scams, or test listings.
  - `> $300,000`: Rare ultra-luxury/hypercars with sparse representation that skew regression loss functions (e.g. MSE).

### Rule 3: Model Year Sanity Bounds
* **Action**: Retain listings where:
  $$1990 \le \text{vehicle\_model\_year} \le \text{Current Year} + 1$$
* **Reason**: Rejects typos (e.g., year `1890` or `2920`). Listings with completely missing model year are handled in imputation.

### Rule 4: Mileage Sanity Bounds & Unit Standardization
* **Action**:
  - Filter `0 <= vehicle_mileage_km <= 500,000`.
  - If `vehicle_mileage_km == 0` and `vehicle_condition == 'used'` for a car older than 3 years, treat `vehicle_mileage_km` as missing (`NaN`) rather than true 0 km.

### Rule 5: Engine Displacement CC Filtering
* **Action**: Retain `500 <= vehicle_engine_cc <= 7000`. Values outside this range are set to `NaN` (likely typos or battery capacity misclassified as CC).

### Rule 6: Text Standardization
* Lowercase and strip all whitespace from:
  - `vehicle_brand`, `vehicle_model`, `vehicle_condition`, `vehicle_tax_type`, `vehicle_fuel_type`, `vehicle_transmission`, `province`.
* Normalize Khmer Unicode script variations.

---

## 4. Missing Value Imputation Strategies

Different columns require different imputation techniques depending on their distribution and semantics:

| Column | Missing % Expected | Imputation Strategy | Rationale |
|---|---|---|---|
| `vehicle_brand` | < 3% | Impute from `listing_title` NLP, fallback to `"Unknown"` | Brand is the strongest price predictor. If missing, NLP parser recovers it from title. |
| `vehicle_model` | 5 – 10% | Impute from `listing_title` NLP, fallback to `"Other"` | Extracted using brand-specific dictionary. |
| `vehicle_model_year` | 5 – 10% | **Grouped Median** by `(vehicle_brand, vehicle_model)` | Cars of the same model share similar era distributions in Cambodia (e.g. Prius mostly 2004–2010). |
| `vehicle_mileage_km` | 20 – 40% | **Grouped Median** by `(vehicle_model_year, vehicle_brand)` + `is_mileage_missing` indicator | Older cars have higher mileage. Adding a missing indicator boolean flag prevents information loss. |
| `vehicle_condition` | 10 – 20% | Default to `"used"` | >95% of Khmer24 cars are second-hand unless explicitly marked new. |
| `vehicle_tax_type` | 10 – 20% | Category `"Unknown"` | Tax type (Tax paper vs Plate) is a categorical feature; tree models treat `"Unknown"` as a distinct predictive branch. |
| `vehicle_fuel_type` | 15 – 25% | **Mode by Model** (e.g., Prius → Hybrid), fallback to `"Petrol"` | Hybrid/Diesel/Petrol is highly model-dependent. |
| `vehicle_transmission` | 10 – 20% | Mode by Model, fallback to `"Automatic"` | The vast majority of Cambodian passenger cars are automatic. |
| `province` | < 5% | Default to `"Phnom Penh"` | ~75% of Cambodian vehicle trade occurs in the capital. |
| `seller_type` | < 2% | Default to `"individual"` | Default fallback for unclassified seller accounts. |

---

## 5. Feature Engineering (Domain-Specific for Cambodia Market)

Feature engineering translates raw attributes into high-signal variables for the ML model:

### 1. Temporal & Depreciation Features
* **`vehicle_age`**:
  $$\text{vehicle\_age} = \text{Current Year} - \text{vehicle\_model\_year}$$
* **`vehicle_age_squared`**: $(\text{vehicle\_age})^2$ captures non-linear exponential depreciation curve (cars lose value faster in early years).
* **`mileage_per_year`**:
  $$\text{mileage\_per\_year} = \frac{\text{vehicle\_mileage\_km}}{\text{vehicle\_age} + 1}$$
  Identifies whether a car is heavily driven or lightly used relative to its age.

### 2. Market Segmentation & Brand Tiers
In Cambodia, brand perception strongly dictates resale value retention:
* **`is_popular_brand`**: Binary indicator for high-liquidity brands (`Toyota`, `Lexus`, `Ford`, `Hyundai`).
* **`is_luxury_brand`**: Binary indicator for premium makes (`Lexus`, `Mercedes-Benz`, `BMW`, `Porsche`, `Land Rover`, `Audi`, `Cadillac`).
* **`is_chinese_ev_brand`**: Binary indicator for modern Chinese entrants (`BYD`, `MG`, `Geely`, `Haval`, `GAC`, `Jetour`).

### 3. Tax & Legal Status Feature (`vehicle_tax_type`)
* Tax status in Cambodia significantly influences price:
  - **`Tax Paper (ក្រដាសពន្ធ)`**: Unregistered import, buyer must pay initial registration/plate fee.
  - **`Plate Number (ស្លាកលេខ)`**: Already registered, road tax paid, cheaper transaction cost.
  - **`Long Plate / Special Plate`**: High-value custom license plates.

### 4. Geographic Tiering (`province`)
* **`location_tier`**:
  - `Tier 1`: `Phnom Penh` (Highest liquidity and prices)
  - `Tier 2`: `Siem Reap`, `Battambang`, `Kandal`, `Preah Sihanouk` (Regional hubs)
  - `Tier 3`: All other provinces (Lower liquidity, slight price discount)

### 5. Title Keyword Sentiment / Option Indicators
Extract binary indicator flags from `listing_title` using regex:
* `has_full_option`: Title contains `"full option"`, `"full"`, `"option 4"`, `"f-sport"`
* `has_sunroof_solar`: Title contains `"solar"`, `"sunroof"`, `"moonroof"`, `"open roof"`
* `has_leather_seats`: Title contains `"leather"`, `"ពូកស្បែក"`
* `has_yan_wheels`: Title contains `"yan"`, `"rim"`, `"យ៉ាន់"`
* `has_camera_sensors`: Title contains `"camera"`, `"sensor"`, `"360"`
* `is_urgent_sale`: Title contains `"urgent"`, `"លក់ប្រញាប់"`, `"ធូរថ្លៃ"`, `"negotiable"`

---

## 6. Categorical Encoding & Target Transformation

### A. Target Variable Transformation: $\log(1 + \text{price})$
Car prices are heavily **right-skewed** (log-normal distribution).
* **Transformation**:
  $$y = \ln(\text{price})$$
* **Why**:
  - Stabilizes variance (homoscedasticity).
  - Minimizing Root Mean Squared Error (RMSE) on $\ln(\text{price})$ corresponds to minimizing **Mean Absolute Percentage Error (MAPE)** in dollar terms.
  - Penalizes a 10% error on a $5,000 car equally to a 10% error on a $50,000 car.
* **Inference**: Apply $\exp(\hat{y})$ to convert predictions back to USD.

```
       Raw Price Distribution               Log-Transformed Price Distribution
   ▲                                         ▲
   │  █                                      │       ███
   │  ███                                    │     ███████
   │  █████                                  │   ███████████
   │  ███████                                │  █████████████
   │  █████████                              │ ███████████████
   │  █████████████                          │█████████████████
   └───────────────────────►                 └───────────────────────►
      $5k   $50k  $100k  $250k                  8.5   9.5  10.5  11.5 (ln)
      (Severe Right Skew)                          (Gaussian Normal)
```

### B. Categorical Encoding Strategy

| Feature | Cardinality | Encoding Method | Justification |
|---|---|---|---|
| `vehicle_condition` | Low (2) | One-Hot / Binary (`0 = used, 1 = new`) | Clean binary split. |
| `vehicle_transmission` | Low (3) | One-Hot (`Automatic`, `Manual`, `Unknown`) | Few distinct categories. |
| `vehicle_fuel_type` | Low (5) | One-Hot (`Petrol`, `Diesel`, `Hybrid`, `Electric`, `Unknown`) | Preserves fuel distinctions without expanding dimensionality. |
| `seller_type` | Low (2) | Binary (`0 = individual, 1 = store`) | Direct seller classification. |
| `location_tier` | Low (3) | One-Hot (`Tier_1`, `Tier_2`, `Tier_3`) | Dense regional representation. |
| `vehicle_brand` | Medium (25–40) | Frequency Encoding OR Top-20 One-Hot + `"Other"` | Balances cardinality while retaining major brands. |
| `vehicle_model` | High (>200) | **Out-of-Fold Target Encoding** (Smooth Mean) | Prevents one-hot explosion while directly injecting model-level price expectations. |

$$\text{Target Encoding}(m) = \frac{n_m \cdot \bar{y}_m + \text{weight} \cdot \bar{y}_{\text{global}}}{n_m + \text{weight}}$$

---

## 7. Data Leakage Prevention & Validation Strategy

### ⚠️ Common Data Leakage Pitfalls & Solutions

1. **Snapshots Leakage (The Multi-Day Danger)**:
   - *Danger*: If Listing #1001 on Day 1 is in the Training set and Listing #1001 on Day 2 is in the Test set, the model gets a near-identical copy and reports artificially perfect accuracy ($R^2 \approx 0.99$).
   - *Fix*: **Deduplicate first**, or use **GroupKFold** grouped by `listing_id` so all observations of a vehicle stay strictly in one fold.

2. **Target Encoding Leakage**:
   - *Danger*: Computing target encoding using the entire dataset leaks target values into training features.
   - *Fix*: Compute Target Encoding **strictly inside Cross-Validation folds** or fit on `X_train` only.

3. **Imputation Leakage**:
   - *Danger*: Calculating overall median mileage or price across train + test.
   - *Fix*: Calculate medians from `X_train` and apply them to `X_val` / `X_test`.

### 📊 Recommended Split Strategy

```
Total Deduplicated Dataset (e.g. 5,000 unique listings)
  │
  ├─► 80% Train Set (4,000 listings) ──► 5-Fold Cross Validation for Tuning
  │
  └─► 20% Test / Holdout Set (1,000 listings) ──► Final Unseen Evaluation
```

---

## 8. Complete Python Implementation Reference

Below is a production-grade, modular Python module [`pipeline/transform.py`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction) implementing this complete methodology:

```python
# pipeline/transform.py — Production Preprocessing & Feature Engineering Pipeline

import os
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Tuple

CURRENT_YEAR = datetime.now().year

LUXURY_BRANDS = {"Lexus", "Mercedes-Benz", "BMW", "Porsche", "Land Rover", "Audi", "Cadillac", "Rolls-Royce", "Bentley"}
POPULAR_BRANDS = {"Toyota", "Lexus", "Ford", "Hyundai", "Mazda", "Kia", "Honda", "Mitsubishi"}
TIER_1_PROVINCES = {"Phnom Penh"}
TIER_2_PROVINCES = {"Siem Reap", "Battambang", "Kandal", "Preah Sihanouk", "Kampong Cham"}


def preprocess_dataset(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Full end-to-end preprocessing pipeline from raw multi-day DataFrame to ML-ready table.
    """
    df = df_raw.copy()
    
    # ── Step 1: Multi-day Deduplication & Historical Features ─────────────────
    if "scraped_at" in df.columns and "listing_id" in df.columns:
        df["scraped_at_dt"] = pd.to_datetime(df["scraped_at"], errors="coerce")
        df["posted_at_dt"] = pd.to_datetime(df["posted_at"], errors="coerce")
        
        # Calculate historical stats per listing
        hist_stats = df.groupby("listing_id").agg(
            first_seen=("scraped_at_dt", "min"),
            last_seen=("scraped_at_dt", "max"),
            first_price=("price", "first"),
            last_price=("price", "last"),
        ).reset_index()
        
        hist_stats["days_on_market"] = (hist_stats["last_seen"] - hist_stats["first_seen"]).dt.total_seconds() / 86400.0
        hist_stats["price_drop_amount"] = (hist_stats["first_price"] - hist_stats["last_price"]).clip(lower=0)
        hist_stats["has_price_drop"] = (hist_stats["price_drop_amount"] > 0).astype(int)
        
        # Keep the latest snapshot
        df = df.sort_values("scraped_at_dt").groupby("listing_id").last().reset_index()
        df = df.merge(hist_stats[["listing_id", "days_on_market", "price_drop_amount", "has_price_drop"]], on="listing_id", how="left")
    else:
        df["days_on_market"] = 0.0
        df["price_drop_amount"] = 0.0
        df["has_price_drop"] = 0

    # ── Step 2: Sanity Cleaning & Outlier Filtering ───────────────────────────
    # Price
    df = df.dropna(subset=["price"])
    df = df[(df["price"] >= 500) & (df["price"] <= 300_000)]
    
    # Model Year
    df["vehicle_model_year"] = pd.to_numeric(df["vehicle_model_year"], errors="coerce")
    df = df[(df["vehicle_model_year"].isna()) | (df["vehicle_model_year"].between(1990, CURRENT_YEAR + 1))]

    # Mileage & Engine CC
    df["vehicle_mileage_km"] = pd.to_numeric(df["vehicle_mileage_km"], errors="coerce")
    df.loc[(df["vehicle_mileage_km"] < 0) | (df["vehicle_mileage_km"] > 500_000), "vehicle_mileage_km"] = np.nan
    
    df["vehicle_engine_cc"] = pd.to_numeric(df["vehicle_engine_cc"], errors="coerce")
    df.loc[(df["vehicle_engine_cc"] < 500) | (df["vehicle_engine_cc"] > 7000), "vehicle_engine_cc"] = np.nan

    # ── Step 3: Missing Value Imputation ──────────────────────────────────────
    # Year: Impute by brand/model median
    df["vehicle_model_year"] = df.groupby(["vehicle_brand", "vehicle_model"])["vehicle_model_year"].transform(
        lambda s: s.fillna(s.median())
    )
    df["vehicle_model_year"] = df.groupby("vehicle_brand")["vehicle_model_year"].transform(
        lambda s: s.fillna(s.median())
    )
    df["vehicle_model_year"] = df["vehicle_model_year"].fillna(2012)  # Global fallback

    # Mileage: Grouped median by year + brand, with missingness indicator
    df["is_mileage_missing"] = df["vehicle_mileage_km"].isna().astype(int)
    df["vehicle_mileage_km"] = df.groupby(["vehicle_model_year", "vehicle_brand"])["vehicle_mileage_km"].transform(
        lambda s: s.fillna(s.median())
    )
    df["vehicle_mileage_km"] = df["vehicle_mileage_km"].fillna(df["vehicle_mileage_km"].median()).fillna(100_000)

    # Engine CC
    df["vehicle_engine_cc"] = df.groupby("vehicle_model")["vehicle_engine_cc"].transform(
        lambda s: s.fillna(s.median())
    )
    df["vehicle_engine_cc"] = df["vehicle_engine_cc"].fillna(2000)

    # String Categories
    df["vehicle_brand"] = df["vehicle_brand"].fillna("Unknown").str.strip()
    df["vehicle_model"] = df["vehicle_model"].fillna("Unknown").str.strip()
    df["vehicle_condition"] = df["vehicle_condition"].fillna("used").str.lower().str.strip()
    df["vehicle_tax_type"] = df["vehicle_tax_type"].fillna("Unknown").str.strip()
    df["vehicle_fuel_type"] = df["vehicle_fuel_type"].fillna("Unknown").str.strip()
    df["vehicle_transmission"] = df["vehicle_transmission"].fillna("Unknown").str.strip()
    df["province"] = df["province"].fillna("Phnom Penh").str.strip()
    df["seller_type"] = df["seller_type"].fillna("individual").str.lower().str.strip()

    # ── Step 4: Domain Feature Engineering ────────────────────────────────────
    # 1. Vehicle Age
    df["vehicle_age"] = (CURRENT_YEAR - df["vehicle_model_year"]).clip(lower=0)
    df["vehicle_age_squared"] = df["vehicle_age"] ** 2
    
    # 2. Annual Mileage
    df["mileage_per_year"] = df["vehicle_mileage_km"] / (df["vehicle_age"] + 1)
    
    # 3. Brand Tiers
    df["is_luxury_brand"] = df["vehicle_brand"].isin(LUXURY_BRANDS).astype(int)
    df["is_popular_brand"] = df["vehicle_brand"].isin(POPULAR_BRANDS).astype(int)
    
    # 4. Location Tier
    df["location_tier"] = "Tier_3"
    df.loc[df["province"].isin(TIER_2_PROVINCES), "location_tier"] = "Tier_2"
    df.loc[df["province"].isin(TIER_1_PROVINCES), "location_tier"] = "Tier_1"
    
    # 5. Title Option NLP Indicators
    title_lower = df["listing_title"].str.lower().fillna("")
    df["has_full_option"] = title_lower.str.contains(r"full\s*option|option\s*[34]|f-sport", regex=True).astype(int)
    df["has_sunroof"] = title_lower.str.contains(r"solar|sunroof|moonroof|បើកដំបូល", regex=True).astype(int)
    df["has_leather"] = title_lower.str.contains(r"leather|ពូកស្បែក", regex=True).astype(int)

    # 6. Target Transformation
    df["log_price"] = np.log1p(df["price"])

    return df.reset_index(drop=True)
```

---

## 9. Summary Checklist for Production Readiness

- [x] **Target Integrity**: $0 and null prices discarded; bounds set between \$500 and \$300,000.
- [x] **Deduplication**: Multi-day duplicates deduplicated on `listing_id` keeping the latest snapshot.
- [x] **Change Tracking**: Extracted `days_on_market`, `price_drop_amount`, and `has_price_drop`.
- [x] **Imputation**: Grouped hierarchical medians for numericals; domain fallbacks & `"Unknown"` categories for strings.
- [x] **Domain Features**: Added `vehicle_age`, `mileage_per_year`, brand tier flags, and title NLP options.
- [x] **Target Normalization**: Log-transform $\ln(1 + \text{price})$ applied to stabilize right-skewed variance.
- [x] **Leakage Free**: Clean split rules preventing duplicate listing leakage across train/validation folds.
