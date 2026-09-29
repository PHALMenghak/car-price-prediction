"""
dashboard/views/price_prediction.py
===================================
Page 3 — AI Vehicle Price Predictor (The Core Platform Engine)
Answers:
  1. What is the fair market value of this specific vehicle in Cambodia?
  2. How does the predicted appraisal compare to actual market medians?
  3. Why did the machine learning model predict this price (SHAP XAI)?
  4. What negotiation strategies should buyers and sellers apply?
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from dashboard import config
from dashboard.services import duckdb_service, prediction_service


def render(active_date: str | None = None) -> None:
    """Render the AI Vehicle Price Predictor page."""
    st.markdown(
        config.section_header(
            "AI VEHICLE PRICE PREDICTOR",
            "Estimate the fair market value of a used vehicle in Cambodia using certified machine learning",
        ),
        unsafe_allow_html=True,
    )

    # Load brand-model hierarchy for cascading dropdowns
    brand_hierarchy = duckdb_service.get_brand_model_options()
    if not brand_hierarchy:
        brand_hierarchy = {
            "Toyota": ["Prius", "Camry", "Highlander", "Corolla", "Land Cruiser", "Hilux"],
            "Lexus": ["RX300", "RX330", "RX350", "LX470", "LX570", "NX200t"],
            "Ford": ["Ranger", "Everest", "F-150"],
            "Mazda": ["Mazda 3", "CX-5"],
            "Hyundai": ["Tucson", "Santa Fe", "H-1"],
        }

    available_brands = sorted(list(brand_hierarchy.keys()))

    # Initialize session state for presets & selections if not present
    if "pred_brand" not in st.session_state:
        st.session_state["pred_brand"] = "Toyota"
    if "pred_model" not in st.session_state:
        st.session_state["pred_model"] = "Prius"
    if "pred_year" not in st.session_state:
        st.session_state["pred_year"] = 2010
    if "pred_body" not in st.session_state:
        st.session_state["pred_body"] = "Hatchback"
    if "pred_fuel" not in st.session_state:
        st.session_state["pred_fuel"] = "Hybrid"
    if "pred_trans" not in st.session_state:
        st.session_state["pred_trans"] = "Automatic"
    if "pred_doc" not in st.session_state:
        st.session_state["pred_doc"] = "Plate Number (ផ្លាកលេខ)"
    if "pred_full_opt" not in st.session_state:
        st.session_state["pred_full_opt"] = True
    if "pred_color" not in st.session_state:
        st.session_state["pred_color"] = "White"
    if "pred_prov" not in st.session_state:
        st.session_state["pred_prov"] = "Phnom Penh"

    # ── 1. One-Click Market Presets ───────────────────────────────────────────
    st.markdown(
        """
        <div style='font-size: 0.70rem; font-weight: 800; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;'>
            ⚡ ONE-CLICK CAMBODIAN MARKET ARCHETYPE PRESETS
        </div>
        """,
        unsafe_allow_html=True,
    )
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        if st.button("🚗 Toyota Prius (2010)", use_container_width=True, help="High-volume hybrid hatchback with plate number"):
            st.session_state["pred_brand"] = "Toyota"
            st.session_state["pred_model"] = "Prius"
            st.session_state["pred_year"] = 2010
            st.session_state["pred_body"] = "Hatchback"
            st.session_state["pred_fuel"] = "Hybrid"
            st.session_state["pred_trans"] = "Automatic"
            st.session_state["pred_doc"] = "Plate Number (ផ្លាកលេខ)"
            st.session_state["pred_full_opt"] = True
            st.session_state["pred_color"] = "White"
            st.session_state["pred_prov"] = "Phnom Penh"
            st.rerun()
    with p2:
        if st.button("🚙 Lexus RX350 (2015)", use_container_width=True, help="Luxury prestige SUV with fresh tax paper"):
            st.session_state["pred_brand"] = "Lexus"
            st.session_state["pred_model"] = "RX350"
            st.session_state["pred_year"] = 2015
            st.session_state["pred_body"] = "SUV"
            st.session_state["pred_fuel"] = "Gasoline"
            st.session_state["pred_trans"] = "Automatic"
            st.session_state["pred_doc"] = "Tax Paper (ក្រដាសពន្ធ)"
            st.session_state["pred_full_opt"] = True
            st.session_state["pred_color"] = "White"
            st.session_state["pred_prov"] = "Phnom Penh"
            st.rerun()
    with p3:
        if st.button("🛻 Ford Ranger (2020)", use_container_width=True, help="Popular utility diesel pickup"):
            st.session_state["pred_brand"] = "Ford"
            st.session_state["pred_model"] = "Ranger"
            st.session_state["pred_year"] = 2020
            st.session_state["pred_body"] = "Pickup"
            st.session_state["pred_fuel"] = "Diesel"
            st.session_state["pred_trans"] = "Automatic"
            st.session_state["pred_doc"] = "Plate Number (ផ្លាកលេខ)"
            st.session_state["pred_full_opt"] = True
            st.session_state["pred_color"] = "Black"
            st.session_state["pred_prov"] = "Phnom Penh"
            st.rerun()
    with p4:
        if st.button("🚘 Mazda 3 (2018)", use_container_width=True, help="Urban executive gasoline sedan"):
            st.session_state["pred_brand"] = "Mazda"
            st.session_state["pred_model"] = "Mazda 3"
            st.session_state["pred_year"] = 2018
            st.session_state["pred_body"] = "Sedan"
            st.session_state["pred_fuel"] = "Gasoline"
            st.session_state["pred_trans"] = "Automatic"
            st.session_state["pred_doc"] = "Plate Number (ផ្លាកលេខ)"
            st.session_state["pred_full_opt"] = True
            st.session_state["pred_color"] = "Red"
            st.session_state["pred_prov"] = "Phnom Penh"
            st.rerun()

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # ── 2. Two-Column Layout: Inputs vs Appraisal ─────────────────────────────
    col_input, col_output = st.columns([1.05, 1.35], gap="large")

    with col_input:
        st.markdown(
            """
            <div style='background: #ffffff; border: 1px solid #e2e8f0; border-top: 4px solid #2563eb;
                        border-radius: 8px; padding: 16px 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 16px;'>
                <div style='font-size: 0.92rem; font-weight: 800; color: #0f172a; margin-bottom: 2px;'>
                    📋 VEHICLE SPECIFICATIONS
                </div>
                <div style='font-size: 0.75rem; color: #64748b;'>
                    Verified Day-0 physical features · Real-time ML appraisal
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Brand & Model Cascading
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            cur_brand = st.session_state["pred_brand"]
            brand_idx = available_brands.index(cur_brand) if cur_brand in available_brands else 0
            selected_brand = st.selectbox(
                "Brand (ម៉ាក)",
                options=available_brands,
                index=brand_idx,
                help="Manufacturer brand",
            )
            if selected_brand != cur_brand:
                st.session_state["pred_brand"] = selected_brand
                st.session_state["pred_model"] = brand_hierarchy.get(selected_brand, ["Other"])[0]
                st.rerun()

        model_options = brand_hierarchy.get(selected_brand, ["Other"])
        with c_b2:
            cur_model = st.session_state["pred_model"]
            model_idx = model_options.index(cur_model) if cur_model in model_options else 0
            selected_model = st.selectbox(
                "Model (ម៉ូដែល)",
                options=model_options,
                index=model_idx,
                help="Specific vehicle model",
            )
            st.session_state["pred_model"] = selected_model

        # Year & Body Type
        c_y1, c_y2 = st.columns(2)
        with c_y1:
            selected_year = st.slider(
                "Manufacturing Year (ឆ្នាំផលិត)",
                min_value=1998,
                max_value=2026,
                value=int(st.session_state["pred_year"]),
                step=1,
            )
            st.session_state["pred_year"] = selected_year
        with c_y2:
            body_types = ["SUV", "Sedan", "Pickup", "Hatchback", "Van", "Coupe"]
            cur_body = st.session_state["pred_body"]
            body_idx = body_types.index(cur_body) if cur_body in body_types else 0
            selected_body = st.selectbox("Vehicle Type (ប្រភេទឡាន)", options=body_types, index=body_idx)
            st.session_state["pred_body"] = selected_body

        # Fuel & Transmission
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            fuels = ["Gasoline", "Hybrid", "Diesel", "Electric"]
            cur_fuel = st.session_state["pred_fuel"]
            fuel_idx = fuels.index(cur_fuel) if cur_fuel in fuels else 0
            selected_fuel = st.selectbox("Fuel Type (ប្រេង)", options=fuels, index=fuel_idx)
            st.session_state["pred_fuel"] = selected_fuel
        with c_f2:
            transmissions = ["Automatic", "Manual"]
            cur_trans = st.session_state["pred_trans"]
            trans_idx = transmissions.index(cur_trans) if cur_trans in transmissions else 0
            selected_trans = st.selectbox("Transmission (ប្រអប់លេខ)", options=transmissions, index=trans_idx)
            st.session_state["pred_trans"] = selected_trans

        # Documentation & Option Trim
        c_t1, c_t2 = st.columns(2)
        with c_t1:
            doc_options = ["Plate Number (ផ្លាកលេខ)", "Tax Paper (ក្រដាសពន្ធ)"]
            cur_doc = st.session_state["pred_doc"]
            doc_idx = doc_options.index(cur_doc) if cur_doc in doc_options else 0
            doc_status = st.radio(
                "Documentation Status (ពន្ធ)",
                options=doc_options,
                index=doc_idx,
                horizontal=True,
            )
            st.session_state["pred_doc"] = doc_status
            is_plate = 1 if "Plate" in doc_status else 0
        with c_t2:
            has_full_opt = st.checkbox("Full Option Trim (អុបសិនពេញ)", value=bool(st.session_state["pred_full_opt"]))
            st.session_state["pred_full_opt"] = has_full_opt

        # Color & Province
        c_loc1, c_loc2 = st.columns(2)
        with c_loc1:
            color_list = ["White", "Silver", "Black", "Gray", "Gold", "Blue", "Red"]
            cur_color = st.session_state["pred_color"]
            color_idx = color_list.index(cur_color) if cur_color in color_list else 0
            selected_color = st.selectbox("Color (ពណ៌)", options=color_list, index=color_idx)
            st.session_state["pred_color"] = selected_color
        with c_loc2:
            prov_list = ["Phnom Penh", "Kandal", "Siem Reap", "Battambang", "Banteay Meanchey", "Sihanoukville", "Kampong Cham", "Other"]
            cur_prov = st.session_state["pred_prov"]
            prov_idx = prov_list.index(cur_prov) if cur_prov in prov_list else 0
            selected_prov = st.selectbox("Location (រាជធានី/ខេត្ត)", options=prov_list, index=prov_idx)
            st.session_state["pred_prov"] = selected_prov

        st.markdown(
            """
            <div style='background: #f8fafc; border: 1px solid #e2e8f0; border-left: 3px solid #2563eb;
                        border-radius: 6px; padding: 10px 14px; font-size: 0.74rem; color: #475569; margin-top: 14px; line-height: 1.5;'>
                💡 <b>Day-0 Specification Architecture</b>: In Cambodian classifieds, ~94% of sellers omit mileage and engine displacement. This production model evaluates verified Day-0 physical attributes with peer-consensus imputation across brand/model/year groups.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        if st.button("🎯 Recalculate Fair Valuation", type="primary", use_container_width=True):
            st.rerun()

    # ── Output Column: Live Appraisal Display ─────────────────────────────────
    with col_output:
        # Run ML Inference dynamically
        pred = prediction_service.predict_price(
            vehicle_brand=selected_brand,
            vehicle_model=selected_model,
            vehicle_year=selected_year,
            vehicle_body_type=selected_body,
            vehicle_fuel_type=selected_fuel,
            vehicle_transmission=selected_trans,
            vehicle_color=selected_color,
            vehicle_condition="used",
            vehicle_province=selected_prov,
            is_plate_number=is_plate,
            has_full_option=1 if has_full_opt else 0,
        )

        comparison = prediction_service.compare_to_market(
            vehicle_brand=selected_brand,
            vehicle_model=selected_model,
            predicted_price=pred["fair_price"],
        )

        xai = prediction_service.explain_prediction(
            vehicle_brand=selected_brand,
            vehicle_model=selected_model,
            vehicle_year=selected_year,
            vehicle_body_type=selected_body,
            vehicle_fuel_type=selected_fuel,
            vehicle_transmission=selected_trans,
            vehicle_color=selected_color,
            vehicle_condition="used",
            vehicle_province=selected_prov,
            is_plate_number=is_plate,
            has_full_option=1 if has_full_opt else 0,
        )

        fair_price = pred["fair_price"]
        low_p = pred["low_range"]
        high_p = pred["high_range"]
        market_med = comparison["market_median"]
        p25_p = comparison.get("p25_price", market_med * 0.85)
        p75_p = comparison.get("p75_price", market_med * 1.15)
        diff_usd = comparison["diff_usd"]
        diff_pct = comparison["diff_pct"]
        pos_badge = comparison["pos_badge"]
        pos_color = comparison["pos_color"]
        pos_text = comparison["position"]
        smear_val = pred.get("smearing_factor", 1.0452)

        diff_sign = "+" if diff_usd >= 0 else "-"

        # ── 1. Hero Valuation Display Card ────────────────────────────────────
        st.markdown(
            f"""
            <div style='background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                        border-radius: 10px; padding: 22px 24px; color: #ffffff;
                        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15); margin-bottom: 14px;'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size: 0.75rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.8px;'>
                        Estimated Fair Market Price
                    </span>
                    <div style='display: flex; gap: 6px;'>
                        <span style='background: rgba(37,99,235,0.3); border: 1px solid rgba(37,99,235,0.6); padding: 3px 10px; border-radius: 20px; font-size: 0.70rem; color: #93c5fd;'>
                            Duan's Smearing: {smear_val:.4f}
                        </span>
                        <span style='background: rgba(255,255,255,0.12); padding: 3px 10px; border-radius: 20px; font-size: 0.70rem; color: #cbd5e1;'>
                            {pred['model_name']}
                        </span>
                    </div>
                </div>
                <div style='font-size: 2.75rem; font-weight: 900; color: #ffffff; margin: 8px 0 4px 0; letter-spacing: -1px;'>
                    ${fair_price:,.0f} <span style='font-size: 1.1rem; font-weight: 500; color: #94a3b8;'>USD</span>
                </div>
                <div style='font-size: 0.82rem; color: #cbd5e1;'>
                    Calibrated Valuation Range (±14.3% Holdout MAPE): <b style='color: #60a5fa;'>${low_p:,.0f} – ${high_p:,.0f} USD</b>
                </div>
                <div style='height: 1px; background: rgba(255,255,255,0.1); margin: 14px 0;'></div>
                <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;'>
                    <div>
                        <div style='font-size: 0.70rem; color: #94a3b8;'>Market Valuation Position ({selected_prov})</div>
                        <div style='font-size: 0.85rem; font-weight: 700; color: {pos_color};'>{pos_badge} {pos_text}</div>
                    </div>
                    <div style='text-align: right;'>
                        <div style='font-size: 0.70rem; color: #94a3b8;'>Model Median Delta</div>
                        <div style='font-size: 0.85rem; font-weight: 700; color: #ffffff;'>
                            {diff_sign}${abs(diff_usd):,.0f} ({diff_sign}{abs(diff_pct):.1f}%)
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── 2. Visual Market Distribution Gauge ───────────────────────────────
        st.markdown(
            f"""
            <div style='background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                    <span style='font-size: 0.72rem; font-weight: 800; color: #475569; text-transform: uppercase; letter-spacing: 0.5px;'>
                        📊 Model Market Distribution ({selected_brand} {selected_model})
                    </span>
                    <span style='font-size: 0.72rem; font-weight: 600; color: #2563eb;'>
                        {comparison['active_listings']:,} Active Market Listings
                    </span>
                </div>
                <div style='display: flex; justify-content: space-between; font-size: 0.75rem; color: #334155; margin-bottom: 4px;'>
                    <span>25th Pct: <b>${p25_p:,.0f}</b></span>
                    <span>Median: <b>${market_med:,.0f}</b></span>
                    <span>75th Pct: <b>${p75_p:,.0f}</b></span>
                </div>
                <div style='background: #e2e8f0; border-radius: 6px; height: 10px; width: 100%; position: relative; overflow: hidden; margin: 6px 0;'>
                    <div style='position: absolute; left: 0; width: 100%; height: 100%; background: linear-gradient(90deg, #10b981 0%, #3b82f6 50%, #f59e0b 100%); opacity: 0.85;'></div>
                </div>
                <div style='display: flex; justify-content: space-between; font-size: 0.68rem; color: #64748b;'>
                    <span>🟢 Value Spectrum</span>
                    <span>🔵 Market Core</span>
                    <span>🟡 Premium Spec</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── 3. Commercial Negotiation Strategy Guidance ───────────────────────
        seller_target = round(fair_price * 1.05, -1)
        buyer_target = round(fair_price * 0.95, -1)
        is_high_liquid = selected_brand in ["Toyota", "Lexus", "Ford"] or comparison["active_listings"] >= 100
        liquid_text = "⚡ High Resale Liquidity" if is_high_liquid else "⏳ Standard Liquidity"
        liquid_desc = "Rapid turnover (10–25 days on market)" if is_high_liquid else "Niche market demand profile"

        neg1, neg2 = st.columns(2)
        with neg1:
            st.markdown(
                f"""
                <div style='background: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #10b981; border-radius: 6px; padding: 12px 14px;'>
                    <div style='font-size: 0.70rem; font-weight: 800; color: #047857; text-transform: uppercase;'>
                        🏷️ Seller Asking Target
                    </div>
                    <div style='font-size: 1.15rem; font-weight: 900; color: #0f172a; margin-top: 2px;'>
                        ${seller_target:,.0f} <span style='font-size: 0.75rem; font-weight: 600; color: #64748b;'>USD</span>
                    </div>
                    <div style='font-size: 0.70rem; color: #64748b; margin-top: 2px;'>
                        +5% cushion for negotiation headroom
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with neg2:
            st.markdown(
                f"""
                <div style='background: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid #3b82f6; border-radius: 6px; padding: 12px 14px;'>
                    <div style='font-size: 0.70rem; font-weight: 800; color: #1d4ed8; text-transform: uppercase;'>
                        🤝 Buyer Counter-Offer
                    </div>
                    <div style='font-size: 1.15rem; font-weight: 900; color: #0f172a; margin-top: 2px;'>
                        ${buyer_target:,.0f} <span style='font-size: 0.75rem; font-weight: 600; color: #64748b;'>USD</span>
                    </div>
                    <div style='font-size: 0.70rem; color: #64748b; margin-top: 2px;'>
                        -5% target to anchor around fair value
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ── 4. Explainable AI: SHAP Contribution Breakdown ───────────────────
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        st.markdown(
            config.section_header(
                "WHY DID THE MODEL PREDICT THIS PRICE?",
                "SHAP marginal price contributions relative to Cambodian market baseline",
            ),
            unsafe_allow_html=True,
        )

        contributions = xai["contributions"]
        pos_contribs = [c for c in contributions if c["impact_usd"] > 0]
        neg_contribs = [c for c in contributions if c["impact_usd"] < 0]

        top_pos = pos_contribs[0] if pos_contribs else None
        top_neg = neg_contribs[0] if neg_contribs else None

        if top_pos and top_neg:
            narrative = f"This appraisal is primarily elevated by <b>{top_pos['feature']}</b> (+${top_pos['impact_usd']:,.0f}) and offset by <b>{top_neg['feature']}</b> (-${abs(top_neg['impact_usd']):,.0f}) relative to baseline."
        elif top_pos:
            narrative = f"This appraisal is elevated across key attributes, led by <b>{top_pos['feature']}</b> (+${top_pos['impact_usd']:,.0f})."
        elif top_neg:
            narrative = f"This appraisal reflects significant market discount primarily due to <b>{top_neg['feature']}</b> (-${abs(top_neg['impact_usd']):,.0f})."
        else:
            narrative = "This vehicle aligns closely with standard market baseline specifications."

        st.markdown(
            f"""
            <div style='background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 10px 14px; font-size: 0.78rem; color: #1e3a8a; margin-bottom: 10px;'>
                💡 {narrative}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Plotly Horizontal Bar Chart
        feat_names = [c["feature"] for c in reversed(contributions)]
        feat_impacts = [c["impact_usd"] for c in reversed(contributions)]
        bar_colors = ["#10b981" if imp >= 0 else "#ef4444" for imp in feat_impacts]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                y=feat_names,
                x=feat_impacts,
                orientation="h",
                marker_color=bar_colors,
                text=[f"{'+' if v>=0 else ''}${v:,.0f}" for v in feat_impacts],
                textposition="outside",
                cliponaxis=False,
            )
        )

        config.apply_plot_theme(
            fig,
            height=260,
            show_legend=False,
            xaxis_title="Marginal Price Impact (USD)",
        )
        fig.update_xaxes(zeroline=True, zerolinecolor="#64748b", zerolinewidth=1.5)
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "📌 **Methodological Note**: SHAP values explain each feature's marginal attribution to this specific "
            "prediction relative to the market baseline vehicle ($18,450 USD). They do not establish causal effects."
        )

        # ── 5. Real Comparable Market Listings ────────────────────────────────
        similar_df = duckdb_service.get_similar_market_listings(selected_brand, selected_model, limit=4)
        if not similar_df.empty:
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            st.markdown(
                config.section_header(
                    "RECENT COMPARABLE MARKET LISTINGS",
                    f"Live verified listings of {selected_brand} {selected_model} currently in analytical lakehouse",
                ),
                unsafe_allow_html=True,
            )
            st.dataframe(
                similar_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Asking Price (USD)": st.column_config.NumberColumn("Price", format="$%d"),
                },
            )
