"""
This module defines functions for evaluating expressions on pandas DataFrames.

Functions:
    - find_operator_type(operation): Finds the appropriate function for the given
    operation type.
    - store_columns_in_temp(df, temp_df, temp_df_header, input_col): Stores a column from
    the DataFrame `df` in the temporary DataFrame `temp_df` and its header in
    `temp_df_header` if it's not already present and not an empty string.
    - add_or_update_column(df, temp_df, output_column, input_column, col): Adds a new
    column named `output_column` to the DataFrame `df` or updates an existing one.
    - expression(df, operations): Evaluates the expressions defined in the operations on
    the DataFrame.

Usage:
    To execute the expressions defined in the `main_operations` dictionary on the
    `main_df` DataFrame,
    simply run the script. The result will be saved in a CSV file named "result.csv"
    and printed to the console.
"""
import logging
import pandas as pd
from expression.conditional import conditional_exp
from expression.dtypes import dtype_exp
from expression.date import date_time_exp
from expression.maths import math_exp
from expression.strings import string_exp
from expression.window import window_exp
from expression.conversion import conversion_exp
from update_audit import audit_failure
task_logger = logging.getLogger('task_logger')


def extract_columns(arguments,transformations):
    """
    Extracts input and output column names from a transformations dictionary.

    Args:
        transformations (dict): A dictionary containing transformation details.
            Expected keys include:
                - 'input_df' : The input DataFrame (not extracted here).
                - 'output_df' : The output DataFrame (not extracted here).
                - 'transformation_name' : The name of the transformation (not extracted here).
                - 'input_col_name' (str): The name of the input column.
                - 'output_col_name' (str): The name of the output column.

    Returns:
        tuple: A tuple containing two lists:
            input_columns (list): A list of input column names extracted from the transformations.
            output_columns (list): A list of output column names extracted from the transformations.

    Raises:
        Exception: If an error occurs while processing the transformations dictionary.
    """

    try:
        input_columns = []
        output_columns = []

        # Iterate over the keys in the transformations dictionary
        for key, details in transformations.items():
            # Exclude specific keys
            if key not in ['input_df', 'output_df', 'transformation_name']:
                # Extract input and output column names
                input_col_name = details.get("input_col_name")
                output_col_name = details.get("output_col_name")

                # Add to the respective lists if not empty
                if input_col_name:
                    input_columns.append(input_col_name)
                else:
                    input_columns.append(0)  # Placeholder for missing input column

                if output_col_name:
                    output_columns.append(output_col_name)

        return input_columns, output_columns
    except Exception as e:
        task_logger.exception("Error occured in extract_columns function with error : %s", e)
        audit_failure(arguments)
        raise e


def find_operator_type(arguments,operation):
    """
    Finds the appropriate function for the given operation type.

    Args:
        operation (dict): The operation details.

    Returns:
        function: The function corresponding to the operation type.

    Raises:
        NotImplementedError: If the operation type is not implemented.
    """
    op_type = {
        "Conditional": conditional_exp,
        "Data Type Formatting": dtype_exp,
        "Date and Time": date_time_exp,
        "Math": math_exp,
        "String": string_exp,
        "Window Function":window_exp,
        "Converter":conversion_exp,
    }
    try:
        return op_type[operation['operatorType']]
    except KeyError as e:
        audit_failure(arguments)
        raise NotImplementedError(f"Operation type {operation.get('operator_type', 'Unknown')} \
             not implemented") from e

def store_columns_in_temp(arguments,df, temp_df, temp_df_header, input_col):
    """
    Stores a column from the DataFrame `df` in the temporary DataFrame `temp_df`
    and its header in `temp_df_header` if it's not already present and not an empty string.

    Args:
        df (pandas.DataFrame): The source DataFrame.
        temp_df (pandas.DataFrame): The temporary DataFrame where columns are stored.
        temp_df_header (list): A list containing headers of the columns in `temp_df`.
        input_col (str): The name of the column to be stored.

    Returns:
        tuple: A tuple containing the updated `temp_df_header` list and the updated `temp_df`.
    """
    try:
        if input_col not in temp_df and input_col != "":
            temp_df[input_col] = df[input_col]
            temp_df_header.append(input_col)
        return temp_df_header, temp_df
    except Exception as e:
        task_logger.exception("Error occured in store_columns_in_temp function with error : %s", e)
        audit_failure(arguments)
        raise e

def perform_rename_drop(arguments,df,input_columns,output_columns):
    """
    It performs the droping of columns not present in the output columns and
    renames the columns where required
    Args:
        df (pandas.DataFrame): The source DataFrame.
        input_columns (List): The input columns that the backend recived
        ouput_columns (list): A list containing the output columns


    Returns:
        df (pandas.DataFrame): The result dataframe
    """
    try:
        # for i in range(len(input_columns)):
        #     if input_columns[i] != output_columns[i] and input_columns[i]!=0:
        #         if output_columns[i] in df.columns:
        #             df.drop(columns=input_columns[i],inplace=True)
        #         else:
        #             df.rename(columns={input_columns[i]: output_columns[i]}, inplace=True)
        for i, (input_col, output_col) in enumerate(zip(input_columns, output_columns)):
            if input_col != output_col and input_col != 0:
                if output_col in df.columns:
                    df.drop(columns=input_col, inplace=True)
                else:
                    df.rename(columns={input_col: output_col}, inplace=True)
        for i in df.columns:
            if i not in output_columns:
                df.drop(columns=i,inplace=True)
        return df
    except Exception as e:
        task_logger.exception("Error occured in perform_rename_drop function with error : %s", e)
        audit_failure(arguments)
        raise e

def expression(arguments,df, operations):
    """
    Evaluates the expressions defined in the operations on the DataFrame.
    Args:
        df (pandas.DataFrame): The DataFrame to evaluate expressions on.
        operations (dict): The operations to perform.
    Returns:
        pandas.DataFrame: The DataFrame after applying the expressions.
    """
    try:
        input_columns,output_columns=extract_columns(arguments,operations)
        temp_df = pd.DataFrame()
        temp_df_header = []
        expression_list = []
        for key, details in operations.items():
            if key not in ['input_df', 'output_df', 'transformation_name']:
                expression_list.append(details)
        expression_list = sorted(expression_list,key=lambda x: x['sequence'])
        for operation in expression_list:
            if operation['operatorType']!="":
                operation_func = find_operator_type(arguments,operation)
                if operation['output_col_name'] in input_columns and \
                operation['input_col_name']=="":
                    raise ValueError("Column already Present")
                if operation['input_col_name']==operation['output_col_name']:
                    temp_df_header, temp_df = store_columns_in_temp(arguments,df,
                                                                    temp_df,
                                                                    temp_df_header,
                                                                    operation['input_col_name'])
                task_logger.info("%s has been apllied",operation['expression_value'])
                #calling from expression folder
                temp_df, df = operation_func(arguments,temp_df, temp_df_header, df, operation)
        task_logger.info(df.head())
        df=perform_rename_drop(arguments,df,input_columns,output_columns)
        return df
    except KeyError as e:
        task_logger.error("KeyError occurred: %s", e)
        audit_failure(arguments)
        raise KeyError(f"Invalid key in operations dictionary: {e}") from e
    except ValueError as e:
        task_logger.error("ValueError occurred: %s", e)
        audit_failure(arguments)
        raise ValueError(f"Invalid value in operations: {e}") from e
    except Exception as e:
        task_logger.error("Error occurred: %s", e)
        audit_failure(arguments)
        raise e
