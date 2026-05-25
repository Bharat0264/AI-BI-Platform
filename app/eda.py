def perform_eda(df):

    print("\nFirst 5 Rows:")
    print(df.head())

    print("\nDataset Information:")
    print(df.info())

    print("\nStatistical Summary:")
    print(df.describe())

    print("\nColumns:")
    print(df.columns)