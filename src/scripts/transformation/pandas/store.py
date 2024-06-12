"""
Python modeule to store the dataframe to different location and format:
csv
db
json
xml
parquet
excel
"""
import os
import logging
import tarfile
import zipfile
import bz2
import gzip
import snappy

from update_audit import audit_failure
from fetch import establish_connection

task_logger = logging.getLogger('task_logger')

NOT_COMPATIBLE="Source Type not compatible"

def store_data(arguments,result_df, destination):
    """
    Function to store the result data in location specified by user

    Parameters:
        result_df (dataframe): Result DataFrames after performing operations that has to be stored.
        destination (dict): Dictionary containing details of destination type and location.

    Raises:
        Exception: If an error occurs while storing the data.
    """
    try:
        task_logger.info("Table to be stored: %s",result_df)
        if destination["target_type"]=="Local Server":

            if destination['file_type'] == 'csv':
                store_data_to_csv(arguments,result_df, destination)
            elif destination['file_type'] == 'json':
                store_data_to_json(arguments,result_df, destination)
            elif destination['file_type'] == 'xml':
                store_data_to_xml(arguments,result_df, destination)
            elif destination['file_type'] == 'parquet':
                store_data_to_parquet(arguments,result_df, destination)
            elif destination['file_type'] == 'excel':
                store_data_to_excel(arguments,result_df, destination)
            else:
                task_logger.error(NOT_COMPATIBLE)
                raise SyntaxError(NOT_COMPATIBLE)
        elif destination['target_type'] == 'PostgreSQL':
            store_data_to_db_postgres(arguments,result_df,
                                    destination['connection_name'],
                                    destination['schema'],
                                    destination['table_name'])
        elif destination['target_type'] == 'MYSQL':
            store_data_to_db_mysql(arguments,result_df,
                                    destination['connection_name'],
                                    destination['table_name'])
        elif destination['target_type'] == 'MSSQL':
            store_data_to_db_mssql(arguments,result_df,
                                    destination['connection_name'],
                                    destination['table_name'])
        else:
            task_logger.error(NOT_COMPATIBLE)
            raise SyntaxError(NOT_COMPATIBLE)
    except Exception as e:
        task_logger.error("Failed to store data: %s", e)
        audit_failure(arguments)
        raise

def store_data_to_csv(arguments,df, destination):
    """
    Store DataFrame to a CSV file.

    Parameters:
        df (pandas.DataFrame): DataFrame to be stored.
        csv_location (str): Filepath where CSV file will be saved.

    Raises:
        Exception: If an error occurs during the data storing process.
    """
    try:
        csv_location=destination['file_path']+destination['file_name']
        if os.path.splitext(csv_location)[1]=="parquet":
            raise TypeError("Invalid csv file type. File extension is wrong")
        df.to_csv(csv_location,index=False)
        if destination["compression"]!="":
            compress_file(arguments,csv_location, destination["compression"])
        task_logger.info("Data stored successfully to CSV at %s",csv_location)
    except Exception as e:
        task_logger.error("Error storing data to CSV at %s: %s",csv_location,e)
        audit_failure(arguments)
        raise

def store_data_to_db_mysql(arguments,df,connection_name, table):
    """
    Store DataFrame to a SQL database.

    Parameters:
        df (pandas.DataFrame): DataFrame to be stored.
        user (str): Username for database authentication.
        password (str): Password for database authentication.
        host (str): Hostname of the database server.
        port (str): Port number of the database server.
        database (str): Name of the database.
        schema (str): Name of the schema in the database.
        table (str): Name of the table to store data.

    Raises:
        Exception: If an error occurs during the data storing process.
    """
    try:
        connections = establish_connection(arguments)
        connection,connection_detials = connections.establish_conn_for_mysql(arguments["json_data"],
        connection_name,arguments["config_file_path"],arguments["paths_data"])
        df.to_sql(name=table, con=connection, if_exists="replace", index=False)
        task_logger.info("Data stored successfully to the %s table in the %s" \
        "database.",table,connection_detials['database'])
    except Exception as e:
        print(e)
        task_logger.error("Error storing data to SQL database %s, table %s: %s",
                      connection_detials['database'],table,e)
        audit_failure(arguments)
        raise

def store_data_to_db_mssql(arguments,df,connection_name, table):
    """
    Store DataFrame to a SQL database.

    Parameters:
        df (pandas.DataFrame): DataFrame to be stored.
        user (str): Username for database authentication.
        password (str): Password for database authentication.
        host (str): Hostname of the database server.
        port (str): Port number of the database server.
        database (str): Name of the database.
        schema (str): Name of the schema in the database.
        table (str): Name of the table to store data.

    Raises:
        Exception: If an error occurs during the data storing process.
    """
    try:
        connections = establish_connection(arguments)
        connection,connection_detials=connections.establish_conn_for_sqlserver(
        arguments["json_data"],connection_name,arguments["config_file_path"],
        arguments["paths_data"])
        chunksize = 60000
        for i, start in enumerate(range(0, df.shape[0], chunksize)):
            print(f"Chunck number:{i}")
            chunk = df.iloc[start:start + chunksize]
            if i == 0:
                chunk.to_sql(table, connection, if_exists='replace', index=False)
            else:
                chunk.to_sql(table, connection, if_exists='append', index=False)
        task_logger.info("Data stored successfully to the %s table in the %s database.",
                     table,connection_detials['database'])
    except Exception as e:
        task_logger.error("Error storing data to SQL database %s, table %s: %s",
                      connection_detials['database'],table,e)
        audit_failure(arguments)
        raise

def store_data_to_db_postgres(arguments,df,connection_name, schema, table):
    """
    Store DataFrame to a SQL database.

    Parameters:
        df (pandas.DataFrame): DataFrame to be stored.
        user (str): Username for database authentication.
        password (str): Password for database authentication.
        host (str): Hostname of the database server.
        port (str): Port number of the database server.
        database (str): Name of the database.
        schema (str): Name of the schema in the database.
        table (str): Name of the table to store data.

    Raises:
        Exception: If an error occurs during the data storing process.
    """
    try:
        connections = establish_connection(arguments)
        connection,connection_detials=connections.establish_conn_for_postgres(arguments["json_data"]
        ,connection_name,arguments["config_file_path"],arguments["paths_data"])
        chunksize = 60000
        for i, start in enumerate(range(0, df.shape[0], chunksize)):
            # print(f"Chunck number:{i}")
            chunk = df.iloc[start:start + chunksize]
            if i == 0:
                chunk.to_sql(table, connection, if_exists='replace', \
                index=False,schema=schema)
            else:
                chunk.to_sql(table, connection, if_exists='append', \
                index=False,schema=schema)

        # df.to_sql(table, connection_string, if_exists="replace", index=False)
        task_logger.info("Data stored successfully to the %s.%s table in the %s database.",
                     schema,table,connection_detials['database'])
    except Exception as e:
        task_logger.error("Error storing data to SQL database %s, table %s.%s: %s",
                      connection_detials['database'],schema,table,e)
        audit_failure(arguments)
        raise

def store_data_to_json(arguments,df, destination):
    """
    Store data to a JSON file.

    Parameters:
        data: Data to be stored.
        json_location (str): Filepath where JSON file will be saved.

    Raises:
        Exception: If an error occurs during the data storing process.
    """
    try:
        json_location=destination['file_path']+destination['file_name']
        if os.path.splitext(json_location)[1]=="json":
            raise TypeError("Invalid json file type. File extension is wrong")
        df.to_json(json_location,index=False)
        if destination["compression"]!="":
            compress_file(arguments,json_location, destination["compression"])
        task_logger.info("Data stored successfully to JSON at %s",json_location)
    except Exception as e:
        task_logger.error("Error in storing data to JSON at %s: %s",json_location,e)
        audit_failure(arguments)
        raise

# Function to store data to XML
def store_data_to_xml(arguments,df, destination):
    """
    Store DataFrame to an XML file.

    Parameters:
        df (pandas.DataFrame): DataFrame to be stored.
        xml_location (str): Filepath where XML file will be saved.

    Raises:
        Exception: If an error occurs during the data storing process.
    """
    try:
        xml_location=destination['file_path']+destination['file_name']
        if os.path.splitext(xml_location)[1]=="xml":
            raise TypeError("Invalid xml file type. File extension is wrong")
        df.to_xml(xml_location, index=False)
        if destination["compression"]!="":
            compress_file(arguments,xml_location, destination["compression"])
        task_logger.info("Data stored successfully to XML at %s",xml_location)
    except Exception as e:
        task_logger.error("Error storing data to XML at %s: %s",xml_location,e)
        audit_failure(arguments)
        raise

# Function to store data to Parquet
def store_data_to_parquet(arguments,df, destination):
    """
    Store DataFrame to a Parquet file.

    Parameters:
        df (pandas.DataFrame): DataFrame to be stored.
        parquet_location (str): Filepath where Parquet file will be saved.

    Raises:
        Exception: If an error occurs during the data storing process.
    """
    try:
        parquet_location=destination['file_path']+destination['file_name']
        if os.path.splitext(parquet_location)[1]=="parquet":
            raise TypeError("Invalid parquet file type. File extension is wrong")
        df.to_parquet(parquet_location, index=False)
        if destination["compression"]!="":
            compress_file(arguments,parquet_location, destination["compression"])
        task_logger.info("Data stored successfully to Parquet at %s",parquet_location)
    except Exception as e:
        task_logger.error("Error storing data to Parquet at %s: %s",parquet_location,e)
        audit_failure(arguments)
        raise

# Function to store data to Excel
def store_data_to_excel(arguments,df, destination):
    """
    Store DataFrame to an Excel file.

    Parameters:
        df (pandas.DataFrame): DataFrame to be stored.
        excel_location (str): Filepath where Excel file will be saved.

    Raises:
        Exception: If an error occurs during the data storing process.
    """
    try:
        excel_location=destination['file_path']+destination['file_name']
        if os.path.splitext(excel_location)[1]=="xlsx":
            raise TypeError("Invalid excel file type. File extension is wrong")
        df.to_excel(excel_location, index=False)
        if destination["compression"]!="":
            compress_file(arguments,excel_location, destination["compression"])
        task_logger.info("Data stored successfully to Excel at %s",excel_location)
    except Exception as e:
        task_logger.error("Error storing data to Excel at %s: %s",excel_location,e)
        audit_failure(arguments)
        raise

def compress_file(arguments,file_path, compression):
    '''function to compress a file with options for zip, tar, gzip, and bzip'''
    try:
        task_logger.info("compression of file started:")
        if compression == 'zip':
            with zipfile.ZipFile(f"{file_path}.zip", 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, arcname=os.path.basename(file_path))
            os.remove(file_path)
            return f"{file_path}.zip"

        if compression == 'tar':
            with tarfile.open(f"{file_path}.tar", 'w') as tarf:
                tarf.add(file_path, arcname=os.path.basename(file_path))
            os.remove(file_path)
            return f"{file_path}.tar"
        if compression == 'bzip':
            with open(file_path, 'rb') as f_in:
                with bz2.BZ2File(f"{file_path}.bz2", 'wb') as f_out:
                    f_out.writelines(f_in)
            os.remove(file_path)
            return f"{file_path}.bz2"
        if compression == 'gzip':
            with open(file_path, 'rb') as f_in:
                with gzip.open(f"{file_path}.gz", 'wb') as f_out:
                    f_out.writelines(f_in)
            os.remove(file_path)
            return f"{file_path}.gz"
        if compression == 'snappy':
            with open(file_path, 'rb') as f_in:
                data = f_in.read()
                compressed_data = snappy.compress(data)
                snappy_file_path = f"{file_path}.snappy"
                with open(snappy_file_path, 'wb') as f_out:
                    f_out.write(compressed_data)
            os.remove(file_path)
        return file_path
    except Exception as e:
        task_logger.error("Unexpected error in compress_file: %s", str(e))
        audit_failure(arguments)
        raise
