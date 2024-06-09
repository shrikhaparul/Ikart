"""
This module provides functionality to apply window functions to Pandas DataFrames. 
"""
import logging
from expression.add_column import add_or_update_column

task_logger = logging.getLogger('task_logger')

def get_clauses(syntax_parts):
    """
    Extract the partition and order by clauses from the window function syntax.

    Args:
    - syntax_parts (list): List containing the parts of the window function syntax.

    Returns:
    - tuple: A tuple containing the partition clause and the order by clause.
    """
    partition_clause = None
    order_by_clause = None
    over_clause = syntax_parts[1].strip()
    if over_clause.startswith("(") and over_clause.endswith(")"):
        over_clause = over_clause[1:-1].strip()
        clauses = over_clause.split(" ")
        if "PARTITION" in clauses and "BY" in clauses:
            partition_clause = clauses[2]
        if "ORDER" in clauses and "BY" in clauses:
            order_by_clause = clauses[-1]
    return partition_clause,order_by_clause

def add_row_number(temp_df, temp_df_header, df, syntax):
    """
    Add a row number column to the DataFrame based on the window function syntax.

    Args:
    - temp_df (DataFrame): Temporary DataFrame used for referencing columns.
    - temp_df_header (list): List of headers in the temporary DataFrame.
    - df (DataFrame): DataFrame to which the row number column will be added.
    - syntax (str): Syntax of the row_number window function.

    Returns:
    - Series: A pandas Series containing the row numbers.
    """
    partition_clause = None
    order_by_clause = None
    syntax = syntax.replace("ROW_NUMBER()", "")
    syntax_parts = syntax.split("OVER")
    if len(syntax_parts) > 1:
        partition_clause,order_by_clause=get_clauses(syntax_parts)
    # Adding ROW_NUMBER column
    if partition_clause is not None and order_by_clause is not None:
        if partition_clause in temp_df_header:
            partition_cols =temp_df[partition_clause]
        else:
            partition_cols=df[partition_clause]
        row_number=df.groupby(partition_cols)[order_by_clause].rank(method='first',ascending=False)
        return  row_number.astype(int)
    raise SyntaxError("Invalid syntax of row_number function")

def window_exp(temp_df, temp_df_header, df, expression):
    """
    Apply window functions like ROW_NUMBER to a DataFrame.

    Args:
    - temp_df (DataFrame): Temporary DataFrame used for referencing columns.
    - temp_df_header (list): List of headers in the temporary DataFrame.
    - df (DataFrame): DataFrame to which the window function result will be applied.
    - expression (dict): Dictionary containing the expression details including:
        - "output_column" (str): Name of the column to store the window function result.
        - "operator_name" (str): Type of window function, e.g., 'row_number'.
        - "operation" (str): Syntax of the window function.

    Returns:
    - tuple: A tuple containing the updated temporary DataFrame and 
    the DataFrame with the window function result applied.
    """
    try:
        output_column = expression['output_col_name']
        operator_name = expression['operator']
        match operator_name:
            case 'row_number':
                df = add_or_update_column(df,
                                        temp_df,
                                        expression['output_col_name'],
                                        expression['input_col_name'],
                                        '')
                df[output_column]=add_row_number(temp_df,
                                                 temp_df_header,
                                                 df,
                                                 expression['expression_value'])
    except Exception as e:
        task_logger.error("Unable to perform window expression. Exception %s",e)
        raise
    return temp_df, df
