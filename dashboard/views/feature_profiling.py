"""
dashboard/views/feature_profiling.py
======================================
Page 6 — Feature Profiling
Statistical characteristics and distributions of Silver features.
Focused on Silver layer only (no Gold ML references).
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import config
from dashboard.data_loader import (
    load_categorical_cardinality,
    load_categorical_distribution,
    load_feature_distribution_sample,
    load_feature_numeric_stats,
)


def render(active_date: str | None = None) -> None:
    """Render the Feature Profiling page."""
    st.markdown(
        config.section_header(
            "FEATURE PROFILING",
            "Statistical characteristics and distributions of the Silver dataset.",
        ),
        unsafe_allow_html=True,
    )

    st.info(
        "💡 **Silver Layer Profile.** These statistics describe the cleaned, standardized Silver dataset "
        "(`data/silver/cars_cleaned.parquet`). All values come from records that passed dbt processing."
    )

    st.divider()

    # ── 1. Numeric Features ───────────────────────────────────────────────────
    st.markdown(
        config.section_header(
            "1 · NUMERIC FEATURE STATISTICS",
            "Descriptive statistics for continuous and discrete numerical fields.",
        ),
        unsafe_allow_html=True,
    )

    num_stats = load_feature_numeric_stats("silver", scrape_date=active_date)
    if not num_stats.empty:
        # Friendly labels
        label_map = {
            "price":             "Price (USD)",
            "log_price":         "Log Price (ln)",
            "vehicle_year":      "Model Year",
            "vehicle_age":       "Vehicle Age (years)",
            "vehicle_mileage_km":"Mileage (km)",
            "vehicle_engine_cc": "Engine Size (cc)",
        }
        num_stats = num_stats.copy()
        num_stats["feature"] = num_stats["feature"].map(lambda f: label_map.get(f, f))

        st.dataframe(
            num_stats,
            hide_index=True,
            use_container_width=True,
            column_config={
                "feature":         st.column_config.TextColumn("Feature", width="medium"),
                "populated_count": st.column_config.NumberColumn("Count", format="%d"),
                "mean":            st.column_config.NumberColumn("Mean", format="%.2f"),
                "std_dev":         st.column_config.NumberColumn("Std Dev", format="%.2f"),
                "min_val":         st.column_config.NumberColumn("Min", format="%.2f"),
                "p25":             st.column_config.NumberColumn("P25", format="%.2f"),
                "median_val":      st.column_config.NumberColumn("Median", format="%.2f"),
                "p75":             st.column_config.NumberColumn("P75", format="%.2f"),
                "max_val":         st.column_config.NumberColumn("Max", format="%.2f"),
                "skewness":        st.column_config.NumberColumn("Skewness", format="%.2f"),
            },
        )

        # Skewness interpretation
        with st.expander("📌 How to interpret Skewness"):
            st.markdown(
                "- **Skewness ≈ 0:** Symmetric (roughly normal) distribution.\n"
                "- **Skewness > 1:** Right-skewed (long right tail — common for price data).\n"
                "- **Skewness < −1:** Left-skewed (long left tail).\n"
                "- For heavily right-skewed features like `Price`, log transformation (`log_price`) "
                "reduces skewness and often improves downstream model training."
            )
    else:
        st.warning("No numeric statistics available. Check that Silver data exists.")

    st.divider()

    # ── 2. Distribution Visualizer ────────────────────────────────────────────
    st.markdown(
        config.section_header(
            "2 · DISTRIBUTION EXPLORER",
            "Histograms and box plots — inspect shape, spread, and outliers.",
        ),
        unsafe_allow_html=True,
    )

    dist_sample = load_feature_distribution_sample("silver", limit=5000, scrape_date=active_date)

    if not dist_sample.empty:
        num_cols = [
            c for c in ["price", "log_price", "vehicle_year", "vehicle_age",
                         "vehicle_mileage_km", "vehicle_engine_cc"]
            if c in dist_sample.columns
        ]
        label_map = {
            "price": "Price (USD)", "log_price": "Log Price", "vehicle_year": "Model Year",
            "vehicle_age": "Vehicle Age (yrs)", "vehicle_mileage_km": "Mileage (km)",
            "vehicle_engine_cc": "Engine Size (cc)",
        }

        sel_col, grp_col = st.columns([2, 2])
        with sel_col:
            selected_feature = st.selectbox(
                "Select Feature to Visualize:",
                options=num_cols,
                format_func=lambda f: label_map.get(f, f),
                index=0,
            )
        with grp_col:
            group_options = [c for c in ["brand_tier", "vehicle_body_type", "vehicle_fuel_type"]
                             if c in dist_sample.columns]
            selected_group = st.selectbox(
                "Group Box Plot By (Optional):",
                options=["(None)"] + group_options,
                index=1 if group_options else 0,
            )

        col_hist, col_box = st.columns(2, gap="large")
        series = dist_sample[selected_feature].dropna()
        feat_label = label_map.get(selected_feature, selected_feature)

        with col_hist:
            st.markdown(f"**Distribution — {feat_label}**")
            fig_h = px.histogram(
                series,
                x=selected_feature,
                nbins=40,
                marginal="rug",
                color_discrete_sequence=["#1e3a8a"],
                labels={selected_feature: feat_label},
            )
            config.apply_plot_theme(fig_h, height=300, show_legend=False)
            fig_h.update_layout(xaxis_title=feat_label, yaxis_title="Count")
            st.plotly_chart(fig_h, use_container_width=True)

        with col_box:
            st.markdown(f"**Box Plot — {feat_label}**")
            if selected_group != "(None)":
                plot_df = dist_sample.dropna(subset=[selected_feature, selected_group])
                fig_b = px.box(
                    plot_df,
                    x=selected_group,
                    y=selected_feature,
                    color=selected_group,
                    labels={selected_feature: feat_label, selected_group: selected_group},
                )
                fig_b.update_layout(showlegend=False)
            else:
                fig_b = px.box(
                    series,
                    y=selected_feature,
                    color_discrete_sequence=["#0284c7"],
                    labels={selected_feature: feat_label},
                )
            config.apply_plot_theme(fig_b, height=300, show_legend=False)
            st.plotly_chart(fig_b, use_container_width=True)

        st.caption(
            f"ℹ️ Outliers shown in box plot are **statistical** outliers (beyond 1.5×IQR). "
            "They are **not** automatically classified as invalid — domain judgment required. "
            "DQ flags (SUSPICIOUS, INVALID) are assigned by separate rules in `int_cars_cleaned.sql`."
        )
    else:
        st.info("No distribution sample available.")

    st.divider()

    # ── 3. Categorical Features ───────────────────────────────────────────────
    st.markdown(
        config.section_header(
            "3 · CATEGORICAL FEATURE PROFILES",
            "Cardinality, top categories, and missingness for categorical fields.",
        ),
        unsafe_allow_html=True,
    )

    cat_card = load_categorical_cardinality("silver", scrape_date=active_date)
    if not cat_card.empty:
        # Friendly names
        cat_label_map = {
            "vehicle_brand":        "Brand",
            "vehicle_model":        "Model",
            "vehicle_fuel_type":    "Fuel Type",
            "vehicle_transmission": "Transmission",
            "vehicle_body_type":    "Body Type",
            "province":             "Province",
            "brand_tier":           "Brand Tier",
            "seller_type":          "Seller Type",
        }
        cat_card_disp = cat_card.copy()
        cat_card_disp["feature"] = cat_card_disp["feature"].map(lambda f: cat_label_map.get(f, f))

        st.dataframe(
            cat_card_disp,
            hide_index=True,
            use_container_width=True,
            column_config={
                "feature":        st.column_config.TextColumn("Feature", width="medium"),
                "distinct_count": st.column_config.NumberColumn("Unique Values", format="%d"),
                "top_1":          st.column_config.TextColumn("Top #1 (% share)", width="medium"),
                "top_2":          st.column_config.TextColumn("Top #2 (% share)", width="medium"),
                "top_3":          st.column_config.TextColumn("Top #3 (% share)", width="medium"),
                "missing_count":  st.column_config.NumberColumn("Missing Count", format="%d"),
                "missing_pct":    st.column_config.NumberColumn("Missing %", format="%.1f%%"),
            },
        )

        # Top-N frequency chart
        st.markdown("**Top Category Frequency Chart**")
        cat_opts = cat_card["feature"].tolist()
        c1, c2 = st.columns([2, 1])
        with c1:
            selected_cat = st.selectbox(
                "Select Feature:",
                options=cat_opts,
                format_func=lambda f: cat_label_map.get(f, f),
                index=0,
            )
        with c2:
            top_n = st.slider("Top N:", min_value=5, max_value=20, value=10)

        cat_dist = load_categorical_distribution(selected_cat, top_n=top_n, target_dataset="silver", scrape_date=active_date)
        if not cat_dist.empty:
            feat_display = cat_label_map.get(selected_cat, selected_cat)
            fig_c = go.Figure(go.Bar(
                x=cat_dist["category"],
                y=cat_dist["count"],
                marker_color="#1e3a8a",
                text=[f"{c:,} ({p:.1f}%)" for c, p in zip(cat_dist["count"], cat_dist["pct"])],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Count: %{y:,}<extra></extra>",
            ))
            config.apply_plot_theme(fig_c, height=300, show_legend=False)
            fig_c.update_layout(
                xaxis_title=feat_display,
                yaxis_title="Record Count",
                title=dict(text=f"Top {top_n} — {feat_display}", font=dict(size=12)),
            )
            st.plotly_chart(fig_c, use_container_width=True)
        else:
            st.info("No distribution data available for this feature.")
    else:
        st.warning("No categorical profile data available.")
