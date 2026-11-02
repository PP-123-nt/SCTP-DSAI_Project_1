## use streamlit_app environment

import streamlit as st
import pandas as pd
from datetime import datetime
import json
import altair as alt
import math
import plotly.express as px

st.set_page_config(page_title="Sector Demand for Entry Level Workers", layout="wide")

print(f"🟢 Rerun at: {datetime.now()}")

DATA_PATH = "SGJobData.csv"

@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    df = df.dropna(axis = 1, how = 'all')               # drop the empty column
    remove_row = (df.isna() | df.eq(0)).all(axis=1)     # drop the empty rows (all NaN or 0)
    df = df.loc[~remove_row]                            # drop the empty rows (all NaN or 0)
    df['metadata_expiryDate'] = pd.to_datetime(df['metadata_expiryDate'], format = '%Y-%m-%d')
    df['metadata_newPostingDate'] = pd.to_datetime(df['metadata_newPostingDate'], format = '%Y-%m-%d')
    df['metadata_originalPostingDate'] = pd.to_datetime(df['metadata_originalPostingDate'], format = '%Y-%m-%d')
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
## PHASE 2: SECTOR DEMAND & SALARY ANALYSIS
################################################### 

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


###################################################
## RAW / FILTERED RESULTS VIEW
################################################### 
st.markdown("---")
st.header("Filtered Results Data View (Entry-Level Focus)")
st.write(f"Matching entry-level rows: {len(entry_df):,} | Columns: {len(entry_df.columns)}")
st.dataframe(entry_df, use_container_width=True)

