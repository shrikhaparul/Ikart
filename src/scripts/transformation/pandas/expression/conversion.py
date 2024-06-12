"""script to convert currency values from one format to another"""
import logging
import os
import re
from fetch import fetch_data_from_json
from expression.add_column import add_or_update_column
from update_audit import audit_failure

task_logger = logging.getLogger('task_logger')

def fetch_conversion_value(arguments,from_currency,to_currency):
    """
    Fetches the conversion value between two currencies from a JSON file.

    Args:
        from_currency (str): The source currency code.
        to_currency (str): The target currency code.

    Returns:
        float: The conversion rate from the source currency to the target currency.
            Returns 1 if the currencies are the same.

    Raises:
        Exception: If an error occurs while fetching data or processing the JSON file.
    """
    try:
        paths_data = arguments["paths_data"]
        currency_location=os.path.expanduser(paths_data["folder_path"])+paths_data['src']+ \
        paths_data["transformation_path"]+arguments["json_data"]["job_execution"]+"/"+ \
        "expression/"+paths_data["currency_json_path"]
        currency_df = fetch_data_from_json(arguments,currency_location)
        # Assuming this function exists
        value = 1
        if from_currency != to_currency:
            # Assuming currency_df is your DataFrame and from_currency and to_currency are defined
            filtered_df = currency_df[(currency_df['from_currency'] == from_currency) & (
            currency_df['to_currency'] == to_currency)]
            task_logger.info("conversion_rate:\n %s", filtered_df)
            value = filtered_df['value'].iloc[0]
            task_logger.info("value: %s", value)
        return value
    except Exception as e:
        task_logger.exception("Error occured in fetch_conversion_value function with error : %s", e)
        audit_failure(arguments)

def perform_currency_conv(arguments,df, temp_df, column_name, expression, value):
    """Performs currency conversion on a specified column in a DataFrame based on a
    conversion rate and expression.

    Args:
        df (pandas.DataFrame): The DataFrame containing the column to convert.
        temp_df (pandas.DataFrame): The DataFrame (optional) containing the conversion rate value.
        column_name (str): The name of the column in `temp_df` that holds the conversion rate
        (or the column to convert in `df` if `temp_df` is not provided).
        expression (dict): A dictionary containing details of the conversion operation,
        including the output column name.
        'output_col_name' (str): The name of the new column in `df` to store the converted values.
        value (float): The conversion rate value (can be provided directly or
        retrieved from `temp_df`).

    Raises:
        ValueError: If the data type of the column to be converted is not integer or float.

    Returns:
        pandas.DataFrame: The DataFrame with the new converted column.
    """
    try:
        if temp_df[column_name].dtype in ['int64','float64','double','int64[pyarrow]',
            'float64[pyarrow]','double[pyarrow]']:
            df[expression['output_col_name']] = temp_df[column_name] * value
        # task_logger.info("%s,%s",temp_df[column_name],df[expression['output_col_name']])
        else:
            task_logger.info(df[expression['output_col_name']])
            raise ValueError("input column type should be integer or float datatype")
        return df
    except Exception as e:
        task_logger.exception("Error occured in perform_currency_conv function with error : %s", e)
        audit_failure(arguments)

def conversion_exp(arguments,temp_df, temp_df_header, df, expression):
    """
    Apply currency conversion operation to the DataFrame.

    Args:
        temp_df (pandas.DataFrame): Temporary DataFrame containing the data.
        temp_df_header (list): Header of the temporary DataFrame.
        df (pandas.DataFrame): DataFrame to which the operation will be applied.
        expression (dict): Dictionary containing details of the expression.

    Returns:
        tuple: Tuple containing updated temporary DataFrame and DataFrame.

    Raises:
        ValueError: If the input column type is not integer or float datatype.
        ValueError: If the input should be numeric or column name.
        SyntaxError: If the operation syntax is not in the format:
        currency(column_name/numeric,from_currency,to_currency).
    """
    try:
        match expression['operator']:
            case 'currency_conv':
                # task_logger.info(currency_df)
                op_string=expression['expression_value']
                pattern=r"currency_conv\(\s*(.*?)\s*,"
                pattern1=r"\s*(.*?)\s*,\s*(.*?)\s*\)"
                pattern=pattern+pattern1
                match = re.match(pattern, op_string)
                try:
                    if match:
                        df = add_or_update_column(arguments,df,
                                    temp_df,
                                    expression['output_col_name'],
                                    expression['input_col_name'],
                                    '')
                        column_name=match.group(1).strip()
                        from_currency=match.group(2).strip()
                        to_currency=match.group(3).strip()
                        value=fetch_conversion_value(arguments,from_currency,to_currency)
                        if column_name in temp_df_header:
                            df=perform_currency_conv(arguments,df,temp_df,column_name,
                            expression,value)
                        elif column_name in df.columns:
                            df=perform_currency_conv(arguments,df,df,column_name,expression,value)
                        else:
                            try:
                                df[expression['output_col_name']]=float(column_name)*value
                                task_logger.info("%s",df[expression['output_col_name']])
                            except ValueError:
                                raise ValueError("input should be numeric or column name")
                    else:
                        raise SyntaxError
                except SyntaxError:
                    task_logger.exception("operation synatax not in the format : currency( \
                    column_name/numeric,from_currency,to_currency)")
                    raise SyntaxError("operation synatax not in the format : currency( \
                    column_name/numeric,from_currency,to_currency)")
        return temp_df, df
    except Exception as e:
        task_logger.exception("Error occured in conversion_exp function with error : %s",e)
        audit_failure(arguments)
        raise e
