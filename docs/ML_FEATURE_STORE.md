# 🤖 Machine Learning Feature Store Guide

> **Project**: Cambodia Used Car Price Prediction  
> **Layer**: Gold Layer (ML Training Matrix)  
> **File**: `data/gold/fct_cars_ml_features.parquet` (and `.csv`)  
> **Engine**: dbt + DuckDB SQL  

---

## 1. What is the ML Feature Store?

The **ML Feature Store** table ([`fct_cars_ml_features`](file:///D:/ITC3_AMS_2025/I4_AMS_S2/Y4_Internship/Car_price_prediction/dbt/models/marts/ml/fct_cars_ml_features.sql)) is the final, fully-prepared dataset used to train regression models (such as **LightGBM**, **XGBoost**, **Random Forest**, and **CatBoost**).

Unlike raw data, the Feature Store guarantees:
* **Zero Missing Values**: Numeric missing values are filled using smart group medians.
* **Missing Value Flags**: Tells the model when an odometer or engine size was originally missing.
* **Log-Transformed Target**: Converts skewed car prices into a normal distribution for accurate regression.
* **No Target Leakage**: Only uses information available at the time of prediction.

---

## 2. Feature Summary Table

| Category | Feature Name | Data Type | Description |
| :--- | :--- | :--- | :--- |
| **Target (Y)** | `log_price` | Float | $\ln(1 + \text{price})$ — Primary ML training target |
| **Target (Y)** | `price` | Float | Raw asking price in USD (for evaluation metrics like MAE / RMSE) |
| **Vehicle Core** | `vehicle_brand` | String | Car manufacturer (e.g. `Toyota`, `Lexus`, `Ford`) |
| **Vehicle Core** | `vehicle_model` | String | Canonical model (e.g. `Prius`, `Camry`, `Ranger`) |
| **Vehicle Core** | `vehicle_model_year` | Integer | Release year (imputed if missing) |
| **Vehicle Core** | `vehicle_age` | Integer | `Current_Year - vehicle_model_year` ($\ge 0$) |
| **Vehicle Core** | `vehicle_mileage_km` | Float | Odometer reading in km (imputed if missing) |
| **Vehicle Core** | `is_mileage_missing` | Binary (0/1) | 1 if mileage was missing in raw post |
| **Vehicle Core** | `vehicle_engine_cc` | Float | Engine displacement in cc (imputed if missing) |
| **Vehicle Core** | `is_engine_cc_missing` | Binary (0/1) | 1 if engine displacement was missing |
| **Powertrain** | `vehicle_fuel_type` | String | `Petrol`, `Diesel`, `Hybrid`, `Electric`, `LPG` |
| **Powertrain** | `vehicle_transmission` | String | `Automatic` vs `Manual` |
| **Powertrain** | `vehicle_color` | String | Standardized exterior color (`White`, `Black`, `Silver`, etc.) |
| **Legal Status** | `vehicle_condition` | String | `new` vs `used` |
| **Legal Status** | `is_plate_number` | Binary (0/1) | 1 = Local Plate Number, 0 = Tax Paper / Unregistered |
| **Market Segment**| `brand_category` | String | `Luxury`, `Mass_Market`, `Chinese_EV`, `Other` |
| **Geography** | `province` | String | Province listed (e.g. `Phnom Penh`, `Siem Reap`) |
| **Geography** | `location_tier` | String | `Tier_1` (Phnom Penh), `Tier_2` (Major), `Tier_3` (Regional) |
| **Seller** | `seller_type` | String | `store` (car dealership) vs `individual` (private owner) |
| **Market Dynamics**| `days_on_market` | Float | Days the listing has been live |
| **Market Dynamics**| `initial_price` | Float | First recorded asking price |
| **Market Dynamics**| `price_drop_amount` | Float | Total USD discount since first listed |
| **Market Dynamics**| `has_price_drop` | Binary (0/1) | 1 if seller dropped price |
| **Market Dynamics**| `view_count` | Integer | Total page views on Khmer24 |
| **Market Dynamics**| `view_velocity` | Float | Views per day on market |
| **NLP Title Signals**| `has_full_option` | Binary (0/1) | 1 if title mentions full options / top trim |
| **NLP Title Signals**| `is_urgent_sale` | Binary (0/1) | 1 if title indicates urgent sale / negotiable |

---

## 3. How Missing Data is Filled (Hierarchical Imputation)

In Cambodia marketplace data, sellers often do not fill out mileage or engine size. Rather than throwing these rows away, dbt uses **hierarchical median imputation** with SQL window functions:

```
                  HIERARCHICAL IMPUTATION FLOW
┌──────────────────────────────────────────────────────────────┐
│ 1. Specific Group Median                                     │
│    Take the median of the exact Brand + Model                │
│    (e.g., Median mileage of all Toyota Prius cars)           │
│                           │ (if still null)                  │
│                           ▼                                  │
│ 2. General Brand Median                                      │
│    Take the median of all cars for that Brand                │
│    (e.g., Median mileage of all Toyota cars)                 │
│                           │ (if still null)                  │
│                           ▼                                  │
│ 3. Global Market Fallback                                    │
│    Use the market-wide median (e.g., 100,000 km, 2000 cc)   │
└──────────────────────────────────────────────────────────────┘
```

> **Why Missing Flags Matter**:  
> When we fill a missing mileage with a median, we also set `is_mileage_missing = 1`. This allows tree-based models (LightGBM/XGBoost) to know that the number was estimated.

---

## 4. Why Use Log-Transformed Price?

Car prices have a wide range (from $1,000 for an old sedan to $250,000 for a Lexus LX600). The price distribution is heavily skewed to the right.

* By training the model on **`log_price = ln(1 + price)`**, errors on cheap cars and expensive cars are treated proportionally (e.g., a 10% error is evaluated the same regardless of car price).
* At prediction time, we convert the output back to dollars using:  
  $$\text{Predicted Price} = \exp(\text{Predicted Log Price}) - 1$$

---

## 5. Recommended Encoding for ML Models

When loading `fct_cars_ml_features.parquet` into Python:

1. **Tree-Based Models (LightGBM / XGBoost / CatBoost)**:
   * Pass categorical columns (`vehicle_brand`, `vehicle_model`, `vehicle_fuel_type`, `location_tier`) directly using `category` dtype in Pandas.
2. **Linear Models (Ridge / Lasso / Linear Regression)**:
   * Use `OneHotEncoder` on low-cardinality categories (`fuel_type`, `transmission`, `brand_category`, `location_tier`).
   * Use Target Encoding or Frequency Encoding on high-cardinality categories (`vehicle_brand`, `vehicle_model`).
