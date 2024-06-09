""" dfd"""
import re
import logging
from datetime import datetime
import pandas as pd
from dateutil import parser
from expression.add_column import add_or_update_column

task_logger = logging.getLogger('task_logger')

INVALID_SYNTAX="Invalid syntax"
ERROR_EXTRACT="Error extract: Invalid syntax"
def extract_datepart(input_string, df,temp_df):
    """
    Extracts a specific part of a date from a DataFrame column.

    Args:
        input_string (str): The input string containing the date part and column name.
        df (pandas.DataFrame): The DataFrame containing the date column.

    Returns:
        pandas.Series: A pandas Series containing the extracted date part.

    Raises:
        ValueError: If the column does not contain datetime values.
    """
    parts = input_string.split(' ')
    datepart = parts[0]
    column_name = parts[2]
    if column_name not in df.columns:
        raise ValueError
    if column_name in temp_df.columns and is_valid_datetime_or_date(temp_df[column_name][0]):
        temp_df[column_name]=pd.to_datetime(temp_df[column_name])
    elif is_valid_datetime_or_date(df[column_name][0]):
        df[column_name]=pd.to_datetime(df[column_name])
    else:
        raise ValueError("Column not a datetime value")
    if column_name not in df.columns:
        raise ValueError
    date_functions = {
        'year': lambda x: x.dt.year,
        'month': lambda x: x.dt.month,
        'day': lambda x: x.dt.day,
        'hour': lambda x: x.dt.hour,
        'minute': lambda x: x.dt.minute,
        'second': lambda x: x.dt.second,
        'week': lambda x: x.dt.isocalendar().week,
        'quarter': lambda x: x.dt.quarter,
        'day_of_week': lambda x: x.dt.dayofweek,
        'day_of_year': lambda x: x.dt.dayofyear,
        'decade': lambda x: (x.dt.year // 10) * 10,
        'century': lambda x: (x.dt.year // 100) + 1,
        'millennium': lambda x: (x.dt.year // 1000) + 1,
        'timezone_hour': lambda x: x.dt.tz_convert(None).dt.tz_localize(None).dt.tz_convert('UTC' \
        ).dt.tz_convert(x.dt.tz).dt.hour,
        'timezone_minute': lambda x: x.dt.tz_convert(None).dt.tz_localize(None).dt.tz_convert('UTC'\
        ).dt.tz_convert(x.dt.tz).dt.minute
    }
    if datepart in date_functions and column_name in temp_df.columns:
        return date_functions[datepart](temp_df[column_name])
    if datepart in date_functions and column_name in df.columns:
        return date_functions[datepart](df[column_name])
    else:
        raise ValueError("Invalid datepart specified.")

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
                               pandas_specifier,
                               pandas_format)

    return pandas_format

def frequency_alias(word):
    """
    Maps frequency words to their Pandas frequency aliases.

    Args:
        word (str): The frequency word.

    Returns:
        str or None: The corresponding Pandas frequency alias, or None if not found.
    """
    word = word.lower()
    frequency_map = {
        'day': 'D',
        'week': 'W',
        'month': 'M',
        'quarter': 'Q',
        'year': 'Y',
        'hour': 'H',
        'minute': 'T',  # or 'min'
        'second': 'S',
        'millisecond': 'L',
        'microsecond': 'U'
    }
    return frequency_map.get(word, None)

def extract_words(input_string):
    """
    Extracts words within brackets from an input string.

    Args:
        input_string (str): The input string.

    Returns:
        list of str: A list containing the extracted words.
    """
    # Define a regular expression pattern to match words within brackets
    pattern = r"\((.*?)\)"
    # Use re.findall() to extract words within brackets
    words_within_brackets = re.findall(pattern, input_string)

    # If there are more than two words within brackets, return only the first two
    words = words_within_brackets[0].split(',')[:2]

    # Strip extra spaces and inverted commas
    words = [word.strip().strip("'") for word in words]
    return words

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
        datetime.strptime(str(date_str), '%Y-%m-%d %H:%M:%S')
        return True
    except ValueError:
        try:
            # Attempt to parse as date
            parser.parse(date_str).date()
            return True
        except ValueError:
            return False

def get_date(df,expression):
    """
    Sets the output column in the DataFrame to the current date.

    Args:
        df (pandas.DataFrame): The DataFrame to be modified.
        expression (dict): The expression containing operation details.

    Returns:
        pandas.DataFrame: The modified DataFrame.
    """
    # Case expression applies conditions and assigns values accordingly
    pattern=r"getdate\(\)"
    match = re.match(pattern, expression['expression_value'])
    if match:
        try:
            task_logger.info("getdata expression :%s\n",expression)
            current_date = pd.Timestamp.now().date()
            df[expression['output_col_name']] = current_date
            task_logger.info("DF:%s",df.head())
        except Exception as e:
            task_logger.error("Error getdata: %s",e)
    else:
        task_logger.error("Error in syntax of getdate")
        raise SyntaxError
    return df

def calculate_months_between(d1, d2):
    """
    Calculates the difference in months between two dates.

    Args:
        d1 (datetime): The first date.
        d2 (datetime): The second date.

    Returns:
        int: The difference in months.
    """
    # Calculate the difference in years and months
    year_diff = d1.year - d2.year
    month_diff = d1.month - d2.month
    total_months_diff = year_diff * 12 + month_diff
    # Adjust for the day if d1.day < d2.day
    if d1.day < d2.day:
        total_months_diff -= 1
    return abs(total_months_diff)

def apply_months_between(df,expression,temp_df):
    """
    Applies the MONTHS_BETWEEN function to the DataFrame.

    Args:
        df (pandas.DataFrame): The DataFrame to be modified.
        expression (dict): The expression containing operation details.

    Returns:
        pandas.DataFrame: The modified DataFrame.
    """
    df = add_or_update_column(df ,temp_df ,expression['output_col_name'],\
    expression['input_col_name'],'')
    task_logger.info("Handling MONTHS_BETWEEN: %s",expression)
    # Define the regular expression pattern to match the MONTHS_BETWEEN function
    pattern = r"^MONTHS_BETWEEN\s*\(\s*('[^']+'|[^,\s]+)\s*,\s*('[^']+'|[^,\s]+)\s*\)$"
    # Match the input string using the pattern
    match = re.match(pattern, expression['expression_value'])
    if match:
        # Extract date1 and date2
        date1 = match.group(1)
        date2 = match.group(2)
        # Convert date1 and date2 to datetime objects if they are in df columns
        if date1 in temp_df.columns:
            temp_df[date1] = pd.to_datetime(temp_df[date1])
        elif date1 in df.columns:
            df[date1] = pd.to_datetime(df[date1])
        else:
            date1 = pd.to_datetime(date1)
        if date2 in temp_df.columns:
            temp_df[date2]=pd.to_datetime(temp_df[date2])
        elif date2 in df.columns:
            df[date2] = pd.to_datetime(df[date2])
        else:
            date2 = pd.to_datetime(date2)
        # Calculate the difference in months between date1 and date2
        # Apply the calculation
        if (date1 in df.columns or date1 in temp_df.columns) and (
            date2 in df.columns or date2 in temp_df.columns):
            df[expression['output_col_name']]=df.apply(lambda row:
                calculate_months_between(row[date1],row[date2]),axis=1)
        elif date1 in df.columns or date1 in temp_df.columns    :
            df[expression['output_col_name']] = df[date1].apply(
                lambda d1: calculate_months_between(d1,date2))
        elif date2 in df.columns or date2 in temp_df.columns:
            df[expression['output_col_name']] = df[date2].apply(
            lambda d2: calculate_months_between(date1,d2))
        else:
            df[expression['output_col_name']] = calculate_months_between(date1, date2)
        task_logger.info("MONTHS_BETWEEN calculation completed: %s",df)
    else:
        task_logger.error("Error in syntax of MONTHS_BETWEEN expression")
        raise SyntaxError
    return df

def apply_date_trunc(df,temp_df,expression):
    """
    Applies the DATE_TRUNC function to the DataFrame.

    Args:
        df (pandas.DataFrame): The DataFrame to be modified.
        temp_df (pandas.DataFrame): Temporary DataFrame.
        expression (dict): The expression containing operation details.

    Returns:
        pandas.DataFrame: The modified DataFrame.
    """
    df = add_or_update_column(df ,temp_df ,expression['output_col_name'],
        expression['input_col_name'],'')
    match = re.search(r"date_trunc\(([^,]+),", expression['expression_value'])
    if match:
        values = extract_words(expression['expression_value'])
    else:
        raise SyntaxError
    try:
        if values[1] in temp_df.columns:
            df[expression['output_col_name']] = pd.to_datetime(temp_df[values[1]])
        else:
            df[expression['output_col_name']] = pd.to_datetime(df[values[1]])
        df[expression['output_col_name']] = df[expression['output_col_name']].dt.to_period(
        frequency_alias(values[0])).dt.to_timestamp()
        task_logger.info(df.head())
    except Exception as e:
        task_logger.error("Error date_trunc: %s",e)
    return df

def apply_timestamp(df,temp_df,expression):
    """
    Applies the TO_TIMESTAMP function to the DataFrame.

    Args:
        df (pandas.DataFrame): The DataFrame to be modified.
        temp_df (pandas.DataFrame): Temporary DataFrame.
        expression (dict): The expression containing operation details.

    Returns:
        pandas.DataFrame: The modified DataFrame.
    """
    df = add_or_update_column(df ,temp_df ,expression['output_col_name'],
    expression['input_col_name'],'')
    original_string = expression['expression_value']
    # Extracting the format part from the original string
    format_part = re.search(r"'(.*?)'", original_string).group(1)
    match = re.search(r"to_timestamp\(([^,]+),", original_string)
    if match:
        column_name = match.group(1).strip()
    # Replacing the format part with the result of pyspark_to_pandas_format
    new_format_part = pyspark_to_pandas_format(format_part)
    try:
        if is_valid_datetime_or_date(df[column_name][0]):
            if column_name in temp_df.columns:
                df[expression['output_col_name']]= pd.to_datetime(temp_df[column_name])
            else:
                df[expression['output_col_name']]= pd.to_datetime(df[column_name])
            df[expression['output_col_name']]=df[expression['output_col_name']].apply(
            lambda x: x.strftime(new_format_part))
    except Exception as e:
        task_logger.error("Error to_number: %s",e)
    return df

def apply_datediff(df,match,expression):
    """
    Applies the DATEDIFF function to the DataFrame.

    Args:
        df (pandas.DataFrame): The DataFrame to be modified.
        match (str): The matched pattern from the expression.
        expression (dict): The expression containing operation details.

    Returns:
        pandas.DataFrame: The modified DataFrame.
    """
    datepart = match.group(1)
    from_date = match.group(2)
    to_date = match.group(3)
    task_logger.info("Reached here Datepart : %s from: %s to: %s\n%s",datepart,
    datepart,to_date,to_date)
    if from_date in df.columns:
        from_date = pd.to_datetime(df[from_date])
    else:
        from_date = pd.to_datetime(from_date)
    if to_date in df.columns:
        to_date = pd.to_datetime(df[to_date])
    else:
        to_date = pd.to_datetime(to_date)
    task_logger.info("Datepart : %s from: %s to: %s\n%s",datepart,datepart,to_date,df)
    #Calculate the difference using the retrieved function
    if datepart == 'day':
        df[expression['output_col_name']]= (from_date - to_date).dt.days
    elif datepart == 'week':
        df[expression['output_col_name']]= ((from_date - to_date).dt.days / 7).astype(int)
    elif datepart == 'month':
        df[expression['output_col_name']]= (from_date.dt.month - to_date.dt.month + 12 * (
        from_date.dt.year - to_date.dt.year))
    elif datepart == 'hour':
        df[expression['output_col_name']]= ((from_date - to_date).dt.total_seconds(
        ) / 3600).astype(int)
    elif datepart == 'minute':
        df[expression['output_col_name']]= ((from_date - to_date).dt.total_seconds(
        ) / 60).astype(int)
    elif datepart == 'year':
        df[expression['output_col_name']] = from_date.dt.year - to_date.dt.year
    else:
        task_logger.error("Error in syntax of datetime")
        raise SyntaxError
    print(df[expression['output_col_name']])
    task_logger.info(df.head())
    return df

def appy_extract(df,temp_df,expression):
    """
    Applies the EXTRACT function to the DataFrame.

    Args:
        df (pandas.DataFrame): The DataFrame to be modified.
        temp_df (pandas.DataFrame): Temporary DataFrame.
        expression (dict): The expression containing operation details.

    Returns:
        pandas.DataFrame: The modified DataFrame.
    """
    df = add_or_update_column(df ,temp_df ,expression['output_col_name'],
    expression['input_col_name'],'')
    original_string = expression['expression_value']
    match = re.search(r'extract\((.*?)\)', original_string)
        # Extracted text within brackets
    if match:
        extracted_text = match.group(1)
    else:
        task_logger.error(ERROR_EXTRACT)
        raise SyntaxError(INVALID_SYNTAX)
    df[expression['output_col_name']]=extract_datepart(extracted_text,df,temp_df)
    return df

def gregorian(df,expression):
    """" Return a gregorian expression object representing the current calendar"""
    original_string = expression['expression_value']
    match = re.search(r'to_gregorian\((.*?)\)', original_string)
    if match:
        extracted_text = match.group(1)
    else:
        task_logger.error(ERROR_EXTRACT)
        raise SyntaxError(INVALID_SYNTAX)
    def convert_julian_date(julian_date):
        julian_str = str(julian_date)
        year = julian_str[:3]
        year_century = int(year)+1900
        day_of_year = int(julian_str[3:])
        return str(pd.to_datetime(f'{year_century}-{day_of_year}', format='%Y-%j'))
    def apply_conversion(row):
        # Extract the date string from the tuple (if Polars passes a tuple to the apply function)
        date_str = row[0] if isinstance(row, tuple) else row
        return convert_julian_date(date_str)
    df[expression['output_col_name']] = df[extracted_text].apply(apply_conversion)
    return df

def date_time_exp(temp_df, temp_df_header, df, expression):
    """
    Evaluates datetime expressions and modifies DataFrame accordingly.

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
        case 'datediff':
            task_logger.info("Datediff :%s\n",expression)
            # Define the regular expression pattern to match the datediff function

            pattern =r"^datediff\s*\(\s*([^,\s]+)\s*,\s*('[^']+'|[^,\s]+)\s*"
            pattern2=r",\s*('[^']+'|[^,\s]+)\s*\)$"
            pattern=pattern+pattern2
            # Match the input string using the pattern
            match = re.match(pattern, expression['expression_value'])
            task_logger.info(match)
            if match:
                df=apply_datediff(df,match,expression)
            else:
                task_logger.error("Error in syntax of datetime")
                raise SyntaxError
        case 'getdate':
            df=get_date(df,expression)
        case 'months_between':
            df=apply_months_between(df,expression,temp_df)
        case 'date_trunc':
            df = apply_date_trunc(df,temp_df,expression)
        case 'to_timestamp':
            df=apply_timestamp(df,temp_df,expression)
        case 'extract':
            df = appy_extract(df,temp_df,expression)
        case 'to_julian':
            df = add_or_update_column(df ,temp_df ,expression['output_col_name'],
            expression['input_col_name'],'')
            original_string = expression['expression_value']
            match = re.search(r'to_julian\((.*?)\)', original_string)
            if match:
                extracted_text = match.group(1)
            else:
                task_logger.error(ERROR_EXTRACT)
                raise SyntaxError(INVALID_SYNTAX)
            formats_with_regex = {
                '%m/%d/%Y': r'\d{1,2}/\d{1,2}/\d{4}',
                '%Y-%m-%d': r'\d{4}-\d{2}-\d{2}',
                '%Y/%m/%d': r'\d{4}/\d{2}/\d{2}',
                '%Y.%m.%d': r'\d{4}\.\d{2}\.\d{2}',
                '%d-%m-%Y': r'\d{2}-\d{2}-\d{4}',
                '%Y,%m,%d': r'\d{4},\d{2},\d{2}',
                '%d %B %Y': r'\d{2} \w{4,9} \d{4}',
                '%d %b %Y': r'\d{2} \w{3} \d{4}',
                '%d %m %Y': r'\d{2} \d{2} \d{4}',
                '%B %d, %Y': r'\w{4,9} \d{2}, \d{4}',
                '%b %d, %Y': r'\w{3} \d{2}, \d{4}',
                '%m %d, %Y': r'\d{1,2} \d{1,2}, \d{4}',
                '%Y-%m-%d %H:%M:%S': r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
                '%Y/%m/%d %H:%M:%S': r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}',
                '%Y-%m-%d %H:%M': r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}',
                '%Y/%m/%d %H:%M': r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}',
                '%Y-%m-%d %I:%M:%S %p': r'\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2} [AP]M',
                '%Y/%m/%d %I:%M:%S %p': r'\d{4}/\d{2}/\d{2} \d{1,2}:\d{2}:\d{2} [AP]M',
                '%Y-%m-%d %I:%M %p': r'\d{4}-\d{2}-\d{2} \d{1,2}:\d{2} [AP]M',
                '%Y/%m/%d %I:%M %p': r'\d{4}/\d{2}/\d{2} \d{1,2}:\d{2} [AP]M',
                '%d %B %Y %H:%M:%S': r'\d{2} \w{4,9} \d{4} \d{2}:\d{2}:\d{2}',
                '%d %b %Y %H:%M:%S': r'\d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2}',
                '%d %m %Y %H:%M:%S': r'\d{2} \d{2} \d{4} \d{2}:\d{2}:\d{2}',
                '%B %d, %Y %H:%M:%S': r'\w{3,9} \d{2}, \d{4} \d{2}:\d{2}:\d{2}',
                '%b %d, %Y %H:%M:%S': r'\w{3} \d{2}, \d{4} \d{2}:\d{2}:\d{2}',
                '%m %d, %Y %H:%M:%S': r'\d{2} \d{2}, \d{4} \d{2}:\d{2}:\d{2}',
                '%Y-%m-%d %H:%M:%S.%f': r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}',
                '%Y/%m/%d %H:%M:%S.%f': r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\.\d{6}',
                '%Y-%m-%d %H:%M:%S,%f': r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{6}',
                '%Y/%m/%d %H:%M:%S,%f': r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2},\d{6}',
                '%d %B %Y %H:%M:%S.%f': r'\d{2} \w{4,9} \d{4} \d{2}:\d{2}:\d{2}\.\d{6}',
                '%d %b %Y %H:%M:%S.%f': r'\d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2}\.\d{6}',
                '%d %m %Y %H:%M:%S.%f': r'\d{2} \d{2} \d{4} \d{2}:\d{2}:\d{2}\.\d{6}',
                '%B %d, %Y %H:%M:%S.%f': r'\w{4,9} \d{2}, \d{4} \d{2}:\d{2}:\d{2}\.\d{6}',
                '%b %d, %Y %H:%M:%S.%f': r'\w{3} \d{2}, \d{4} \d{2}:\d{2}:\d{2}\.\d{6}',
                '%m %d, %Y %H:%M:%S.%f': r'\d{2} \d{2}, \d{4} \d{2}:\d{2}:\d{2}\.\d{6}',
                }
            def detect_date_format(date_str):
                for fmt, regex in formats_with_regex.items():
                    if re.match(regex,date_str):
                        return fmt
                raise ValueError("Date format not recognized")
            def convert_to_julian_date(date_str):
                date_format = detect_date_format(date_str)
                date = pd.to_datetime(date_str, format=date_format)
                # Extract year and day of year
                year = date.year
                day_of_year = date.dayofyear
    # Calculate century and year within century
                century = (year - 1900) // 100
                year_within_century = (year - 1900) % 100
# Format Julian Date string
                julian_date = f"{century:01d}{year_within_century:02d}{day_of_year:03d}"
                return julian_date
            df[expression['output_col_name']] = df[extracted_text].apply(convert_to_julian_date)
        case "to_gregorian":
            df = add_or_update_column(df ,temp_df ,expression['output_col_name'],
            expression['input_col_name'],'')
            df=gregorian(df,expression)
        case _:
            raise ValueError("Unsupported operation type: %s", expression['operator'])
    return temp_df, df
