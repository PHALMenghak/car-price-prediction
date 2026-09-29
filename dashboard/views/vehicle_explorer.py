"""
dashboard/views/vehicle_explorer.py
===================================
Page 2 — Vehicle Explorer
Explore actual Cambodian marketplace listings with faceted filtering,
interactive formatted table, and live listing-level AI appraisal comparison.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard import config
from dashboard.services import duckdb_service, prediction_service


def render(active_date: str | None = None) -> None:
    """Render the Vehicle Explorer page."""
    st.markdown(
        config.section_header(
            "VEHICLE EXPLORER",
            "Explore verified Cambodian marketplace listings and evaluate fair market deal values",
        ),
        unsafe_allow_html=True,
    )

    # ── 1. Faceted Filter Bar ─────────────────────────────────────────────────
    with st.expander("🔍 Filter Inventory (Brand, Model, Year, Price, Specs)", expanded=True):
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)

        # Brand & Model
        brand_hierarchy = duckdb_service.get_brand_model_options()
        all_brands = ["All"] + sorted(list(brand_hierarchy.keys()))

        with f_col1:
            sel_brand = st.selectbox("Brand", options=all_brands, index=0)

        model_opts = ["All"]
        if sel_brand != "All" and sel_brand in brand_hierarchy:
            model_opts += brand_hierarchy[sel_brand]
        with f_col2:
            sel_model = st.selectbox("Model", options=model_opts, index=0)

        # Body & Fuel
        with f_col3:
            body_opts = ["All", "SUV", "Sedan", "Pickup", "Hatchback", "Van"]
            sel_body = st.selectbox("Vehicle Type", options=body_opts, index=0)

        with f_col4:
            fuel_opts = ["All", "Gasoline", "Hybrid", "Diesel", "Electric"]
            sel_fuel = st.selectbox("Fuel Type", options=fuel_opts, index=0)

        # Year Range & Price Range
        r_col1, r_col2, r_col3 = st.columns([1.5, 1.5, 1])
        with r_col1:
            year_range = st.slider("Manufacturing Year", min_value=2000, max_value=2026, value=(2005, 2024))
        with r_col2:
            price_range = st.slider("Price Range (USD)", min_value=2000, max_value=250000, value=(5000, 120000), step=1000)
        with r_col3:
            tax_opts = ["All", "Plate Number", "Tax Paper"]
            sel_tax = st.selectbox("Tax Status", options=tax_opts, index=0)

        search_q = st.text_input("Search Brand or Model (e.g. Prius, RX330, Ranger)", value="")

    # ── 2. Query Listings via DuckDB ──────────────────────────────────────────
    with st.spinner("Filtering marketplace inventory..."):
        listings_df = duckdb_service.query_vehicle_listings(
            brand=sel_brand if sel_brand != "All" else None,
            model=sel_model if sel_model != "All" else None,
            body_type=sel_body if sel_body != "All" else None,
            fuel_type=sel_fuel if sel_fuel != "All" else None,
            tax_type=sel_tax if sel_tax != "All" else None,
            min_year=year_range[0],
            max_year=year_range[1],
            min_price=price_range[0],
            max_price=price_range[1],
            search_term=search_q,
            limit=500,
        )

    st.markdown(
        f"<div style='font-size: 0.85rem; font-weight: 700; color: #475569; margin: 12px 0 8px 0;'>"
        f"Showing <b style='color: #0f172a;'>{len(listings_df):,}</b> vehicle listings"
        f"</div>",
        unsafe_allow_html=True,
    )

    if listings_df.empty:
        st.warning("⚠️ No vehicle listings matched your active filter criteria. Try expanding the price or year range.")
        return

    # ── 3. Formatted Interactive Data Table ───────────────────────────────────
    display_df = listings_df.copy()
    display_df["price_fmt"] = display_df["price"].apply(config.format_currency)
    display_df["mileage_fmt"] = display_df["vehicle_mileage_km"].apply(config.format_mileage)
    display_df["engine_fmt"] = display_df["vehicle_engine_cc"].apply(config.format_engine)

    table_cols = [
        "listing_id", "vehicle_brand", "vehicle_model", "vehicle_year",
        "price_fmt", "mileage_fmt", "vehicle_body_type", "vehicle_fuel_type",
        "vehicle_transmission", "vehicle_tax_type", "province"
    ]
    renamed_cols = {
        "listing_id": "ID",
        "vehicle_brand": "Brand",
        "vehicle_model": "Model",
        "vehicle_year": "Year",
        "price_fmt": "Asking Price",
        "mileage_fmt": "Mileage",
        "vehicle_body_type": "Body Type",
        "vehicle_fuel_type": "Fuel",
        "vehicle_transmission": "Transmission",
        "vehicle_tax_type": "Documentation",
        "province": "Location",
    }

    st.dataframe(
        display_df[table_cols].rename(columns=renamed_cols),
        hide_index=True,
        use_container_width=True,
        height=320,
    )

    st.divider()

    # ── 4. Selected Vehicle Appraisal Detail Card ─────────────────────────────
    st.markdown(
        config.section_header(
            "SELECTED VEHICLE APPRAISAL & DEAL ANALYSIS",
            "Select any listing to evaluate dealer asking price vs. predicted model valuation and market medians",
        ),
        unsafe_allow_html=True,
    )

    c_sel1, c_sel2 = st.columns([3, 1])
    with c_sel1:
        sel_idx = st.selectbox(
            "Select listing to inspect:",
            options=range(len(display_df)),
            format_func=lambda i: (
                f"ID #{display_df.iloc[i]['listing_id']}: {display_df.iloc[i]['vehicle_brand']} "
                f"{display_df.iloc[i]['vehicle_model']} {display_df.iloc[i]['vehicle_year']} — "
                f"{config.format_currency(display_df.iloc[i]['price'])} ({display_df.iloc[i]['province']})"
            ),
        )
    with c_sel2:
        quick_id = st.text_input("Or Jump to Listing ID:", value="", placeholder="e.g. 14026618")
        if quick_id.strip():
            matches = display_df.index[display_df["listing_id"].astype(str) == quick_id.strip()].tolist()
            if matches:
                sel_idx = matches[0]
            else:
                st.caption("ID not in current filter")

    selected_row = display_df.iloc[sel_idx]

    # Run AI prediction on this selected vehicle
    is_p = 1 if selected_row["vehicle_tax_type"] == "Plate Number" else 0
    full_opt = int(selected_row.get("has_full_option", 0))

    pred = prediction_service.predict_price(
        vehicle_brand=str(selected_row["vehicle_brand"]),
        vehicle_model=str(selected_row["vehicle_model"]),
        vehicle_year=int(selected_row["vehicle_year"]),
        vehicle_body_type=str(selected_row["vehicle_body_type"]),
        vehicle_fuel_type=str(selected_row["vehicle_fuel_type"]),
        vehicle_transmission=str(selected_row["vehicle_transmission"]),
        vehicle_province=str(selected_row.get("province", "Phnom Penh")),
        is_plate_number=is_p,
        has_full_option=full_opt,
    )

    comp = prediction_service.compare_to_market(
        vehicle_brand=str(selected_row["vehicle_brand"]),
        vehicle_model=str(selected_row["vehicle_model"]),
        predicted_price=pred["fair_price"],
    )

    actual_p = float(selected_row["price"])
    pred_p = pred["fair_price"]
    market_med = comp["market_median"]
    brand_avg = comp["brand_avg"]

    # Deal assessment
    price_delta = actual_p - pred_p
    price_delta_pct = (price_delta / pred_p * 100.0) if pred_p > 0 else 0.0

    if price_delta_pct <= -8.0:
        deal_label = "🟢 VALUE DEAL (Priced Below Model Valuation)"
        deal_color = "#10b981"
        deal_desc = "The asking price is significantly below estimated market value. Ensure physical inspection."
    elif price_delta_pct >= 8.0:
        deal_label = "🔴 OVERPRICED (Priced Above Model Valuation)"
        deal_color = "#ef4444"
        deal_desc = "The seller is asking above fair market value. Negotiate towards the predicted price."
    else:
        deal_label = "🔵 FAIR MARKET DEAL"
        deal_color = "#2563eb"
        deal_desc = "The asking price is consistent with current market valuation."

    # Render Card
    c_specs, c_metrics = st.columns([1.2, 1.8], gap="large")

    seller_info = f"{selected_row.get('seller_type', 'Private Seller')} · Tel: {selected_row.get('seller_phones', 'Not Disclosed')}"
    url_link = f"<a href='{selected_row['listing_url']}' target='_blank' style='color:#2563eb; text-decoration:none; font-weight:600;'>View on Khmer24 ↗</a>" if selected_row.get("listing_url") else ""

    with c_specs:
        st.markdown(
            f"""
            <div style='background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px;'>
                <div style='font-size: 1.15rem; font-weight: 800; color: #0f172a;'>
                    {selected_row['vehicle_brand']} {selected_row['vehicle_model']} ({selected_row['vehicle_year']})
                </div>
                <div style='font-size: 0.78rem; color: #64748b; margin-top: 4px;'>
                    Listing #{selected_row['listing_id']} · {selected_row['province']} · {url_link}
                </div>
                <div style='margin-top: 14px; font-size: 0.82rem; line-height: 1.8; color: #334155;'>
                    <div>• <b>Seller:</b> {seller_info}</div>
                    <div>• <b>Mileage:</b> {config.format_mileage(selected_row['vehicle_mileage_km'])}</div>
                    <div>• <b>Engine:</b> {config.format_engine(selected_row['vehicle_engine_cc'])}</div>
                    <div>• <b>Body Type:</b> {selected_row['vehicle_body_type']}</div>
                    <div>• <b>Fuel / Trans:</b> {selected_row['vehicle_fuel_type']} · {selected_row['vehicle_transmission']}</div>
                    <div>• <b>Documentation:</b> {selected_row['vehicle_tax_type']}</div>
                    <div>• <b>Trim Level:</b> {'Full Option' if full_opt else 'Standard Trim'}</div>
                    <div>• <b>DQ Tier:</b> <span style='font-weight:700; color:#0f2b5c;'>{selected_row.get('data_quality_status', 'VALID')}</span></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c_metrics:
        st.markdown(
            f"""
            <div style='background: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid {deal_color};
                        border-radius: 8px; padding: 18px 20px; margin-bottom: 14px;'>
                <div style='font-size: 0.85rem; font-weight: 800; color: {deal_color};'>{deal_label}</div>
                <div style='font-size: 0.78rem; color: #475569; margin-top: 3px;'>{deal_desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Actual Asking", f"${actual_p:,.0f}")
        with m2:
            st.metric("Predicted Fair", f"${pred_p:,.0f}", delta=f"{'-' if price_delta>0 else '+'}${abs(price_delta):,.0f}", delta_color="inverse")
        with m3:
            st.metric("Market Median", f"${market_med:,.0f}" if market_med > 0 else "—")
        with m4:
            st.metric("Brand Average", f"${brand_avg:,.0f}" if brand_avg > 0 else "—")
