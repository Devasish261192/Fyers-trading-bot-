import pandas as pd
def add_fractals(df):
    df['upfractal'] = False
    df['downfractal'] = False

    for i in range(4, len(df)):
        # Use .iloc for consistent integer-based indexing
        if (df['close'].iloc[i-2] > df['close'].iloc[i] and
            df['close'].iloc[i-2] > df['close'].iloc[i-1] and
            df['close'].iloc[i-2] > df['close'].iloc[i-3] and
            df['close'].iloc[i-2] > df['close'].iloc[i-4]):
            df.iloc[i-2, df.columns.get_loc('upfractal')] = True  # Use .iloc and column name

        if (df['close'].iloc[i-2] < df['close'].iloc[i] and
            df['close'].iloc[i-2] < df['close'].iloc[i-1] and
            df['close'].iloc[i-2] < df['close'].iloc[i-3] and
            df['close'].iloc[i-2] < df['close'].iloc[i-4]):
            df.iloc[i-2, df.columns.get_loc('downfractal')] = True  # Use .iloc and column name

    
    return df

def add_recursive_fractals(df):
    fr_test_df = df.copy()
    fr_test_df.reset_index(drop=False, inplace=True)
    fr_test_df['key'] = fr_test_df.index
    fractal_75 = add_fractals(fr_test_df)
    fractal_df_1 = fractal_75[(fractal_75['Fractals'] == 1) | (fractal_75['Fractals'] == -1)]

    fractal_df_1['index_1'] = fractal_df_1.index
    fractal_df_1.reset_index(drop=True, inplace=True)
    fractal_df_2 = add_fractals(fractal_df_1)
    fractal_df_2 = fractal_df_2[(fractal_df_2['Fractals'] == 1) | (fractal_df_2['Fractals'] == -1)]

    fractal_df_2.reset_index(drop=True, inplace=True)
    fractal_df_3 = add_fractals(fractal_df_2)
    print(fractal_df_3[(fractal_df_3['Fractals'] == 1) | (fractal_df_3['Fractals'] == -1)].head(60))
    fractal_df_3 = fractal_df_3[(fractal_df_3['Fractals'] == 1) | (fractal_df_3['Fractals'] == -1)]

    # Step 6: Add Fractal 1, Fractal 2, and Fractal 3 columns to the original DataFrame
    fr_test_df['Fractal_1'] = 0
    fr_test_df['Fractal_2'] = 0
    fr_test_df['Fractal_3'] = 0

    df1 = fractal_df_1[['Fractals','key']].copy()
    df2 = fractal_df_2[['Fractals','key']].copy()
    df3 = fractal_df_3[['Fractals','key']].copy()

    merged_df = pd.merge(fr_test_df, df1, on='key', how='left')
    
    merged_df['Fractal_1'] = merged_df['Fractals_x'].fillna(0).astype(int)
    # print(merged_df)
    merged_df.drop(columns=['Fractals_x'], inplace=True)
    merged_df = pd.merge(merged_df, df2, on='key', how='left')
    merged_df['Fractal_2'] = merged_df['Fractals_y'].fillna(0).astype(int)
    merged_df.drop(columns=['Fractals_y'], inplace=True)
    merged_df.drop(columns=['Fractals'], inplace=True)
    # print(df3)
    merged_df = pd.merge(merged_df, df3, on='key', how='left')
    merged_df['Fractal_3'] = merged_df['Fractals'].fillna(0).astype(int)
    merged_df.drop(columns=['Fractals'], inplace=True)
    # print(merged_df.head(60))
    # pass
    return merged_df