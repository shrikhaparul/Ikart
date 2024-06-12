"""
Module for parsing and evaluating string expressions in DataFrames.
"""
import logging
import re
from update_audit import audit_failure
from expression.add_column import add_or_update_column

task_logger = logging.getLogger('task_logger')

def extract_values(arguments,values):
    """
    Extract values from the given list.

    Args:
        values (list): A list containing values.

    Returns:
        tuple: A tuple containing extracted values.

    """
    try:
        temp_df=values[0]
        temp_df_header=values[1]
        df=values[2]
        expression=values[3]
        argument=values[4]
        output_column=values[5]
        df = add_or_update_column(df,
                                    temp_df,
                                    expression['output_col_name'],
                                    expression['input_col_name'],
                                    '')
        if argument[0] in temp_df_header:
            argument[0] = temp_df[argument[0]]
        elif argument[0] in df.columns:
            argument[0] = df[argument[0]]
        return df,argument,output_column
    except Exception as e:
        task_logger.exception("Error occured in extract_values function with error : %s",e)
        audit_failure(arguments)
        raise e

def apply_lower(arguments,values):
    """
    Apply lower case transformation to a DataFrame column.

    Args:
        values (list): A list containing values.

    Returns:
        pandas.DataFrame: The DataFrame with the lower case transformation applied.

    """
    try:

        df,argument,output_column=extract_values(arguments,values)
        df[output_column] = argument[0].str.lower()
        return df
    except Exception as e:
        task_logger.exception("Error occured in apply_lower function with error : %s",e)
        audit_failure(arguments)
        raise e

def apply_upper(arguments,values):
    """
    Apply upper case transformation to a DataFrame column.

    Args:
        values (list): A list containing values.

    Returns:
        pandas.DataFrame: The DataFrame with the upper case transformation applied.

    """
    try:

        df,argument,output_column=extract_values(arguments,values)
        df[output_column] = argument[0].str.upper()
        return df
    except Exception as e:
        task_logger.exception("Error occured in apply_upper function with error : %s",e)
        audit_failure(arguments)
        raise e

def trim_function(arguments,temp_df, temp_df_header,df, trim_syntax):
    """
    TRIM function implementation for a pandas DataFrame.

    Args:
    - df: pandas DataFrame containing the data to be trimmed.
    - trim_syntax: string containing the trim syntax to be applied.

    Returns:
    - pandas DataFrame with the trim operation applied.
    """
    try:

        trim_syntax = trim_syntax.replace("trim(", "").replace(")", "")
        # Parse trim syntax
        trim_operands = trim_syntax.split()
        # Extract trimType, trimCharacter, and trimSource
        trim_type = 'BOTH'  # Default trimType
        trim_character = ' '  # Default trimCharacter
        if len(trim_operands) >= 2:
            trim_type = trim_operands[0].upper()
            if trim_type not in ['LEADING', 'TRAILING', 'BOTH']:
                raise ValueError("Invalid trimType. It must be one of 'LEADING', \
                'TRAILING', or 'BOTH'.")
            if len(trim_operands) >=3:
                trim_character = trim_operands[1]
        trim_source = trim_operands[-1]
        if trim_source in temp_df_header:
            trim_source = temp_df[trim_source]
        elif trim_source in df.columns:
            trim_source = df[trim_source]
        # Apply trim operation to DataFrame
        if trim_type == 'LEADING':
            result = trim_source.str.lstrip(trim_character)
        elif trim_type == 'TRAILING':
            result = trim_source.str.rstrip(trim_character)
        elif trim_type == 'BOTH':
            result = trim_source.str.strip(trim_character)
        return result
    except Exception as e:
        task_logger.exception("Error occured in trim_function function with error : %s",e)
        audit_failure(arguments)
        raise e

def apply_initcap(arguments,values):
    """
    Apply initcap case transformation to a DataFrame column.

    Args:
        values (list): A list containing values.

    Returns:
        pandas.DataFrame: The DataFrame with the initcap case transformation applied.

    """
    try:
        df,argument,output_column=extract_values(arguments,values)
        df[output_column] = argument[0].str.title()
        return df
    except Exception as e:
        task_logger.exception("Error occured in apply_initcap function with error : %s",e)
        audit_failure(arguments)
        raise e

def apply_replace(arguments,values):
    """
    Apply string replacement to a DataFrame column.
    Args:
        values (list): A list containing values.
    Returns:
        pandas.DataFrame: The DataFrame with the string replacement applied.
    """
    try:

        df,argument,output_column=extract_values(arguments,values)
        df[output_column] = argument[0].str.replace(argument[1], argument[2])
        return df
    except Exception as e:
        task_logger.exception("Error occured in apply_replace function with error : %s",e)
        audit_failure(arguments)
        raise e

def apply_ltrim(arguments,values):
    """
    Apply left trim operation to a DataFrame column.
    Args:
        values (list): A list containing values.
    Returns:
        pandas.DataFrame: The DataFrame with the left trim operation applied.
    """
    try:

        df,argument,output_column=extract_values(arguments,values)
        if len(argument)>2:
            df[output_column] = argument[0].str.lstrip(argument[1])
        else:
            df[output_column] = argument[0].str.lstrip()
        return df
    except Exception as e:
        task_logger.exception("Error occured in apply_ltrim function with error : %s",e)
        audit_failure(arguments)
        raise e

def apply_lpad(arguments,values):
    """
    Apply left padding to a DataFrame column.
    Args:
        values (list): A list containing values.
    Returns:
        pandas.DataFrame: The DataFrame with the left padding applied.
    """
    try:
        df,argument,output_column=extract_values(arguments,values)
        if len(argument)<3:
            argument.append(" ")
        df[output_column] = argument[0].str.pad(width=int(argument[1]),
                                                    side='left',
                                                    fillchar=argument[2])
        return df
    except Exception as e:
        task_logger.exception("Error occured in apply_lpad function with error : %s",e)
        audit_failure(arguments)
        raise e

def apply_regex_replace(arguments,values):
    """
    Apply regular expression replacement to a DataFrame column.
    Args:
        values (list): A list containing values.
    Returns:
        pandas.DataFrame: The DataFrame with the regular expression replacement applied.
    """
    try:

        df,argument,output_column=extract_values(arguments,values)
        source_string = argument[0]
        pattern = argument[1]
        replace_string = argument[2] if len(argument) > 2 else ''
        df[output_column] = source_string.replace(regex=pattern, value=replace_string)
        return df
    except Exception as e:
        task_logger.exception("Error occured in apply_regex_replace function with error : %s",e)
        audit_failure(arguments)
        raise e

def apply_rpad(arguments,values):
    """
    Apply right padding to a DataFrame column.
    Args:
        values (list): A list containing values.
    Returns:
        pandas.DataFrame: The DataFrame with the right padding applied.
    """
    try:

        df,argument,output_column=extract_values(arguments,values)
        if len(argument)<3:
            argument.append(" ")
        df[output_column] = argument[0].str.pad(width=int(argument[1]),
                                                    side='right',
                                                    fillchar=argument[2])
        return df
    except Exception as e:
        task_logger.exception("Error occured in apply_rpad function with error : %s",e)
        audit_failure(arguments)
        raise e

def string_exp(arguments,temp_df, temp_df_header, df, expression):
    """Evaluate string expressions and update the DataFrame.

    This function evaluates string expressions provided in the expression
    dictionary and updates the DataFrame accordingly.

    Args:
        temp_df (pandas.DataFrame): Temporary DataFrame.
        temp_df_header (list): Headers of the temporary DataFrame.
        df (pandas.DataFrame): Main DataFrame.
        expression (dict): Dictionary containing expression details.

    Returns:
        tuple: Tuple containing the updated temporary DataFrame and the main DataFrame.
    """
    try:
        patterns = {
            'upper': r'upper\((.*?)\)',
            'lower': r'lower\((.*?)\)',
            'replace': r'replace\((.*?),\s*(.*?),\s*(.*?)\)',
            'ltrim': r'ltrim\((.*?)(?:,\s*\'(.*?)\')?\)',
            'trim': r'trim(?:\((both)?\s?(?:\'(.*?)\'\s?from)?\s?(.*?)\))?',
            'lpad': r'lpad\((.*?),\s*(.*?)(?:,\s*(.*?))?\)',
            'rpad': r'rpad\((.*?),\s*(.*?)(?:,\s*(.*?))?\)',
            'initcap': r'initcap\((.*?)\)',
            'regexp_replace': r'REGEXP_REPLACE\s*\(\s*(.*?)\s*,\s*(.*?)\s*,\s*(.*?)\)',
            'substring': r'substring\((.*?),\s*(.*?),\s*(.*?)\)',
            'concat': r'concat\((.*?),\s*(.*?)\)'
        }
        output_column = expression['output_col_name']
        argument = []
        match = re.search(patterns[expression['operator']], expression['expression_value'])
        if match:
            argument = [arg.strip("'") if arg is not None else arg for arg in match.groups()]
        else:
            raise SyntaxError("Invalid Syntax")
        operator_name = expression['operator']
        argument = [s.strip() for s in argument if s]
        values=[temp_df, temp_df_header, df, expression,argument,output_column]
        match operator_name:
            case 'lower':
                df=apply_lower(arguments,values)
            case 'upper':
                df=apply_upper(arguments,values)
            case 'trim':
                df = add_or_update_column(arguments,df,
                                          temp_df,
                                          expression['output_col_name'],
                                          expression['input_col_name'],
                                          '')
                df[output_column]=trim_function(arguments,temp_df, temp_df_header,df,
                expression['expression_value'])
            case 'initcap':
                df=apply_initcap(arguments,values)
            case 'replace':
                df=apply_replace(arguments,values)
            case 'ltrim':
                df = apply_ltrim(arguments,values)
            case 'lpad':
                df=apply_lpad(arguments,values)
            case 'regexp_replace':
                df=apply_regex_replace(arguments,values)
            case 'rpad':
                df=apply_rpad(arguments,values)
            case 'substring':
                df,argument,output_column=extract_values(arguments,values)
                df[output_column] = argument[0].str[int(argument[1]):int(argument[1])
                                                     +
                                                     int(argument[2])]
            case 'concat':
                df = add_or_update_column(arguments,df,
                                          temp_df,
                                          expression['output_col_name'],
                                          expression['input_col_name'],
                                          '')
                concat_syntax=expression['expression_value'].replace("concat(","")
                concat_syntax=concat_syntax[:-1]
                argument=concat_syntax.split(",")
                # print(argument)
                for i, argument in enumerate(argument):
                    if argument in temp_df_header:
                        argument[i] = temp_df[argument]
                    elif argument in df.columns:
                        argument[i] = df[argument]
                df[output_column] = argument[0]
                for i in range(1,len(argument)):
                    df[output_column]+=argument[i]
            case _:
                raise ValueError(f"Unsupported operation type: {expression['operator_name']}")

        task_logger.info("DF after string expression:%s",df.head())
        return temp_df, df
    except Exception as e:
        task_logger.error("Unable to perform string expression. Exception: %s",e)
        audit_failure(arguments)
        raise e
