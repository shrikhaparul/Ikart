import duckdb
import pandas as pd
import polars as pl

def perform_sql_operation(data_sources,operation):
    """
    Execute a SQL operation on the provided data sources.

    Parameters:
        data_sources (dict): A dictionary containing DataFrames to be used as tables.
        operation (dict): A dictionary containing details of the operation to be performed.
            It should have the following keys:
                - "input_df" (list): A list of table names to be used in the operation.
                - "sql_query" (str): The SQL query to be executed.

    Returns:
        DataFrame: The result of the SQL operation as a pandas DataFrame.
    """
    try:
        input_dfs=operation["input_df"]
        query=operation["query"]
        dataframes={}
        for i in input_dfs:
            dataframes[i]=data_sources[i]
        con = duckdb.connect(database=':memory:')
        for table_name, dataframe in dataframes.items():
            con.register(table_name, dataframe)
        result_df = con.execute(query).fetchdf()
        print(result_df)
        return result_df
    except KeyError as e:
        print(f"KeyError: {e}. Please ensure the keys in 'input_dfs' are present in 'data_sources'.")
        raise
    except duckdb.Error as e:
        print(f"DuckDB Error: {e}. There was an error with the DuckDB execution.")
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise

if __name__=="__main__":  
    df1 = pd.DataFrame({
        'id': [4,5, 6],
        'name': ['Alice', 'Bob', 'Charlie']
    })

    df2 = pd.DataFrame({
        'id': [4, 5, 6],
        'age': [25, 30, 35]
    })
    pdf1=pl.from_pandas(df1).lazy()
    pdf2=pl.from_pandas(df2).lazy()
    print(type(df1))
    # Dictionary with DataFrames
    dataframes = {
        'table1': df1,
        'table2': df2
    }
    operation={"input_df":["table1","table2"],
            "query":"select * from table2,table1 where table1.id=table2.id"}

    perform_sql_operation(dataframes,operation)
    