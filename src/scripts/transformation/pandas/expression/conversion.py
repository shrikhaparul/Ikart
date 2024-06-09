"""script to convert currency values from one format to another"""
import os
import logging
import re
from fetch import fetch_data_from_json
from expression.add_column import add_or_update_column

task_logger = logging.getLogger('task_logger')


def fetch_conversion_value(from_currency,to_currency):
    """ To fetch currency details from json 
    return: value of the currency"""
    data_location='/home/rperuman/src_files/transformation/data/currency.json'
    currency_df=fetch_data_from_json(data_location)
    value=1
    if from_currency!=to_currency:
        # Assuming currency_df is your DataFrame and from_currency and to_currency are defined
        filtered_df = currency_df[(currency_df['from_currency'] == from_currency) & (
        currency_df['to_currency'] == to_currency)]
        task_logger.info("conversion_rate:\n %s", filtered_df)
        value = filtered_df['value'].iloc[0]
        task_logger.info("value: %s", value)
    return value

def perform_currency_conv(df,temp_df,column_name,expression,value):
    """Converts a currency expression to a currency expression"""
    if temp_df[column_name].dtype in ['int64','float64','double',
        'int64[pyarrow]','float64[pyarrow]','double[pyarrow]']:
        df[expression['output_col_name']]=temp_df[column_name]*value
        task_logger.info("temp_df[column_name]:%s,df[expression['output_col_name']:%s",temp_df[column_name],df[expression['output_col_name']])
    else :
        raise ValueError("input column type should be integer or float datatype")
    task_logger.info(df[expression['output_col_name']])
    return df

def conversion_exp(temp_df, temp_df_header, df, expression):
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
    match expression['operator']:
        case 'currency_conv':
            # logging.info(currency_df)
            op_string=expression['expression_value']
            pattern=r"currency_conv\(\s*(.*?)\s*,"
            pattern1=r"\s*(.*?)\s*,\s*(.*?)\s*\)"
            pattern=pattern+pattern1
            match = re.match(pattern, op_string)
            # print(match)
            try:
                if match:
                    df = add_or_update_column(df,
                                temp_df,
                                expression['output_col_name'],
                                expression['input_col_name'],
                                '')
                    column_name=match.group(1).strip()
                    from_currency=match.group(2).strip()
                    to_currency=match.group(3).strip()
                    value=fetch_conversion_value(from_currency,to_currency)
                    if column_name in temp_df_header:
                        df=perform_currency_conv(df,temp_df,column_name,expression,value)
                    elif column_name in df.columns:
                        df=perform_currency_conv(df,df,column_name,expression,value)
                    else:
                        try:
                            df[expression['output_col_name']]=float(column_name)*value
                            task_logger.info("%s",df[expression['output_col_name']])
                        except ValueError:
                            raise ValueError("input should be numeric or column name")
                else:
                    raise SyntaxError
            except SyntaxError:
                raise SyntaxError("operation synatax not in the format : currency( \
                column_name/numeric,from_currency,to_currency)")
    return temp_df, df
