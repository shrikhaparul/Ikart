"""
Module for parsing and evaluating conditional expressions in DataFrames.
"""
import re
import logging
import numpy as np
from pandasql import sqldf
from expression.add_column import add_or_update_column

task_logger = logging.getLogger('task_logger')

COLUMN_DATATYPE_MISMATCH_ERROR = "columns are not of same datatype"
def perform_coalesce(temp_df, temp_df_header, df, expression):
    """
    Perform coalesce operation on the DataFrame.

    Coalesce returns the first non-null value among the specified columns and updates
    the DataFrame accordingly.

    Args:
        temp_df (pandas.DataFrame): Temporary DataFrame.
        temp_df_header (list): Headers of the temporary DataFrame.
        df (pandas.DataFrame): Main DataFrame.
        expression (dict): Dictionary containing expression details.

    Returns:
        pandas.DataFrame: Updated DataFrame after performing the coalesce operation.
    """
    coalesce_str=expression['expression_value']
    coalesce_str=coalesce_str.strip()
    pattern = r"coalesce\s*\(\s*\w+\s*(?:,\s*\w+\s*)*(?:,\s*\"[\w\s]*\"\s*)?\)"
    match = re.match(pattern, coalesce_str)
    # print(match)
    if match:
        coalesce_str=expression['expression_value']
        coalesce_str=coalesce_str.strip()
        column_str = coalesce_str[9:-1]
        pattern = r'\s*,\s*'
        elements = re.split(pattern, column_str.strip())
        columns = [re.sub(r'^(")?("")?$', '', element) for element in elements]
        df = add_or_update_column(df,
                                    temp_df,
                                    expression['output_col_name'],
                                    expression['input_col_name'],
                                    columns[0])
        # for col in columns[1:]:
            # if col in temp_df_header:
            #     df[expression['output_col_name']] = df[expression['output_col_name']].fillna(
            #     temp_df[col]).combine_first(temp_df[col])
            # elif col in df.columns:
            #     df[expression['output_col_name']] = df[expression['output_col_name']].fillna(
            #     df[col]).combine_first(df[col])
            # else:
            #     df[expression['output_col_name']] = df[expression['output_col_name']].fillna(col)
        for col in columns[1:]:
            if col in temp_df_header:
                df.loc[:, expression['output_col_name']] = df[expression['output_col_name']].fillna(
                    temp_df[col]).combine_first(temp_df[col])
            elif col in df.columns:
                df.loc[:, expression['output_col_name']] = df[expression['output_col_name']].fillna(
                    df[col]).combine_first(df[col])
            else:
                df.loc[:, expression['output_col_name']] = df[expression['output_col_name']].fillna(col)
        task_logger.info("coalesce : \n%s",df.head())
    else:
        raise SyntaxError("Input did not match coalesce syntax")
    return df

def perform_case_expression(temp_df, temp_df_header, df, expression):
    """
    Perform case expression operation on the DataFrame.

    Case expression applies conditions and assigns values accordingly and updates
    the DataFrame accordingly.

    Args:
        temp_df (pandas.DataFrame): Temporary DataFrame.
        temp_df_header (list): Headers of the temporary DataFrame.
        df (pandas.DataFrame): Main DataFrame.
        expression (dict): Dictionary containing expression details.

    Returns:
        pandas.DataFrame: Updated DataFrame after performing the case expression operation.
    """
    lines = expression['expression_value']
    pattern = r'(?i)\bCASE\b.*?\bEND\b'
    match = re.match(pattern,lines)
    if match:
        df = add_or_update_column(df,
                                    temp_df,
                                    expression['output_col_name'],
                                    expression['input_col_name'],
                                    '')
        query = f"SELECT {expression['operator']} AS result FROM df"
        df[expression['output_col_name']] = sqldf(query)
        task_logger.info("Case expression :\n%s",df.head())
    else:
        raise SyntaxError("Input did not match Case expression syntax")
    return df

def apply_nullif_tempdf(df,expression,temp_df,temp_df_header,columns):
    """
    Apply a NULLIF-like operation to a DataFrame.

    This function sets values in a specified output column to NaN if they match
    a comparison condition between columns in the original and temporary DataFrames.

    Parameters:
    df (pd.DataFrame): The DataFrame to modify.
    expression (dict): Contains 'output_column', the column to store results.
    temp_df (pd.DataFrame): The temporary DataFrame for comparison.
    temp_df_header (list): The column names of temp_df.
    columns (list): The names of columns to compare and a value if needed.

    Returns:
    pd.DataFrame: The modified DataFrame.

    Raises:
    TypeError: If the columns being compared have different data types.
    """
    df[expression['output_col_name']] = df[columns[0]]
    if columns[1] in temp_df_header:
        if temp_df[columns[1]].dtype != temp_df[columns[0]].dtype:
            raise TypeError(COLUMN_DATATYPE_MISMATCH_ERROR)
        df[expression['output_col_name']] = np.where(temp_df[columns[0]].equals(
        temp_df[columns[1]]), np.nan, temp_df[columns[0]])
    elif columns[1] in df.columns:
        if df[columns[1]].dtype != temp_df[columns[0]].dtype:
            raise TypeError(COLUMN_DATATYPE_MISMATCH_ERROR)
        df[expression['output_col_name']] = np.where(temp_df[columns[0]].equals(
        df[columns[1]]), np.nan, temp_df[columns[0]])
    else:
        column_name, value = columns
        value = temp_df[column_name].dtype.type(value)
        df[expression['output_col_name']] = np.where(temp_df[column_name] \
        == value, np.nan, temp_df[column_name])
    return df

def apply_nullif_df(df,expression,temp_df,temp_df_header,columns):
    """
    Apply a NULLIF-like operation to a DataFrame.

    This function sets values in a specified output column to NaN if they match
    a comparison condition between columns in the original DataFrame and a temporary DataFrame.

    Parameters:
    df (pd.DataFrame): The DataFrame to modify.
    expression (dict): Contains 'output_column', the column to store the results.
    temp_df (pd.DataFrame): The temporary DataFrame for comparison.
    temp_df_header (list): The column names of temp_df.
    columns (list): The names of the columns to compare and a value if needed.

    Returns:
    pd.DataFrame: The modified DataFrame with the NULLIF-like operation applied.

    Raises:
    TypeError: If the columns being compared have different data types.
    """
    df[expression['output_col_name']] = df[columns[0]]
    if columns[1] in temp_df_header:
        if temp_df[columns[1]].dtype != df[columns[0]].dtype:
            raise TypeError(COLUMN_DATATYPE_MISMATCH_ERROR)
        df[expression['output_col_name']] = np.where(df[columns[0]].equals(
        temp_df[columns[1]]), np.nan, df[columns[0]])
    elif columns[1] in df.columns:
        if df[columns[1]].dtype != df[columns[0]].dtype:
            raise TypeError(COLUMN_DATATYPE_MISMATCH_ERROR)
        df[expression['output_col_name']] = np.where(df[columns[0]].equals(
        df[columns[1]]), np.nan, df[columns[0]])
    else:
        column_name = columns[0]
        value = columns[1]
        value = df[column_name].dtype.type(value)
        df[expression['output_col_name']] = np.where(df[column_name]
        == value,np.nan, df[column_name])
    return df

def perform_nullif(temp_df, temp_df_header, df, expression):
    """
    Perform nullif operation on the DataFrame.

    Nullif compares two expressions and returns null if they are equal; otherwise,
    returns the first expression and updates the DataFrame accordingly.

    Args:
        temp_df (pandas.DataFrame): Temporary DataFrame.
        temp_df_header (list): Headers of the temporary DataFrame.
        df (pandas.DataFrame): Main DataFrame.
        expression (dict): Dictionary containing expression details.

    Returns:
        pandas.DataFrame: Updated DataFrame after performing the nullif operation.

    Raises:
        SyntaxError: If the input does not match nullif syntax.
    """
    nullif = expression['expression_value']
    nullif = nullif.strip()
    pattern = r"nullif\(\s*(.*?)\s*,\s*(.*?)\s*\)"
    match = re.match(pattern, nullif)
    if match:
        df = add_or_update_column(df,
                                    temp_df,
                                    expression['output_col_name'],
                                    expression['input_col_name'],
                                    '')
        task_logger.info("df :\n%s",df.head())
        nullif = nullif[7:-1]
        pattern = r'\s*,\s*'
        elements = re.split(pattern, nullif.strip())
        columns = [re.sub(r'^(")?("")?$', '', element) for element in elements]
        if columns[0] in temp_df_header:
            df=apply_nullif_tempdf(df,expression,temp_df,temp_df_header,columns)
        elif columns[0] in df.columns:
            df=apply_nullif_df(df,expression,temp_df,temp_df_header,columns)
        else :
            raise SyntaxError("Did not match nullif pattern ( \
            first parameter error).First parameter is not a column ")
        # cannot convert the datatype from float to int if nan is present in the values
        task_logger.info("nullif :\n%s",df.head())
    else:
        raise SyntaxError("Input did not match nullif syntax")
    return df

def conditional_exp(temp_df, temp_df_header, df, expression):
    """
    Evaluate conditional expressions and update the DataFrame.

    This function evaluates conditional expressions provided in the expression
    dictionary and updates the DataFrame accordingly.

    Args:
        temp_df (pandas.DataFrame): Temporary DataFrame.
        temp_df_header (list): Headers of the temporary DataFrame.
        df (pandas.DataFrame): Main DataFrame.
        expression (dict): Dictionary containing expression details.

    Returns:
        tuple: Tuple containing the updated temporary DataFrame and the main DataFrame.

    Raises:
        ValueError: If the operation type is unsupported.
    """
    match expression['operator']:
        case 'coalesce':
          # Coalesce returns the first non-null value among the specified columns
            df=perform_coalesce(temp_df, temp_df_header, df, expression)
        case 'case expression':
          # Case expression applies conditions and assigns values accordingly
            df=perform_case_expression(temp_df, temp_df_header, df, expression)
        case 'nullif':
            df=perform_nullif(temp_df, temp_df_header, df, expression)
        case _:
            raise ValueError(f"Unsupported operation type: {expression['operator']}")
    return temp_df, df
