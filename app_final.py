from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Global Carbon Emissions Analytics", page_icon="🌍", layout="wide")
DATA_PATH = Path(__file__).parent / "owid_co2_cleaned_1990_2024.csv"

METRICS = {
    "Total CO₂ emissions": "co2",
    "CO₂ emissions per capita": "co2_per_capita",
    "CO₂ including land-use change": "co2_including_luc",
    "Coal-related CO₂": "coal_co2",
    "Oil-related CO₂": "oil_co2",
    "Gas-related CO₂": "gas_co2",
    "Cement-related CO₂": "cement_co2",
}
SOURCES = {
    "Coal": "coal_co2", "Oil": "oil_co2", "Gas": "gas_co2",
    "Cement": "cement_co2", "Flaring": "flaring_co2",
    "Other industry": "other_industry_co2",
}

st.markdown("""
<style>
.block-container {padding-top:1.4rem;padding-bottom:2rem;}
div[data-testid="stMetric"] {
background:rgba(128,128,128,.08);padding:14px;border-radius:10px;
border:1px solid rgba(128,128,128,.18);}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data(path):
    d = pd.read_csv(path)
    d.columns = d.columns.str.strip()
    if not {"country", "year"}.issubset(d.columns):
        raise ValueError("CSV must contain 'country' and 'year' columns.")
    d["country"] = d["country"].astype("string").str.strip()
    d["year"] = pd.to_numeric(d["year"], errors="coerce")
    d = d.dropna(subset=["country", "year"]).copy()
    d["year"] = d["year"].astype(int)
    for c in d.columns:
        if c not in ["country", "iso_code", "entity_type"]:
            d[c] = pd.to_numeric(d[c], errors="coerce")

    # Prefer ISO-3 country/territory codes. OWID aggregate codes are not ISO-3.
    if "iso_code" in d.columns:
        iso = d["iso_code"].astype("string").str.strip().str.upper()
        d["is_country"] = iso.str.fullmatch(r"[A-Z]{3}", na=False)
    elif "entity_type" in d.columns:
        label = (d["entity_type"].astype("string").str.strip().str.lower()
                 .str.replace(" ", "_", regex=False))
        d["is_country"] = label.isin(["country_or_territory", "country", "territory"])
    else:
        d["is_country"] = False
    return d


def val(data, year, col):
    if col not in data.columns:
        return float("nan")
    x = data.loc[data["year"].eq(year), col].dropna()
    return x.iloc[0] if len(x) else float("nan")


def fmt(x, n=2):
    return "N/A" if pd.isna(x) else f"{x:,.{n}f}"


def fmt_mt(x):
    return "N/A" if pd.isna(x) else f"{x:,.2f} Mt"


def pct(start, end):
    if pd.isna(start) or pd.isna(end) or start == 0:
        return None
    return (end - start) / abs(start) * 100


def compare_period(data, metric, start, end):
    a = data.loc[data.year.eq(start), ["country", metric]].rename(columns={metric: "start_value"})
    b = data.loc[data.year.eq(end), ["country", metric]].rename(columns={metric: "end_value"})
    out = a.merge(b, on="country", how="inner").dropna(subset=["start_value", "end_value"]).copy()
    out["absolute_change"] = out["end_value"] - out["start_value"]
    out["percentage_change"] = out.apply(lambda r: pct(r.start_value, r.end_value), axis=1)
    return out


try:
    df = load_data(str(DATA_PATH))
except Exception as e:
    st.error(f"Could not load the dataset: {e}")
    st.info("Keep owid_co2_cleaned_1990_2024.csv in the same folder as app_final.py.")
    st.stop()

if "co2" not in df.columns:
    st.error("The CSV does not contain the required 'co2' column.")
    st.stop()

countries = df[df["is_country"]].copy()
world = df[df["country"].astype(str).str.lower().eq("world")].copy()
if countries.empty:
    st.error("No country rows identified. This app checks ISO-3 codes such as IND, USA, CHN and excludes aggregate codes such as OWID_WRL.")
    if "iso_code" in df:
        st.write("Sample ISO codes:", df["iso_code"].dropna().astype(str).unique()[:30].tolist())
    st.stop()

st.title("🌍 Global Carbon Emissions & Climate Sustainability")
st.caption("Explore global trends, compare countries, analyse emission sources, and discover evidence-based findings.")
st.caption("Data source: Our World in Data — CO₂ and Greenhouse Gas Emissions.")

min_year, max_year = int(df.year.min()), int(df.year.max())
st.sidebar.header("Dashboard Filters")
period_default = (max(min_year, 1990), max_year)
start, end = st.sidebar.slider("Analysis period", min_year, max_year, period_default, step=1)
country_names = sorted(countries.country.dropna().unique().tolist())
defaults = [x for x in ["India", "United States", "China"] if x in country_names]
selected_countries = st.sidebar.multiselect("Countries to compare", country_names, default=defaults)
metrics = {label: col for label, col in METRICS.items() if col in df.columns}
metric_label = st.sidebar.selectbox("Metric for rankings and comparisons", list(metrics))
metric = metrics[metric_label]

period = df[df.year.between(start, end)].copy()
pcountries = period[period.is_country].copy()
pworld = period[period.country.astype(str).str.lower().eq("world")].copy()
st.sidebar.caption("Global indicators use the World aggregate; country comparisons exclude aggregates.")

overview, comparison, sources, insights = st.tabs([
    "🌎 Global Overview", "📊 Country Comparison", "🏭 Emission Sources", "💡 Sustainability Insights"
])

with overview:
    st.subheader("Global emissions at a glance")
    g_end, g_prev = val(pworld, end, "co2"), val(pworld, end-1, "co2")
    g_start, g_pc = val(pworld, start, "co2"), val(pworld, end, "co2_per_capita")
    yoy, total_change = pct(g_prev, g_end), pct(g_start, g_end)
    latest = pcountries[pcountries.year.eq(end) & pcountries[metric].notna()].copy()
    ranking = latest.sort_values(metric, ascending=False)
    top = ranking.iloc[0].country if not ranking.empty else "N/A"
    a,b,c,d = st.columns(4)
    a.metric(f"Global CO₂ ({end})", fmt_mt(g_end), delta=f"{yoy:+.2f}% YoY" if yoy is not None else None)
    b.metric(f"Global CO₂ per capita ({end})", f"{g_pc:.2f} tonnes" if pd.notna(g_pc) else "N/A")
    c.metric(f"Top country by {metric_label.lower()}", top)
    d.metric(f"Change since {start}", f"{total_change:+.2f}%" if total_change is not None else "N/A")
    left,right = st.columns(2)
    with left:
        st.markdown("#### Global CO₂ emissions over time")
        trend = pworld.dropna(subset=["co2"]).sort_values("year")
        if not trend.empty:
            fig = px.line(trend, x="year", y="co2", markers=True,
                          labels={"year":"Year","co2":"CO₂ emissions (million tonnes)"})
            fig.update_layout(height=380, margin=dict(t=20,b=10))
            st.plotly_chart(fig, use_container_width=True)
            peak, low = trend.loc[trend.co2.idxmax()], trend.loc[trend.co2.idxmin()]
            st.info(f"Within {start}–{end}, highest recorded global emissions were {fmt_mt(peak.co2)} in {int(peak.year)}; lowest were {fmt_mt(low.co2)} in {int(low.year)}.")
        else:
            st.info("World aggregate data is unavailable for this period.")
    with right:
        st.markdown(f"#### Top 10 countries by {metric_label.lower()}")
        top10 = ranking.head(10).sort_values(metric)
        if not top10.empty:
            fig = px.bar(top10, x=metric, y="country", orientation="h",
                         labels={metric:metric_label,"country":"Country or territory"})
            fig.update_layout(height=380, margin=dict(t=20,b=10), yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No country ranking data available.")
    if total_change is not None:
        direction = "increased" if total_change > 0 else "decreased" if total_change < 0 else "remained unchanged"
        st.markdown("#### What the global trend indicates")
        st.write(f"Global CO₂ emissions {direction} by {abs(total_change):.2f}% between {start} and {end}, based on World aggregate observations.")

with comparison:
    st.subheader("Compare national emissions")
    selected = pcountries[pcountries.country.isin(selected_countries)].copy()
    if selected.empty:
        st.info("Select at least one country in the sidebar.")
    else:
        st.markdown(f"#### {metric_label} over time")
        trend = selected.dropna(subset=[metric]).sort_values("year")
        if not trend.empty:
            fig = px.line(trend, x="year", y=metric, color="country", markers=True,
                          labels={"year":"Year",metric:metric_label,"country":"Country"})
            fig.update_layout(height=400, margin=dict(t=20,b=10))
            st.plotly_chart(fig, use_container_width=True)
        changes = compare_period(selected, metric, start, end)
        st.markdown(f"#### Change from {start} to {end}")
        if changes.empty:
            st.warning("Comparable non-missing data is unavailable at both endpoints.")
        else:
            inc = changes.sort_values("absolute_change", ascending=False).iloc[0]
            dec = changes.sort_values("absolute_change").iloc[0]
            a,b = st.columns(2)
            a.metric("Largest absolute increase", inc.country, delta=fmt(inc.absolute_change))
            b.metric("Largest absolute decrease", dec.country, delta=fmt(dec.absolute_change))
            left,right = st.columns(2)
            with left:
                fig = px.bar(changes.sort_values("absolute_change"), x="absolute_change", y="country", orientation="h",
                             labels={"absolute_change":f"Change in {metric_label}","country":"Country"})
                fig.update_layout(height=340, margin=dict(t=15,b=10))
                st.plotly_chart(fig, use_container_width=True)
            with right:
                pchanges = changes.dropna(subset=["percentage_change"]).sort_values("percentage_change")
                if not pchanges.empty:
                    fig = px.bar(pchanges, x="percentage_change", y="country", orientation="h",
                                 labels={"percentage_change":"Change (%)","country":"Country"})
                    fig.update_layout(height=340, margin=dict(t=15,b=10))
                    st.plotly_chart(fig, use_container_width=True)
            pchanges = changes.dropna(subset=["percentage_change"])
            if not pchanges.empty:
                hi = pchanges.sort_values("percentage_change", ascending=False).iloc[0]
                lo = pchanges.sort_values("percentage_change").iloc[0]
                st.info(f"Finding: {inc.country} had the largest absolute increase ({fmt(inc.absolute_change)}), while {dec.country} had the largest absolute decrease ({fmt(dec.absolute_change)}). By percentage, the largest increase was {hi.country} ({hi.percentage_change:+.2f}%) and the largest decrease was {lo.country} ({lo.percentage_change:+.2f}%).")
            display = changes.rename(columns={"country":"Country","start_value":f"Value in {start}","end_value":f"Value in {end}","absolute_change":"Absolute change","percentage_change":"Percentage change (%)"})
            st.markdown("#### Country change analysis")
            st.dataframe(display[["Country",f"Value in {start}",f"Value in {end}","Absolute change","Percentage change (%)"]].round(2), use_container_width=True, hide_index=True)
        st.markdown(f"#### Per-capita comparison ({end})")
        if "co2_per_capita" in selected.columns:
            pc = selected[selected.year.eq(end)][["country","co2_per_capita"]].dropna().sort_values("co2_per_capita",ascending=False)
            if not pc.empty:
                fig = px.bar(pc,x="country",y="co2_per_capita",color="country",
                             labels={"country":"Country","co2_per_capita":"CO₂ per capita (tonnes)"})
                fig.update_layout(height=340,showlegend=False,margin=dict(t=15,b=10))
                st.plotly_chart(fig,use_container_width=True)
        cols = [x for x in ["country","year","co2","co2_per_capita","co2_including_luc","population","gdp"] if x in selected.columns]
        latest_table = selected[selected.year.eq(end)][cols].rename(columns={
            "country":"Country","year":"Year","co2":"CO₂ emissions","co2_per_capita":"CO₂ per capita",
            "co2_including_luc":"CO₂ including land-use change","population":"Population","gdp":"GDP"})
        st.markdown("#### Latest-year comparison table")
        st.dataframe(latest_table,use_container_width=True,hide_index=True)

with sources:
    st.subheader("Where do emissions come from?")
    available = {label:col for label,col in SOURCES.items() if col in df.columns}
    options = sorted(countries.country.dropna().unique().tolist())
    if not available:
        st.warning("No source-level columns were found.")
    else:
        default_country = "India" if "India" in options else options[0]
        source_country = st.selectbox("Select a country",options,index=options.index(default_country))
        cdata = pcountries[pcountries.country.eq(source_country)].copy()
        years = sorted(cdata.year.unique().tolist())
        if years:
            default_year = end if end in years else max(years)
            sy = st.selectbox("Year for source breakdown",years,index=years.index(default_year))
            row = cdata[cdata.year.eq(sy)]
            records = [{"Source":label,"CO₂ emissions":row.iloc[0][col]} for label,col in available.items()
                       if not row.empty and pd.notna(row.iloc[0][col])]
            sd = pd.DataFrame(records)
            if sd.empty:
                st.info("No source breakdown is available for this selection.")
            else:
                total = sd["CO₂ emissions"].sum()
                sd["Share of available sources (%)"] = sd["CO₂ emissions"]/total*100 if total else float("nan")
                left,right = st.columns(2)
                with left:
                    st.markdown("#### Source distribution")
                    fig = px.pie(sd,names="Source",values="CO₂ emissions",hole=.45)
                    fig.update_layout(height=370,margin=dict(t=20,b=10))
                    st.plotly_chart(fig,use_container_width=True)
                with right:
                    st.markdown("#### Emissions by source")
                    fig = px.bar(sd.sort_values("CO₂ emissions"),x="CO₂ emissions",y="Source",orientation="h",
                                 labels={"CO₂ emissions":"CO₂ emissions (Mt)"})
                    fig.update_layout(height=370,margin=dict(t=20,b=10))
                    st.plotly_chart(fig,use_container_width=True)
                dominant = sd.sort_values("CO₂ emissions",ascending=False).iloc[0]
                st.info(f"In {sy}, {dominant['Source']} was the largest available source category for {source_country}, representing {dominant['Share of available sources (%)']:.2f}% of the available source-specific total.")
                st.markdown("#### Source contribution table")
                st.dataframe(sd.sort_values("CO₂ emissions",ascending=False).round(2),use_container_width=True,hide_index=True)
                st.markdown("#### Source trends over time")
                trend_parts = []
                for label,col in available.items():
                    part = cdata[["year",col]].dropna().rename(columns={col:"CO₂ emissions"})
                    part["Source"] = label
                    trend_parts.append(part)
                stdata = pd.concat(trend_parts,ignore_index=True) if trend_parts else pd.DataFrame()
                if not stdata.empty:
                    fig = px.line(stdata,x="year",y="CO₂ emissions",color="Source",labels={"year":"Year"})
                    fig.update_layout(height=390,margin=dict(t=20,b=10))
                    st.plotly_chart(fig,use_container_width=True)
                st.caption("Source shares use non-missing source-specific categories and may not represent shares of total emissions. Missing values are not treated as zero.")

with insights:
    st.subheader("Sustainability insights")
    st.caption("Findings update automatically when you change the period or metric.")
    global_start, global_end = val(pworld,start,"co2"), val(pworld,end,"co2")
    change = pct(global_start,global_end)
    st.markdown("#### Global trend")
    if change is None:
        st.write("Insufficient World aggregate data to calculate the period change.")
    else:
        direction = "increased" if change>0 else "decreased" if change<0 else "remained unchanged"
        st.write(f"Global CO₂ emissions {direction} by {abs(change):.2f}% between {start} and {end}, from {fmt_mt(global_start)} to {fmt_mt(global_end)}.")
    st.divider()
    st.markdown(f"#### Country-level findings: {metric_label}")
    changes = compare_period(pcountries,metric,start,end)
    if changes.empty:
        st.info("Insufficient comparable country observations at both endpoints.")
    else:
        inc = changes.sort_values("absolute_change",ascending=False).iloc[0]
        dec = changes.sort_values("absolute_change").iloc[0]
        pchanges = changes.dropna(subset=["percentage_change"])
        a,b,c = st.columns(3)
        a.metric("Largest absolute increase",inc.country,delta=fmt(inc.absolute_change))
        b.metric("Largest absolute decrease",dec.country,delta=fmt(dec.absolute_change))
        if not pchanges.empty:
            hi = pchanges.sort_values("percentage_change",ascending=False).iloc[0]
            c.metric("Largest percentage increase",hi.country,delta=f"{hi.percentage_change:+.2f}%")
        else:
            c.metric("Largest percentage increase","N/A")
        chart = changes.sort_values("absolute_change",ascending=False).head(10).sort_values("absolute_change")
        fig = px.bar(chart,x="absolute_change",y="country",orientation="h",
                     labels={"absolute_change":f"Change in {metric_label}","country":"Country"})
        fig.update_layout(height=390,margin=dict(t=15,b=10))
        st.plotly_chart(fig,use_container_width=True)
        st.info(f"Finding: {inc.country} recorded the largest absolute increase in {metric_label.lower()} among countries with data at both endpoints: {fmt(inc.absolute_change)}.")
        if not pchanges.empty:
            lo = pchanges.sort_values("percentage_change").iloc[0]
            st.write(f"By percentage, the largest increase was in {hi.country} ({hi.percentage_change:+.2f}%) and the largest decrease was in {lo.country} ({lo.percentage_change:+.2f}%). Low starting values can make percentage changes appear unusually large.")
        display = changes.rename(columns={"country":"Country","start_value":f"Value in {start}","end_value":f"Value in {end}","absolute_change":"Absolute change","percentage_change":"Percentage change (%)"})
        with st.expander("View full country findings table"):
            st.dataframe(display[["Country",f"Value in {start}",f"Value in {end}","Absolute change","Percentage change (%)"]].round(2),use_container_width=True,hide_index=True)
    st.divider()
    st.markdown("#### How to interpret the results")
    st.markdown("""
    - **Total emissions** show absolute contributions.
    - **Per-capita emissions** compare emissions relative to population.
    - **Absolute changes** measure the size of an increase or decrease.
    - **Percentage changes** measure relative growth but can be distorted by low baselines.
    - **Source breakdowns** identify the largest reported categories available.

    These are descriptive findings. They do not independently establish why emissions changed or prove the effectiveness of a policy.
    """)
    with st.expander("Data quality and methodology"):
        st.write("Country rows are identified using valid three-letter ISO codes (for example IND, USA and CHN); aggregate codes such as OWID_WRL are excluded from country comparisons.")
        st.write("Missing observations are preserved as missing, not replaced with zero. Period comparisons use entities with data at both selected endpoints.")
        st.write("Source shares use the available source-specific categories and may not equal shares of total CO₂.")
        missing = period.isna().mean().mul(100).sort_values(ascending=False).rename("Missing values (%)").reset_index()
        missing.columns = ["Column","Missing values (%)"]
        st.markdown("**Missing values by column**")
        st.dataframe(missing.head(20).round(2),use_container_width=True,hide_index=True)
        st.write(f"Rows in selected period: {len(period):,} | Entities: {period.country.nunique():,} | Years: {start}–{end}")
        st.markdown("[Our World in Data CO₂ dataset](https://github.com/owid/co2-data)")

st.divider()
st.caption("Academic capstone | Global Carbon Emissions and Climate Sustainability Analytics Dashboard")
st.caption("Data: Our World in Data — https://github.com/owid/co2-data")
