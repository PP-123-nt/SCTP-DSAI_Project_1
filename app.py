
# ============================================================
# SECTOR DEMAND FOR ENTRY-LEVEL WORKERS
# Python 3.14.7 | Streamlit 1.36.0 | Altair 5.5.0
# ============================================================

import os
import re
import json
import math
from datetime import datetime

import streamlit as st
import pandas as pd
import altair as alt
import plotly.express as px


st.set_page_config(page_title="Sector Demand for Entry Level Workers - TEST", layout="wide")
print(f"🟢 Rerun at: {datetime.now()}")

DATA_PATH = "SGJobData.csv"
DATA_MTIME = os.path.getmtime(DATA_PATH)


# ============================================================
# 1. DATA LOADING
# ============================================================

@st.cache_resource(show_spinner="Loading job data...")
def load_data(path, file_mtime):
    df = pd.read_csv(path)
    df = df.dropna(axis=1, how="all")
    remove_row = (df.isna() | df.eq(0)).all(axis=1)
    df = df.loc[~remove_row]

    df["metadata_expiryDate"] = pd.to_datetime(df["metadata_expiryDate"])
    df["metadata_newPostingDate"] = pd.to_datetime(df["metadata_newPostingDate"])
    df["metadata_originalPostingDate"] = pd.to_datetime(df["metadata_originalPostingDate"])

    df["employmentTypes"] = df["employmentTypes"].astype("category")
    df["positionLevels"] = df["positionLevels"].astype("category")

    df = df.loc[df["metadata_newPostingDate"] >= "2023-05"]

    return df


df = load_data(DATA_PATH, DATA_MTIME)


# ============================================================
# 2. SIDEBAR FILTERS AND CATEGORY EXTRACTION
# ============================================================

st.title("Sector Demand for Entry Level Workers - TEST")
st.sidebar.header("Filters")


def extract_categories(categories_str):
    if not isinstance(categories_str, str):
        return []
    try:
        items = json.loads(categories_str)
        if isinstance(items, list):
            return [item["category"] for item in items if isinstance(item, dict) and item.get("category")]
    except (TypeError, json.JSONDecodeError):
        pass
    return []


@st.cache_resource(show_spinner="Preparing sector filters...")
def get_category_lookup(path, file_mtime):
    source = load_data(path, file_mtime)
    lookup = {}

    for value in source["categories"].dropna().unique():
        lookup[value] = tuple(extract_categories(value))

    sectors = sorted({sector for values in lookup.values() for sector in values})
    return lookup, tuple(sectors)


category_lookup, unique_sectors = get_category_lookup(DATA_PATH, DATA_MTIME)

selected_sectors = st.sidebar.multiselect("Sector", list(unique_sectors), default=[])

# Reuse the original DataFrame if there is no sector filter.
filtered_df = df

# Filter using unique JSON category strings rather than parsing every row.
if selected_sectors:
    matching_categories = [raw for raw, sectors in category_lookup.items() if any(sector in sectors for sector in selected_sectors)]
    filtered_df = df.loc[df["categories"].isin(matching_categories)]

# Create a Boolean mask rather than copying the complete entry-level dataset.
entry_mask = filtered_df["positionLevels"].eq("Fresh/entry level")
entry_jobs_count = int(entry_mask.sum())


# ============================================================
# PHASE 1: MACRO ECONOMIC CLIMATE
# ============================================================

st.markdown("---")
st.header("Phase 1: Macro Economic Climate (Entry-Level Overview)")

if not filtered_df.empty:

    total_jobs_count = len(filtered_df)
    avg_entry_pct = entry_jobs_count / total_jobs_count * 100 if total_jobs_count else 0.0

    col_m1, col_m2, col_m3 = st.columns(3)

    with col_m1:
        st.metric("Total Entry-Level Postings", f"{entry_jobs_count:,}")

    with col_m2:
        total_apps = filtered_df.loc[entry_mask, "metadata_totalNumberJobApplication"].sum()
        st.metric("Total Entry-Level Applications", f"{int(total_apps):,}")

    with col_m3:
        unique_companies = filtered_df.loc[entry_mask, "postedCompany_name"].nunique()
        st.metric("Hiring Companies (Entry-Level)", f"{unique_companies:,}")

    st.markdown("---")

    # --------------------------------------------------------
    # ROW 1: MONTHLY POSTING VOLUME AND JOB STATUS
    # --------------------------------------------------------

    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:

        st.subheader("1. Monthly Job Posting Volume (Segmented)")
        st.markdown("Monthly volume breakdown highlighting entry-level roles versus other position levels.")

        # Only copy the two columns needed for this chart.
        macro_df = filtered_df.loc[filtered_df["metadata_newPostingDate"].notna(), ["metadata_newPostingDate", "positionLevels"]].copy()

        macro_df["YearMonth"] = macro_df["metadata_newPostingDate"].dt.to_period("M").astype(str)
        macro_df["Level_Type"] = macro_df["positionLevels"].eq("Fresh/entry level").map({True: "Fresh / Entry Level", False: "Other Position Levels"})

        monthly_grouped = macro_df.groupby(["YearMonth", "Level_Type"], observed=True).size().reset_index(name="Count")

        if not monthly_grouped.empty:

            stack_chart = alt.Chart(monthly_grouped).mark_bar().encode(
                x=alt.X("YearMonth:N", title="Month", sort=alt.EncodingSortField(field="YearMonth", op="min", order="ascending")),
                y=alt.Y("Count:Q", title="Job Postings Count"),
                color=alt.Color("Level_Type:N", title="Position Level", scale=alt.Scale(domain=["Fresh / Entry Level", "Other Position Levels"], range=["#ff7f0e", "#aec7e8"])),
                tooltip=["YearMonth", "Level_Type", "Count"]
            ).properties(height=300)

            st.altair_chart(stack_chart, use_container_width=True)

        else:
            st.info("No monthly data available.")

        del macro_df

        st.info(
            f"📌 **Key Finding (Volume & Velocity):** Fresh/entry-level positions track alongside overall market volumes. "
            f"**Percentage of entry level jobs {avg_entry_pct:.1f}%**. "
            f"Highlighting entry-level roles against broader market postings shows their relative share over time."
        )

    with row1_col2:

        st.subheader("2. Entry-Level Job Status Breakdown")
        st.markdown("Proportion of status states for entry-level roles.")

        if "status_jobStatus" in filtered_df.columns:

            status_counts = filtered_df.loc[entry_mask, "status_jobStatus"].value_counts()
            total_status_count = status_counts.sum()

            status_df = status_counts.reset_index()
            status_df.columns = ["Job Status", "Count"]
            status_df["Percentage (%)"] = (status_df["Count"] / total_status_count * 100).round(1)

            pie_chart = alt.Chart(status_df).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="Count", type="quantitative"),
                color=alt.Color(field="Job Status", type="nominal"),
                tooltip=["Job Status", "Count", "Percentage (%)"]
            ).properties(height=300)

            st.altair_chart(pie_chart, use_container_width=True)

            pct_dict = {str(k).strip().casefold(): v for k, v in zip(status_df["Job Status"], status_df["Percentage (%)"])}

            open_pct = pct_dict.get("open", 0.0)
            reopen_pct = pct_dict.get("reopen", pct_dict.get("re-open", 0.0))
            closed_pct = pct_dict.get("closed", 0.0)

            st.info(
                f"📌 **Key Finding (Market Urgency):** The job status distribution shows "
                f"**Open jobs: {open_pct}%**, **Reopen jobs: {reopen_pct}%**, "
                f"and **Closed jobs: {closed_pct}%**. "
                f"This balance reflects overall hiring urgency and market liquidity for new entrants."
            )

        else:
            st.info("Job status column not found.")

else:
    st.info("No data available for the selected filters.")


# ============================================================
# RAW / FILTERED RESULTS DATA VIEW
# ============================================================

st.markdown("---")
st.header("Filtered Results Data View (Entry-Level Focus)")

st.write(f"Matching entry-level rows: {entry_jobs_count:,} | Columns: {len(filtered_df.columns)}")

# Display only the first 1,000 matching records.
PREVIEW_ROWS = 1000
entry_preview_index = entry_mask[entry_mask].index[:PREVIEW_ROWS]
entry_preview = filtered_df.loc[entry_preview_index]

st.caption(f"Displaying the first {len(entry_preview):,} matching records.")
st.dataframe(entry_preview, use_container_width=True, height=500)

del entry_preview
del entry_preview_index


# ============================================================
# PHASE 2: SECTOR DEMAND & SALARY ANALYSIS
# ============================================================

SHORT = {
    "Banking and Finance": "Banking & Finance",
    "Building and Construction": "Building & Constr.",
    "Education and Training": "Education",
    "Information Technology": "IT",
    "Accounting / Auditing / Taxation": "Accounting",
    "Admin / Secretarial": "Admin",
    "Customer Service": "Customer service",
    "Sales / Retail": "Sales/Retail",
    "Human Resources": "HR",
    "Advertising / Media": "Advertising",
    "Healthcare / Pharmaceutical": "Healthcare"
}

ORANGE, TEAL = "#e76f51", "#2a9d8f"
BETTER = "Smaller Talent Pool: higher pay with fewer applicants than the median of the sectors shown"


# ------------------------------------------------------------
# BUBBLE CHART FUNCTION
# ------------------------------------------------------------

def bubble_figure(s):
    s = s.copy()

    mx, my = s["applicants_per_job"].median(), s["median_salary"].median()

    s["group"] = ((s["applicants_per_job"] <= mx) & (s["median_salary"] >= my)).map({True: BETTER, False: "Other sector"})
    s["label"] = s["sector"].map(lambda n: SHORT.get(n, n))

    xmax = max(1, math.ceil(s["applicants_per_job"].max() * 1.25 * 2) / 2)
    ymin = math.floor((s["median_salary"].min() - 250) / 250) * 250
    ymax = math.ceil((s["median_salary"].max() + 250) / 250) * 250

    fig = px.scatter(
        s,
        x="applicants_per_job",
        y="median_salary",
        size="postings",
        text="label",
        color="group",
        custom_data=["sector", "postings"],
        size_max=40,
        color_discrete_map={BETTER: ORANGE, "Other sector": TEAL},
        category_orders={"group": [BETTER, "Other sector"]}
    )

    for t in fig.data:

        better = t.name == BETTER

        t.update(
            marker=dict(opacity=0.85 if better else 0.5, line=dict(width=1.5, color=ORANGE if better else TEAL)),
            textposition=["middle left" if x > 0.85 * xmax else "middle right" for x in t.x],
            textfont=dict(size=11),
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:,} postings<br>Median salary S$%{y:,.0f} a month<br>%{x:.2f} applicants per job<extra></extra>"
        )

    fig.add_shape(type="rect", x0=0, x1=mx, y0=my, y1=ymax, fillcolor="rgba(42,157,143,0.10)", line_width=0, layer="below")
    fig.add_vline(x=mx, line_dash="dash", line_color="grey", line_width=1)
    fig.add_hline(y=my, line_dash="dash", line_color="grey", line_width=1)

    fig.add_annotation(
        x=0.02 * xmax,
        y=ymax,
        text="Fewer applicants with higher pay",
        showarrow=False,
        xanchor="left",
        yanchor="top",
        font=dict(size=12)
    )

    grid = "rgba(128,128,128,0.15)"

    fig.update_xaxes(range=[0, xmax], gridcolor=grid, zeroline=False, title="Applicants per Job (total applications ÷ postings)")
    fig.update_yaxes(range=[ymin, ymax], gridcolor=grid, zeroline=False, tickprefix="S$", tickformat=",", title="Median Average Salary (S$ per month)")

    fig.update_layout(
        height=520,
        margin=dict(l=0, r=0, t=50, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text="")
    )

    return fig


# ------------------------------------------------------------
# PREPARE ONE SHARED ENTRY-LEVEL DATASET
# ------------------------------------------------------------

AGENCY_PAT = r"recruit|hr advisory|manpower|staffing|talent|headhunt|persol|adecco|randstad|hays|michael page|robert walters|employment|personnel|executive search"


@st.cache_resource(show_spinner="Preparing entry-level analysis...")
def add_sector_and_clean(path, file_mtime):

    source = load_data(path, file_mtime)

    needed_cols = [
        "categories",
        "employmentTypes",
        "metadata_jobPostId",
        "metadata_totalNumberJobApplication",
        "average_salary",
        "postedCompany_name",
        "status_jobStatus"
    ]

    entry_mask_full = source["positionLevels"].eq("Fresh/entry level")
    d = source.loc[entry_mask_full, needed_cols].copy()

    # Parse each unique category string once.
    def first_sector(value):
        try:
            items = json.loads(value) if isinstance(value, str) else []
            if items and isinstance(items[0], dict):
                return items[0].get("category", "Unknown") or "Unknown"
        except (TypeError, json.JSONDecodeError):
            pass
        return "Unknown"

    category_lookup = {value: first_sector(value) for value in d["categories"].dropna().unique()}
    d["sector"] = d["categories"].map(category_lookup).fillna("Unknown")

    # Calculate salary boundaries and median once per sector.
    salary_stats = d.groupby("sector", observed=True)["average_salary"].agg(
        lower=lambda x: x.quantile(0.01),
        upper=lambda x: x.quantile(0.99),
        median="median"
    )

    lower = d["sector"].map(salary_stats["lower"])
    upper = d["sector"].map(salary_stats["upper"])
    median = d["sector"].map(salary_stats["median"])

    within_range = d["average_salary"].between(lower, upper)
    d["average_salary_clean"] = d["average_salary"].where(within_range, median)

    # Prepare company and re-open fields once for both analyses.
    d["company"] = d["postedCompany_name"].fillna("Unknown").str.strip().str.title()
    d["is_reopen"] = d["status_jobStatus"].eq("Re-open")
    d["is_agency"] = d["company"].str.contains(AGENCY_PAT, case=False, regex=True, na=False)

    # Convert repeated text fields to categories to reduce memory usage.
    d["sector"] = d["sector"].astype("category")
    d["company"] = d["company"].astype("category")

    # Remove raw columns no longer needed by Phase 2 or Re-open Analysis.
    d.drop(columns=["categories", "postedCompany_name", "status_jobStatus"], inplace=True)

    return d


entry_all = add_sector_and_clean(DATA_PATH, DATA_MTIME)


# ------------------------------------------------------------
# BUBBLE CHART
# ------------------------------------------------------------

st.subheader("Top 10 Sectors by Median Average Salary")

chart_emp = st.multiselect(
    "Employment Type (this chart only)",
    sorted(entry_all["employmentTypes"].dropna().unique()),
    default=[]
)

c = entry_all.loc[entry_all["employmentTypes"].isin(chart_emp)] if chart_emp else entry_all

s = (
    c.groupby("sector", observed=True)
    .agg(
        postings=("metadata_jobPostId", "count"),
        median_salary=("average_salary_clean", "median"),
        applications=("metadata_totalNumberJobApplication", "sum")
    )
    .reset_index()
)

s["applicants_per_job"] = s["applications"] / s["postings"]
s = s[s["postings"] > 1000].sort_values(["median_salary", "postings"], ascending=[False, False]).head(10)

del c

if len(s) < 3:

    st.info(f"Only {len(s)} sector(s) have more than 1,000 postings for this selection, too few to compare.")

else:

    st.caption(
        f"{int(s['postings'].sum()):,} postings across the selected top sectors. "
        + (
            "Showing the top 10 sectors with > 1,000 postings ranked by median salary."
            if len(s) == 10
            else f"Only {len(s)} sectors have more than 1,000 postings."
        )
    )

    st.plotly_chart(bubble_figure(s), use_container_width=True)

    mx, my = s["applicants_per_job"].median(), s["median_salary"].median()
    better = s[(s["applicants_per_job"] <= mx) & (s["median_salary"] >= my)]

    top_pay = s.loc[s["median_salary"].idxmax()]
    crowded = s.loc[s["applicants_per_job"].idxmax()]

    st.info(
        f"📌 **Key Finding (Pay vs Competition):** Among these {len(s)} sectors, "
        f"**{top_pay['sector']}** pays the most (S${top_pay['median_salary']:,.0f} a month, "
        f"{top_pay['applicants_per_job']:.2f} applicants per job). "
        f"**Limited Talent Pool** (fewer applicants and higher pay than the median of the sectors shown): "
        f"**{', '.join(better['sector'].astype(str)) if len(better) else 'none in this selection'}**. "
        f"The most crowded is **{crowded['sector']}** with {crowded['applicants_per_job']:.2f} applicants per job."
    )

    st.caption("Median average salary is calculated after removing outliers (top and bottom 1% of salaries for each sector).")


# ============================================================
# RE-OPEN DRILL-DOWN: SECTOR VS COMPANY
# ============================================================

st.markdown("---")
st.header("Re-Open Drill-Down: Driven by a Sector or a Company?")

# Reuse the prepared entry-level DataFrame. Do not make another copy.
ro_all = entry_all


# ============================================================
# 1. SESSION STATE AND CHART CALLBACKS
# ============================================================

st.session_state.setdefault("ro_dropdown", "All sectors")
st.session_state.setdefault("ro_selected_company", None)
st.session_state.setdefault("ro_sector_chart_version", 0)
st.session_state.setdefault("ro_company_chart_version", 0)


def get_chart_selection(chart_key, selection_name, field):
    state = st.session_state.get(chart_key)
    selection = state.get("selection", {}).get(selection_name, []) if state else []
    return selection[0].get(field) if selection else None


def on_sector_chart_select():
    chart_key = st.session_state.get("ro_active_sector_chart_key")
    selected = get_chart_selection(chart_key, "sector_pick", "sector")
    st.session_state["ro_dropdown"] = selected if selected else "All sectors"
    st.session_state["ro_sector_chart_version"] += 1
    st.session_state["ro_company_chart_version"] += 1


def on_company_chart_select():
    chart_key = st.session_state.get("ro_active_company_chart_key")
    selected = get_chart_selection(chart_key, "company_pick", "company")
    st.session_state["ro_selected_company"] = selected
    st.session_state["ro_sector_chart_version"] += 1
    st.session_state["ro_company_chart_version"] += 1


def on_sector_dropdown_change():
    st.session_state["ro_sector_chart_version"] += 1
    st.session_state["ro_company_chart_version"] += 1


def clear_all_reopen_filters():
    st.session_state["ro_dropdown"] = "All sectors"
    st.session_state["ro_selected_company"] = None
    st.session_state["ro_sector_chart_version"] += 1
    st.session_state["ro_company_chart_version"] += 1


def clear_company_filter():
    st.session_state["ro_selected_company"] = None
    st.session_state["ro_sector_chart_version"] += 1
    st.session_state["ro_company_chart_version"] += 1


# ============================================================
# 2. FILTERS
# ============================================================

f1, f2, f3 = st.columns([1.3, 1.3, 1.3])

with f1:
    emp_sel = st.multiselect(
        "Employment type",
        sorted(ro_all["employmentTypes"].dropna().unique()),
        default=[],
        key="ro_emp"
    )

ro_df = ro_all.loc[ro_all["employmentTypes"].isin(emp_sel)] if emp_sel else ro_all

sector_order = (
    ro_df.groupby("sector", observed=True)["is_reopen"]
    .sum()
    .sort_values(ascending=False)
    .index.astype(str)
    .tolist()
)

sector_options = ["All sectors"] + sector_order

if st.session_state["ro_dropdown"] not in sector_options:
    st.session_state["ro_dropdown"] = "All sectors"

with f2:
    dropdown = st.selectbox(
        "Sector (pick here or click chart 1)",
        sector_options,
        key="ro_dropdown",
        on_change=on_sector_dropdown_change
    )

with f3:
    metric = st.radio(
        "Show",
        ["Re-Open Postings (Count)", "Re-Open Rate (% of Postings)"],
        horizontal=True,
        key="ro_metric"
    )

rate_view = metric.startswith("Re-Open Rate")
value_col = "rate" if rate_view else "reopen"
x_title = "Re-Open Rate (% of postings)" if rate_view else "Re-Open Postings"

sector_filter = None if dropdown == "All sectors" else dropdown


# ============================================================
# 3. VALIDATE COMPANY SELECTION
# ============================================================

company_filter = st.session_state["ro_selected_company"]

if company_filter and sector_filter:
    company_available = ((ro_df["company"] == company_filter) & (ro_df["sector"] == sector_filter)).any()
elif company_filter:
    company_available = ro_df["company"].eq(company_filter).any()
else:
    company_available = True

if company_filter and not company_available:
    st.session_state["ro_selected_company"] = None
    st.session_state["ro_company_chart_version"] += 1
    st.session_state["ro_sector_chart_version"] += 1
    company_filter = None


# ============================================================
# 4. FILTER SCOPE AND CLEAR BUTTON
# ============================================================

if company_filter and sector_filter:
    scope_text = f"**{company_filter}** in **{sector_filter}**"
elif company_filter:
    scope_text = f"**{company_filter}** (all sectors)"
elif sector_filter:
    scope_text = f"sector **{sector_filter}** (all companies)"
else:
    scope_text = "all entry-level postings"

b1, b2 = st.columns([4, 1])

b1.markdown(
    f"**Showing:** {scope_text}"
    + (f" · employment type: {', '.join(emp_sel)}" if emp_sel else "")
)

if sector_filter or company_filter:
    b2.button("✖ Clear all", key="ro_clear_all_button", on_click=clear_all_reopen_filters)


# ============================================================
# 5. DATA FILTERING
# ============================================================

all_n = len(ro_df)
all_r = int(ro_df["is_reopen"].sum())
all_rate = all_r / all_n * 100 if all_n else 0

# Sector chart data: filter by selected company.
d_sector = ro_df.loc[ro_df["company"] == company_filter] if company_filter else ro_df

# Company chart data: filter by selected sector.
d_company = ro_df.loc[ro_df["sector"] == sector_filter] if sector_filter else ro_df

# Calculate KPI scope using a Boolean mask instead of copying another DataFrame.
scope_mask = pd.Series(True, index=ro_df.index)

if sector_filter:
    scope_mask &= ro_df["sector"].eq(sector_filter)

if company_filter:
    scope_mask &= ro_df["company"].eq(company_filter)

s_n = int(scope_mask.sum())
s_r = int(ro_df.loc[scope_mask, "is_reopen"].sum())
scope_sector_count = int(ro_df.loc[scope_mask, "sector"].nunique())


# ============================================================
# 6. AGGREGATION AND SORTING
# ============================================================

def stats(d, group_col):
    g = (
        d.groupby(group_col, observed=True)
        .agg(postings=("is_reopen", "size"), reopen=("is_reopen", "sum"))
        .reset_index()
    )

    g["rate"] = g["reopen"] / g["postings"] * 100
    total_reopen = g["reopen"].sum()
    g["share"] = g["reopen"] / total_reopen * 100 if total_reopen else 0

    return g


def company_stats(d):
    g = (
        d.groupby("company", observed=True)
        .agg(
            postings=("is_reopen", "size"),
            reopen=("is_reopen", "sum"),
            is_agency=("is_agency", "max")
        )
        .reset_index()
    )

    g["rate"] = g["reopen"] / g["postings"] * 100
    total_reopen = g["reopen"].sum()
    g["share"] = g["reopen"] / total_reopen * 100 if total_reopen else 0

    return g


def sort_rows(d, group_col):
    if d.empty:
        return d.copy()

    if rate_view:
        sort_cols = ["rate", "reopen", group_col]
        ascending = [False, False, True]
    else:
        sort_cols = ["reopen", "postings", group_col]
        ascending = [False, False, True]

    return d.sort_values(sort_cols, ascending=ascending, kind="stable").copy()


def top_rows(d, group_col):
    return sort_rows(d[d["reopen"] > 0], group_col).head(15).copy()


sec = stats(d_sector, "sector")
comp = company_stats(d_company)

scope_name = " / ".join(x for x in (sector_filter, company_filter) if x) or "all sectors"


# ============================================================
# 7. KPI
# ============================================================

if s_n == 0 or s_r == 0:

    st.info(f"No re-open postings for {scope_name} with these filters. Press Clear all or change the filters.")

else:

    scope_rate = s_r / s_n * 100
    vs = f", {scope_rate / all_rate:.1f}x the overall {all_rate:.1f}%" if (sector_filter or company_filter) and all_rate else ""

    k = st.columns(5)

    k[0].metric("Postings", f"{s_n:,}")
    k[1].metric("Re-Open Postings", f"{s_r:,}")
    k[2].metric(
        "Re-Open Rate",
        f"{scope_rate:.1f}%",
        f"{scope_rate / all_rate:.1f}x overall at {all_rate:.1f}%" if (sector_filter or company_filter) and all_rate else None,
        delta_color="off"
    )

    if company_filter:

        k[3].metric("Sectors covered", f"{scope_sector_count:,}")
        k[4].metric("Share of all re-open", f"{s_r / all_r * 100:.1f}%" if all_r else "0%")

    else:

        comp_by_count = comp.sort_values(
            ["reopen", "postings", "company"],
            ascending=[False, False, True],
            kind="stable"
        )

        top = comp_by_count.iloc[0]
        top_share = top["reopen"] / s_r * 100 if s_r else 0
        top10_share = comp_by_count.head(10)["reopen"].sum() / s_r * 100 if s_r else 0

        k[3].metric("Top company's share", f"{top_share:.0f}%", str(top["company"]), delta_color="off")
        k[4].metric("Top 10 companies' share", f"{top10_share:.0f}%")


    # ========================================================
    # 8. INTERACTIVE CHARTS
    # ========================================================

    left, right = st.columns(2)

    # --------------------------------------------------------
    # CHART 1: SECTOR
    # --------------------------------------------------------

    with left:

        st.subheader("1. Which Sectors Re-Open the Most?" + (f" ({company_filter})" if company_filter else ""))
        st.caption("Click a bar to drill into that sector. Click the empty chart background to reset. Share = share of re-open postings in this chart.")

        ld = top_rows(sec, "sector")

        if ld.empty:

            st.info("No sector data available.")

        else:

            ld["label"] = [
                f"{name} ({rate:.1f}%; {int(reopen):,}/{int(postings):,})" if rate_view
                else f"{name} ({int(reopen):,})"
                for name, rate, reopen, postings in zip(ld["sector"].astype(str), ld["rate"], ld["reopen"], ld["postings"])
            ]

            ld["highlight"] = ["Selected" if str(x) == sector_filter else "Other" for x in ld["sector"]]

            pick_s = alt.selection_point(
                name="sector_pick",
                fields=["sector"],
                toggle=False,
                empty=False,
                clear="click[!event.item]"
            )

            chart1 = (
                alt.Chart(ld)
                .mark_bar()
                .add_params(pick_s)
                .encode(
                    # Sort bars by the quantitative X value, descending.
                    y=alt.Y(
                        "label:N",
                        sort="-x",
                        title=None,
                        axis=alt.Axis(labelLimit=300, labelOverlap=False)
                    ),
                    x=alt.X(f"{value_col}:Q", title=x_title),
                    color=alt.Color(
                        "highlight:N",
                        scale=alt.Scale(domain=["Selected", "Other"], range=["#e76f51", "#2a9d8f"]),
                        legend=None
                    ),
                    tooltip=[
                        alt.Tooltip("sector:N", title="Sector"),
                        alt.Tooltip("postings:Q", format=",", title="Total postings"),
                        alt.Tooltip("reopen:Q", format=",", title="Re-open postings"),
                        alt.Tooltip("rate:Q", format=".1f", title="Re-open rate (%)"),
                        alt.Tooltip("share:Q", format=".1f", title="Share of re-open here (%)")
                    ]
                )
                .properties(height=max(320, 30 * len(ld)))
            )

            sector_key = f"ro_sector_chart_{st.session_state['ro_sector_chart_version']}"
            st.session_state["ro_active_sector_chart_key"] = sector_key

            st.altair_chart(
                chart1,
                use_container_width=True,
                on_select=on_sector_chart_select,
                key=sector_key
            )


    # --------------------------------------------------------
    # CHART 2: COMPANY
    # --------------------------------------------------------

    with right:

        st.subheader(f"2. Which Companies Drive Re-Open in {sector_filter or 'All Sectors'}?")
        st.caption("Click a bar to drill into that company. Click the empty chart background to clear the company. Orange = selected; dark blue = potential recruitment agency.")

        if company_filter:
            st.button("✖ Show all companies", key="ro_show_all_companies", on_click=clear_company_filter)

        rd = top_rows(comp, "company")

        if rd.empty:

            st.info("No company data available.")

        else:

            rd["type"] = rd["is_agency"].map({True: "Recruitment agency", False: "Other employer"})

            rd["label"] = [
                f"{name} ({rate:.1f}%; {int(reopen):,}/{int(postings):,})" if rate_view
                else f"{name} ({int(reopen):,})"
                for name, rate, reopen, postings in zip(rd["company"].astype(str), rd["rate"], rd["reopen"], rd["postings"])
            ]

            rd["highlight"] = [
                "Selected" if str(name) == company_filter
                else ("Recruitment agency" if agency else "Other employer")
                for name, agency in zip(rd["company"], rd["is_agency"])
            ]

            pick_c = alt.selection_point(
                name="company_pick",
                fields=["company"],
                toggle=False,
                empty=False,
                clear="click[!event.item]"
            )

            chart2 = (
                alt.Chart(rd)
                .mark_bar()
                .add_params(pick_c)
                .encode(
                    # Sort bars by the quantitative X value, descending.
                    y=alt.Y(
                        "label:N",
                        sort="-x",
                        title=None,
                        axis=alt.Axis(labelLimit=330, labelOverlap=False)
                    ),
                    x=alt.X(f"{value_col}:Q", title=x_title),
                    color=alt.Color(
                        "highlight:N",
                        scale=alt.Scale(
                            domain=["Selected", "Recruitment agency", "Other employer"],
                            range=["#e76f51", "#264653", "#2a9d8f"]
                        ),
                        legend=alt.Legend(orient="bottom", title=None, labelLimit=300)
                    ),
                    tooltip=[
                        alt.Tooltip("company:N", title="Company"),
                        alt.Tooltip("type:N", title="Company type"),
                        alt.Tooltip("postings:Q", format=",", title="Total postings"),
                        alt.Tooltip("reopen:Q", format=",", title="Re-open postings"),
                        alt.Tooltip("rate:Q", format=".1f", title="Re-open rate (%)"),
                        alt.Tooltip("share:Q", format=".1f", title="Share of re-open here (%)")
                    ]
                )
                .properties(height=max(320, 30 * len(rd)))
            )

            company_key = f"ro_company_chart_{st.session_state['ro_company_chart_version']}"
            st.session_state["ro_active_company_chart_key"] = company_key

            st.altair_chart(
                chart2,
                use_container_width=True,
                on_select=on_company_chart_select,
                key=company_key
            )


    # ========================================================
    # 9. KEY FINDINGS
    # ========================================================

    if company_filter:

        sec_by_count = sec.sort_values(
            ["reopen", "postings", "sector"],
            ascending=[False, False, True],
            kind="stable"
        )

        main_text = ""

        if not sector_filter and not sec_by_count.empty and sec_by_count["reopen"].sum():
            main = sec_by_count.iloc[0]
            main_text = f" Most of its re-open postings are in **{main['sector']}** ({main['reopen'] / sec['reopen'].sum() * 100:.0f}%)."

        st.info(
            f"📌 **Key Finding (Re-open drivers):** For {scope_name}, "
            f"{s_r:,} of {s_n:,} postings are re-open ({scope_rate:.1f}%{vs}). "
            f"That is {s_r / all_r * 100:.1f}% of all re-open postings "
            f"from {s_n / all_n * 100:.1f}% of postings."
            f"{main_text}"
        )

    else:

        rate_ex = (s_r - top["reopen"]) / (s_n - top["postings"]) * 100 if s_n > top["postings"] else 0.0
        driver = "driven mainly by one company" if top_share >= 25 else "spread across many companies"

        st.info(
            f"📌 **Key Finding (Re-open drivers):** In {scope_name}, "
            f"{s_r:,} of {s_n:,} postings are re-open ({scope_rate:.1f}%{vs}). "
            f"The top company, **{top['company']}**, accounts for **{top_share:.0f}%** "
            f"of them (on {top['postings'] / s_n * 100:.1f}% of postings); "
            f"the top 10 companies account for {top10_share:.0f}%. "
            f"Without {top['company']} the re-open rate would be {rate_ex:.1f}%. "
            f"Re-open here is therefore **{driver}**."
        )


    # ========================================================
    # 10. DETAIL TABLES
    # ========================================================

    with st.expander("See the tables", expanded=bool(sector_filter or company_filter)):

        t1, t2 = st.columns(2)

        # Match sector table to the selected sector and selected company.
        sec_view = sec.loc[sec["sector"].astype(str).eq(sector_filter)] if sector_filter else sec

        # Match company table to the selected company and selected sector.
        comp_view = comp.loc[comp["company"].astype(str).eq(company_filter)] if company_filter else comp

        sec_view = sort_rows(sec_view, "sector")
        comp_view = sort_rows(comp_view, "company").head(50)

        t1.subheader("Sector ranking")
        t1.caption("Same filtered sector data as chart 1. Chart displays the top 15.")

        t1.dataframe(
            sec_view.rename(columns={
                "sector": "Sector",
                "postings": "Postings",
                "reopen": "Re-open",
                "rate": "Re-open rate (%)",
                "share": "Share of re-open here (%)"
            }),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Re-open rate (%)": st.column_config.NumberColumn(format="%.1f"),
                "Share of re-open here (%)": st.column_config.NumberColumn(format="%.1f")
            }
        )

        t2.subheader("Company ranking")
        t2.caption("Same filtered company data as chart 2. Table displays the top 50.")

        t2.dataframe(
            comp_view.drop(columns="is_agency").rename(columns={
                "company": "Company",
                "postings": "Postings",
                "reopen": "Re-open",
                "rate": "Re-open rate (%)",
                "share": "Share of re-open here (%)"
            }),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Re-open rate (%)": st.column_config.NumberColumn(format="%.1f"),
                "Share of re-open here (%)": st.column_config.NumberColumn(format="%.1f")
            }
        )





