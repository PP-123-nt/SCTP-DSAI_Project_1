## use streamlit_app environment

import streamlit as st
import pandas as pd
from datetime import datetime
import json
import altair as alt
import math
import plotly.express as px

st.set_page_config(page_title="Which Sectors Need More Workers?", layout="wide")

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
    return df

df = load_data(DATA_PATH)

@st.cache_data
def load_e_data():
    e_df = df[df['positionLevels'] == 'Fresh/entry level'].copy()
    # replaces outlier 'average salary' values with the median for that sector ("category")
    # outliers are > or < 3 std from mean for each sector
    # THIS IS TEMP COMMENTED OUT TO REDUCE LOADING TIMES
    #############################################
    def category_names(value):
        if isinstance(value, str):
            value = json.loads(value)
        return [item["category"] for item in value] if isinstance(value, list) else []

    category_salary = (
        e_df.assign(category=e_df["categories"].map(category_names))
        .explode("category")
        .dropna(subset=["category", "average_salary"])
        .groupby("category")["average_salary"]
        .agg(mean="mean", median="median")
        .sort_index()
    )
    category_rows = (
    e_df.assign(category=e_df["categories"].map(category_names))
        .explode("category")
        .dropna(subset=["category", "average_salary"])
    )

    category_std = category_rows.groupby("category")["average_salary"].std()
    category_stats = category_salary.join(category_std.rename("std"))

    def replace_salary(row):
        salary = row["average_salary"]
        if pd.isna(salary):
            return salary

        categories = list(dict.fromkeys(category_names(row["categories"])))
        stats = category_stats.reindex(categories)

        is_outlier = (
            ((salary - stats["mean"]).abs() > 3 * stats["std"]) | (salary - stats["mean"]).abs() < 3 * stats["std"]
        ).fillna(False).any()

        if is_outlier:
            medians = category_salary.reindex(categories)["median"].dropna()
            if not medians.empty:
                return medians.mean()

        return salary

    e_df["average_salary"] = e_df.apply(replace_salary, axis=1)
    return e_df

e_df = load_e_data()

st.title("Which Sectors Need More Workers?")
#st.dataframe(df.head(10))

# Business case and objective of the dashboard. We can either list here or verbalise it during the presentation.
st.write(
    "**Scenario**: As government policymakers, we want to identify sectors with high demand"
    " for entry-level hires, which will inform training decisions, employment support and"
    " employer partnerships. Towards that end, this dashboard compares the volume of job"
    " postings and associated salary between different sectors."
)

###################################################
## PHASE 1: MACRO ECONOMIC CLIMATE
###################################################

st.markdown("---")
st.header("1. Volume of entry-level job postings is similar across months")

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

selected_sectors = st.multiselect("Sector", unique_sectors, default=[])

# Filtered DataFrame containing ALL position levels
filtered_df = df.copy()

if selected_sectors:
    filtered_df = filtered_df[filtered_df["categories"].apply(
        lambda x: any(sec in extract_categories(x) for sec in selected_sectors)
    )]

# Dedicated subset for entry-level specific metrics & status chart
entry_df = filtered_df[filtered_df['positionLevels'] == 'Fresh/entry level']

if not filtered_df.empty:
    
    # Calculate overall average percentage of entry level jobs
    total_jobs_count = len(filtered_df)
    entry_jobs_count = len(entry_df)
    avg_entry_pct = (entry_jobs_count / total_jobs_count * 100) if total_jobs_count > 0 else 0.0

    # Quick Summary Metrics (Strictly Entry-Level)
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Total Postings", f"{entry_jobs_count:,}")
    with col_m2:
        entry_share = (entry_jobs_count / len(filtered_df) * 100 if len(filtered_df) > 0 else 0)
        st.metric("Share of Postings", f"{entry_share:.1f}%")
    with col_m3:
        unique_categories = (entry_df["categories"].dropna().apply(lambda value: [item["category"] for item in json.loads(value)]).explode().nunique())
        st.metric("Sectors with Postings",f"{unique_categories:,}")
    with col_m4:
        median_salary = entry_df["average_salary"].median()
        st.metric("Median Average Salary",f"S${median_salary:,.0f}")
    
        # --- ROW 1: SEGMENTED HISTOGRAM & JOB STATUS PIE CHART BESIDE IT ---
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        st.subheader("Monthly Job Posting Volume")
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
        st.subheader("Entry-Level Job Status Breakdown")
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

#st.markdown("---")

###################################################
## Entry-Level Employment Types by Sector
###################################################
st.header("2. Entry-level positions are predominantly permanent or full-time")

st.markdown(
    "Employment types across sectors with the most entry-level "
    "postings, ranked by permanent employment share."
)

# 1. Create a separate dataset for this chart
chart3_df = e_df.copy()

# chart3_df["Chart Posting Date"] = pd.to_datetime(
#     chart3_df["metadata_newPostingDate"],
#     errors="coerce"
# ).dt.normalize()

# valid_dates = chart3_df["Chart Posting Date"].dropna()

# 2. Select the number of sectors
top_n = st.selectbox(
    "Number of sectors shown",
    options=[5, 10, 15, 43],
    index=1,
    key="chart3_top_n"
)

# 3. Extract sectors from JSON categories
def get_sector_names(value):
    if pd.isna(value):
        return []

    return sorted({
        item["category"].strip()
        for item in json.loads(value)
        if item.get("category")
    })

# date_min = chart3_df ["metadata_newPostingDate"].min().date()
# date_max = chart3_df ["metadata_newPostingDate"].max().date()

# selected_dates = st.date_input(
#     "Posting Date Range — this chart only",
#     value=(date_min, date_max),
#     min_value=date_min,
#     max_value=date_max,
#     key="metadata_newPostingDate"
# )

#     if len(selected_dates) != 2:
#         st.info("Select both a start date and an end date.")

#     else:
#         start_date, end_date = selected_dates

#         # 4. Apply the date filter
#         chart3_df = chart3_df[
#             chart3_df ["metadata_newPostingDate"].between(
#                 pd.Timestamp(start_date),
#                 pd.Timestamp(end_date)
#             )
#         ].copy()

        # # 5. Keep only Fresh/Entry Level postings
        # entry_jobs = chart3_df[
        #     chart3_df["positionLevels"]
        #     .str.strip()
        #     .str.casefold()
        #     .isin(["fresh/entry", "fresh/entry level"])
        # ].copy()

        # 6. Prepare sectors and employment types
chart3_df["Sector"] = chart3_df["categories"].apply(
    get_sector_names
)

chart3_df["Employment Type"] = (
    chart3_df["employmentTypes"]
    .astype("string")
    .str.strip()
    .fillna("Not specified")
    .replace("", "Not specified")
)

# Keep Permanent and Full Time separate
label_map = {
    "permanent": "Permanent",
    "full time": "Full Time"
}

chart3_df["Employment Type"] = (
    chart3_df["Employment Type"]
    .apply(
        lambda value: label_map.get(
            value.casefold(), value
        )
    )
)

# 7. Create one row per posting per sector
sector_jobs = (
    chart3_df.explode("Sector")
    .dropna(subset=["Sector"])
    .drop_duplicates(
        subset=["metadata_jobPostId", "Sector"]
    )
)

# 8. Count postings tagged Others
others_mask = (
    sector_jobs["Sector"]
    .str.casefold()
    .eq("others")
)

others_count = sector_jobs.loc[
    others_mask, "metadata_jobPostId"
].nunique()

total_entry_postings = (
    chart3_df["metadata_jobPostId"].nunique()
)

others_share = (
    others_count / total_entry_postings * 100
    if total_entry_postings > 0 else 0
)

# Exclude Others from this chart only
named_sector_jobs = sector_jobs.loc[
    ~others_mask
].copy()

# 9. Select top sectors by posting count
sector_totals = named_sector_jobs.groupby("Sector").size()

permanent_counts = (
    named_sector_jobs.loc[
        named_sector_jobs["Employment Type"] == "Permanent"
    ]
    .groupby("Sector")
    .size()
)

top_sectors = (
    permanent_counts.div(sector_totals)
    .fillna(0)
    .sort_values(ascending=False, kind="stable")
    .head(top_n)
    .index
    .tolist()
)

if not top_sectors:
    st.info(
        "No sectors available for the selected filters. "
        "Try widening the date range."
    )

else:
    # 10. Count postings by sector and employment type
    breakdown = (
        named_sector_jobs[
            named_sector_jobs["Sector"].isin(top_sectors)
        ]
        .groupby(["Sector", "Employment Type"])
        .size()
        .reset_index(name="Postings")
    )

    breakdown["Total"] = (
        breakdown.groupby("Sector")["Postings"]
        .transform("sum")
    )

    breakdown["Share"] = (
        breakdown["Postings"] / breakdown["Total"]
    )

    # 11. Sort sectors by Permanent share
    permanent_share = (
        breakdown[
            breakdown["Employment Type"] == "Permanent"
        ]
        .set_index("Sector")["Share"]
        .reindex(top_sectors, fill_value=0)
        .sort_values(
            ascending=False,
            kind="stable"
        )
        
    )

    sector_order = permanent_share.index.tolist()

    # 12. Put Permanent first, followed by Full Time
    priority_types = ["Permanent", "Full Time"]

    present_types = (
        breakdown["Employment Type"].unique().tolist()
    )

    employment_order = [
        label for label in priority_types
        if label in present_types
    ] + sorted(
        label for label in present_types
        if label not in priority_types
    )

    breakdown["Type Order"] = (
        breakdown["Employment Type"]
        .map({
            label: i
            for i, label in enumerate(employment_order)
        })
    )

    # 13. Create the chart using Set2 colours
    chart = alt.Chart(breakdown).mark_bar().encode(
        y=alt.Y(
            "Sector:N",
            sort=sector_order,
            title="Sector"
        ),
        x=alt.X(
            "Share:Q",
            stack="zero",
            title="Share of Entry-Level Postings",
            axis=alt.Axis(format=".0%"),
            scale=alt.Scale(domain=[0, 1])
        ),
        color=alt.Color(
            "Employment Type:N",
            scale=alt.Scale(
                domain=employment_order,
                scheme="set2"
            ),
            title="Employment Type"
        ),
        order=alt.Order(
            "Type Order:Q",
            sort="ascending"
        ),
        tooltip=[
            alt.Tooltip("Sector:N"),
            alt.Tooltip("Employment Type:N"),
            alt.Tooltip("Postings:Q", format=","),
            alt.Tooltip("Share:Q", format=".1%"),
            alt.Tooltip(
                "Total:Q",
                title="Sector Postings",
                format=","
            )
        ]
    ).properties(
        height=max(250, len(top_sectors) * 35)
    )

    st.altair_chart(
        chart,
        use_container_width=True
    )

    # 14. Findings update with the selected filters
    highest_share = permanent_share.max()
    lowest_share = permanent_share.min()

    highest_sectors = ", ".join(
        permanent_share[
            permanent_share == highest_share
        ].index
    )

    lowest_sectors = ", ".join(
        permanent_share[
            permanent_share == lowest_share
        ].index
    )

    st.info(
        f"📌 **Key Findings:** Among the "
        f"{len(top_sectors)} sectors shown, "
        f"the permanent posting share ranges from "
        f"**{lowest_share:.1%}** to "
        f"**{highest_share:.1%}**. "
        f"Highest: **{highest_sectors}**. "
        f"Lowest: **{lowest_sectors}**."
    )

    # 15. Chart notes
    st.caption(
        f"Showing {len(top_sectors)} of up to "
        f"{top_n} sectors with the most entry-level "
        "postings, ordered by permanent share."
    )

st.caption(
    f"'Others' is excluded from this sector ranking. "
    f"{others_count:,} postings ({others_share:.1f}%) "
    "carry this category within this chart's date "
    "range and current sidebar filters. The exclusion "
    "does not change overall dashboard metrics. "
    "Jobs tagged with multiple sectors are "
    "counted once in each sector."
)

##
###########################
st.header("3. Entry-level salaries vary between sectors")

def get_sectors(value):
    try:
        categories = json.loads(value)
        return [
            item["category"]
            for item in categories
            if isinstance(item, dict) and "category" in item
        ]
    except (TypeError, json.JSONDecodeError):
        return []

e_df["sector"] = e_df["categories"].apply(get_sectors)
e_df = e_df.explode("sector").dropna(subset=["sector"])

salary_columns = ["salary_minimum", "salary_maximum", "average_salary"]
for column in salary_columns:
    e_df[column] = pd.to_numeric(e_df[column], errors="coerce")

sector_salary = (
    e_df.groupby("sector")[salary_columns]
    .mean()
    .dropna(subset=["salary_minimum", "salary_maximum"])
    .sort_values("salary_maximum", ascending=False)
    .reset_index()
)

sector_order = sector_salary["sector"].tolist()

floating_bars = alt.Chart(sector_salary).mark_bar(size=15).encode(
    x=alt.X("sector:N", sort=sector_order, title="Sector"),
    y=alt.Y("salary_minimum:Q", title="Salary"),
    y2=alt.Y2("salary_maximum:Q"),
    color=alt.value("steelblue"),
    tooltip=[
        "sector",
        alt.Tooltip("salary_minimum:Q", title="Average minimum", format=",.0f"),
        alt.Tooltip("salary_maximum:Q", title="Average maximum", format=",.0f"),
    ],
)

average_points = alt.Chart(
    sector_salary.dropna(subset=["average_salary"])
).mark_point(
    filled=True,
    color="orange",
    size=100,
).encode(
    x=alt.X("sector:N", sort=sector_order),
    y=alt.Y("average_salary:Q"),
    tooltip=[
        "sector",
        alt.Tooltip("average_salary:Q", title="Average salary", format=",.0f"),
    ],
)

chart = (floating_bars + average_points).properties(
    title="Salary Range and Average by Sector",
    height=500,
)

st.altair_chart(chart, use_container_width=True)

st.info(
        f"📌 **Key Findings:** Salary data appears less reliable, due to job postings created"
        f"with extreme salary ranges in order to boost visibilty."
        f"After replacing outlier average salary values (exceeds sector mean +/- 3 std.) with "
        f"sector medians, average entry-level salaries range from $3,450 to $2,262 per month."
        f"Highest: **Insurance, Banking and Finance**. Lowest: **General Work, Advertising/Media**"
    )

st.markdown('---')        

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

st.header("4. Entry-level postings associated with higher salary and fewer applicants")
chart_emp = st.multiselect("Employment Type (this chart only)",
                           sorted(entry_all["employmentTypes"].dropna().unique()), default=["Permanent", "Full Time"])
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

st.markdown('---')     

## Policy Implications 
st.header("5. Policy Implications")

st.markdown("""
- **Expand entry-level pathways:** Partner with employers on
  structured onboarding and workplace training.
- **Explore permanent employment pathways:** Engage sectors with
  lower permanent shares to understand barriers and conversion options.
- **Target training and job matching:** Investigate recruitment
  barriers before deciding on courses or career outreach.
""")

with st.expander("View illustrative policy actions"):
    st.markdown("""
    - **Engineering:** Pilot paid entry-level roles with mentoring.
    - **F&B:** Explore contract-to-permanent pathways where appropriate.
    - **Construction:** Link short courses to verified vacancies
      if employers confirm specific skills gaps.
    """)

st.caption(
    "These are proposed actions for further assessment. "
    "Job-posting data alone cannot establish skills shortages "
    "or actual employment outcomes."
)

###################################################
## RAW / FILTERED RESULTS VIEW
################################################### 
# st.markdown("---")
# st.header("Filtered Results Data View (Entry-Level Focus)")
# st.write(f"Matching entry-level rows: {len(entry_df):,} | Columns: {len(entry_df.columns)}")
# st.dataframe(entry_df, use_container_width=True)