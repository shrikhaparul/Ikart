"""
Python modeule to get the dataframe from different location and format:
csv
db
json
xml
parquet
excel
"""
import os
import sys
import importlib
import logging
import sqlalchemy
import pandas as pd

task_logger = logging.getLogger('task_logger')
NOT_COMPATIBLE="Source Type not compatible"

SUCCESS="Data fetched successfully from"

# def get_data_info(df):
#     """fetch datframes size and rows, columns"""
#     memory_usage_kb =(df.memory_usage(deep=True).sum())/ 1024
#     rows, columns = df.shape
#     task_logger.info("Fetched data memory usage :%s",memory_usage_kb)
#     task_logger.info("The data has %d rows and %d columns.",rows,columns)

def establish_connection(arguments):
    """Establishes connection module dynamically."""
    try:
        paths_data =arguments["paths_data"]
        connection_path = os.path.expanduser(paths_data["folder_path"]) + \
        paths_data['src'] + paths_data["ingestion_path"]
        sys.path.insert(0, connection_path)
        connections = importlib.import_module("connections")
        return connections
    except ImportError as e:
        task_logger.error("Failed to import connections module: %s", str(e))
        # bulk_subtask_failed(arguments['task_id'],arguments['json_data'],
        # arguments['run_id'],arguments['paths_data'],arguments['iter_value'],arguments['group_no'],
        # arguments['subtask_no'])
        # update_status_file(arguments['task_id'],'SUCCESS',arguments['text_file_path'])
        raise
    except Exception as e:
        task_logger.error("Unexpected error in establish_connection: %s", str(e))
        # audit_failure(arguments)
        raise

def fetch_data(source_details,arguments):
    """
    Function that fetches data from different locations and gets a dataframe
    Parameters:
        source_details (dict): Dictionary containing source type and location.
    Returns:
        pandas.DataFrame: DataFrame of data fetched.

    Raises:
        Exception: If an error occurs fetching the data.
    """
    try:
        if source_details['source_type']=="Local Server":
            if source_details['file_type'] == 'csv':
                return fetch_data_from_csv(source_details['file_path'])
            if source_details['file_type'] == 'xml':
                return fetch_data_from_xml(source_details['file_path'])
            if source_details['file_type'] == 'excel':
                return fetch_data_from_excel(source_details['file_path'])
            if source_details['file_type'] == 'parquet':
                return fetch_data_from_parquet(source_details['file_path'])
            if source_details['file_type'] == 'json':
                return fetch_data_from_json(source_details['file_path'])
        elif source_details['source_type']=="PostgreSQL":
            return fetch_data_from_postgres(
                source_details['connection_name'],
                source_details['schema'],
                source_details['table_name'],arguments
            )
        elif source_details['source_type']=="MYSQL":
            return fetch_data_from_mysql(
                source_details['connection_name'],
                source_details['table_name'],arguments
            )
        task_logger.error(NOT_COMPATIBLE)
        raise SyntaxError(NOT_COMPATIBLE)
    except Exception as e:
        task_logger.error("Failed to fetch data: %s", e)
        raise

def fetch_data_from_csv(csv_location):
    """
    Fetch data from a CSV file.

    Parameters:
    csv_location (str): The file path to the CSV file.

    Returns:
    pandas.DataFrame: DataFrame containing the data from the CSV file.

    """
    try:
        chunks = []
        if os.path.splitext(csv_location)[1]=="csv":
            raise TypeError("Invalid csv file type. File extension is wrong")

        # Iterate over the file in chunks
        for chunk in pd.read_csv(csv_location, chunksize=10000, dtype_backend= "pyarrow"):
            # Process the chunk (e.g., data cleaning, analysis)
            chunks.append(chunk)
        # Concatenate all chunks into a single DataFrame
        df = pd.concat(chunks, ignore_index=True)
        df.columns = df.columns.str.replace(' ', '_')
        task_logger.info("%s %s",SUCCESS,csv_location)
        return df
    except pd.errors.EmptyDataError:
        task_logger.error("CSV file is empty: %s", csv_location)
        raise
    except Exception as e:
        task_logger.error("Error fetching data from CSV at %s: %s",csv_location,e)
        raise

def fetch_data_from_mssql(connection_name, table,arguments):
    """
    Fetch data from a SQL database.

    Parameters:
    user (str): Username for connecting to the database.
    password (str): Password for connecting to the database.
    host (str): Hostname of the database server.
    port (str): Port number of the database server.
    database (str): Name of the database.
    schema (str): Name of the schema in the database.
    table (str): Name of the table from which data will be fetched.

    Returns:
    pandas.DataFrame: DataFrame containing the data from the specified SQL table.

    """
    try:
        connections = establish_connection(arguments)
        connection,connection_detials=connections.establish_conn_for_sqlserver(
        arguments["json_data"],connection_name,arguments["config_file_path"],
        arguments["paths_data"])
        # connection_string,connection_detials = establish_conn_for_sqlserver(connection_name)
        query = f"SELECT * FROM {table}"
        df = pd.read_sql(query, connection, dtype_backend= "pyarrow")
        task_logger.info("%s in the %s database.",table, connection_detials['database'])
        return df
    except sqlalchemy.exc.OperationalError as e:
        task_logger.error("Operational error fetching data from SQL database %s, table %s: %s",
                      connection_detials['database'],  table, e)
        raise
    except Exception as e:
        task_logger.error("Error fetching data from SQL database %s, table %s: %s",
                      connection_detials['database'],table,e)
        raise

def fetch_data_from_postgres(connection_name, schema, table,arguments):
    """
    Fetch data from a SQL database.

    Parameters:
    user (str): Username for connecting to the database.
    password (str): Password for connecting to the database.
    host (str): Hostname of the database server.
    port (str): Port number of the database server.
    database (str): Name of the database.
    schema (str): Name of the schema in the database.
    table (str): Name of the table from which data will be fetched.

    Returns:
    pandas.DataFrame: DataFrame containing the data from the specified SQL table.

    """
    try:
        connections = establish_connection(arguments)
        connection,connection_detials=connections.establish_conn_for_postgres(arguments["json_data"]
        ,connection_name,arguments["config_file_path"],arguments["paths_data"])
        # connection_string,connection_detials = establish_conn_for_postgres(connection_name)
        query = f"SELECT * FROM {schema}.{table}"
        df = pd.read_sql(query, connection, dtype_backend= "pyarrow")
        task_logger.info("%s.%s in the %s database.",schema,table,connection_detials['database'])
        return df
    except sqlalchemy.exc.OperationalError as e:
        task_logger.error("Operational error fetching data from SQL database %s, table %s.%s: %s",
                      connection_detials['database'], schema, table, e)
        raise
    except Exception as e:
        task_logger.error("Error fetching data from SQL database %s, table %s.%s: %s",
                      connection_detials['database'],schema,table,e)
        raise

def fetch_data_from_mysql(connection_name, table,arguments):
    """
    Fetch data from a SQL database.

    Parameters:
    user (str): Username for connecting to the database.
    password (str): Password for connecting to the database.
    host (str): Hostname of the database server.
    port (str): Port number of the database server.
    database (str): Name of the database.
    schema (str): Name of the schema in the database.
    table (str): Name of the table from which data will be fetched.

    Returns:
    pandas.DataFrame: DataFrame containing the data from the specified SQL table.

    """
    try:
        connections = establish_connection(arguments)
        connection,connection_detials = connections.establish_conn_for_mysql(arguments["json_data"],
        connection_name,arguments["config_file_path"],arguments["paths_data"])
        query = f"SELECT * FROM {table}"
        df = pd.read_sql(query, con=connection, dtype_backend= "pyarrow")
        task_logger.info("%s in the %s database.",table,connection_detials['database'])
        return df
    except sqlalchemy.exc.OperationalError as e:
        task_logger.error("Operational error fetching data from SQL database %s, table %s: %s",
                      connection_detials['database'], table, e)
        raise
    except Exception as e:
        task_logger.error("Error fetching data from SQL database %s, table %s: %s",
                      connection_detials['database'],table,e)
        raise

def fetch_data_from_xml(xml_location):
    """
    Fetch data from an XML file.

    Parameters:
    xml_location (str): The file path to the XML file.

    Returns:
    pandas.DataFrame: DataFrame containing the data from the XML file.
    """
    try:
        if os.path.splitext(xml_location)[1]=="xml":
            raise TypeError("Invalid xml file type. File extension is wrong")
        df=pd.read_xml(xml_location, dtype_backend= "pyarrow")
        task_logger.info("%s %s",SUCCESS,xml_location)
        return df
    except Exception as e:
        task_logger.error("Error fetching data from XML at %s: %s",xml_location,e)
        raise

def fetch_data_from_excel(excel_location):
    """
    Fetch data from an Excel file.

    Parameters:
    excel_location (str): The file path to the Excel file.

    Returns:
    pandas.DataFrame: DataFrame containing the data from the Excel file.
    """
    try:
        if os.path.splitext(excel_location)[1]=="xlsx":
            raise TypeError("Invalid excel file type. File extension is wrong")
        df = pd.read_excel(excel_location, dtype_backend= "pyarrow")
        task_logger.info("%s %s",SUCCESS,excel_location)
        return df
    except Exception as e:
        task_logger.error("Error fetching data from Excel at %s: %s",excel_location,e)
        raise

def fetch_data_from_parquet(parquet_location):
    """
    Fetch data from a Parquet file.

    Parameters:
    parquet_location (str): The file path to the Parquet file.

    Returns:
    pandas.DataFrame: DataFrame containing the data from the Parquet file.
    """
    try:
        if os.path.splitext(parquet_location)[1]=="parquet":
            raise TypeError("Invalid parquet file type. File extension is wrong")
        df = pd.read_parquet(parquet_location, dtype_backend= "pyarrow")
        task_logger.info("%s %s",SUCCESS,parquet_location)
        return df
    except Exception as e:
        task_logger.error("Error fetching data from Parquet at %s: %s",parquet_location,e)
        raise

def fetch_data_from_json(json_location):
    """
    Fetch data from a JSON file.

    Parameters:
    json_location (str): The file path to the JSON file.

    Returns:
    pandas.DataFrame: DataFrame containing the data from the JSON file.
    """
    try:
        if os.path.splitext(json_location)[1]=="json":
            raise TypeError("Invalid json file type. File extension is wrong")
        df = pd.read_json(json_location, dtype_backend= "pyarrow")
        task_logger.info("%s %s",SUCCESS,json_location)
        return df
    except Exception as e:
        task_logger.error("Error fetching data from JSON at %s: %s",json_location,e)
        raise
