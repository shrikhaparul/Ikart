"""
Module for parsing and evaluating string expressions in DataFrames.
"""
import logging
import re
from expression.add_column import add_or_update_column

task_logger = logging.getLogger('task_logger')

def extract_values(values):
    """
    Extract values from the given list.

    Args:
        values (list): A list containing values.

    Returns:
        tuple: A tuple containing extracted values.

    """
    temp_df=values[0]
    temp_df_header=values[1]
    df=values[2]
    expression=values[3]
    arguments=values[4]
    output_column=values[5]
    df = add_or_update_column(df,
                                temp_df,
                                expression['output_col_name'],
                                expression['input_col_name'],
                                '')
    if arguments[0] in temp_df_header:
        arguments[0] = temp_df[arguments[0]]
    elif arguments[0] in df.columns:
        arguments[0] = df[arguments[0]]
    return df,arguments,output_column

def apply_lower(values):
    """
    Apply lower case transformation to a DataFrame column.

    Args:
        values (list): A list containing values.

    Returns:
        pandas.DataFrame: The DataFrame with the lower case transformation applied.

    """
    df,arguments,output_column=extract_values(values)
    df[output_column] = arguments[0].str.lower()
    return df

def apply_upper(values):
    """
    Apply upper case transformation to a DataFrame column.

    Args:
        values (list): A list containing values.

    Returns:
        pandas.DataFrame: The DataFrame with the upper case transformation applied.

    """
    df,arguments,output_column=extract_values(values)
    df[output_column] = arguments[0].str.upper()
    return df

def trim_function(temp_df, temp_df_header,df, trim_syntax):
    """
    TRIM function implementation for a pandas DataFrame.

    Args:
    - df: pandas DataFrame containing the data to be trimmed.
    - trim_syntax: string containing the trim syntax to be applied.

    Returns:
    - pandas DataFrame with the trim operation applied.
    """
    trim_syntax = trim_syntax.replace("trim(", "").replace(")", "")
    # Parse trim syntax
    trim_operands = trim_syntax.split()
    # Extract trimType, trimCharacter, and trimSource
    trim_type = 'BOTH'  # Default trimType
    trim_character = ' '  # Default trimCharacter
    if len(trim_operands) >= 2:
        trim_type = trim_operands[0].upper()
        if trim_type not in ['LEADING', 'TRAILING', 'BOTH']:
            raise ValueError("Invalid trimType.It must be one of 'LEADING','TRAILING', or 'BOTH'.")
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

def apply_initcap(values):
    """
    Apply initcap case transformation to a DataFrame column.

    Args:
        values (list): A list containing values.

    Returns:
        pandas.DataFrame: The DataFrame with the initcap case transformation applied.

    """
    df,arguments,output_column=extract_values(values)
    df[output_column] = arguments[0].str.title()
    return df

def apply_replace(values):
    """
    Apply string replacement to a DataFrame column.
    Args:
        values (list): A list containing values.
    Returns:
        pandas.DataFrame: The DataFrame with the string replacement applied.
    """
    df,arguments,output_column=extract_values(values)
    df[output_column] = arguments[0].str.replace(arguments[1], arguments[2])
    return df

def apply_ltrim(values):
    """
    Apply left trim operation to a DataFrame column.
    Args:
        values (list): A list containing values.
    Returns:
        pandas.DataFrame: The DataFrame with the left trim operation applied.
    """
    df,arguments,output_column=extract_values(values)
    if len(arguments)>2:
        df[output_column] = arguments[0].str.lstrip(arguments[1])
    else:
        df[output_column] = arguments[0].str.lstrip()
    return df

def apply_lpad(values):
    """
    Apply left padding to a DataFrame column.
    Args:
        values (list): A list containing values.
    Returns:
        pandas.DataFrame: The DataFrame with the left padding applied.
    """
    df,arguments,output_column=extract_values(values)
    if len(arguments)<3:
        arguments.append(" ")
    df[output_column] = arguments[0].str.pad(width=int(arguments[1]),
         side='left',fillchar=arguments[2])
    return df

def apply_regex_replace(values):
    """
    Apply regular expression replacement to a DataFrame column.
    Args:
        values (list): A list containing values.
    Returns:
        pandas.DataFrame: The DataFrame with the regular expression replacement applied.
    """
    df,arguments,output_column=extract_values(values)
    source_string = arguments[0]
    pattern = arguments[1]
    replace_string = arguments[2] if len(arguments) > 2 else ''
    df[output_column] = source_string.replace(regex=pattern, value=replace_string)
    return df

def apply_rpad(values):
    """
    Apply right padding to a DataFrame column.
    Args:
        values (list): A list containing values.
    Returns:
        pandas.DataFrame: The DataFrame with the right padding applied.
    """
    df,arguments,output_column=extract_values(values)
    if len(arguments)<3:
        arguments.append(" ")
    df[output_column] = arguments[0].str.pad(width=int(arguments[1]),
        side='right',fillchar=arguments[2])
    return df

def string_exp(temp_df, temp_df_header, df, expression):
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
        arguments = []
        match = re.search(patterns[expression['operator']], expression['expression_value'])
        if match:
            arguments = [arg.strip("'") if arg is not None else arg for arg in match.groups()]
        else:
            raise SyntaxError("Invalid Syntax")
        operator_name = expression['operator']
        arguments = [s.strip() for s in arguments if s]
        values=[temp_df, temp_df_header, df, expression,arguments,output_column]
        match operator_name:
            case 'lower':
                df=apply_lower(values)
            case 'upper':
                df=apply_upper(values)
            case 'trim':
                df = add_or_update_column(df,
                                          temp_df,
                                          expression['output_col_name'],
                                          expression['input_col_name'],
                                          '')
                df[output_column]=trim_function(temp_df, temp_df_header,df,
                expression['expression_value'])
            case 'initcap':
                df=apply_initcap(values)
            case 'replace':
                df=apply_replace(values)
            case 'ltrim':
                df = apply_ltrim(values)
            case 'lpad':
                df=apply_lpad(values)
            case 'regexp_replace':
                df=apply_regex_replace(values)
            case 'rpad':
                df=apply_rpad(values)
            case 'substring':
                df,arguments,output_column=extract_values(values)
                df[output_column] = arguments[0].str[int(arguments[1]):int(arguments[1])
                                                     +
                                                     int(arguments[2])]
            case 'concat':
                df = add_or_update_column(df,
                                          temp_df,
                                          expression['output_col_name'],
                                          expression['input_col_name'],
                                          '')
                concat_syntax=expression['expression_value'].replace("concat(","")
                concat_syntax=concat_syntax[:-1]
                arguments=concat_syntax.split(",")
                print(arguments)
                for i in range(len(arguments)):
                    if arguments[i] in temp_df_header:
                        arguments[i] = temp_df[arguments[i]]
                    elif arguments[i] in df.columns:
                        arguments[i] = df[arguments[i]]
                df[output_column] = arguments[0]
                for i in range(1,len(arguments)):
                    df[output_column]+=arguments[i]
            case _:
                raise ValueError(f"Unsupported operation type: {expression['operator_name']}")
        task_logger.info("DF after string expression:%s",df.head())
        return temp_df, df
    except Exception as e:
        task_logger.error("Unable to perform string expression. Exception: %s",e)
        raise e
