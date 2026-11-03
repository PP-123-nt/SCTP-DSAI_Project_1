## use streamlit_app environment

import streamlit as st
import pandas as pd
from datetime import datetime
import json
import altair as alt

st.set_page_config(page_title="Sector Demand for Entry Level Workers", layout="wide")

print(f"🟢 Rerun at: {datetime.now()}")

DATA_PATH = "SGJobData.csv"

@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    df = df.dropna(axis = 1, how = 'all')               # drop the empty column
    remove_row = (df.isna() | df.eq(0)).all(axis=1)     # drop the empty rows (all NaN or 0)
    df = df.loc[~remove_row]                            # drop the empty rows (all NaN or 0)
    df['metadata_expiryDate'] = pd.to_datetime(df['metadata_expiryDate'])
    df['metadata_newPostingDate'] = pd.to_datetime(df['metadata_newPostingDate'])
    df['metadata_originalPostingDate'] = pd.to_datetime(df['metadata_originalPostingDate'])
    df['employmentTypes'] = df['employmentTypes'].astype('category')
    df['positionLevels'] = df['positionLevels'].astype('category')

    # filters
    # df = df[df['positionLevels']=='Fresh/entry level'] 
    df = df[df['metadata_newPostingDate']>= '2023-05']

    # replaces outlier 'average salary' values with the median for that sector ("category")
    # outliers are > or < 3 std from mean for each sector
    # THIS IS TEMP COMMENTED OUT TO REDUCE LOADING TIMES
    #############################################
    # def category_names(value):
    #     if isinstance(value, str):
    #       value = json.loads(value)
    #     return [item["category"] for item in value] if isinstance(value, list) else []

    # category_salary = (
    #     df.assign(category=df["categories"].map(category_names))
    #     .explode("category")
    #     .dropna(subset=["category", "average_salary"])
    #     .groupby("category")["average_salary"]
    #     .agg(mean="mean", median="median")
    #     .sort_index()
    # )
    # category_rows = (
    # df.assign(category=df["categories"].map(category_names))
    #   .explode("category")
    #   .dropna(subset=["category", "average_salary"])
    # )

    # category_std = category_rows.groupby("category")["average_salary"].std()
    # category_stats = category_salary.join(category_std.rename("std"))

    # def replace_salary(row):
    #     salary = row["average_salary"]
    #     if pd.isna(salary):
    #         return salary

    #     categories = list(dict.fromkeys(category_names(row["categories"])))
    #     stats = category_stats.reindex(categories)

    #     is_outlier = (
    #         (salary > stats["mean"] + 3 * stats["std"]) | (salary < stats["mean"] - 3 * stats["std"])
    #     ).fillna(False).any()

    #     if is_outlier:
    #         medians = category_salary.reindex(categories)["median"].dropna()
    #         if not medians.empty:
    #             return medians.mean()

    #     return salary

    # df["average_salary"] = df.apply(replace_salary, axis=1)

    return df

df = load_data(DATA_PATH)

st.title("Sector Demand for Entry Level Workers")
#st.dataframe(df.head(10))

###################################################
## ADD SIDEBAR WIDGETS HERE VVVVVVVV
################################################### 

## FILTER SIDEBAR AND DATA FILTERED BY SECTOR
# 
st.sidebar.header("Filters")

def extract_categories(categories_str):
    if pd.isna(categories_str) or not isinstance(categories_str, str):
        return []
    try:
        items = json.loads(categories_str)
        if isinstance(items, list):
            return [item.get("category") for item in items if isinstance(item, dict) and "category" in item]
    except:
        pass
    return []

# Robust extraction for unique sectors in sidebar
parsed_categories = []
for cat_str in df["categories"].dropna():
    res = extract_categories(cat_str)
    if res:
        parsed_categories.extend(res)

unique_sectors = sorted(list(set(parsed_categories)))

selected_sectors = st.sidebar.multiselect("Sector", unique_sectors, default=[])

# Filtered DataFrame containing ALL position levels
filtered_df = df.copy()

if selected_sectors:
    filtered_df = filtered_df[filtered_df["categories"].apply(
        lambda x: any(sec in extract_categories(x) for sec in selected_sectors)
    )]

# Dedicated subset for entry-level specific metrics & status chart
entry_df = filtered_df[filtered_df['positionLevels'] == 'Fresh/entry level']


###################################################
## PHASE 1: MACRO ECONOMIC CLIMATE
###################################################

st.markdown("---")
st.header("Phase 1: Macro Economic Climate (Entry-Level Overview)")

if not filtered_df.empty:
    
    # Calculate overall average percentage of entry level jobs
    total_jobs_count = len(filtered_df)
    entry_jobs_count = len(entry_df)
    avg_entry_pct = (entry_jobs_count / total_jobs_count * 100) if total_jobs_count > 0 else 0.0

    # Quick Summary Metrics (Strictly Entry-Level)
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Total Entry-Level Postings", f"{entry_jobs_count:,}")
    with col_m2:
        total_apps = entry_df['metadata_totalNumberJobApplication'].sum() if 'metadata_totalNumberJobApplication' in entry_df.columns else 0
        st.metric("Total Entry-Level Applications", f"{int(total_apps):,}")
    with col_m3:
        unique_companies = entry_df['postedCompany_name'].nunique() if 'postedCompany_name' in entry_df.columns else 0
        st.metric("Hiring Companies (Entry-Level)", f"{unique_companies:,}")

    st.markdown("---")

    # --- ROW 1: SEGMENTED HISTOGRAM & JOB STATUS PIE CHART BESIDE IT ---
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.subheader("1. Monthly Job Posting Volume (Segmented)")
        st.markdown("Monthly volume breakdown highlighting entry-level roles versus other position levels.")
        
        macro_df = filtered_df.copy()
        macro_df = macro_df.dropna(subset=['metadata_newPostingDate'])
        macro_df['YearMonth'] = macro_df['metadata_newPostingDate'].dt.to_period('M').astype(str)
        
        # Categorize position level cleanly
        macro_df['Level_Type'] = macro_df['positionLevels'].apply(
            lambda x: 'Fresh / Entry Level' if x == 'Fresh/entry level' else 'Other Position Levels'
        )
        
        monthly_grouped = macro_df.groupby(['YearMonth', 'Level_Type']).size().reset_index(name='Count')
        
        if not monthly_grouped.empty:
            # Altair bar chart with distinct color for entry-level highlighting
            stack_chart = alt.Chart(monthly_grouped).mark_bar().encode(
                x=alt.X('YearMonth:N', title='Month', sort=alt.EncodingSortField(field="YearMonth", op="min", order="ascending")),
                y=alt.Y('Count:Q', title='Job Postings Count'),
                color=alt.Color('Level_Type:N', title='Position Level',
                                scale=alt.Scale(domain=['Fresh / Entry Level', 'Other Position Levels'],
                                              range=['#ff7f0e', '#aec7e8'])),
                tooltip=['YearMonth', 'Level_Type', 'Count']
            ).properties(height=300)
            
            st.altair_chart(stack_chart, use_container_width=True)
        else:
            st.info("No monthly data available.")
        
        # --- Commentary / Findings for Chart 1 with the average percentage included ---
        st.info(
            f"📌 **Key Finding (Volume & Velocity):** "
            f"Fresh/entry-level positions track alongside overall market volumes. "
            f"**Percentage of entry level jobs {avg_entry_pct:.1f}%**. "
            f"Highlighting entry-level roles against broader market postings shows their relative share over time."
        )

    with row1_col2:
        st.subheader("2. Entry-Level Job Status Breakdown")
        st.markdown("Proportion of status states for entry-level roles.")
        
        if 'status_jobStatus' in entry_df.columns:
            status_counts = entry_df['status_jobStatus'].value_counts()
            total_status_count = status_counts.sum()
            
            status_df = status_counts.reset_index()
            status_df.columns = ['Job Status', 'Count']
            status_df['Percentage (%)'] = (status_df['Count'] / total_status_count * 100).round(1)
            
            pie_chart = alt.Chart(status_df).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="Count", type="quantitative"),
                color=alt.Color(field="Job Status", type="nominal"),
                tooltip=['Job Status', 'Count', 'Percentage (%)']
            ).properties(height=300)
            
            st.altair_chart(pie_chart, use_container_width=True)
            
            pct_dict = dict(zip(status_df['Job Status'], status_df['Percentage (%)']))
            open_pct = pct_dict.get('Open', pct_dict.get('open', 0.0))
            reopen_pct = pct_dict.get('Reopen', pct_dict.get('reopen', pct_dict.get('Re-open', 0.0)))
            closed_pct = pct_dict.get('Closed', pct_dict.get('closed', 0.0))
            
            st.info(
                f"📌 **Key Finding (Market Urgency):** "
                f"The job status distribution shows **Open jobs: {open_pct}%**, "
                f"**Reopen jobs: {reopen_pct}%**, and **Closed jobs: {closed_pct}%**. "
                f"This balance reflects overall hiring urgency and market liquidity for new entrants."
            )
        else:
            st.info("Job status column not found.")

else:
    st.info("No data available for the selected filters.")

###################################################
## RAW / FILTERED RESULTS VIEW
################################################### 
st.markdown("---")
st.header("Filtered Results Data View (Entry-Level Focus)")
st.write(f"Matching entry-level rows: {len(entry_df):,} | Columns: {len(entry_df.columns)}")
st.dataframe(entry_df, use_container_width=True)




################################################### 
## PHASE 2: SECTOR DEMAND & SALARY ANALYSIS
################################################### 

import math
import plotly.express as px

SHORT = {"Banking and Finance": "Banking & Finance", "Building and Construction": "Building & Constr.",
         "Education and Training": "Education", "Information Technology": "IT",
         "Accounting / Auditing / Taxation": "Accounting", "Admin / Secretarial": "Admin",
         "Customer Service": "Customer service", "Sales / Retail": "Sales/Retail", "Human Resources": "HR",
         "Advertising / Media": "Advertising", "Healthcare / Pharmaceutical": "Healthcare"}
ORANGE, TEAL = "#e76f51", "#2a9d8f"
BETTER = "Smaller Talent Pool: higher pay with fewer applicants than the median of the sectors shown"


def bubble_figure(s):
    """s = top sectors with columns: sector, postings, median_salary, applicants_per_job"""
    s = s.copy()
    mx, my = s["applicants_per_job"].median(), s["median_salary"].median()
    s["group"] = ((s["applicants_per_job"] <= mx) & (s["median_salary"] >= my)).map({True: BETTER, False: "Other sector"})
    s["label"] = s["sector"].map(lambda n: SHORT.get(n, n))
    xmax = max(1, math.ceil(s["applicants_per_job"].max() * 1.25 * 2) / 2)
    ymin = math.floor((s["median_salary"].min() - 250) / 250) * 250
    ymax = math.ceil((s["median_salary"].max() + 250) / 250) * 250

    fig = px.scatter(s, x="applicants_per_job", y="median_salary", size="postings", text="label", color="group",
                     custom_data=["sector", "postings"], size_max=40,
                     color_discrete_map={BETTER: ORANGE, "Other sector": TEAL},
                     category_orders={"group": [BETTER, "Other sector"]})
    for t in fig.data:
        better = t.name == BETTER
        t.update(marker=dict(opacity=0.85 if better else 0.5, line=dict(width=1.5, color=ORANGE if better else TEAL)),
                 textposition=["middle left" if x > 0.85 * xmax else "middle right" for x in t.x],
                 textfont=dict(size=11),
                 hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]:,} postings<br>"
                               "Median salary S$%{y:,.0f} a month<br>"
                               "%{x:.2f} applicants per job<extra></extra>")

    fig.add_shape(type="rect", x0=0, x1=mx, y0=my, y1=ymax, fillcolor="rgba(42,157,143,0.10)", line_width=0, layer="below")
    fig.add_vline(x=mx, line_dash="dash", line_color="grey", line_width=1)
    fig.add_hline(y=my, line_dash="dash", line_color="grey", line_width=1)
    fig.add_annotation(x=0.02 * xmax, y=ymax, text="Fewer applicants with higher pay", showarrow=False,
                       xanchor="left", yanchor="top", font=dict(size=12))
    grid = "rgba(128,128,128,0.15)"
    fig.update_xaxes(range=[0, xmax], gridcolor=grid, zeroline=False,
                     title="Applicants per Job (total applications ÷ postings)")
    fig.update_yaxes(range=[ymin, ymax], gridcolor=grid, zeroline=False, tickprefix="S$", tickformat=",",
                     title="Median Average Salary (S$ per month)")
    fig.update_layout(height=520, margin=dict(l=0, r=0, t=50, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""))
    return fig

@st.cache_data
def add_sector_and_clean(d):
    d = d.copy()
    d["sector"] = d["categories"].map(
        lambda s: json.loads(s)[0]["category"] if isinstance(s, str) and s != "[]" else "Unknown")
    g = d.groupby("sector")["average_salary"]
    lo, hi, med = g.transform(lambda s: s.quantile(0.01)), g.transform(lambda s: s.quantile(0.99)), g.transform("median")
    d["average_salary_clean"] = d["average_salary"].where(d["average_salary"].between(lo, hi), med)
    return d

# bubble chart base = Fresh/entry level only (the loader no longer filters position level)
entry_all = add_sector_and_clean(df[df["positionLevels"] == "Fresh/entry level"])

## Bubble chart for top 10 sectors by cleaned median average salary

st.subheader("Top 10 Sectors by Median Average Salary")
chart_emp = st.multiselect("Employment Type (this chart only)",
                           sorted(entry_all["employmentTypes"].dropna().unique()), default=[])
c = entry_all[entry_all["employmentTypes"].isin(chart_emp)] if chart_emp else entry_all

s = (c.groupby("sector")
       .agg(postings=("metadata_jobPostId", "count"),
            median_salary=("average_salary_clean", "median"),
            applications=("metadata_totalNumberJobApplication", "sum"))
       .reset_index())
s["applicants_per_job"] = s["applications"] / s["postings"]
s = s[s["postings"] > 1000].sort_values(["median_salary", "postings"], ascending=False).head(10)

if len(s) < 3:
    st.info(f"Only {len(s)} sector(s) have more than 1,000 postings for this selection, too few to compare.")
else:
    st.caption(f"{len(c):,} postings in this filter. "
               + ("Showing the top 10 sectors with > 1,000 postings ranked by median salary."
                  if len(s) == 10 else f"Only {len(s)} sectors have more than 1,000 postings."))
    st.plotly_chart(bubble_figure(s), width="stretch")

    mx, my = s["applicants_per_job"].median(), s["median_salary"].median()
    better = s[(s["applicants_per_job"] <= mx) & (s["median_salary"] >= my)]
    top_pay = s.iloc[s["median_salary"].argmax()]
    crowded = s.iloc[s["applicants_per_job"].argmax()]
    st.info(
        f"📌 **Key Finding (Pay vs Competition):** "
        f"Among these {len(s)} sectors, **{top_pay['sector']}** pays the most "
        f"(S${top_pay['median_salary']:,.0f} a month, {top_pay['applicants_per_job']:.2f} applicants per job). "
        f"**Limited Talent Pool** (fewer applicants and higher pay than the median of the sectors shown): "
        f"**{', '.join(better['sector']) if len(better) else 'none in this selection'}**. "
        f"The most crowded is **{crowded['sector']}** with {crowded['applicants_per_job']:.2f} applicants per job."
    )
    st.caption("Median average salary is calculated after removing outliers (top and bottom 1% of salaries for each sector). ")






# ============================================================
# RE-OPEN DRILL-DOWN: SECTOR VS COMPANY
# Streamlit 1.36.0 | Altair 5.5.0
# ============================================================

AGENCY_PAT = r"recruit|hr advisory|manpower|staffing|talent|headhunt|persol|adecco|randstad|hays|michael page|robert walters|employment|personnel|executive search"

st.markdown("---")
st.header("Re-Open Drill-down: Driven by A Sector or A Company?")


# ============================================================
# 1. PREPARE DATA
# ============================================================

@st.cache_data(show_spinner=False)
def prepare_reopen_data(df):
    d = df.assign(company=df["postedCompany_name"].fillna("Unknown").str.strip().str.title(), is_reopen=df["status_jobStatus"].eq("Re-open"))
    d["is_agency"] = d["company"].str.contains(AGENCY_PAT, case=False, regex=True, na=False)
    return d

ro_all = prepare_reopen_data(entry_all)


# ============================================================
# 2. SESSION STATE AND CHART CALLBACKS
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
# 3. FILTERS
# ============================================================

f1, f2, f3 = st.columns([1.3, 1.3, 1.3])

with f1:
    emp_sel = st.multiselect("Employment type", sorted(entry_all["employmentTypes"].dropna().unique()), default=[], key="ro_emp")

ro_df = ro_all[ro_all["employmentTypes"].isin(emp_sel)] if emp_sel else ro_all

sector_order = ro_df.groupby("sector", observed=True)["is_reopen"].sum().sort_values(ascending=False).index.tolist()
sector_options = ["All sectors"] + sector_order

if st.session_state["ro_dropdown"] not in sector_options:
    st.session_state["ro_dropdown"] = "All sectors"

with f2:
    dropdown = st.selectbox("Sector (pick here or click chart 1)", sector_options, key="ro_dropdown", on_change=on_sector_dropdown_change)

with f3:
    metric = st.radio("Show", ["Re-Open Postings (Count)", "Re-Open Rate (% of Postings)"], horizontal=True, key="ro_metric")

rate_view = metric.startswith("Re-Open Rate")
value_col = "rate" if rate_view else "reopen"
x_title = "Re-Open Rate (% of Postings)" if rate_view else "Re-Open Postings"

sector_filter = None if dropdown == "All sectors" else dropdown


# ============================================================
# 4. VALIDATE COMPANY SELECTION
# ============================================================

company_filter = st.session_state["ro_selected_company"]

d_company_scope = ro_df[ro_df["sector"] == sector_filter] if sector_filter else ro_df
available_companies = set(d_company_scope["company"].dropna().unique())

if company_filter and company_filter not in available_companies:
    st.session_state["ro_selected_company"] = None
    st.session_state["ro_company_chart_version"] += 1
    st.session_state["ro_sector_chart_version"] += 1
    company_filter = None


# ============================================================
# 5. FILTER SCOPE AND CLEAR BUTTON
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
b1.markdown(f"**Showing:** {scope_text}" + (f" · employment type: {', '.join(emp_sel)}" if emp_sel else ""))

if sector_filter or company_filter:
    b2.button("✖ Clear all", key="ro_clear_all_button", on_click=clear_all_reopen_filters)


# ============================================================
# 6. DATA FILTERING
# ============================================================

all_n = len(ro_df)
all_r = int(ro_df["is_reopen"].sum())
all_rate = all_r / all_n * 100 if all_n else 0

# Chart 1: company filter affects the sector distribution.
d_sector = ro_df[ro_df["company"] == company_filter] if company_filter else ro_df

# Chart 2: sector filter affects the company distribution.
d_company = ro_df[ro_df["sector"] == sector_filter] if sector_filter else ro_df

# KPI scope: apply both filters together.
scope = d_company[d_company["company"] == company_filter] if company_filter else d_company

s_n = len(scope)
s_r = int(scope["is_reopen"].sum())


# ============================================================
# 7. AGGREGATION AND SORTING
# ============================================================

def stats(d, group_col):
    g = d.groupby(group_col, observed=True).agg(postings=("is_reopen", "size"), reopen=("is_reopen", "sum")).reset_index()
    g["rate"] = g["reopen"] / g["postings"] * 100
    total_reopen = g["reopen"].sum()
    g["share"] = g["reopen"] / total_reopen * 100 if total_reopen else 0
    return g


def company_stats(d):
    g = d.groupby("company", observed=True).agg(postings=("is_reopen", "size"), reopen=("is_reopen", "sum"), is_agency=("is_agency", "max")).reset_index()
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
# 8. KPI
# ============================================================

if s_n == 0 or s_r == 0:

    st.info(f"No re-open postings for {scope_name} with these filters. Press Clear all or change the filters.")

else:

    scope_rate = s_r / s_n * 100
    vs = f", {scope_rate / all_rate:.1f}x the overall {all_rate:.1f}%" if (sector_filter or company_filter) and all_rate else ""

    k = st.columns(5)
    k[0].metric("Postings", f"{s_n:,}")
    k[1].metric("Re-Open Postings", f"{s_r:,}")
    k[2].metric("Re-Open Rate", f"{scope_rate:.1f}%", f"{scope_rate / all_rate:.1f}x overall at {all_rate:.1f}%" if (sector_filter or company_filter) and all_rate else None, delta_color="off")

    if company_filter:
        k[3].metric("Sectors covered", f"{scope['sector'].nunique():,}")
        k[4].metric("Share of all re-open", f"{s_r / all_r * 100:.1f}%" if all_r else "0%")
    else:
        comp_by_count = comp.sort_values(["reopen", "postings", "company"], ascending=[False, False, True], kind="stable")
        top = comp_by_count.iloc[0]
        top_share = top["reopen"] / s_r * 100 if s_r else 0
        top10_share = comp_by_count.head(10)["reopen"].sum() / s_r * 100 if s_r else 0
        k[3].metric("Top Company's Share", f"{top_share:.0f}%", top["company"], delta_color="off")
        k[4].metric("Top 10 Companies' Share", f"{top10_share:.0f}%")


    # ========================================================
    # 9. INTERACTIVE CHARTS
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
            ld["label"] = [f"{n} ({v:.1f}%)" if rate_view else f"{n} ({int(v):,})" for n, v in zip(ld["sector"], ld[value_col])]
            ld["highlight"] = ld["sector"].eq(sector_filter).map({True: "Selected", False: "Other"})

            pick_s = alt.selection_point(name="sector_pick", fields=["sector"], toggle=False, empty=False, clear="click[!event.item]")

            chart1 = alt.Chart(ld).mark_bar().add_params(pick_s).encode(
                y=alt.Y("label:N", sort=ld["label"].tolist(), title=None, axis=alt.Axis(labelLimit=300, labelOverlap=False)),
                x=alt.X(f"{value_col}:Q", title=x_title),
                color=alt.Color("highlight:N", scale=alt.Scale(domain=["Selected", "Other"], range=["#e76f51", "#2a9d8f"]), legend=None),
                tooltip=[
                    alt.Tooltip("sector:N", title="Sector"),
                    alt.Tooltip("postings:Q", format=",", title="Total postings"),
                    alt.Tooltip("reopen:Q", format=",", title="Re-open postings"),
                    alt.Tooltip("rate:Q", format=".1f", title="Re-open rate (%)"),
                    alt.Tooltip("share:Q", format=".1f", title="Share of re-open here (%)")
                ]
            ).properties(height=max(320, 30 * len(ld)))

            sector_key = f"ro_sector_chart_{st.session_state['ro_sector_chart_version']}"
            st.session_state["ro_active_sector_chart_key"] = sector_key

            st.altair_chart(chart1, use_container_width=True, on_select=on_sector_chart_select, key=sector_key)


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
            rd["label"] = [f"{n} ({v:.1f}%)" if rate_view else f"{n} ({int(v):,})" for n, v in zip(rd["company"], rd[value_col])]
            rd["highlight"] = rd.apply(lambda r: "Selected" if r["company"] == company_filter else ("Recruitment agency" if r["is_agency"] else "Other employer"), axis=1)

            pick_c = alt.selection_point(name="company_pick", fields=["company"], toggle=False, empty=False, clear="click[!event.item]")

            chart2 = alt.Chart(rd).mark_bar().add_params(pick_c).encode(
                y=alt.Y("label:N", sort=rd["label"].tolist(), title=None, axis=alt.Axis(labelLimit=330, labelOverlap=False)),
                x=alt.X(f"{value_col}:Q", title=x_title),
                color=alt.Color("highlight:N", scale=alt.Scale(domain=["Selected", "Recruitment agency", "Other employer"], range=["#e76f51", "#264653", "#2a9d8f"]), legend=alt.Legend(orient="bottom", title=None, labelLimit=300)),
                tooltip=[
                    alt.Tooltip("company:N", title="Company"),
                    alt.Tooltip("type:N", title="Company type"),
                    alt.Tooltip("postings:Q", format=",", title="Total postings"),
                    alt.Tooltip("reopen:Q", format=",", title="Re-open postings"),
                    alt.Tooltip("rate:Q", format=".1f", title="Re-open rate (%)"),
                    alt.Tooltip("share:Q", format=".1f", title="Share of re-open here (%)")
                ]
            ).properties(height=max(320, 30 * len(rd)))

            company_key = f"ro_company_chart_{st.session_state['ro_company_chart_version']}"
            st.session_state["ro_active_company_chart_key"] = company_key

            st.altair_chart(chart2, use_container_width=True, on_select=on_company_chart_select, key=company_key)


    # ========================================================
    # 10. KEY FINDINGS
    # ========================================================

    if company_filter:

        sec_by_count = sec.sort_values(["reopen", "postings", "sector"], ascending=[False, False, True], kind="stable")
        main_text = ""

        if not sector_filter and not sec_by_count.empty and sec_by_count["reopen"].sum():
            main = sec_by_count.iloc[0]
            main_text = f" Most of its re-open postings are in **{main['sector']}** ({main['reopen'] / sec['reopen'].sum() * 100:.0f}%)."

        st.info(f"📌 **Key Finding (Re-open drivers):** For {scope_name}, {s_r:,} of {s_n:,} postings are re-open ({scope_rate:.1f}%{vs}). That is {s_r / all_r * 100:.1f}% of all re-open postings from {s_n / all_n * 100:.1f}% of postings.{main_text}")

    else:

        rate_ex = (s_r - top["reopen"]) / (s_n - top["postings"]) * 100 if s_n > top["postings"] else 0.0
        driver = "driven mainly by one company" if top_share >= 25 else "spread across many companies"

        st.info(f"📌 **Key Finding (Re-open drivers):** In {scope_name}, {s_r:,} of {s_n:,} postings are re-open ({scope_rate:.1f}%{vs}). The top company, **{top['company']}**, accounts for **{top_share:.0f}%** of them (on {top['postings'] / s_n * 100:.1f}% of postings); the top 10 companies account for {top10_share:.0f}%. Without {top['company']} the re-open rate would be {rate_ex:.1f}%. Re-open here is therefore **{driver}**.")


    # ========================================================
    # 11. DETAIL TABLES
    # ========================================================

    with st.expander("See the tables", expanded=bool(sector_filter or company_filter)):

        t1, t2 = st.columns(2)

        # Match the sector table to chart 1's data scope.
        sec_view = sec[sec["sector"] == sector_filter].copy() if sector_filter else sec.copy()

        # Match the company table to chart 2's data scope.
        comp_view = comp[comp["company"] == company_filter].copy() if company_filter else comp.copy()

        # Apply the same sorting rules as the charts.
        sec_view = sort_rows(sec_view, "sector")
        comp_view = sort_rows(comp_view, "company")

        t1.subheader("Sector ranking")
        t1.caption("Same filtered sector data as chart 1. Chart displays the top 15.")

        t1.dataframe(
            sec_view.rename(columns={"sector": "Sector", "postings": "Postings", "reopen": "Re-open", "rate": "Re-open rate (%)", "share": "Share of re-open here (%)"}),
            hide_index=True,
            use_container_width=True,
            column_config={"Re-open rate (%)": st.column_config.NumberColumn(format="%.1f"), "Share of re-open here (%)": st.column_config.NumberColumn(format="%.1f")}
        )

        t2.subheader("Company ranking")
        t2.caption("Same filtered company data as chart 2. Table displays the top 50.")

        t2.dataframe(
            comp_view.head(50).drop(columns="is_agency").rename(columns={"company": "Company", "postings": "Postings", "reopen": "Re-open", "rate": "Re-open rate (%)", "share": "Share of re-open here (%)"}),
            hide_index=True,
            use_container_width=True,
            column_config={"Re-open rate (%)": st.column_config.NumberColumn(format="%.1f"), "Share of re-open here (%)": st.column_config.NumberColumn(format="%.1f")}
        )
