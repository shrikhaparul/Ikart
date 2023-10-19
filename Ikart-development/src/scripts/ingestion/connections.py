"""script for connecting different databases and s3"""
import importlib
import logging
import sqlalchemy
import boto3
import pymysql
# from snowflake-sqlalchemy import dialect as snowflake

task_logger = logging.getLogger('task_logger')
module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")
JSON = '.json'
CONN_ESTB_MSG = "establish_conn() is %s"

def establish_conn_for_s3(json_data: dict, json_section: str,config_file_path:str):
    """establishes connection for the mysql database
       you pass it through the json"""
    try:
        connection_details = get_config_section(config_file_path+json_data["task"][json_section]\
        ["connection_name"]+JSON)
        d_aws_access_key_id = decrypt(connection_details["access_key"])
        d_aws_secret_access_key = decrypt(connection_details["secret_access_key"])
        s3_conn = boto3.client( service_name= 's3',region_name=
        connection_details["region_name"],aws_access_key_id=d_aws_access_key_id,
        aws_secret_access_key=d_aws_secret_access_key)
        task_logger.info("connection established")
        return s3_conn,connection_details
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error

def establish_conn_for_snowflake(json_data: dict, json_section: str,config_file_path:str):
    """establishes connection for the snowflake database
       you pass it through the json"""
    try:
        connection_details =  get_config_section(config_file_path+json_data["task"][json_section]\
        ["connection_name"]+JSON)
        password = decrypt(connection_details["password"])
        snowflake_conn = sqlalchemy.create_engine(f'snowflake://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["account"]}/'
        f':{connection_details["database"]}/{json_data["task"][json_section]["schema"]}'
        f'?warehouse={connection_details["warehouse"]}&role={connection_details["role"]}')
        return snowflake_conn,connection_details
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error

def establish_conn_for_mysql(json_data: dict, json_section: str,config_file_path:str):
    """establishes connection for the mysql database
       you pass it through the json"""
    try:
        connection_details = get_config_section(config_file_path+json_data["task"][json_section]
        ["connection_name"]+JSON)
        password = decrypt(connection_details["password"])
        mysql_conn = sqlalchemy.create_engine(f'mysql+pymysql://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["hostname"]}'
        f':{int(connection_details["port"])}/{connection_details["database"]}')
        # logging.info("connection established")
        return mysql_conn,connection_details
    except pymysql.err.OperationalError as error:
        task_logger.exception("error occured due to: %s",str(error))
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error

def establish_conn_for_postgres(json_data: dict, json_section: str, config_file_path:str):
    """establishes connection for the postgres database
       you pass it through the json"""
    try:
        connection_details = get_config_section(config_file_path+json_data["task"][json_section]
        ["connection_name"]+JSON)
        # print(connection_details["user"])
        password = decrypt(connection_details["password"])
        postgres_conn = sqlalchemy.create_engine(f'postgresql://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["hostname"]}'
        f':{int(connection_details["port"])}/{connection_details["database"]}')
        # logging.info("connection established")
        return postgres_conn,connection_details
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error

def establish_conn_for_sqlserver(json_data: dict, json_section: str, config_file_path:str):
    """establishes connection for the sqlsqerver database
       you pass it through the json"""
    try:
        connection_details = get_config_section(config_file_path+json_data["task"][json_section]
        ["connection_name"]+JSON)
        password = decrypt(connection_details["password"])
        sqlserver_conn=sqlalchemy.create_engine(f'mssql+pymssql://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["hostname"]}'
        f':{connection_details["port"]}/{connection_details["database"]}')
        logging.info("connection established")
        return sqlserver_conn,connection_details
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error
