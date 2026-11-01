## use streamlit_app environment

import streamlit as st
import pandas as pd
from datetime import datetime
import json

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
    df = df[df['positionLevels']=='Fresh/entry level'] 
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
    #         ((salary - stats["mean"]).abs() > 3 * stats["std"]) | (salary - stats["mean"]).abs() < 3 * stats["std"]
    #     ).fillna(False).any()

    #     if is_outlier:
    #         medians = category_salary.reindex(categories)["median"].dropna()
    #         if not medians.empty:
    #             return medians.mean()

    #     return salary

    # df["average_salary"] = df.apply(replace_salary, axis=1)

    # return df

df = load_data(DATA_PATH)

st.title("Sector Demand for Entry Level Workers")
#st.dataframe(df.head(10))

###################################################
## ADD SIDEBAR WIDGETS HERE VVVVVVVV
################################################### 

## FILTER SIDEBAR AND DATA FILTERED BY SECTOR
# 
st.sidebar.header("Filters")
# get sectors
unique_sectors = pd.json_normalize(df["categories"].dropna().map(json.loads).explode()).drop_duplicates().sort_values('id')
unique_sectors = unique_sectors["category"]

#FILTER WIDGETS
selected_sectors = st.sidebar.multiselect("Sector", unique_sectors, default=[])

filtered_df = df.copy()

if selected_sectors:
    filtered_df = filtered_df[filtered_df["categories"].apply(
    lambda categories: any(value in categories for value in selected_sectors))]

# st.header("Filtered Results")
# st.write(
#     f"Matching rows: {len(filtered_df):,} | Columns: {len(filtered_df.columns)}")
# st.dataframe(filtered_df)

###################################################
## ADD REST OF YOUR CODE HERE VVVVVVVV
################################################### 