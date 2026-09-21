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
            "FEATURE PROFILING & DISTRIBUTIONS",
            "Statistical characteristics, distribution shapes, and categorical cardinality of the Silver dataset.",
        ),
        unsafe_allow_html=True,
    )

    num_stats = load_feature_numeric_stats("silver", scrape_date=active_date)
    cat_card = load_categorical_cardinality("silver", scrape_date=active_date)
    dist_sample = load_feature_distribution_sample("silver", limit=5000, scrape_date=active_date)

    # ── Top Summary KPI Cards ────────────────────────────────────────────────
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(
            config.kpi_card(
                title="Continuous Variables",
                value=str(len(num_stats)) if not num_stats.empty else "6",
                subtitle="Price, Mileage, Age, Engine CC...",
                accent_color="#0284c7",
                icon="🔢",
            ),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            config.kpi_card(
                title="Categorical Attributes",
                value=str(len(cat_card)) if not cat_card.empty else "8",
                subtitle="Brand, Model, Fuel, Body, Province...",
                accent_color="#8b5cf6",
                icon="🔤",
            ),
            unsafe_allow_html=True,
        )
    with k3:
        sample_count = int(num_stats["populated_count"].max()) if not num_stats.empty else 0
        st.markdown(
            config.kpi_card(
                title="Observations Profiled",
                value=f"{sample_count:,}",
                subtitle="Cleaned records in Silver dataset",
                accent_color="#10b981",
                icon="📋",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    tab_num, tab_dist, tab_cat = st.tabs([
        "📊 Numeric Statistics & Skewness",
        "📈 Distribution Explorer",
        "🔤 Categorical Cardinality & Share",
    ])

    # ── Tab 1: Numeric Features & Skewness ────────────────────────────────────
    with tab_num:
        st.markdown(
            config.section_header(
                "DESCRIPTIVE STATISTICS (SILVER CONFORMED)",
                "Continuous and discrete numerical field metrics after cleaning and type coercion.",
            ),
            unsafe_allow_html=True,
        )

        if not num_stats.empty:
            label_map = {
                "price":              "Price (USD)",
                "log_price":          "Log Price (ln)",
                "vehicle_year":       "Model Year",
                "vehicle_age":        "Vehicle Age (years)",
                "vehicle_mileage_km": "Mileage (km)",
                "vehicle_engine_cc":  "Engine Size (cc)",
            }
            num_stats_disp = num_stats.copy()
            num_stats_disp["feature"] = num_stats_disp["feature"].map(lambda f: label_map.get(f, f))

            st.dataframe(
                num_stats_disp,
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

            with st.expander("📌 Statistical Interpretation: Skewness & Log-Transformation", expanded=True):
                st.markdown(
                    """
- **Symmetric Distribution (Skewness ≈ 0):** Balanced bell shape around the mean.
- **Positive / Right-Skewed (Skewness > +1.0):** Long right-hand tail with extreme high values (typical of raw car prices in Cambodia where luxury vehicles reach \$150k+).
- **Log Price Rationale:** Applying the natural logarithm $\\ln(\\text{Price})$ dramatically compresses skewness (often from $>3.5$ down to $\\approx 0.1$), satisfying the homoscedasticity assumption and improving linear and tree-based model convergence.
                    """
                )
        else:
            st.warning("No numeric statistics available. Check that Silver data exists.")

    # ── Tab 2: Distribution Explorer ──────────────────────────────────────────
    with tab_dist:
        st.markdown(
            config.section_header(
                "HISTOGRAMS & SPREAD ANALYSIS",
                "Inspect frequency distribution shapes, density, and box plot quartiles.",
            ),
            unsafe_allow_html=True,
        )

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
                config.apply_plot_theme(fig_h, height=320, show_legend=False)
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
                config.apply_plot_theme(fig_b, height=320, show_legend=False)
                st.plotly_chart(fig_b, use_container_width=True)

            st.caption(
                f"ℹ️ Outliers highlighted in the box plot are statistical outliers beyond $1.5 \\times \\text{IQR}$. "
                "These are valid high-end or older vehicles unless flagged by dbt data contract tests."
            )
        else:
            st.info("No distribution sample available.")

    # ── Tab 3: Categorical Features ───────────────────────────────────────────
    with tab_cat:
        st.markdown(
            config.section_header(
                "CATEGORICAL CARDINALITY & PROFILES",
                "Distinct value counts, dominant categories, and missingness rates across categorical features.",
            ),
            unsafe_allow_html=True,
        )

        if not cat_card.empty:
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

            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            st.markdown("#### Top Category Frequency Breakdown")
            cat_opts = cat_card["feature"].tolist()
            c1, c2 = st.columns([2, 1])
            with c1:
                selected_cat = st.selectbox(
                    "Select Categorical Feature:",
                    options=cat_opts,
                    format_func=lambda f: cat_label_map.get(f, f),
                    index=0,
                )
            with c2:
                top_n = st.slider("Top N Categories:", min_value=5, max_value=20, value=10)

            cat_dist = load_categorical_distribution(
                selected_cat, top_n=top_n, target_dataset="silver", scrape_date=active_date
            )
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
                config.apply_plot_theme(fig_c, height=320, show_legend=False)
                fig_c.update_layout(
                    xaxis_title=feat_display,
                    yaxis_title="Record Count",
                    title=dict(text=f"Top {top_n} Distribution — {feat_display}", font=dict(size=12)),
                )
                st.plotly_chart(fig_c, use_container_width=True)
            else:
                st.info("No distribution data available for this feature.")
        else:
            st.warning("No categorical profile data available.")
