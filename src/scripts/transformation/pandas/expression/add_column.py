"""
Module for adding or updating columns in a DataFrame.
"""
import logging
from update_audit import audit_failure

task_logger = logging.getLogger('task_logger')

# def insert_new_column(df, temp_df, output_column, input_column, col):
#     """inserts new columns in a DataFrame"""
#     try:
#         if input_column in df.columns:
#             insert_loc = df.columns.get_loc(input_column) + 1
#             if isinstance(col, str):
#                 if col in temp_df.columns:
#                     df.insert(insert_loc, output_column, temp_df[col])
#                 elif col in df.columns:
#                     df.insert(insert_loc, output_column, df[col])
#                 elif col == '':
#                     df.insert(insert_loc, output_column, "")
#                 else:
#                     raise ValueError(f"Column {col} not found in df or temp_df." )
#         else:
#             if col in temp_df.columns:
#                 df[output_column] = temp_df[col]
#             elif col in df.columns:
#                 df[output_column] = df[col]
#             else:
#                 df[output_column] = ''
#         return df
#     except Exception as e:
#         logging.exception("Error occured in insert_new_column function with error : %s",e)
#         raise e

def insert_new_column(arguments,df, temp_df, output_column, input_column, col):
    """Inserts new columns in a DataFrame"""
    try:
        df = df.copy()  # Ensure df is a copy to avoid SettingWithCopyWarning

        if input_column in df.columns:
            insert_loc = df.columns.get_loc(input_column) + 1
            if isinstance(col, str):
                if col in temp_df.columns:
                    df.insert(insert_loc, output_column, temp_df[col].copy())
                elif col in df.columns:
                    df.insert(insert_loc, output_column, df[col].copy())
                elif col == '':
                    df.insert(insert_loc, output_column, "")
                else:
                    raise ValueError(f"Column {col} not found in df or temp_df.")
        else:
            if col in temp_df.columns:
                df.loc[:, output_column] = temp_df[col].copy()
            elif col in df.columns:
                df.loc[:, output_column] = df[col].copy()
            else:
                df.loc[:, output_column] = ''

        return df
    except Exception as e:
        logging.exception("Error occured in insert_new_column function with error : %s",e)
        audit_failure(arguments)
        raise e

def add_or_update_column(arguments,df, temp_df, output_column, input_column, col):
    """
    Adds a new column named `output_column` to the DataFrame `df` or updates an existing one.

    Args:
        df (pandas.DataFrame): The DataFrame to modify.
        temp_df (pandas.DataFrame): A temporary DataFrame used to store columns (optional).
        output_column (str): The name of the new or updated column.
        input_column (str, optional): The name of the existing column to insert the new
        column after.col (str or pandas.Series, optional): The column to use for the new
        column's values.
            - If a string, it represents a column name in `df` or `temp_df` (if provided).
            - If a pandas.Series, its values are used to populate the new column.
            - Defaults to None, creating an empty column.

    Returns:
        pandas.DataFrame: The modified DataFrame.

    Raises:
        ValueError: If the 'output_column' already exists and `col` is None (empty).
    """
    try:
        # Check for existing output column
        if output_column in df.columns:
            if col in temp_df.columns:
                df[output_column] = temp_df[col]
            elif col in df.columns:
                df[output_column] = df[col]
            else:
                return df
        else:
            # Insert new column
            df=insert_new_column(arguments,df, temp_df, output_column, input_column, col)
        return df
    except ValueError as e:
        # Handle the specific ValueError here, if necessary
        task_logger.error("An error occurred in add_or_update_column function with error :%s",e)
        audit_failure(arguments)
        raise
