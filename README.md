# TDT4225-Assignment2

## Overview

This project contains the code used for the exploratory data analysis, data cleaning, database loading, and queries for the assignment.

The repository/zip file contains the following files:

- `eda.ipynb` – Contains the code used for the exploratory data analysis (EDA) in Part 1.
- `data_cleansing.py` – Cleans the dataset based on the findings from the EDA and loads the cleaned data into the Docker database container using the configuration specified in `DbConnector.py`.
- `queries.py` – Contains the queries used for Part 2 of the assignment.
- `DbConnector.py` – Contains the database connection setup used to connect to the Docker database container.
- `utils.py` – Contains constants and utility functions that are used by both `eda.ipynb` and `data_cleansing.py`.

Helper functions that are only used during the exploratory data analysis are defined directly in `eda.ipynb`.

## Required Dataset

**Note:** The `porto.csv` dataset is not included in the repository or the submitted zip file.

To run the code, add `porto.csv` to the same directory as the other project files.

The folder should therefore look approximately like this:

```text
project/
├── porto.csv
├── eda.ipynb
├── data_cleansing.py
├── queries.py
├── DbConnector.py
└── utils.py
```

## Workflow

1. Add `porto.csv` to the project folder.
2. Run `eda.ipynb` to reproduce the exploratory data analysis from Part 1.
3. Run `data_cleansing.py` to clean the dataset and load it into the Docker database container.
4. Run `queries.py` to execute the queries used in Part 2.
