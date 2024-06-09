"""
Module for parsing and evaluating mathematical expressions in DataFrames
"""
import re
import logging
import math
from expression.add_column import add_or_update_column

task_logger = logging.getLogger('task_logger')

def parse_arguments(temp_df, temp_df_header, df, expression):
    """
    Parse arguments from the mathematical expression.

    Args:
        temp_df (pandas.DataFrame): Temporary DataFrame.
        temp_df_header (list): Headers of the temporary DataFrame.
        df (pandas.DataFrame): Main DataFrame.
        expression (dict): Dictionary containing expression details.

    Returns:
        list: Processed arguments extracted from the expression.
    """
    patterns = {
        'trunc': r'trunc\((.*?)\)',
        'round': r'round\((.*?)\)',
        'addition': r'(\w+(?:\s*\+\s*\w+)+)',
        'subtraction': r'(\w+(?:\s*-\s*\w+)+)',
        'multiplication': r'(\w+(?:\s*\*\s*\w+)+)',
        'division': r'(\w+(?:\s*/\s*\w+)+)',
        'modulo': r'(\w+(?:\s*%\s*\w+)+)',
        'equal': r'(\w+\s*==\s*\w+)',
        'not_equal': r'(\w+\s*<>\s*\w+)',
        'greater_than': r'(\w+\s*>\s*\w+)',
        'greater_than_equal': r'(\w+\s*>=\s*\w+)',
        'less_than': r'(\w+\s*<\s*\w+)',
        'less_than_equal': r'(\w+\s*<=\s*\w+)',
    }

    operator_name = expression['operator']
    operation = expression['expression_value']
    arguments = []

    matches = re.findall(patterns.get(operator_name, ''), operation)
    if not matches:
        error_message="Invalid math function syntax of "+operator_name
        print(error_message)
        task_logger.error(error_message)
        raise SyntaxError(error_message)

    for match in matches:
        if operator_name in ['addition', 'subtraction', 'multiplication', 'division',
                             'modulo','equal', 'not_equal', 'greater_than', 
                             'greater_than_equal', 'less_than', 'less_than_equal']:
            variables = re.split(r'\+|-|\*|/|%|<=|>=|<|>|==|<>', match)
            arguments.extend([var.strip() for var in variables if var.strip()])
        elif operator_name in ["trunc","round"]:
            variables = re.split(r',', match)
            arguments.extend([var.strip() for var in variables if var.strip()])
    processed_arguments = []
    for arg in arguments:
        if arg.replace('.', '', 1).lstrip('-').isdigit():
            processed_arguments.append(float(arg) if '.' in arg else int(arg))
        elif arg in temp_df_header:
            processed_arguments.append(temp_df[arg])
        elif arg in df.columns:
            processed_arguments.append(df[arg])
    return processed_arguments

# def apply_trunc(df,output_column,arguments):
#     """
#     Apply truncation to a DataFrame column and update it with the result.

#     Args:
#         df (pandas.DataFrame): The DataFrame to which truncation is applied.
#         output_column (str): The name of the column where the truncated values will be stored.
#         arguments (list): A list containing the arguments for truncation.
#             The first argument (arguments[0]) is the number to truncate.
#             The second argument (arguments[1]), if provided, is the number of decimal places to 
#             keep after truncation.

#     Returns:
#         pandas.DataFrame: The DataFrame with the updated output column
#     """
#     number=arguments[0]
#     if len(arguments)>1:
#         decimal=arguments[1]
#     else:
#         decimal=None
#     def trunc_value(value):
#         if isinstance(value, (int, float)):
#             if decimal is None:
#                 return math.trunc(value)            
#             multiplier = 10 ** decimal
#             return math.trunc(value * multiplier) / multiplier
#         return value
#     # Update the output column in the DataFrame
#     df[output_column] = number.apply(trunc_value)
#     return df

def apply_trunc(df,output_column,arguments):
    """
    Apply truncation to a DataFrame column and update it with the result.

    Args:
        df (pandas.DataFrame): The DataFrame to which truncation is applied.
        output_column (str): The name of the column where the truncated values will be stored.
        arguments (list): A list containing the arguments for truncation.
            The first argument (arguments[0]) is the number to truncate.
            The second argument (arguments[1]), if provided, is the number of decimal places to 
            keep after truncation.

    Returns:
        pandas.DataFrame: The DataFrame with the updated output column
    """
    try:
            
        number=arguments[0]
        if len(arguments)>1:
            decimal=arguments[1]
        else:
            decimal=None
        def trunc_value(value):
            if isinstance(value, (int, float)):
                if decimal is None:
                    return math.trunc(value)
                
                multiplier = 10 ** decimal
                return math.trunc(value * multiplier) / multiplier
            return value
        # Update the output column in the DataFrame
        if isinstance(number, (int, float, complex)):
            trunced_valued=trunc_value(number)
            logging.info(trunced_valued)
            df[output_column]=trunced_valued
            return df
        df[output_column] = number.apply(trunc_value)
        return df
    except Exception as e:
        logging.exception("Error occured in apply_trunc function with error : %s",e)
        raise e

def apply_round(df,output_column,arguments):
    """
    Apply rounding to a DataFrame column and update it with the result.

    Args:
        df (pandas.DataFrame): The DataFrame to which rounding is applied.
        output_column (str): The name of the column where the rounded values will be stored.
        arguments (list): A list containing the arguments for truncation.
            The first argument (arguments[0]) is the number to round.
            The second argument (arguments[1]), if provided, is the number of decimal places to 
            keep after rounding.

    Returns:
        pandas.DataFrame: The DataFrame with the updated output column
    """
    number=arguments[0]
    if len(arguments)>1:
        decimal=arguments[1]
    else:
        decimal=0
    rounded_values = number.round(decimal)
    df[output_column] = rounded_values
    return df

def math_exp(temp_df, temp_df_header, df, expression):
    """
    Evaluate mathematical expressions and update the DataFrame.

    This function evaluates mathematical expressions provided in the expression
    dictionary and updates the DataFrame accordingly.

    Args:
        temp_df (pandas.DataFrame): Temporary DataFrame.
        temp_df_header (list): Headers of the temporary DataFrame.
        df (pandas.DataFrame): Main DataFrame.
        expression (dict): Dictionary containing expression details.

    Returns:
        tuple: Tuple containing the updated temporary DataFrame and the main DataFrame.
    """
    output_column = expression['output_col_name']
    operator_name = expression['operator']
    arguments=parse_arguments(temp_df, temp_df_header, df, expression)
    df = add_or_update_column(df,temp_df,expression['output_col_name'],
                              expression['input_col_name'],'')
    print(arguments)
    try:
        match operator_name:
            case 'trunc':
                df=apply_trunc(df,output_column,arguments)
            case 'round':
                df=apply_round(df,output_column,arguments)
            case 'addition':
                result = 0
                print(arguments)
                for i in arguments:
                    result+=i
                df[output_column] = result
            case 'subtraction':
                result = arguments[0].copy()
                for i in arguments[1:]:
                    result-=i
                df[output_column] = result
            case 'multiplication':
                result = 1
                for i in arguments:
                    result=result*i
                df[output_column] = result
            case 'division':
                result = arguments[0].copy()
                for i in arguments[1:]:
                    result/=i
                df[output_column] = result
            case 'modulo':
                result = arguments[0].copy()
                for i in arguments[1:]:
                    result%=i
                df[output_column] = result
            case 'equal':
                result = arguments[0] == arguments[1]
                df[output_column] = result
            case 'not_equal':
                result = arguments[0] != arguments[1]
                df[output_column] = result
            case 'greater_than':
                result = arguments[0] > arguments[1]
                df[output_column] = result
            case 'greater_than_equal':
                result = arguments[0] >= arguments[1]
                df[output_column] = result
            case 'less_than':
                result = arguments[0] < arguments[1]
                df[output_column] = result
            case 'less_than_equal':
                result = arguments[0] <= arguments[1]
                df[output_column] = result
        task_logger.info("DF after math expression:%s",df.head())
    except IndexError:
        task_logger.error("Invalid number of arguments")
        raise SyntaxError("Invalid number of arguments")
    except Exception as e:
        task_logger.error("Unable to perform math expression\nExcpetion: %s",e)
        raise
    return temp_df, df
