def clean_data(df):

    print("\nChecking Missing Values:")
    print(df.isnull().sum())

    print("\nRemoving Duplicate Rows...")
    df = df.drop_duplicates()

    print("\nDataset Cleaned Successfully")

    return df