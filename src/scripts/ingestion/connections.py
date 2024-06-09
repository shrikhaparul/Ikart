"""script for connecting different databases and s3"""
import importlib
import logging
import sqlalchemy
import boto3
import pymysql
import paramiko

task_logger = logging.getLogger('task_logger')
module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")
JSON = '.json'
CONN_ESTB_MSG = "establish_conn() is %s"
SUCCESS_MSG = "connection established successfully!"
BULK_INGESTION = "Bulk Ingestion"

def establish_conn_for_s3(json_data: dict, json_section: str,config_file_path:str,paths_data):
    """establishes connection for the AWS S3"""
    try:
        if json_data['task_type']=="Ingestion":
            connection_details = get_config_section(config_file_path+json_data["task"][json_section]
            ["connection_name"]+JSON)
        elif json_data['task_type']==BULK_INGESTION:
            connection_details = get_config_section(config_file_path+json_data['task']['details']
            [0][json_section]['connection_name']+JSON)
        elif json_data['task_type']== "Transformation":
            #json_section is being used to give connection_name
            connection_details = get_config_section(config_file_path+json_section+JSON)
        d_aws_access_key_id = decrypt(connection_details["access_key"],paths_data)
        d_aws_secret_access_key = decrypt(connection_details["secret_access_key"],paths_data)
        s3_conn = boto3.client( service_name= 's3',region_name=
        connection_details["region_name"],aws_access_key_id=d_aws_access_key_id,
        aws_secret_access_key=d_aws_secret_access_key)
        task_logger.info(SUCCESS_MSG)
        return s3_conn,connection_details
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error

def establish_conn_for_remoteserver(json_data:dict,json_section:str,config_file_path,paths_data):
    """Establishes connection for the snowflake database."""
    try:
        # create ssh client
        if json_data['task_type']=="Ingestion":
            connection_details = get_config_section(config_file_path + \
            json_data["task"][json_section]["connection_name"] + JSON)
        elif json_data['task_type']==BULK_INGESTION:
            connection_details = get_config_section(config_file_path+json_data['task']['details']
            [0][json_section]['connection_name']+JSON)
        elif json_data['task_type']== "Transformation":
            #json_section is being used to give connection_name
            connection_details = get_config_section(config_file_path+json_section+JSON)
        # paramiko.util.log_to_file('paramiko.log')
        ssh_client = paramiko.SSHClient()
        # Load the private key file
        key_file = paramiko.RSAKey.from_private_key_file(paths_data["key_path"],
        paths_data["key_pass"])
        logging.info("Using SSH key authentication for user %s", connection_details["username"])
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(
            hostname=connection_details["hostname"],
            port=int(connection_details["port"]),
            username=connection_details["username"],
            pkey = key_file
        )
        logging.info("connection succcess.")
        return ssh_client, connection_details
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error

def establish_conn_for_snowflake(json_data:dict, json_section:str,config_file_path:str,paths_data):
    """establishes connection for the snowflake database
       you pass it through the json"""
    try:
        if json_data['task_type']=="Ingestion":
            connection_details = get_config_section(config_file_path+json_data["task"][json_section]
            ["connection_name"]+JSON)
        elif json_data['task_type']==BULK_INGESTION:
            connection_details = get_config_section(config_file_path+json_data['task']['details']
            [0][json_section]['connection_name']+JSON)
        elif json_data['task_type']== "Transformation":
            #json_section is being used to give connection_name
            connection_details = get_config_section(config_file_path+json_section+JSON)
        else:
            connection_details = get_config_section(config_file_path+json_data[
                "sql_execution"]["connection_name"]+JSON)
        password = decrypt(connection_details["password"],paths_data)
        snowflake_conn = sqlalchemy.create_engine(f'snowflake://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["account"]}/'
        f':{connection_details["database"]}/{json_data["task"][json_section]["schema"]}'
        f'?warehouse={connection_details["warehouse"]}&role={connection_details["role"]}')
        return snowflake_conn,connection_details
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error

def establish_conn_for_mysql(json_data: dict, json_section: str,config_file_path:str,paths_data):
    """establishes connection for the mysql database
       you pass it through the json"""
    try:
        if json_data['task_type']=="Ingestion":
            connection_details = get_config_section(config_file_path+json_data["task"][json_section]
            ["connection_name"]+JSON)
        elif json_data['task_type']==BULK_INGESTION:
            connection_details = get_config_section(config_file_path+json_data['task']['details']
            [0][json_section]['connection_name']+JSON)
        elif json_data['task_type']== "Transformation":
            #json_section is being used to give connection_name
            connection_details = get_config_section(config_file_path+json_section+JSON)
        else:
            connection_details = get_config_section(config_file_path+json_data[
                "sql_execution"]["connection_name"]+JSON)
        password = decrypt(connection_details["password"],paths_data)
        mysql_conn = sqlalchemy.create_engine(f'mysql+pymysql://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["hostname"]}'
        f':{int(connection_details["port"])}/{connection_details["database"]}')
        return mysql_conn,connection_details
    except pymysql.err.OperationalError as error:
        task_logger.exception("error occured due to: %s",str(error))
        raise error
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error

def establish_conn_for_postgres(json_data:dict, json_section:str,config_file_path:str,paths_data):
    """establishes connection for the postgres database
       you pass it through the json"""
    try:
        if json_data['task_type']=="Ingestion":
            connection_details = get_config_section(config_file_path+json_data["task"][json_section]
            ["connection_name"]+JSON)
        elif json_data['task_type']==BULK_INGESTION:
            connection_details = get_config_section(config_file_path+json_data['task']['details']
            [0][json_section]['connection_name']+JSON)
        elif json_data['task_type']== "Transformation":
            #json_section is being used to give connection_name
            connection_details = get_config_section(config_file_path+json_section+JSON)
        else:
            connection_details = get_config_section(config_file_path+json_data[
                "sql_execution"]["connection_name"]+JSON)
        password = decrypt(connection_details["password"],paths_data)
        postgres_conn = sqlalchemy.create_engine(f'postgresql://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["hostname"]}'
        f':{int(connection_details["port"])}/{connection_details["database"]}')
        return postgres_conn,connection_details
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error

def establish_conn_for_sqlserver(json_data: dict,json_section:str,config_file_path:str,paths_data):
    """establishes connection for the sqlsqerver database
       you pass it through the json"""
    try:
        if json_data['task_type']=="Ingestion":
            connection_details = get_config_section(config_file_path+json_data["task"][json_section]
            ["connection_name"]+JSON)
        elif json_data['task_type']==BULK_INGESTION:
            connection_details = get_config_section(config_file_path+json_data['task']['details'][0]
            [json_section]['connection_name']+JSON)
        elif json_data['task_type']== "Transformation":
            #json_section is being used to give connection_name
            connection_details = get_config_section(config_file_path+json_section+JSON)
        else:
            connection_details = get_config_section(config_file_path+json_data[
                "sql_execution"]["connection_name"]+JSON)
        password = decrypt(connection_details["password"],paths_data)
        sqlserver_conn=sqlalchemy.create_engine(f'mssql+pymssql://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["hostname"]}'
        f':{connection_details["port"]}/{connection_details["database"]}')
        logging.info(SUCCESS_MSG)
        return sqlserver_conn,connection_details
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error

def establish_conn_for_oracle(json_data: dict, json_section: str, config_file_path:str,paths_data):
    """establishes connection for the oracle database
       you pass it through the json"""
    try:
        if json_data['task_type']=="Ingestion":
            connection_details = get_config_section(config_file_path+json_data["task"][json_section]
            ["connection_name"]+JSON)
        elif json_data['task_type']==BULK_INGESTION:
            connection_details = get_config_section(
            config_file_path+json_data['task']['details'][0][json_section]['connection_name']+JSON)
        elif json_data['task_type']== "Transformation":
            #json_section is being used to give connection_name
            connection_details = get_config_section(config_file_path+json_section+JSON)
        else:
            connection_details = get_config_section(
            config_file_path+json_data["sql_execution"]["connection_name"]+JSON)
        password = decrypt(connection_details["password"],paths_data)
        oracle_conn=sqlalchemy.create_engine(f'oracle+cx_oracle://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["hostname"]}'
        f':{connection_details["port"]}/?service_name={connection_details["database"]}',    
        pool_size=20,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800
        )
        logging.info(SUCCESS_MSG)
        return oracle_conn,connection_details
    except Exception as error:
        task_logger.exception(CONN_ESTB_MSG, str(error))
        raise error
