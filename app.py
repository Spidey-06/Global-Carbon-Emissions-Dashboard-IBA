from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Carbon Footprint Analytics",
    page_icon="🌍",
    layout="wide",
)

DATA_PATH = Path(__file__).parent / "owid_co2_cleaned_1990_2024.csv"

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.08);
        padding: 16px;
        border-radius: 12px;
        border: 1px solid rgba(128, 128, 128, 0.18);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# LOAD AND PREPARE DATA
# --------------------------------------------------

@st.cache_data
def load_data(file_path):
    df = pd.read_csv(file_path)

    df.columns = df.columns.str.strip()

    if "country" not in df.columns or "year" not in df.columns:
        raise ValueError("The dataset must contain 'country' and 'year' columns.")

    df["country"] = df["country"].astype("string").str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")

    numeric_columns = [
        col for col in df.columns
        if col not in ["country", "iso_code", "entity_type"]
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["country", "year"])
    df["year"] = df["year"].astype(int)

    # Classify rows using the source's ISO-code field.
    # This is a practical filter, not a definitive geopolitical classification.
    if "iso_code" in df.columns:
        df["iso_code"] = df["iso_code"].astype("string").str.strip()
        df["entity_type"] = df["iso_code"].apply(
            lambda value: (
                "Country or territory"
                if pd.notna(value)
                and value not in ["", "OWID_WRL", "OWID_KOS"]
                else "Aggregate or special entity"
            )
        )
    else:
        df["entity_type"] = "Aggregate or special entity"

    return df


try:
    df = load_data(DATA_PATH)
except Exception as error:
    st.error(f"Could not load the dataset: {error}")
    st.stop()


if "co2" not in df.columns:
    st.error("The dataset does not contain the required 'co2' column.")
    st.stop()


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def format_number(value, decimals=2):
    if pd.isna(value):
        return "N/A"
    return f"{value:,.{decimals}f}"


def format_emissions(value):
    """Display emissions in million tonnes when source values are in million tonnes."""
    if pd.isna(value):
        return "N/A"
    return f"{value:,.2f} Mt"


def get_world_data(data):
    """Use the World aggregate for global-level charts where available."""
    world = data[data["country"].str.lower() == "world"].copy()
    return world.sort_values("year")


def get_country_data(data):
    """Exclude aggregates and special entities from country comparisons."""
    countries = data[
        data["entity_type"] == "Country or territory"
    ].copy()

    return countries


def percent_change(current, previous):
    if pd.isna(current) or pd.isna(previous) or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100


def change_label(current, previous):
    change = percent_change(current, previous)

    if change is None:
        return "Year-over-year change unavailable"

    direction = "increase" if change > 0 else "decrease" if change < 0 else "no change"
    return f"{abs(change):.2f}% {direction} vs. previous year"


def get_latest_value(data, column, year):
    if column not in data.columns:
        return float("nan")

    rows = data[data["year"] == year]
    if rows.empty:
        return float("nan")

    values = rows[column].dropna()
    return values.iloc[0] if not values.empty else float("nan")


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.title("🌍 Global Carbon Emissions & Climate Sustainability")
st.caption(
    "Explore global CO₂ trends, compare countries, analyse emission sources, "
    "and identify sustainability insights."
)

st.markdown(
    "Source: Our World in Data — CO₂ and Greenhouse Gas Emissions dataset."
)


# --------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------

st.sidebar.header("Dashboard Filters")

minimum_year = int(df["year"].min())
maximum_year = int(df["year"].max())

year_range = st.sidebar.slider(
    "Analysis period",
    min_value=minimum_year,
    max_value=maximum_year,
    value=(max(minimum_year, 1990), maximum_year),
    step=1,
)

countries_df = get_country_data(df)
country_names = sorted(countries_df["country"].dropna().unique().tolist())

default_countries = [
    country for country in ["India", "United States", "China"]
    if country in country_names
]

selected_countries = st.sidebar.multiselect(
    "Countries to compare",
    options=country_names,
    default=default_countries,
    help="Choose one or more countries or territories for comparison.",
)

metric_options = {
    "Total CO₂ emissions": "co2",
    "CO₂ emissions per capita": "co2_per_capita",
    "CO₂ including land-use change": "co2_including_luc",
    "Coal-related CO₂": "coal_co2",
    "Oil-related CO₂": "oil_co2",
    "Gas-related CO₂": "gas_co2",
    "Cement-related CO₂": "cement_co2",
}

available_metrics = {
    label: column
    for label, column in metric_options.items()
    if column in df.columns
}

selected_metric_label = st.sidebar.selectbox(
    "Metric for rankings and comparisons",
    options=list(available_metrics.keys()),
    index=0,
)

selected_metric = available_metrics[selected_metric_label]

period_start, period_end = year_range

period_df = df[
    df["year"].between(period_start, period_end)
].copy()

country_period = get_country_data(period_df)
world_period = get_world_data(period_df)

if selected_metric not in country_period.columns:
    st.error(f"The selected metric '{selected_metric}' is unavailable.")
    st.stop()


# --------------------------------------------------
# NAVIGATION
# --------------------------------------------------

overview_tab, comparison_tab, sources_tab, insights_tab = st.tabs(
    [
        "🌎 Global Overview",
        "📊 Country Comparison",
        "🏭 Emission Sources",
        "💡 Sustainability Insights",
    ]
)


# ==================================================
# TAB 1: GLOBAL OVERVIEW
# ==================================================

with overview_tab:
    st.subheader("Global emissions at a glance")

    latest_world = world_period[
        world_period["year"] == period_end
    ]

    previous_world = world_period[
        world_period["year"] == period_end - 1
    ]

    global_co2 = get_latest_value(world_period, "co2", period_end)
    previous_global_co2 = get_latest_value(
        world_period, "co2", period_end - 1
    )
    global_per_capita = get_latest_value(
        world_period, "co2_per_capita", period_end
    )

    emissions_change = percent_change(
        global_co2, previous_global_co2
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        f"Global CO₂ ({period_end})",
        format_emissions(global_co2),
        delta=(
            f"{emissions_change:+.2f}% YoY"
            if emissions_change is not None
            else None
        ),
        help="World aggregate CO₂ emissions for the selected end year.",
    )

    col2.metric(
        f"Global CO₂ per capita ({period_end})",
        (
            f"{global_per_capita:.2f} tonnes"
            if pd.notna(global_per_capita)
            else "N/A"
        ),
        help="World aggregate annual CO₂ emissions per person.",
    )

    ranked_countries = country_period[
        (country_period["year"] == period_end)
        & country_period[selected_metric].notna()
    ].copy()

    top_country = (
        ranked_countries.sort_values(
            selected_metric, ascending=False
        ).head(1)
    )

    if not top_country.empty:
        top_country_name = top_country.iloc[0]["country"]
        top_country_value = top_country.iloc[0][selected_metric]
    else:
        top_country_name = "N/A"
        top_country_value = float("nan")

    col3.metric(
        f"Top country ({period_end})",
        top_country_name,
        help=f"Ranked by {selected_metric_label.lower()}.",
    )

    col4.metric(
        "Countries/territories with data",
        f"{ranked_countries['country'].nunique():,}",
        help="Count of countries or territories with non-missing selected metric data.",
    )

    st.divider()

    left, right = st.columns(2)

    with left:
        st.markdown("#### Global CO₂ emissions over time")

        global_trend = world_period[
            world_period["co2"].notna()
        ].sort_values("year")

        if not global_trend.empty:
            fig = px.line(
                global_trend,
                x="year",
                y="co2",
                markers=True,
                labels={
                    "year": "Year",
                    "co2": "CO₂ emissions (million tonnes)",
                },
            )
            fig.update_layout(
                height=380,
                margin=dict(l=10, r=10, t=20, b=10),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("World aggregate CO₂ data is unavailable for this period.")

    with right:
        st.markdown(f"#### Top 10 countries by {selected_metric_label.lower()}")

        top_10 = (
            ranked_countries.sort_values(
                selected_metric, ascending=False
            ).head(10).sort_values(selected_metric)
        )

        if not top_10.empty:
            fig = px.bar(
                top_10,
                x=selected_metric,
                y="country",
                orientation="h",
                labels={
                    selected_metric: selected_metric_label,
                    "country": "Country or territory",
                },
                hover_data={selected_metric: ":,.2f"},
            )
            fig.update_layout(
                height=380,
                margin=dict(l=10, r=10, t=20, b=10),
                yaxis_title="",
                xaxis_title=selected_metric_label,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No country-level data is available for this ranking.")

    st.caption(
        "Note: emissions are shown in the units provided by Our World in Data. "
        "The global trend uses the World aggregate; country rankings exclude aggregates."
    )


# ==================================================
# TAB 2: COUNTRY COMPARISON
# ==================================================

with comparison_tab:
    st.subheader("Compare national emissions")

    if not selected_countries:
        st.info("Select at least one country in the sidebar to view comparisons.")
    else:
        comparison_df = country_period[
            country_period["country"].isin(selected_countries)
        ].copy()

        line_data = comparison_df[
            comparison_df[selected_metric].notna()
        ].sort_values("year")

        st.markdown(f"#### {selected_metric_label} over time")

        if not line_data.empty:
            fig = px.line(
                line_data,
                x="year",
                y=selected_metric,
                color="country",
                markers=True,
                labels={
                    "year": "Year",
                    selected_metric: selected_metric_label,
                    "country": "Country",
                },
            )
            fig.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=20, b=10),
                legend_title_text="Country",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data is available for the selected countries and metric.")

        left, right = st.columns(2)

        with left:
            st.markdown(f"#### Country ranking ({period_end})")

            ranking = comparison_df[
                comparison_df["year"] == period_end
            ][["country", selected_metric]].dropna()

            ranking = ranking.sort_values(
                selected_metric, ascending=False
            )

            if not ranking.empty:
                fig = px.bar(
                    ranking,
                    x="country",
                    y=selected_metric,
                    color="country",
                    labels={
                        "country": "Country",
                        selected_metric: selected_metric_label,
                    },
                )
                fig.update_layout(
                    height=350,
                    showlegend=False,
                    margin=dict(l=10, r=10, t=20, b=10),
                    xaxis_title="",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"No ranking data available for {period_end}.")

        with right:
            st.markdown(f"#### Per-capita comparison ({period_end})")

            if "co2_per_capita" in comparison_df.columns:
                per_capita = comparison_df[
                    comparison_df["year"] == period_end
                ][["country", "co2_per_capita"]].dropna()

                per_capita = per_capita.sort_values(
                    "co2_per_capita", ascending=False
                )

                if not per_capita.empty:
                    fig = px.bar(
                        per_capita,
                        x="country",
                        y="co2_per_capita",
                        color="country",
                        labels={
                            "country": "Country",
                            "co2_per_capita": "CO₂ per capita (tonnes)",
                        },
                    )
                    fig.update_layout(
                        height=350,
                        showlegend=False,
                        margin=dict(l=10, r=10, t=20, b=10),
                        xaxis_title="",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"No per-capita data available for {period_end}.")
            else:
                st.info("Per-capita emissions are not available in this dataset.")

        st.markdown("#### Comparison table")

        table_columns = [
            col for col in [
                "country",
                "year",
                "co2",
                "co2_per_capita",
                "co2_including_luc",
                "population",
                "gdp",
            ]
            if col in comparison_df.columns
        ]

        latest_table = comparison_df[
            comparison_df["year"] == period_end
        ][table_columns].copy()

        latest_table = latest_table.rename(
            columns={
                "country": "Country",
                "year": "Year",
                "co2": "CO₂ emissions",
                "co2_per_capita": "CO₂ per capita",
                "co2_including_luc": "CO₂ including land-use change",
                "population": "Population",
                "gdp": "GDP",
            }
        )

        st.dataframe(
            latest_table,
            use_container_width=True,
            hide_index=True,
        )


# ==================================================
# TAB 3: EMISSION SOURCES
# ==================================================

with sources_tab:
    st.subheader("Where do emissions come from?")

    source_columns = {
        "Coal": "coal_co2",
        "Oil": "oil_co2",
        "Gas": "gas_co2",
        "Cement": "cement_co2",
        "Flaring": "flaring_co2",
        "Other industry": "other_industry_co2",
    }

    available_sources = {
        label: column
        for label, column in source_columns.items()
        if column in df.columns
    }

    if not available_sources:
        st.warning("The dataset does not contain the expected source-level columns.")
    else:
        source_country_options = sorted(
            countries_df["country"].dropna().unique().tolist()
        )

        default_source_country = (
            "India" if "India" in source_country_options
            else source_country_options[0] if source_country_options
            else None
        )

        selected_source_country = st.selectbox(
            "Select a country",
            options=source_country_options,
            index=(
                source_country_options.index(default_source_country)
                if default_source_country is not None
                else 0
            ),
        )

        source_country_data = country_period[
            country_period["country"] == selected_source_country
        ].copy()

        if source_country_data.empty:
            st.info("No data is available for this country in the selected period.")
        else:
            source_year_options = sorted(
                source_country_data["year"].dropna().unique().tolist()
            )

            if source_year_options:
                default_source_year = (
                    period_end if period_end in source_year_options
                    else max(source_year_options)
                )

                selected_source_year = st.selectbox(
                    "Year for source breakdown",
                    options=source_year_options,
                    index=source_year_options.index(default_source_year),
                )

                selected_source_row = source_country_data[
                    source_country_data["year"] == selected_source_year
                ]

                if not selected_source_row.empty:
                    source_values = []

                    for label, column in available_sources.items():
                        value = selected_source_row.iloc[0][column]
                        if pd.notna(value):
                            source_values.append(
                                {"Source": label, "CO₂ emissions": value}
                            )

                    source_df = pd.DataFrame(source_values)

                    if not source_df.empty:
                        left, right = st.columns(2)

                        with left:
                            st.markdown("#### Emission source distribution")
                            fig = px.pie(
                                source_df,
                                names="Source",
                                values="CO₂ emissions",
                                hole=0.45,
                            )
                            fig.update_layout(
                                height=380,
                                margin=dict(l=10, r=10, t=20, b=10),
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        with right:
                            st.markdown("#### Emissions by source")
                            source_bar = source_df.sort_values(
                                "CO₂ emissions", ascending=True
                            )
                            fig = px.bar(
                                source_bar,
                                x="CO₂ emissions",
                                y="Source",
                                orientation="h",
                                labels={
                                    "CO₂ emissions": "CO₂ emissions (million tonnes)",
                                    "Source": "Source",
                                },
                            )
                            fig.update_layout(
                                height=380,
                                margin=dict(l=10, r=10, t=20, b=10),
                            )
                            st.plotly_chart(fig, use_container_width=True)

                        dominant_source = source_df.sort_values(
                            "CO₂ emissions", ascending=False
                        ).iloc[0]

                        st.info(
                            f"In {selected_source_year}, **{dominant_source['Source']}** "
                            f"was the largest among the available source categories for "
                            f"{selected_source_country}, at "
                            f"**{format_emissions(dominant_source['CO₂ emissions'])}**."
                        )

                        st.caption(
                            "Source categories may not add up to total CO₂ emissions. "
                            "Missing source values are omitted, not treated as zero."
                        )
                    else:
                        st.info(
                            "No source breakdown is available for this country and year."
                        )


# ==================================================
# TAB 4: SUSTAINABILITY INSIGHTS
# ==================================================

with insights_tab:
    st.subheader("Sustainability insights")
    st.caption(
        "Insights are calculated from the selected period and available country-level data."
    )

    insight_countries = get_country_data(period_df)

    # Compare the first and last years selected by the user.
    first_year_data = insight_countries[
        insight_countries["year"] == period_start
    ][["country", selected_metric]].rename(
        columns={selected_metric: "start_value"}
    )

    last_year_data = insight_countries[
        insight_countries["year"] == period_end
    ][["country", selected_metric]].rename(
        columns={selected_metric: "end_value"}
    )

    changes = first_year_data.merge(
        last_year_data, on="country", how="inner"
    ).dropna(subset=["start_value", "end_value"])

    changes = changes[
        changes["start_value"] != 0
    ].copy()

    if not changes.empty:
        changes["percentage_change"] = (
            (changes["end_value"] - changes["start_value"])
            / changes["start_value"].abs()
        ) * 100

        increases = changes[
            changes["percentage_change"] > 0
        ].sort_values("percentage_change", ascending=False)

        decreases = changes[
            changes["percentage_change"] < 0
        ].sort_values("percentage_change", ascending=True)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown(
                f"#### Largest percentage increase "
                f"({period_start}–{period_end})"
            )

            if not increases.empty:
                row = increases.iloc[0]
                st.metric(
                    row["country"],
                    f"{row['percentage_change']:+.2f}%",
                    help=f"Change in {selected_metric_label.lower()} between the selected start and end years.",
                )
            else:
                st.info("No positive changes could be calculated.")

        with col2:
            st.markdown(
                f"#### Largest percentage decrease "
                f"({period_start}–{period_end})"
            )

            if not decreases.empty:
                row = decreases.iloc[0]
                st.metric(
                    row["country"],
                    f"{row['percentage_change']:+.2f}%",
                    help=f"Change in {selected_metric_label.lower()} between the selected start and end years.",
                )
            else:
                st.info("No negative changes could be calculated.")

        st.markdown("#### Countries with the largest changes")

        change_table = changes.sort_values(
            "percentage_change", ascending=False
        ).copy()

        change_table = change_table.rename(
            columns={
                "country": "Country",
                "start_value": f"Value in {period_start}",
                "end_value": f"Value in {period_end}",
                "percentage_change": "Percentage change (%)",
            }
        )

        st.dataframe(
            change_table[
                [
                    "Country",
                    f"Value in {period_start}",
                    f"Value in {period_end}",
                    "Percentage change (%)",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info(
            "There is insufficient comparable data at both ends of the selected period "
            "to calculate country-level percentage changes."
        )

    st.divider()

    st.markdown("#### What the indicators tell us")

    st.markdown(
        """
        - **Total CO₂ emissions** help identify countries contributing the largest
          absolute emissions.
        - **CO₂ per capita** helps compare emissions relative to population size.
        - **Emission-source breakdowns** show which reported fuel or industrial
          categories contribute most to a country's emissions.
        - **Changes over time** help identify where emissions increased or decreased
          during the selected period.

        These indicators describe emissions patterns. They do not, by themselves,
        establish the causes of those changes or prove that a particular policy was effective.
        """
    )

    with st.expander("Data quality and methodology"):
        st.write(
            "This dashboard uses the Our World in Data CO₂ dataset. "
            "Country-level comparisons exclude aggregate and special-entity rows "
            "where the ISO-code field does not identify a country or territory."
        )

        st.write(
            "Missing observations are preserved as missing values. They are not "
            "automatically replaced with zero. Charts use the available observations "
            "for the selected metric and period."
        )

        st.write(
            "The source dataset contains multiple emissions indicators. Their units "
            "and definitions may differ, so indicators should not be treated as "
            "interchangeable. Check the original dataset documentation before "
            "interpreting or comparing individual measures."
        )

        missingness = (
            period_df.isna()
            .mean()
            .mul(100)
            .sort_values(ascending=False)
            .rename("Missing values (%)")
            .reset_index()
        )

        missingness.columns = ["Column", "Missing values (%)"]

        st.markdown("**Missing values by column**")
        st.dataframe(
            missingness.head(20).round(2),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("**Dataset coverage**")
        st.write(f"Rows in selected period: {len(period_df):,}")
        st.write(f"Distinct entities: {period_df['country'].nunique():,}")
        st.write(f"Years covered: {period_start}–{period_end}")

        st.markdown(
            "[Open the Our World in Data CO₂ dataset and documentation]"
            "(https://github.com/owid/co2-data)"
        )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "Academic project | Global Carbon Emissions and Climate Sustainability Analytics Dashboard"
)

st.caption(
    "Data source: Our World in Data — "
    "https://github.com/owid/co2-data"
)