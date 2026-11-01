## Notes

### 1. Data Loading and Cleaning
  - I work with 'SGJobData.csv' located in the same folder as app.py
    - load into dataframe *df*, cached
    - deleted empty occupationId column 
    - deleted ~4000 empty rows (all values are NaN or 0)
    - converted relevant columns to datetime and category type
    - selected rows with ~~positionLevels=='Fresh/entry level'~~ and  *metadata_newPostingDate* >= '2023-05'
  - Outlier salary values were not typos - advertisers deliberately put in very low and very high min/max salary values so that the post is shown to as many people as possible (e.g. salary_minimum =1 and salary_maximum = 100000). So most of these are not reflective of the job's actual salary. Another issue is that advertisers may have indicated yearly or hourly rates instead of the expected monthly. So I did what seemed most sensible:
    - there are 43 unique sectors ("categories" column); compute median *average_salary* for each sector
    - for each sector, identify outlier *average_salary* (exceed mean +/- 3 std) and replace with corresponding median
    - for postings in multiple sectors, replace with average of the medians for those sectors
    - **NOTE**: currently commented out (ln 34-77) because it adds 2 mins to loading time
    - **NOTE 2**: I would suggest that, if you want to do things with salary, only use *average_salary* and not *salary_minimum* or *salary_maximum* (less reliable)

### 2. Dashboard
  - Added a sidebar for filter widgets
    - Made widget to filter data to one/multiple sectors, filtered data goes to *filtered_df*, hopefully helpful for someone
    - entry level -only data goes to *entry_df*   
    - Displays data rows, that's all
  - added V's part
    - overview histogram of fresh entry positions + pie chart fresh entry positions by status (open, reopened, closed) + findings   
