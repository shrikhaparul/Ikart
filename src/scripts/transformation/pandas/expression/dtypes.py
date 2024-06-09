"""converts dtype to string representation  for conversion  functions"""
import logging
from datetime import datetime
import re
from dateutil import parser
import pandas as pd
import pandasql as ps
from expression.add_column import add_or_update_column

task_logger = logging.getLogger('task_logger')

OPERATION="operation :%s"
ERROR_MSG="An unexpected error occurred: %s"
STR="string:%s"
def pyspark_to_pandas_format(pyspark_format):
    """
    Converts a PySpark date format to a Pandas-compatible format.

    Args:
        pyspark_format (str): The PySpark date format string.

    Returns:
        str: The equivalent Pandas-compatible date format string.
    """
    conversion_map = {
        '9': '%s',
        '0': '%02d',
        'y': '%Y',
        'yy': '%y',
        'yyyy': '%Y',
        'd': '%d',
        'dd': '%d',
        'day': '%d',
        'h': '%H',
        'hh': '%H',
        'hh12': '%I',
        'hh24': '%H',
        'm': '%m',
        'mm': '%m',
        'mi': '%M',
        's': '%S',
        'ss': '%S',
        'am': '%p',
        'pm': '%p',
        'ms': '%f',
        'a': '%p'
    }

    pandas_format = pyspark_format.lower()  # Convert to lowercase
    for pyspark_specifier, pandas_specifier in conversion_map.items():
        pandas_format = re.sub(r'\b' + re.escape(pyspark_specifier) + r'\b',
        pandas_specifier, pandas_format)
    return pandas_format

def interger_to_char_using_formate(df,column_name, format_string):
    """
    Formats a pandas Series of numbers according to a specified format string.

    Args:
        series (pd.Series): The pandas Series containing numeric data.
        format_string (str): The format string to apply, similar to those used in
            Oracle's to_char function for numbers.

    Returns:
        pd.Series: A new Series with the formatted numeric data.
    """

    # Handle potential formatting exceptions
    try:
        if '.' not in format_string:
            decimal= str(0)
        else:
            decimal= str(len(format_string.split('.')[1]))
        format_string = ',.'+decimal+'f'
        return df[column_name].apply(lambda x: f"{x:{format_string}}")
    except (ValueError, KeyError):
        raise ValueError("Invalid format string provided.")

def is_valid_datetime_or_date(date_str):
    """
    Checks if a string represents a valid datetime or date.

    Args:
        date_str (str): The date string.

    Returns:
        bool: True if the string represents a valid datetime or date, False otherwise.
    """
    try:
        # Attempt to parse as datetime
        task_logger.info("date :%s",date_str)
        datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return True
    except ValueError:
        try:
            # Attempt to parse as date
            parser.parse(date_str).date()
            return True
        except ValueError:
            return False
        
def is_number(s):
    """
    Function to check if a string datatype is actually a number.

    Parameters:
    s (str): The string to check.

    Returns:
    bool: True if the string is a number, False otherwise.
    """
    try:
        float(s)
        return True
    except ValueError:
        return False

def is_string_or_object(s):
    """
    Function to check if a given variable is of string or object datatype.

    Parameters:
    s: The variable to check.

    Returns:
    bool: True if the variable is of string or object datatype, False otherwise.
    """
    try:
        return isinstance(s, (str, object))
    except Exception:
        return False

def format_value(val):
    """Formats a numeric value as a currency string with a dollar sign."""
    if val >= 0:
        return f"${val}"
    else:
        return f"-${abs(val)}"

def cast_function(df, temp_df,temp_df_header, expression):
    """
    Function to cast a column in a dataframe using a specified cast expression.

    Parameters:
    df (pandas.dataframe): The dataframe to operate on.
    temp_df (pandas.dataframe): The temporary dataframe.
    expression (dict): The cast expression dictionary containing 'operation',
    'output_column', and 'input_column'.

    Returns:
    pandas.dataframe: The dataframe with the casted column.
    """
    cast = expression['expression_value']
    cast = cast.strip()
    pattern = r"(CAST|cast)\(\s*([A-Za-z_]\w*)\s+(AS|as)\s+([A-Za-z_]+)\s*\)"
    match = re.match(pattern, cast)
    task_logger.info("match :%s", match)
    if match:
        column_name = match.group(2)
        task_logger.info("Extracted column name: %s",expression)
        df = add_or_update_column(df, temp_df, expression['output_col_name'], 
        expression['input_col_name'], '')
        task_logger.info("\n%s", df.head())
        task_logger.info("cast expression :%s\n", expression)
        if column_name in temp_df_header:
            cast_query = "SELECT " + expression['expression_value'] + " FROM temp_df"
        elif column_name in df.columns:
            cast_query = "SELECT " + expression['expression_value'] + " FROM df"
        else:
            raise ValueError(f"{column_name} not present in df or temp_df")
        task_logger.info("cast query :%s", cast_query)
        df[expression['output_col_name']] = ps.sqldf(cast_query)
        task_logger.info("\n%s", df[expression['output_col_name']])
        return df
    raise SyntaxError("Doesn't match the cast pattern: CAST( $column_name AS $expression )")

def apply_to_char(df,temp_df,column_name,new_format_part,format_part, expression):
    """Apply the transformation to the given column"""
    if temp_df[column_name].dtype in ['int64','float64']:
        if new_format_part:
            task_logger.info(new_format_part)
            if new_format_part == '$':
                df[expression['output_col_name']] = temp_df[column_name].map(format_value)
            else:
                formatted_series = interger_to_char_using_formate(temp_df,column_name, format_part)
                df[expression['output_col_name']]= formatted_series
            task_logger.info(" df[expression['output_col_name']]: %s", 
            df[expression['output_col_name']])
        else:
            df[expression['output_col_name']]= temp_df[column_name].astype(str)
    elif is_valid_datetime_or_date(temp_df[column_name][0]):
        df[expression['output_col_name']]= pd.to_datetime(temp_df[column_name])
        df[expression['output_col_name']]=df[expression['output_col_name']].apply(
        lambda x: x.strftime(new_format_part))
    elif is_string_or_object(df[column_name][0]):
        df[expression['output_col_name']]= temp_df[column_name].astype(str)
    else:
        raise ValueError("Unsupported data type")
    return df

def to_char_function(df, temp_df,temp_df_header, expression):
    """
    Function to process the TO_CHAR expression in a dataframe.

    Parameters:
    df (pandas.dataframe): The dataframe to operate on.
    temp_df (pandas.dataframe): The temporary dataframe.
    expression (dict): The TO_CHAR expression dictionary containing 
    'output_column', 'input_column', and 'operation'.

    Returns:
    pandas.dataframe: The dataframe with the TO_CHAR operation applied.
    """
    df = add_or_update_column(df ,temp_df ,expression['output_col_name'],
    expression['input_col_name'],'')
    original_string = expression['expression_value']
    # Extracting the format part from the original string
    pattern = r"(TO_CHAR|to_char)\(\s*([A-Za-z_]\w*)\s*(?:,\s*'(.*?)'\s*)?\)"
    match = re.match(pattern, original_string)
    if match:
        column_name = match.group(2).strip()
        task_logger.info("column name :%s",column_name)
        new_format_part = 0
        format_part=0
        if match.group(3):
            format_part= match.group(3).strip()
            task_logger.info("format part :%s",format_part)
            # Replacing the format part with the result of pyspark_to_pandas_format
            new_format_part = pyspark_to_pandas_format(format_part)
            # Reconstructing the original string with the new format part
            task_logger.info(OPERATION,expression['expression_value'])
            expression['expression_value'] = original_string.replace(format_part, new_format_part)
        try:
            if column_name in temp_df_header:
                df=apply_to_char(df,temp_df,column_name,new_format_part,format_part,expression)
            elif column_name in df.columns:
                df=apply_to_char(df,df,column_name,new_format_part,format_part,expression)
            else :
                raise ValueError ("column not present in both df and temp_df")
            task_logger.info(df.head())
        except ValueError as e:
            task_logger.error(ERROR_MSG, e)
            # Handle the error here, if needed
            raise
        except Exception as e:
            task_logger.error(ERROR_MSG, e)
            raise
    else:
        raise SyntaxError("Does not match to_char pattern")

    return df


def apply_to_date(df,temp_df,expression,column_name):
    """Apply the given expression to the given column"""
    if is_valid_datetime_or_date(temp_df[column_name][0]):
        df[expression['output_col_name']]= pd.to_datetime(temp_df[column_name])
        df[expression['output_col_name']]=df[expression['output_col_name']].apply(lambda x: x.strftime(new_format_part))
        df[expression['output_col_name']]= pd.to_datetime(df[expression['output_col_name']],format=new_format_part)
    return df

def to_date_function(df, temp_df, temp_df_header, expression):
    """
    Process and format date columns in a dataframe based on the 'to_date' operation in the expression.

    Parameters:
    df (pandas.dataframe): The dataframe to update.
    temp_df (pandas.dataframe): The dataframe containing the column to process.
    temp_df_header (list): List of column headers in temp_df.
    expression (dict): The expression details.

    Returns:
    pandas.dataframe: The updated dataframe.
    """
    original_string = expression['expression_value']
    task_logger.info(STR,original_string)
    pattern = r"(TO_DATE|to_date)\(\s*([A-Za-z_]\w*)\s*(?:,\s*'(.*?)'\s*)?\)"
    match = re.match(pattern, original_string)
    if match:
        df = add_or_update_column(df ,temp_df ,expression['output_col_name'],
        expression['input_col_name'],'')
        # Extracting the format part from the original string
        new_format_part,format_part= get_fromat_group(match)
        if match.group(3):
            task_logger.info(OPERATION,expression['expression_value'])
            expression['expression_value'] = original_string.replace(format_part, new_format_part)
        column_name = match.group(2).strip()
        task_logger.info("column name:%s",column_name)
        try:
            if column_name in temp_df_header:
                if is_valid_datetime_or_date(temp_df[column_name][0]):
                    df[expression['output_col_name']]= pd.to_datetime(temp_df[column_name])
                    df[expression['output_col_name']]=df[expression['output_col_name']].apply(
                    lambda x: x.strftime(new_format_part))
                    df[expression['output_col_name']]= pd.to_datetime(df[expression['output_col_name']],
                    format=new_format_part)
            elif column_name in df.columns:
                if is_valid_datetime_or_date(df[column_name][0]):
                    df[expression['output_col_name']]= pd.to_datetime(df[column_name])
                    df[expression['output_col_name']]=df[expression['output_col_name']].apply(
                    lambda x: x.strftime(new_format_part))
                    df[expression['output_col_name']]= pd.to_datetime(df[expression['output_col_name']],
                    format=new_format_part)
            else:
                raise ValueError("column name not present in df and temp_df")
        except ValueError as e:
            task_logger.error(ERROR_MSG, e)
            raise
            # Handle the error here, if needed
        except Exception as e:
            task_logger.error(ERROR_MSG, e)
            raise
    return df

def get_fromat_group(match):
    """Returns a list of columns"""
    new_format_part=0
    format_part=0
    if match.group(3):
        format_part=match.group(3).strip()
        task_logger.info("format_part : %s",format_part)
        # Replacing the format part with the result of pyspark_to_pandas_format
        new_format_part = pyspark_to_pandas_format(format_part)
        task_logger.info("new_format_part: %s",new_format_part)
    return new_format_part,format_part

def apply_to_number(temp_df, temp_df_header,df, expression,match):
    """ Apply the expression to the number of rows in the given expression"""
    df = add_or_update_column(df ,temp_df ,expression['output_col_name'],
    expression['input_col_name'],'')
    # Extracting the format part from the original string
    column_name = match.group(2).strip()
    task_logger.info("column_name: %s",column_name)
    new_format_part,format_part= get_fromat_group(match)
    try:
        if column_name in temp_df_header:
            if temp_df[column_name].dtype in ['object'] and new_format_part:
                df[expression['output_col_name']]= temp_df[column_name].apply(lambda x: format(x, format_part))
                df[expression['output_col_name']]=pd.to_numeric(df[expression['output_col_name']], errors='coerce')
            if temp_df[column_name].dtype in ['bool']:
                df[expression['output_col_name']] = temp_df[column_name].astype(int)
        if df[column_name].dtype in ['object']:
            if new_format_part:
                df[expression['output_col_name']]= df[column_name].apply(lambda x: format(x, format_part))
                df[expression['output_col_name']]=pd.to_numeric(df[expression['output_col_name']], errors='coerce')
            else:
                df[expression['output_col_name']]= pd.to_numeric(df[expression['output_col_name']], errors='coerce')
        if df[column_name].dtype in ['bool']:
            df[expression['output_col_name']] = df[column_name].astype(int)
    except ValueError as e:
        task_logger.error(ERROR_MSG, e)
        # Handle the error here, if needed
    except Exception as e:
        task_logger.error(ERROR_MSG, e)
    return df

def dtype_exp(temp_df, temp_df_header,df, expression):
    """
    Evaluates data type conversion expressions and modifies DataFrame accordingly.

    Args:
        temp_df (pandas.DataFrame): Temporary DataFrame.
        temp_df_header (list of str): Temporary DataFrame column headers.
        df (pandas.DataFrame): The DataFrame to be modified.
        expression (dict): The expression to be evaluated.

    Returns:
        tuple of pandas.DataFrame: Tuple containing modified DataFrames.

    Raises:
        ValueError: If an unsupported operation type is encountered.
    """
    match expression['operator']:
        case 'cast':
            df = cast_function(df,temp_df, temp_df_header, expression)
        case 'to_char':
            df= to_char_function(df, temp_df, temp_df_header, expression)
        case 'to_date':
            df= to_date_function(df, temp_df, temp_df_header, expression)
        case 'to_number':
            original_string = expression['expression_value']
            task_logger.info(STR,original_string)
            pattern = r"(TO_NUMBER|to_number)\(\s*([A-Za-z_]\w*)\s*(?:,\s*'(.*?)'\s*)?\)"
            match = re.match(pattern, original_string)
            if match:
                df = apply_to_number(temp_df, temp_df_header,df, expression,match)
        case _:
            raise ValueError("Unsupported operation type: %s",expression['operator'])
    return temp_df, df
