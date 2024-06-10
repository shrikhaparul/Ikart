""" importing modules """
import json
import logging
import sys
import os
from datetime import datetime
import zipfile
import importlib
from collections import defaultdict
import multiprocessing as mp
import requests
import pandas as pd
import mysql.connector
from sqlalchemy.orm import sessionmaker
from master import send_mail
from file_features import compress_file,split_large_file_compress_encrypt,\
gpg_encrypt_file,move_file, gpg_decrypt_file
from tracking import audit,update_status_file,task_failed,task_success, \
bulk_subtask_failed,bulk_subtask_success
from dotenv import load_dotenv

load_dotenv()

PASSPHRASE = os.environ.get("PASSPHRASE")

JSON = ".json"
NO_RESTART = "no restart"
task_logger = logging.getLogger('task_logger')
FAIL_LOG_STATEMENT = "%s got failed engine"
TASK_LOG = 'Task %s Execution Completed'
AUDIT_STATUS_MSG = "audit status code:%s"
URL_MSG = "API URL :%s"
REQ_FAILED_MSG = "Request failed with status code:%s"
INVALID_MSG = "Invalid response format. Expected a list."
BULK_ING = 'Bulk Ingestion'
MSG_AUDIT_CONFIG = "Something is wrong with audit config username or password"
EXECUTE_QRY_MSG = "execute_query() is %s."
ERR_MSG = "Error:%s "
DB_DOESNT_EXST_MSG = "Database does not exist"
RESTART_SQL_QUERY= "restart_sql_query from engine_code"

module = importlib.import_module("master")
log_creation = getattr(module, "log_creation")
setup_logger = getattr(module, "setup_logger")

def task_json_read(paths_data,task_id,prj_nm):
    """function to read task json"""
    try:
        with open(r""+os.path.expanduser(paths_data["folder_path"])+paths_data[
            "local_repo"]+paths_data["programs"]+prj_nm+\
        paths_data["task_json_path"]+task_id+".json","r",encoding='utf-8') as jsonfile:
            task_logger.info("reading TASK JSON data started %s",task_id)
            json_data = json.load(jsonfile)
            task_logger.info("reading TASK JSON data completed")
        return json_data
    except Exception as error:
        task_logger.exception("error in task_json_read %s.", str(error))
        send_mail('Failed', error, 'task_json_read from engine_code')
        raise error

def checks_mapping_read(paths_data):
    """function to read checks_mapping json"""
    try:
        with open(r""+os.path.expanduser(paths_data["folder_path"])+paths_data[
            'src']+paths_data["dq_scripts_path"]+\
        "checks_mapping.json","r",encoding='utf-8') as json_data_new:
            task_logger.info("reading checks mapping json data started")
            json_checks = json.load(json_data_new)
            task_logger.info("reading checks mapping data completed")
        return json_checks
    except Exception as error:
        task_logger.exception("error in checks_mapping_read %s.", str(error))
        send_mail('Failed', error, 'checks_mapping_read from engine_code')
        raise error

def read_write_imports(paths_data,json_data,bulk_source=None,bulk_target=None):
    """function for importing read and write functions"""
    try:
        if json_data["task_type"] == 'Ingestion':
            source = json_data["task"]["source"]
            target = json_data["task"]["target"]
        elif json_data["task_type"] == BULK_ING:
            source = bulk_source
            target = bulk_target
        py_scripts_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
            'src']+paths_data["ingestion_path"]
        sys.path.insert(0, py_scripts_path)
        if json_data["task_type"] == BULK_ING:
            task_logger.info("read imports started")
            source_module = source
            task_logger.info("write imports started")
            target_module = target
        else:
            task_logger.info("read imports started")
            source_module = source["source_type"]
            task_logger.info("write imports started")
            target_module = target["target_type"]
        source_name = importlib.import_module(source_module)
        target_name = importlib.import_module(target_module)
        read = getattr(source_name, "read")
        write = getattr(target_name, "write")
        return read,write
    except Exception as error:
        task_logger.exception("error in read_write_imports %s.", str(error))
        send_mail('Failed', error, 'read_write_imports from engine_code')
        raise error

def data_quality_features(json_data,definitions_qc):
    """function for executing data quality features based on pre and post checks"""
    try:
        if "task" in json_data and "data_quality_features" in json_data["task"]:
            dq_features = json_data['task']['data_quality_features']
            if dq_features['dq_auto_correction_required'] == 'Y' \
            and dq_features['data_masking_required'] == 'Y':
                definitions_qc.auto_correction(json_data)
                definitions_qc.data_masking(json_data)
            elif dq_features['dq_auto_correction_required'] == 'Y' \
            and dq_features['data_encryption_required'] == 'Y':
                definitions_qc.auto_correction(json_data)
                definitions_qc.data_encryption(json_data)
            elif dq_features['dq_auto_correction_required'] == 'Y' \
            and dq_features['data_masking_required'] == 'Y' \
            and dq_features['data_encryption_required'] == 'Y':
                definitions_qc.auto_correction(json_data)
                definitions_qc.data_masking(json_data)
                definitions_qc.data_encryption(json_data)
            elif dq_features['dq_auto_correction_required'] == 'Y':
                definitions_qc.auto_correction(json_data)
            elif dq_features['data_masking_required'] == 'Y':
                definitions_qc.data_masking(json_data)
            elif dq_features['data_encryption_required'] == 'Y':
                definitions_qc.data_encryption(json_data)
    except Exception as error:
        task_logger.exception("error in data_quality_features %s.", str(error))
        send_mail('Failed', error, 'data_quality_features from engine_code')
        raise error

def precheck_status(paths_json_data,task_json_data,run_id):
    '''function to check whether all the checks has been passed
    or failed at target level'''
    try:
        seq_nos = [item['seq_no'] for item in task_json_data['task']['data_quality']
                   if item['type'] == 'pre_check']
        seq_nos_str = ','.join(seq_nos)
        taskorpipelinename = task_json_data['task_name']
        url = (f"{paths_json_data['audit_api_url']}"
            f"/getPostCheckResult/{taskorpipelinename}/{run_id}/{seq_nos_str}")
        task_logger.info("URL from API: %s", url[:30]+" ...")
        response = requests.get(url, timeout=100)
        if response.status_code == 200:
            result = response.json()
        else:
            task_logger.info("Request failed with status code: %s", response.status_code)
        return result
    except Exception as error:
        task_logger.exception("precheck_status() is %s.", str(error))
        send_mail('Failed', error, 'precheck_status from engine_code')
        raise error

def postcheck_status(paths_json_data,task_json_data,run_id):
    '''function to check whether all the checks has been passed
    or failed at target level'''
    try:
        seq_nos = [item['seq_no'] for item in task_json_data['task']['data_quality']
                   if item['type'] == 'post_check']
        seq_nos_str = ','.join(seq_nos)
        taskorpipelinename = task_json_data['task_name']
        url = (f"{paths_json_data['audit_api_url']}"
        f"/getPostCheckResult/{taskorpipelinename}/{run_id}/{seq_nos_str}")
        task_logger.info("URL from API: %s", url[:30]+" ...")
        response = requests.get(url, timeout=100)
        if response.status_code == 200:
            result = response.json()
        else:
            task_logger.info("Request failed with status code: %s", response.status_code)
        return result
    except Exception as error:
        task_logger.exception("postcheck_status() is %s.", str(error))
        send_mail('Failed', error, 'postcheck_status from engine_code')
        raise error

def archive_files(inp_file_names, out_zip_file):
    """Function to Archive files"""
    task_logger.info("Archiving file start time: %s", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    compression = zipfile.ZIP_DEFLATED
    task_logger.info("Archiving of file started %s-", inp_file_names)
    # create the zip file first parameter path/name, second mode
    zipf = zipfile.ZipFile(out_zip_file, mode="w")
    try:
        for file_to_write in inp_file_names:
            zipf.write(file_to_write, file_to_write, compress_type=compression)
    except FileNotFoundError as error:
        task_logger.error("Exception occurred during Archiving process %s-", error)
        send_mail('Failed', error, 'archive_files from engine_code')
    finally:
        zipf.close()
        task_logger.info("Archiving file end time: %s",
                         datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        task_logger.info("Archiving of file ended")

def begin_transaction(paths_data, json_data, config_file_path,
    bulk_target=None):
    '''function to start the transaction'''
    try:
        connections_path = os.path.expanduser(paths_data["folder_path"]) + \
        paths_data['src'] + paths_data["ingestion_path"]
        sys.path.insert(0, connections_path)
        connection = importlib.import_module("connections")
        target_types = {
            'mysql_write': 'establish_conn_for_mysql',
            'snowflake_write': 'establish_conn_for_snowflake',
            'oracle_write': 'establish_conn_for_oracle',
            'postgres_write': 'establish_conn_for_postgres',
            'mssql_write': 'establish_conn_for_sqlserver',
            'bulk_mysql_write': 'establish_conn_for_mysql',
            'bulk_snowflake_write': 'establish_conn_for_snowflake',
            'bulk_oracle_write': 'establish_conn_for_oracle',
            'bulk_postgres_write': 'establish_conn_for_postgres',
            'bulk_mssql_write': 'establish_conn_for_sqlserver'
        }
        engine = None  # Initialize engine to None
        if json_data["task_type"] == 'Ingestion':
            target = json_data['task']['target']
            target_type = target['target_type']
            if target_type in target_types:
                conn_function = getattr(connection, target_types[target_type])
                engine, _ = conn_function(json_data, 'target', config_file_path, paths_data)
        elif json_data["task_type"] == BULK_ING and bulk_target in target_types:
            conn_function = getattr(connection, target_types[bulk_target])
            # calling this conn_function and its returning engine.
            engine, _ = conn_function(json_data, 'target', config_file_path, paths_data)
        if engine:
            session = sessionmaker(bind=engine)()
            session.begin()
            task_logger.info("Transaction Started")
            return session
    except Exception as e:
        task_logger.error("Failed to establish connection or unsupported \
        target type: %s", e, exc_info=True)
        send_mail('Failed', e, 'postcheck_status from engine_code')
    raise ValueError("Failed to establish connection or unsupported target type")

def removesrcfile(json_data,paths_data):
    '''to remove source file from folder when splitting done.'''
    utility_path=os.path.expanduser(paths_data["folder_path"])+paths_data['src']+ \
    paths_data["ingestion_path"]
    sys.path.insert(0, utility_path)
    utility = importlib.import_module("utility")
    target = json_data["task"]["target"]
    records_per_split = 0 if 'target_max_record_count' not in target or \
    target['target_max_record_count'] in (None,"None","") else \
    target['target_max_record_count']
    file_name = utility.replace_date_placeholders(target['file_name'])
    file_path = utility.replace_date_placeholders(target['file_path'])
    if os.path.exists(file_path+file_name):
        if_file_exists = True
    else:
        if_file_exists = False
    if records_per_split not in (0,"",None,"None") and if_file_exists:
        os.remove(file_path+file_name)

def establish_conn(paths_data,prj_nm,task_name):
    """establishes connection for the database
       you pass it through the json"""
    try:
        new_path = os.path.expanduser(paths_data["folder_path"])+\
        paths_data['src']+paths_data[ "ingestion_path"]
        sys.path.insert(0, new_path)
        connection_code = importlib.import_module("connections")
        json_data = task_json_read(paths_data,task_name,prj_nm)
        config_path = paths_data["folder_path"]+paths_data["config_path"]+\
        json_data["sql_execution"]["connection_name"]+JSON
        config_file_path = os.path.expanduser(paths_data[
                "folder_path"])+paths_data["config_path"]
        with open(config_path, encoding="utf-8") as f:
            connection_json_data = json.load(f)
        if connection_json_data['connection_subtype'] == "MySQL":
            connection, _ = connection_code.establish_conn_for_mysql(
                json_data,None,config_file_path,paths_data)
        elif connection_json_data['connection_subtype'] == "PostgreSQL":
            connection, _ = connection_code.establish_conn_for_postgres(
                json_data,None,config_file_path,paths_data)
        elif connection_json_data['connection_subtype'] == "ORACLE":
            connection, _ = connection_code.establish_conn_for_oracle(
                json_data,None,config_file_path,paths_data)
        elif connection_json_data['connection_subtype'] == "MSSQL":
            connection, _ = connection_code.establish_conn_for_sqlserver(
                json_data,None,config_file_path,paths_data)
        elif connection_json_data['connection_subtype'] == "Snowflake":
            connection, _ = connection_code.establish_conn_for_snowflake(
                json_data,None,config_file_path,paths_data)
        return connection
    except Exception as error:
        task_logger.exception("establish_conn() is %s", str(error))
        send_mail('Failed', error, 'establish_conn from engine_code')
        raise error

def execute_query(prj_nm, paths_data: str, task_name: str, json_data,
    run_id, restart_point, itervalue):
    """Execute query based on the mode and its previous execution status"""
    try:
        restart_mode = json_data['sql_execution']['restart']
        sorted_queries = sort_queries(json_data["sql_list"], restart_point, restart_mode)
        all_queries_passed = True
        audit(json_data, task_name, run_id, paths_data, 'STATUS', 'STARTED', itervalue)
        connection = establish_conn(paths_data, prj_nm, task_name).raw_connection()
        cursor = connection.cursor()
        for query in sorted_queries:
            seq_no = query["seq_no"]
            sql_query = query["sql_query"][:30] + "..."
            task_logger.info("Sequence number %s belongs to the query (%s)", seq_no, sql_query)
            try:
                task_logger.info("Query: %s", sql_query)
                variable = cursor.execute(query["sql_query"])
                cursor.execute("Commit")
                audit_query_execution(json_data, task_name, run_id, paths_data, itervalue,variable,
                seq_no, sql_query)
            except Exception as e:
                task_logger.error("Error executing SQL query for sequence number %s: %s",
                seq_no, str(e))
                audit(json_data, task_name, run_id, paths_data, "RESULT", "FAIL", itervalue, seq_no)
                audit(json_data, task_name, run_id, paths_data, 'STATUS', 'FAILED', itervalue)
                all_queries_passed = False
                break
        if all_queries_passed:
            audit(json_data, task_name, run_id, paths_data, 'STATUS', 'COMPLETED', itervalue)
        return all_queries_passed
    except Exception as error:
        task_logger.exception("Error in execute_query: %s.", str(error))
        send_mail('Failed', error, 'execute_query from engine_code')
        raise error

def sort_queries(sql_list, restart_point, restart_mode):
    """Sort queries based on restart mode and point"""
    sorted_queries = sorted(sql_list, key=lambda x: int(x["seq_no"]))
    if restart_mode == "normal":
        return [query for query in sorted_queries if int(query["seq_no"]) >= int(restart_point)]
    if restart_mode == "skip":
        return [query for query in sorted_queries if int(query["seq_no"]) > int(restart_point)]
    return sorted_queries

def audit_query_execution(json_data, task_name, run_id, paths_data, itervalue,
    variable, seq_no, sql_query):
    """Audit query execution"""
    audit(json_data, task_name, run_id, paths_data, "SQL QUERY", sql_query, itervalue, None, seq_no)
    audit(json_data, task_name, run_id, paths_data, 'ROWS AFFECTED', variable, itervalue, seq_no)
    audit(json_data, task_name, run_id, paths_data, "RESULT", "PASS", itervalue, seq_no)


def latest_audit_status(task_nm,paths_data):
    """gets audit status from audit table for given task"""
    try:
        url = f"{paths_data['audit_api_url']}/executequery/" + task_nm
        task_logger.info("API URL :%s",url)
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            json_data = response.json()
            if isinstance(json_data, list):
                column_values = json_data  #Assuming the response is already a list of column values
            else:
                task_logger.info(INVALID_MSG)
        else:
            task_logger.info(REQ_FAILED_MSG,response.status_code)
        return column_values
    except mysql.connector.Error as err:
        send_mail('Failed', err, 'latest_audit_status from engine_code')
        if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
            task_logger.error(MSG_AUDIT_CONFIG)
        elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            task_logger.error(DB_DOESNT_EXST_MSG)
        else:
            task_logger.error(ERR_MSG, err)
        raise err
    except Exception as error1:
        task_logger.exception(EXECUTE_QRY_MSG, str(error1))
        send_mail('Failed', error1, 'latest_audit_status from engine_code')
        raise error1

def subtask_audit_status(task_nm,subtask_no,paths_data):
    """gets audit status from audit table for given task"""
    try:
        url = f"{paths_data['audit_api_url']}/executesubquery/{task_nm}/{subtask_no}"
        task_logger.info(URL_MSG,url)
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            json_data = response.json()
            if isinstance(json_data, list):
                column_values = json_data  #Assuming the response is already a list of column values
            else:
                task_logger.info(INVALID_MSG)
        else:
            task_logger.info(REQ_FAILED_MSG,response.status_code)
        return column_values
    except mysql.connector.Error as err:
        send_mail('Failed', err, 'subtask_audit_status from engine_code')
        if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
            task_logger.error(MSG_AUDIT_CONFIG)
        elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            task_logger.error(DB_DOESNT_EXST_MSG)
        else:
            task_logger.error(ERR_MSG, err)
        raise err
    except Exception as error1:
        task_logger.exception(EXECUTE_QRY_MSG, str(error1))
        send_mail('Failed', error1, 'subtask_audit_status from engine_code')
        raise error1

def prev_group_audit_status(task_nm,run_id,paths_data):
    """gets audit status from audit table for given task"""
    try:
        url = f"{paths_data['audit_api_url']}/previousGrpStatus/{task_nm}/{run_id}"
        task_logger.info(URL_MSG,url)
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            json_data = response.json()
            if isinstance(json_data, list):
                column_values = json_data  #Assuming the response is already a list of column values
            else:
                task_logger.info(INVALID_MSG)
        else:
            task_logger.info(REQ_FAILED_MSG,response.status_code)
        return column_values
    except mysql.connector.Error as err:
        send_mail('Failed', err, 'prev_group_audit_status from engine_code')
        if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
            task_logger.error(MSG_AUDIT_CONFIG)
        elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            task_logger.error(DB_DOESNT_EXST_MSG)
        else:
            task_logger.error(ERR_MSG, err)
        raise err
    except Exception as error1:
        task_logger.exception(EXECUTE_QRY_MSG, str(error1))
        send_mail('Failed', error1, 'prev_group_audit_status from engine_code')
        raise error1

def prev_subtask_audit_status(task_nm,run_id,group_no,paths_data):
    """gets audit status from audit table for given task"""
    try:
        url = f"{paths_data['audit_api_url']}/subtaskStatus/{task_nm}/{run_id}/{group_no}"
        task_logger.info(URL_MSG,url)
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            json_data = response.json()
            if isinstance(json_data, list):
                column_values = json_data  #Assuming the response is already a list of column values
            else:
                task_logger.info(INVALID_MSG)
        else:
            task_logger.info(REQ_FAILED_MSG,response.status_code)
        return column_values
    except mysql.connector.Error as err:
        send_mail('Failed', err, 'prev_subtask_audit_status from engine_code')
        if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
            task_logger.error(MSG_AUDIT_CONFIG)
        elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            task_logger.error(DB_DOESNT_EXST_MSG)
        else:
            task_logger.error(ERR_MSG, err)
        raise err
    except Exception as error1:
        task_logger.exception(EXECUTE_QRY_MSG, str(error1))
        send_mail('Failed', error1, 'prev_subtask_audit_status from engine_code')
        raise error1

def prev_sql_execution_audit_status(task_nm,run_id,paths_data):
    """gets audit status from audit table for given task"""
    try:
        url = f"{paths_data['audit_api_url']}/prevsqltaskStatus/{task_nm}/{run_id}"
        task_logger.info(URL_MSG,url)
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            json_data = response.json()
            if isinstance(json_data, list):
                column_values = json_data  #Assuming the response is already a list of column values
            else:
                task_logger.info(INVALID_MSG)
        else:
            task_logger.info(REQ_FAILED_MSG,response.status_code)
        return column_values
    except mysql.connector.Error as err:
        send_mail('Failed', err, 'prev_sql_execution_audit_status from engine_code')
        if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
            task_logger.error(MSG_AUDIT_CONFIG)
        elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            task_logger.error(DB_DOESNT_EXST_MSG)
        else:
            task_logger.error(ERR_MSG, err)
        raise err
    except Exception as error1:
        task_logger.exception(EXECUTE_QRY_MSG, str(error1))
        send_mail('Failed', error1, 'prev_sql_execution_audit_status from engine_code')
        raise error1

def restart_sql_query(prj_nm, paths_data: str, task_name: str, json_data, run_id, iter_value):
    """function for getting the restart point based on the mode"""
    try:
        restart_mode = json_data['sql_execution']['restart']
        restart_point = 1  # Set a default value for restart_point
        result = latest_audit_status(task_name,paths_data)
        if result and len(result) > 0:
            # Check if the prev execution result is not empty and has at
            #  least one entry in audit table
            prev_task_status = result[0]
            prev_exec_audit_value = prev_task_status['audit_value']
            task_logger.info("previous execution status of task, %s: %s",task_name,
            prev_exec_audit_value)
            task_iteration = prev_task_status['iteration']
            prev_run_id = prev_task_status['run_id']
            if prev_exec_audit_value == "COMPLETED":
                task_logger.info("executing in %s mode",restart_mode)
                task_logger.info("Previous task execution completed sucessfully so"\
                " starting current execution from the beginning.")
                if restart_mode == "skip":
                    #to start from first query in skip mode, restart point should be zero.
                    restart_point = 0
                return execute_query(prj_nm,paths_data,task_name,json_data,run_id,
                restart_point,iter_value)
            # else:
            task_iteration = task_iteration+1
            if restart_mode == "begin":
                task_logger.info("executing in BEGIN mode")
                return execute_query(prj_nm,paths_data,task_name,json_data,run_id,
                restart_point,task_iteration)
            if restart_mode != "begin":
                # fetching the sequence number at which previous execution failed from audit table
                result2 = prev_sql_execution_audit_status(task_name,prev_run_id,paths_data)
                sequence = result2[0]['sequence']
                task_logger.info("restarting the code in %s mode as query"\
                " got failed at seq_no: %s",restart_mode,sequence)
                restart_point = sequence
                return execute_query(prj_nm, paths_data, task_name, json_data, run_id,
                restart_point, task_iteration)
        else:
            # Handle the case when result is empty #fresh run
            task_logger.info("Starting Execution of: %s", task_name)
            if restart_mode == "skip":
                #to start from first query in skip mode, restart point should be zero.
                restart_point = 0
            return execute_query(prj_nm,paths_data,task_name,json_data,run_id,
            restart_point,iter_value)
    except KeyError as e:
        task_logger.error("KeyError: Missing key in json_data or previous task status: %s", e)
        send_mail('Failed', e, RESTART_SQL_QUERY)
    except IndexError as e:
        task_logger.error("IndexError: List index out of range: %s", e)
        send_mail('Failed', e, RESTART_SQL_QUERY)
    except Exception as e:
        task_logger.error("An unexpected error occurred: %s", e)
        send_mail('Failed', e, RESTART_SQL_QUERY)
    return None

def process_file_split_and_compress(arguments,output_file_name,
    output_file_path, target,target_sub_type = None):
    """Process file by splitting it if needed and compressing, with optional encryption."""
    try:
        # Determine the number of records per split
        records_per_split = 0 if 'target_max_record_count' not in target or \
            target['target_max_record_count'] in (None, "None", "") else \
            int(target['target_max_record_count'])
        task_logger.info("records_per_split: %s", records_per_split)

        # Determine the compression type
        compression = None if target['compression'] in ("", None) else target["compression"]
        task_logger.info("compression: %s", compression)
        if int(records_per_split) > 0:
            # Split the file if records_per_split is greater than 0
            filename_wo_ext = os.path.splitext(output_file_name)[0]
            extension = os.path.splitext(output_file_name)[1]
            split_large_file_compress_encrypt(arguments,output_file_path + output_file_name,
            output_file_path + filename_wo_ext,
            records_per_split, extension,target_sub_type,compression,target)
            os.remove(output_file_path + output_file_name)
        else:
            #if spltting is not there
            # Handle file compression and optional encryption
            full_file_path = output_file_path + output_file_name
            temp_file_path = compress_file(arguments,full_file_path, compression)

            if target.get("encryption") == "yes":
                task_logger.info("The %s file encryption started..", temp_file_path)
                response,temp_file_path = gpg_encrypt_file(temp_file_path,target["public_key_path"])
                if not response:
                    task_logger.info("Encryption failed")
            move_file(arguments, temp_file_path, target,target_sub_type)
        return True
    except Exception as error1:
        task_logger.exception(EXECUTE_QRY_MSG, str(error1))
        update_status_file(arguments['task_id'],'FAILED',arguments['text_file_path'])
        audit(arguments['json_data'], arguments['task_id'],arguments['run_id'],
        arguments['paths_data'],'STATUS','FAILED',arguments['iter_value'])
        sys.exit()

def decryption_check(json_data, file_path, local_temp_path, paths_data):
    """Function created to decrypt the encrypted file formats."""
    try:
        # Importing the utility module to get the decrypt function
        new_path = os.path.expanduser(paths_data["folder_path"])+\
            paths_data['src']+paths_data[ "ingestion_path"]
        sys.path.insert(0, new_path)
        connection_code = importlib.import_module("utility")
        decrypt = getattr(connection_code, "decrypt")
        # Decrypting the passphrase
        passphrase = decrypt(PASSPHRASE, paths_data)
        # Condition to check if decryption to be executed or not.
        if json_data['task']['source']['decryption'] == 'yes':
            task_logger.info("Decryption required.")
            new_file, _ = gpg_decrypt_file(file_path, passphrase, local_temp_path)
            return new_file
        if json_data['task']['source']['decryption'] != 'yes':
            task_logger.info("decryption not required.")
            return None
    except Exception :
        task_logger.error("Error caused in decryption_check function.")

def normal_task_execution(json_data,config_file_path,task_id,run_id,paths_data,
    text_file_path,iter_value,session, local_temp_path):
    """executes read and write scripts based on the normal ingestion json"""
    try:
        group_no = None
        subtask_no = None
        arguments = {
            'json_data' : json_data,
            'config_file_path':config_file_path,
            'task_id' : task_id,
            'run_id' : run_id,
            'paths_data' : paths_data,
            'text_file_path' : text_file_path,
            'iter_value' :  iter_value,
            'group_no' : group_no,
            'subtask_no':subtask_no
            }
        task_logger.info("entered in normal task execution")
        # ingestion execution starts here
        read, write =read_write_imports(paths_data,json_data)
        if json_data["task_type"] == 'Ingestion':
            source = json_data["task"]["source"]
            target = json_data["task"]["target"]
        #if source type is database
        counter=0
        total_records_inserted = 0
        if source["source_type"] in ("postgres_read","mysql_read",
        "snowflake_read","mssql_read", "aws_s3_read","remote_server_read","oracle_read"):
            data_fram = read(json_data,config_file_path,task_id,run_id,paths_data,
            text_file_path,iter_value)
            for df_chunk in data_fram :
                counter+=1
                records_in_chunk = len(df_chunk)
                if target["target_type"] != "rest_api_write":
                    #if target is database like mysql,snowflake,postgres, sql_server, oracle
                    if target["target_type"] not in ("csv_write", "parquet_write", "json_write",
                        "xml_write", "xlsx_write","aws_s3_write","remote_server_write"):
                        value=write(json_data, df_chunk,counter,config_file_path,task_id,run_id,
                        paths_data,text_file_path,iter_value,session)
                        total_records_inserted += records_in_chunk
                        if value is False:
                            task_failed(task_id,text_file_path,json_data,run_id,paths_data,
                            iter_value)
                            return False
                    else:
                        #if target is in file based systems like AWS S3, remote server, local
                        value,output_file_path,output_file_name=write(json_data,task_id,
                        run_id,iter_value, paths_data,text_file_path,df_chunk, counter,
                        local_temp_path)
                        total_records_inserted += records_in_chunk
                        if value is False:
                            task_failed(task_id,text_file_path,json_data,run_id,paths_data,
                            iter_value)
                            return False
                else:
                    #if target is rest_API
                    value=write(json_data,df_chunk,task_id,run_id,paths_data,
                    text_file_path,iter_value)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        task_failed(task_id,text_file_path,json_data,run_id,paths_data,iter_value)
                        return False
        #if source type is local server
        elif source["source_type"] in ("csv_read", "parquet_read", "json_read",
                                    "xml_read", "xlsx_read"):
            file_path = json_data['task']['source']['file_path'] + \
            json_data['task']['source']['file_name']
            local_file_path = decryption_check(json_data,file_path,local_temp_path, paths_data)
            data_fram=read(json_data,task_id,run_id,paths_data,text_file_path,
            iter_value,local_file_path)
            for df_chunk in data_fram :
                counter+=1
                records_in_chunk = len(df_chunk)
                #if target is rest_API
                if target["target_type"] == "rest_api_write":
                    value=write(json_data,df_chunk,task_id,run_id,paths_data,
                    text_file_path,iter_value)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        task_failed(task_id,text_file_path,json_data,run_id,paths_data,iter_value)
                        return False
                #if target is database
                elif target["target_type"] not in ("csv_write", "parquet_write", "json_write",
                "xml_write", "xlsx_write","aws_s3_write", "remote_server_write"):
                    value=write(json_data, df_chunk,counter,config_file_path,task_id,run_id,
                        paths_data,text_file_path,iter_value,session)
                    if value is False:
                        task_failed(task_id,text_file_path,json_data,run_id,paths_data,iter_value)
                        return False
                else:
                    #if target is file based
                    value,output_file_path,output_file_name=write(json_data,task_id,
                    run_id,iter_value, paths_data,text_file_path,df_chunk, counter,
                    local_temp_path)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        task_failed(task_id,text_file_path,json_data,run_id,paths_data,iter_value)
                        return False
        # if source is rest API
        elif source["source_type"] in ("rest_api_read"):
            data_fram=read(json_data,task_id,run_id,paths_data,text_file_path,iter_value)
            for df_chunk in data_fram :
                counter+=1
                records_in_chunk = len(df_chunk)
                # if target is database based
                if target["target_type"] not in ("csv_write", "parquet_write", "json_write",
                    "xml_write", "xlsx_write","aws_s3_write", "remote_server_write"):
                    value=write(json_data, df_chunk,counter,config_file_path,task_id,run_id,
                    paths_data,text_file_path,iter_value,session)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        task_failed(task_id,text_file_path,json_data,run_id,paths_data,iter_value)
                        return False
                else:
                    #if target is file and rest api needs to be added below as target
                    value,output_file_path,output_file_name=write(json_data,task_id,
                        run_id,iter_value, paths_data,text_file_path,df_chunk, counter,
                        local_temp_path)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        task_failed(task_id,text_file_path,json_data,run_id,paths_data,iter_value)
                        return False
        else:
            task_logger.info("only ingestion available currently")
        #implemnting file features like splitting, compression,encryption, files moving
        if target["target_type"] in ("csv_write", "parquet_write", "json_write",
            "xml_write", "xlsx_write","aws_s3_write", "remote_server_write"):
            process_file_split_and_compress(arguments,
            output_file_name, output_file_path, target)
        task_logger.info("Total records inserted into target:%s",total_records_inserted)
        audit(json_data, task_id,run_id,paths_data,'TRGT_RECORD_COUNT',total_records_inserted,
                iter_value)
    except Exception as error1:
        task_logger.exception(EXECUTE_QRY_MSG, str(error1))
        update_status_file(task_id,'FAILED',text_file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        send_mail('Failed', error1, 'normal_task_execution from engine_code')
        raise error1

def get_conn_subtype_type(config_path:str) -> dict:
    """reads the connection file and returns connection_subtype details as per
       connection name you pass it through the json"""
    try:
        with open(config_path,'r', encoding='utf-8') as jsonfile:
            task_logger.info("fetching connection details")
            json_data = json.load(jsonfile)
            task_logger.info("reading connection details completed")
            return json_data["connection_subtype"]
    except Exception as error:
        task_logger.exception("get_config_section() is %s.", str(error))
        send_mail('Failed', error, 'get_conn_subtype_type from engine_code')
        raise error

def bulk_task_execution(json_data,config_file_path,task_id,run_id,paths_data,
    text_file_path,iter_value, subtask_source_section, subtask_target_section,group_no,subtask_no,
    local_temp_path):
    """executes read and write scripts based on the bulk ingestion json"""
    try:
        arguments = {
            'json_data' : json_data,
			'config_file_path':config_file_path,
            'task_id' : task_id,
            'run_id' : run_id,
            'paths_data' : paths_data,
            'text_file_path' : text_file_path,
			'iter_value' :  iter_value,
            'group_no' : group_no,
            'subtask_no':subtask_no
            }
        src= subtask_source_section["connection_name"]
        tgt=subtask_target_section["connection_name"]
        source_sub_type = get_conn_subtype_type(config_file_path+src+JSON)
        target_sub_type = get_conn_subtype_type(config_file_path+tgt+JSON)
        homepath = os.path.expanduser(paths_data[
                "folder_path"])

        with open(r""+homepath+paths_data['src']+paths_data[
            "engine_path"]+'subtype_mapping.json',"r",encoding='utf-8') as subtype_mapjson:
            subtype_mapping = json.load(subtype_mapjson)
            if source_sub_type not in ("Local Server"):
                source=os.path.splitext(subtype_mapping[source_sub_type]["source"])[0]
            else:
                source_file_format = subtask_source_section["source_file_format"]
                source=os.path.splitext(subtype_mapping[source_sub_type]
                [source_file_format]["source"])[0]

            if target_sub_type not in ("Local Server"):
                target=os.path.splitext(subtype_mapping[target_sub_type]["target"])[0]
            else:
                target_file_format = subtask_target_section["target_file_format"]
                target=os.path.splitext(subtype_mapping[target_sub_type]
                [target_file_format]["target"])[0]

        read, write =read_write_imports(paths_data,json_data,source,target)
        #creates a session object for databases.
        if target in ("bulk_postgres_write","bulk_mysql_write",
        "bulk_snowflake_write","bulk_mssql_write","bulk_oracle_write"):
            session = begin_transaction(paths_data,json_data,config_file_path,target)
        #if source is database and AWS s3
        if source in ("bulk_postgres_read","bulk_mysql_read","bulk_snowflake_read",
            "bulk_mssql_read","bulk_aws_s3_read","bulk_remote_server_read","bulk_oracle_read"):
            data_fram = read(json_data,config_file_path,task_id,run_id,paths_data,
            text_file_path,iter_value,subtask_source_section,group_no,subtask_no)
            counter=0
            total_records_inserted = 0
            for df_chunk in data_fram:
                records_in_chunk = len(df_chunk)  # Count the records in the current chunk
                counter+=1
                if target != "rest_api_write":
                    #if target is database like mysql,snowflake,postgres, sql_server, oracle
                    if target not in ("bulk_csv_write", "bulk_parquet_write", "bulk_json_write",
                    "bulk_xml_write", "bulk_xlsx_write","bulk_aws_s3_write",
                    "bulk_remote_server_write"):
                        value=write(json_data, df_chunk,counter,config_file_path,task_id,run_id,
                        paths_data,text_file_path,iter_value,session,subtask_target_section,
                        group_no,subtask_no)
                        total_records_inserted += records_in_chunk
                        if value is False:
                            bulk_subtask_failed(task_id,json_data,run_id,paths_data,iter_value,
                            group_no,subtask_no)
                            return False
                    else:
                        #if target is in file based systems like AWS S3, remote server, local
                        value,output_file_path,output_file_name= write(json_data,task_id,run_id,
                        iter_value,paths_data,text_file_path,df_chunk, counter,local_temp_path,
                        subtask_target_section,group_no,subtask_no)
                        total_records_inserted += records_in_chunk
                        if value is False:
                            bulk_subtask_failed(task_id,json_data,run_id,paths_data,iter_value,
                            group_no,subtask_no)
                            return False
                else:
                    #if target is rest_API
                    value=write(json_data,df_chunk,task_id,run_id,paths_data,text_file_path,
                    iter_value,subtask_target_section,group_no,subtask_no)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        bulk_subtask_failed(task_id,json_data,run_id,paths_data,iter_value,
                        group_no,subtask_no)
                        return False
        #if source type is local server
        elif source in ("bulk_csv_read", "bulk_parquet_read", "bulk_json_read",
            "bulk_xml_read", "bulk_xlsx_read"):
            data_fram=read(json_data,task_id,run_id,paths_data,text_file_path,iter_value,
            subtask_source_section,group_no,subtask_no)
            for df_chunk in data_fram :
                records_in_chunk = len(df_chunk)  # Count the records in the current chunk
                counter+=1
                #if target is rest_API
                if target == "bulk_rest_api_write":
                    value=write(json_data,df_chunk,task_id,run_id,paths_data,text_file_path,
                    iter_value,subtask_target_section,
                    group_no,subtask_no)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        bulk_subtask_failed(task_id,json_data,run_id,paths_data,
                        iter_value,group_no,subtask_no)
                        return False
                #if target is database
                elif target not in ("bulk_csv_write", "bulk_parquet_write", "bulk_json_write",
                    "bulk_xml_write", "bulk_xlsx_write","bulk_aws_s3_write",
                    "bulk_remote_server_write"):
                    value=write(json_data,df_chunk,counter,config_file_path,task_id,run_id,
                    paths_data,text_file_path,iter_value,session,subtask_target_section,group_no,
                    subtask_no)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        bulk_subtask_failed(task_id,json_data,run_id,paths_data,iter_value,
                        group_no,subtask_no)
                        return False
                else:
                    #if target is file based
                    value,output_file_path,output_file_name= write(json_data,task_id,run_id,
                        iter_value,paths_data,text_file_path,df_chunk, counter,local_temp_path,
                        subtask_target_section,group_no,subtask_no)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        bulk_subtask_failed(task_id,json_data,run_id,paths_data,iter_value,
                        group_no,subtask_no)
                        return False
        # if source is rest API
        elif source in ("bulk_rest_api_read"):
            data_fram=read(json_data,task_id,run_id,paths_data,paths_data,text_file_path,iter_value,
            subtask_source_section,group_no,subtask_no)
            for df_chunk in data_fram :
                records_in_chunk = len(df_chunk)  # Count the records in the current chunk
                counter+=1
                # if target is database based
                if target not in ("bulk_csv_write", "bulk_parquet_write", "bulk_json_write",
                                                "bulk_xml_write", "bulk_xlsx_write"):
                    value=write(json_data, df_chunk,counter,config_file_path,task_id,run_id,
                    paths_data,text_file_path,iter_value,session,subtask_target_section,
                    group_no,subtask_no)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        bulk_subtask_failed(task_id,json_data,run_id,paths_data,iter_value,
                        group_no,subtask_no)
                        return False
                else:
                    #if target is file based
                    value,output_file_path,output_file_name= write(json_data,task_id,run_id,
                    iter_value,paths_data,text_file_path,df_chunk, counter,local_temp_path,
                    subtask_target_section,group_no,subtask_no)
                    total_records_inserted += records_in_chunk
                    if value is False:
                        bulk_subtask_failed(task_id,json_data,run_id,paths_data,iter_value,
                        group_no,subtask_no)
                        return False
        else:
            task_logger.info("only ingestion available currently")
        #implemnting file features like splitting, compression,encryption, files moving
        if target in ("bulk_csv_write","bulk_parquet_write","bulk_json_write",
            "bulk_xml_write","bulk_xlsx_write","bulk_aws_s3_write","bulk_remote_server_write"):
            process_file_split_and_compress(arguments,
            output_file_name, output_file_path, subtask_target_section,target_sub_type)
        task_logger.info("Total records inserted into target:%s",total_records_inserted)
        audit(json_data, task_id, run_id, paths_data, 'TRGT_RECORD_COUNT',total_records_inserted,
        iter_value, group_no, subtask_no)
        bulk_subtask_success(task_id,json_data,run_id,paths_data,iter_value,group_no,subtask_no)
        if target in ("bulk_postgres_write","bulk_mysql_write",
        "bulk_snowflake_write","bulk_mssql_write","bulk_oracle_write"):
            session.commit()
            task_logger.info("Transaction for subtask: %s commited successfully!",subtask_no)
    except Exception as error1:
        task_logger.exception(EXECUTE_QRY_MSG, str(error1))
        send_mail('Failed', error1, 'bulk_task_execution from engine_code')
        raise error1

def create_hierarchy_for_bulk_subtasks(sorted_data):
    """creates hirearchy for subtasks in bulk json as per the groups order"""
    group_wise_subtasks=[]
    for i in sorted_data:
        group_wise_subtasks.append({i['source']['task_group']:i['subtask']})
    result_dict = defaultdict(list)
    # Collect values for each key from the list of dictionaries
    for group in group_wise_subtasks:
        for key, value in group.items():
            result_dict[int(key)].append(value)
    # Convert the defaultdict to a list of dictionaries with the desired format
    result_list = [{key: values} for key, values in result_dict.items()]
    return result_list

def bulk_execution(paths_data, task_name, hierarchy, file_path, config_file_path,
    json_data, run_id, iter_value,local_temp_path):
    """Execute bulk ingestion process"""
    failed_groups = []
    for data in hierarchy:
        group_number = list(data.keys())[0]
        task_logger.info("Starting the bulk ingestion process for group: %s", group_number)
        audit_group(json_data, task_name, run_id, paths_data, iter_value, group_number)
        processes = start_bulk_processes(data[group_number], json_data,
        config_file_path, run_id, paths_data, file_path, iter_value, group_number,local_temp_path)
        wait_for_processes(processes)
        task_status = check_subtask_status(data[group_number], json_data["task_name"], paths_data)
        if any('FAILED' in status.values() for status in task_status):
            failed_groups.append(group_number)
            task_logger.warning("Execution for task_group:%s FAILED", group_number)
            audit(json_data, task_name, run_id, paths_data,
            'STATUS', 'FAILURE', iter_value, group_number)
            return failed_groups
        audit(json_data, task_name, run_id, paths_data,
        'STATUS', 'SUCCESS', iter_value, group_number)
        task_logger.info("Execution for task_group:%s COMPLETED", group_number)


def audit_group(json_data, task_name, run_id, paths_data, iter_value, group_number):
    """Audit group"""
    audit(json_data, task_name, run_id, paths_data,
    'STATUS', 'TRIGGERED', iter_value, group_number, None)

def start_bulk_processes(group, json_data, config_file_path, run_id,
    paths_data, file_path, iter_value, group_number,local_temp_path):
    """Start bulk processes"""
    processes = []
    for subtask in group:
        source, target = get_subtask_details(json_data["task"]["details"], subtask)
        task_logger.info("Starting the bulk ingestion process for subtask: %s", subtask)
        task_logger.info("Source:%s", source)
        task_logger.info("Target:%s", target)
        bulk_task = mp.Process(target=bulk_task_execution,
        args=[json_data, config_file_path, json_data["task_name"], run_id,
        paths_data, file_path, iter_value, source, target, group_number, subtask,local_temp_path],
        name='Process_' + str(subtask))
        processes.append(bulk_task)
        bulk_task.start()
    return processes

def wait_for_processes(processes):
    """Wait for processes to finish"""
    for process in processes:
        process.join()

def check_subtask_status(group, task_name, paths_data):
    """Check subtask status"""
    task_status = []
    for subtask in group:
        status = subtask_audit_status(task_name, subtask, paths_data)
        task_logger.info("Subtasks status:%s", status)
        if status and len(status) > 0:
            first_dict = status[0]
            audit_value_task = first_dict['audit_value']
            if audit_value_task == 'COMPLETED':
                task_status.append({subtask: 'COMPLETED'})
            elif audit_value_task != 'COMPLETED':
                task_status.append({subtask: 'FAILED'})
    return task_status

def bulk_restart(paths_data, mode,hierarchy,task_name,prev_task_run_id,prev_iter_value):
    """creates new hirerachy based on the mode of run"""
    group_result = prev_group_audit_status(task_name,prev_task_run_id,paths_data)
    if group_result != []:
        first_dict = group_result[0]
        group_no = first_dict['task_group']
        task_logger.info("group that failed in its previous execution:%s",group_no)
        new_iter_value = first_dict['iteration']
        iteration = new_iter_value + 1
    else:
        task_logger.info("since we don't have previous audit information in audit table" \
        "of the task related to its failure, we are starting it in BEGIN mode")
        mode = 'begin'
        iteration = prev_iter_value + 1
    if mode =='begin':
        task_logger.info("task execution running in BEGIN mode")
    elif mode =='skip':
        task_logger.info("task execution running in SKIP mode")
        result = [data for data in hierarchy if list(data.keys())[0] > group_no]
        hierarchy=result
        task_logger.info("hierarchy in skip:%s",hierarchy)
        if len(hierarchy)==0:
            task_logger.info("skipped, as the group %s is the last one to execute. \
            exiting out successfully.", group_no )
    elif mode =='normal':
        task_logger.info("task execution running in NORMAL mode")
        # get the list of sequence that failed in that
        result = [data for data in hierarchy if list(data.keys())[0] >= group_no]
        audit_status = prev_subtask_audit_status(task_name,prev_task_run_id,group_no,paths_data)
        new_subtask_list = [str(item['sequence']) for item in audit_status]
        task_logger.info("failed substaks list:%s for group no: %s:",new_subtask_list,group_no)
        new_result = [{group_no: new_subtask_list} if list(data.keys())[0] ==
         group_no else data for data in result]
        hierarchy=new_result
    return hierarchy,iteration

def get_subtask_details(subtask_section,subtask):
    """returns source and target of that particular subtask"""
    for i in subtask_section:
        if i['subtask']==subtask:
            return (i["source"],i["target"])
    raise ValueError(f"Subtask details not found for subtask: {subtask}")

def engine_type(paths_data, task_id,hierarchy,file_path,config_file_path:str, json_data,
    run_id,new_iter_value,local_temp_path):
    """based on the engine type it will call either seatunnel
     or pandas engine function to execute. """
    if json_data["job_execution"] == 'SeaTunnel':
        seatunnel_dir = paths_data["folder_path"]+ paths_data["seatunnel_folder_path"]
        home_path=os.path.expanduser(paths_data["folder_path"])
        prj_nm = json_data["project_name"]
        task_name = json_data["task_name"]
        seatunnel_log_path =str(home_path)+"/"+paths_data['local_repo']+paths_data[ \
            "programs"] + prj_nm +paths_data['seatunnel_log_path']
        setup_logger('seatunnel_task_logger', seatunnel_log_path + task_name +
         "_seatunnel_Log_" + str(run_id) + '_' + str(new_iter_value) + '.log')
        task_logger.info("For detailed seatunnel log check at the seatunnel log location,\
         seatunnel log location: %s",paths_data["seatunnel_log_path"])
        sys.path.insert(0, seatunnel_dir)
        seatunnel_main = importlib.import_module("seatunnel_main")
        failed_groups = seatunnel_main.seatunnel_execute(json_data, config_file_path,paths_data,
        hierarchy,task_id,run_id,new_iter_value)
    elif json_data["job_execution"] == 'Pandas':
        failed_groups = bulk_execution(paths_data, task_id,hierarchy,
        file_path,config_file_path, json_data, run_id,new_iter_value,local_temp_path)
    return failed_groups

def engine_main(prj_nm,task_id,paths_data,run_id,file_path,iter_value):
    """function consists of pre_checks,conversion,ingestion,post_checks, qc report"""
    try:
        task_logger.info("entered into engine_main")
        json_data = task_json_read(paths_data,task_id,prj_nm)
        if json_data["is_active"] == 'N':
            task_logger.warning("%s task is inactive, Process got Aborted!", task_id)
            sys.exit()
        else:
            config_file_path = os.path.expanduser(paths_data[
                    "folder_path"])+paths_data["config_path"]

        update_status_file(task_id,'STARTED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','STARTED',iter_value)
        local_temp_path = paths_data["folder_path"] + paths_data['local_repo'] + \
        paths_data['programs'] + json_data['project_name']+'/'  +paths_data['pipelines']+ \
        paths_data['tasks'] + paths_data['source_files']
        if json_data['task_type']=="Ingestion":
            source = json_data["task"]["source"]
            target = json_data["task"]["target"]
            if target['target_type'] in {'mysql_write','postgres_write','snowflake_write',
                                        'mssql_write', 'oracle_write'}:
                session = begin_transaction(paths_data,json_data,config_file_path)
            else:
                session = None
            json_checks = checks_mapping_read(paths_data)
            dq_scripts_path=os.path.expanduser(paths_data["folder_path"])+paths_data['src']+ \
            paths_data["dq_scripts_path"]
            sys.path.insert(0, dq_scripts_path)
            definitions_qc = importlib.import_module("definitions_qc")
            if 'data_quality' in json_data['task']:
                # Check if "type": "pre_check" exists in "data_quality"
                pre_check_exists = any(item.get('type') == 'pre_check' \
                for item in json_data['task']['data_quality'])

                # Check if "type": "post_check" exists in "data_quality"
                post_check_exists = any(item.get('type') == 'post_check' \
                for item in json_data['task']['data_quality'])
            else:
                pre_check_exists = False
                post_check_exists = False

            # Set values to true or false based on existence
            pre_check_enable = 'Y' if pre_check_exists else 'N'
            post_check_enable = 'Y' if post_check_exists else 'N'

            # Precheck script execution starts here
            if pre_check_enable == 'Y' and\
            source["source_type"] in ('csv_read','parquet_read','postgres_read','mysql_read',
            'snowflake_read','oracle_read','mssql_read','mssql_read','aws_s3_read',
            'remote_server_read','json_read','xml_read','xlsx_read'):
                pre_check, good_records_df = definitions_qc.qc_pre_check(prj_nm,json_data,
                json_checks,paths_data,config_file_path,task_id,run_id,file_path,iter_value)
            elif source["source_type"] == "csv_read" and \
            (pre_check_enable == 'N' and post_check_enable == 'N'):
                data_quality_features(json_data,definitions_qc)

            #qc report generation
            new_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
                "local_repo"]+paths_data["programs"]+prj_nm+\
            paths_data["qc_reports_path"]
            if pre_check_enable == 'Y' and post_check_enable == 'N':
                post_check = pd.DataFrame()
                definitions_qc.qc_report(pre_check,post_check,new_path,file_path,iter_value,
                            json_data,task_id,run_id,paths_data)

            if pre_check_enable == 'Y':
                result = precheck_status(paths_data,json_data,run_id)
                all_pass = all(item.get('audit_value', '') == 'PASS' for item in result)
                if not all_pass:
                    task_logger.info("Qc has been failed in pre_check level")
                    task_logger.warning("Process Aborted")
                    audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
                    update_status_file(task_id,'FAILED',file_path)
                    sys.exit()
                _, write =read_write_imports(paths_data,json_data)
                if target["target_type"] not in ("csv_write", "parquet_write", "json_write",
                                "xml_write", "xlsx_write","aws_s3_write", "remote_server_write"):
                    value=write(json_data, good_records_df,1,config_file_path,task_id,run_id,
                    paths_data,file_path,iter_value,session)
                    if value is False:
                        task_failed(task_id,file_path,json_data,run_id,paths_data,iter_value)
                        return False
                    if value is True:
                        task_success(task_id,file_path,json_data,run_id,paths_data,iter_value)
                        return False
                else:
                    value,output_file_path,output_file_name =write(json_data, task_id, run_id,
                    iter_value, paths_data, file_path, good_records_df,1, local_temp_path)
                    if value is False:
                        task_failed(task_id,file_path,json_data,run_id,paths_data,iter_value)
                        return False
                arguments = {
                    'json_data' : json_data,
                    'config_file_path':config_file_path,
                    'task_id' : task_id,
                    'run_id' : run_id,
                    'paths_data' : paths_data,
                    'text_file_path' : file_path,
                    'iter_value' :  iter_value,
                    'group_no' : 0,
                    'subtask_no':0
                    }
                #implemnting file features like splitting, compression,encryption, files moving
                if target["target_type"] in ("csv_write", "parquet_write", "json_write",
                    "xml_write", "xlsx_write","aws_s3_write", "remote_server_write"):
                    process_file_split_and_compress(arguments,
                    output_file_name, output_file_path, target)
                task_logger.info("Total records inserted into target:%s",good_records_df.shape[0])
                audit(json_data, task_id,run_id,paths_data,'TRGT_RECORD_COUNT',
                good_records_df.shape[0],iter_value)
            else:
                # ingestion execution starts here
                normal_task_execution(json_data,config_file_path,task_id,run_id,paths_data,
                file_path,iter_value,session,local_temp_path)

            # postcheck script execution starts here
            if target["target_type"] in ('csv_write','parquet_write','aws_s3_write',
            'remote_server_write','json_write','xml_write','xlsx_write') and \
            post_check_enable == 'Y':
                # post check code
                post_check=definitions_qc.qc_post_check(prj_nm,json_data, json_checks,
                paths_data,config_file_path,task_id,run_id,file_path,iter_value,None)
            elif target["target_type"] in ('postgres_write' ,'mysql_write',
                "snowflake_write",'mssql_write', 'oracle_write') and \
            post_check_enable == 'Y':
                post_check=definitions_qc.qc_post_check(prj_nm,json_data, json_checks,
                paths_data,config_file_path,task_id,run_id,file_path,iter_value,session)
            #qc report generation
            new_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
                "local_repo"]+paths_data["programs"]+prj_nm+\
            paths_data["qc_reports_path"]
            if pre_check_enable == 'N' and post_check_enable == 'Y':
                pre_check = pd.DataFrame()
                definitions_qc.qc_report(pre_check,post_check,new_path,file_path,iter_value,
                            json_data,task_id,run_id,paths_data)
            elif pre_check_enable == 'Y' and post_check_enable == 'Y':
                definitions_qc.qc_report(pre_check,post_check,new_path,file_path,iter_value,
                            json_data,task_id,run_id,paths_data)
            #session related script execution starts here
            if target['target_type'] in {'mysql_write',
                'snowflake_write','postgres_write', 'csv_write',
                'mssql_write','oracle_write',"remote_server_write",
                'aws_s3_write'} :
                if post_check_enable == 'Y':
                    result = postcheck_status(paths_data,json_data,run_id)
                    # Checking if all results are 'PASS'
                    all_pass = all(item.get('audit_value', '') == 'PASS' for item in result)
                    if all_pass:
                        if target['target_type'] in {'mysql_write',
                        'snowflake_write','postgres_write','mssql_write','oracle_write'}:
                            session.commit()
                            task_logger.info("Transaction commited successfully!")
                    else:
                        if target['target_type'] in {'csv_write'}:
                            folder_path = os.path.expanduser(paths_data['folder_path'])
                            tgt_file_name = target['file_name']
                            inp_file_names = [os.path.join(folder_path+paths_data["local_repo"
                            ]+paths_data['programs']+prj_nm+paths_data['target_files_path']
                            +tgt_file_name)]
                            task_logger.info(inp_file_names)
                            out_zip_file = os.path.join(folder_path+paths_data["local_repo"]+
                            paths_data['programs']+prj_nm+paths_data['archive_path']+'target/'+
                            str(json_data['id'])+'_'+ json_data['task_name']+'.zip')
                            task_logger.info(out_zip_file)
                            archive_files(inp_file_names, out_zip_file)
                            os.remove(os.path.join(folder_path+paths_data["local_repo"]+
                            paths_data['programs']+prj_nm+paths_data['target_files_path']+
                            tgt_file_name))
                        task_logger.warning("Transaction Rolled back due to Some of the dq" \
                        " checks got failed on target level")
                        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
                        update_status_file(task_id,'FAILED',file_path)
                        sys.exit()
                else:
                    if target['target_type'] not in {'csv_write','aws_s3_write',
                        'remote_server_write','parquet_write','json_write',
                        'xml_write','xlsx_write'}:
                        session.commit()
                        task_logger.info("Transaction commited successfully!")
            task_logger.info(TASK_LOG,task_id)
            update_status_file(task_id,'SUCCESS',file_path)
            audit(json_data, task_id,run_id,paths_data,'STATUS','COMPLETED',iter_value)
        elif json_data['task_type']=="SQL Execution":
            value = restart_sql_query(prj_nm, paths_data, task_id, json_data, run_id,iter_value)
            if value :
                task_logger.info(TASK_LOG,task_id)
                update_status_file(task_id,'SUCCESS',file_path)
            else:
                task_logger.info('Task %s Execution Failed',task_id)
                update_status_file(task_id,'FAILED',file_path)
        elif json_data['task_type']=="Bulk Ingestion":
            if json_data['source_type'] in "Files" and json_data['target_type'] in "Files":
                ingestion_path=os.path.expanduser(paths_data["folder_path"])+paths_data['src']+\
                    paths_data["ingestion_path"]
                sys.path.insert(0, ingestion_path)
                bulk_file_copy = importlib.import_module("bulk_file_copy")
                audit(json_data, task_id,run_id,paths_data,'STATUS','STARTED',iter_value)
                value,source_count,copied_count = bulk_file_copy.copy_files(json_data,
                config_file_path,run_id,paths_data)
                src = json_data["task"]["details"][0]["source"]
                operation = None if "operation" not in src or src["operation"] in {None,"None",
                "none",""} else src["operation"].upper()
                audit(json_data,task_id,run_id,paths_data,'OPERATION',operation,iter_value)
                audit(json_data,task_id,run_id,paths_data,'SRC_FILES_COUNT',source_count,iter_value)
                audit(json_data,task_id,run_id,paths_data,'TGT_FILES_COUNT',copied_count,iter_value)
                if value is False:
                    update_status_file(task_id,'FAILED',file_path)
                    audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
                    return False
                if value is True:
                    update_status_file(task_id,'SUCCESS',file_path)
                    audit(json_data, task_id,run_id,paths_data,'STATUS','COMPLETED',iter_value)
                    return False
            else:
                task_logger.info("entered in bulk ingestion")
                restart_mode = json_data['restartability']
                sorted_data = sorted(json_data["task"]["details"], key=lambda x: (
                int(x['source']['task_group'])))
                #creating hirearachy based on inputs
                hierarchy=create_hierarchy_for_bulk_subtasks(sorted_data)
                task_logger.info("subtasks hierarchy from input task json:%s", hierarchy)

                prev_task_level_status = latest_audit_status(json_data["task_name"],paths_data)
                task_logger.info("tasks previous execution status :%s", prev_task_level_status)
                if prev_task_level_status and len(prev_task_level_status) > 0:
                    # Check if the result is not empty and has at least one element
                    prev_audit_value = prev_task_level_status[0]
                    task_level_audit_value = prev_audit_value['audit_value']
                    prev_task_run_id = prev_audit_value['run_id']
                    prev_iter_value = prev_audit_value['iteration']
                    if task_level_audit_value == 'COMPLETED':
                        task_logger.info("previous task execution completed successfully,"\
                        " so executing in without restart mode")
                        new_iter_value = iter_value
                        failed_groups = engine_type(paths_data, task_id,hierarchy,
                        file_path,config_file_path,json_data,run_id,new_iter_value,local_temp_path)
                    else:
                        task_logger.info("previous task execution was not completed "\
                        "successfully, so executing in restart mode")
                        restart_hierarchy,new_iter_value = bulk_restart(paths_data,restart_mode,
                        hierarchy,task_id,prev_task_run_id,prev_iter_value)
                        task_logger.info("new subtasks hierarchy in restart mode:%s",
                            restart_hierarchy)
                        failed_groups = engine_type(paths_data,task_id,restart_hierarchy,
                        file_path,config_file_path,json_data,run_id,new_iter_value,local_temp_path)
                else:
                    #fresh run
                    task_logger.info("there is no previous task execution, "\
                    "so executing  a fresh run without restart mode")
                    task_logger.info("subtasks hierarchy:%s", hierarchy)
                    failed_groups = engine_type(paths_data,task_id, hierarchy,
                    file_path,config_file_path, json_data, run_id,iter_value,local_temp_path)

                iter_value_to_use = new_iter_value if prev_task_level_status else iter_value
                status = 'COMPLETED' if not failed_groups else 'FAILED'
                update_status_file(task_id,'SUCCESS' if not failed_groups else 'FAILED',
                file_path)
                audit(json_data,task_id,run_id, paths_data,'STATUS',status,iter_value_to_use)
                task_logger.info(TASK_LOG, task_id)
        elif json_data['task_type']=="Transformation":
            task_logger.info("entered in transformation")
            arguments = {
            'json_data' : json_data,
            'config_file_path':config_file_path,
            'task_id' : task_id,
            'run_id' : run_id,
            'paths_data' : paths_data,
            'text_file_path' : file_path,
            'iter_value' :  iter_value
            }
            transform_path=os.path.expanduser(paths_data["folder_path"])+paths_data['src']+ \
            paths_data["transformation_path"]+json_data["job_execution"]+"/"
            sys.path.insert(0, transform_path)
            transform = importlib.import_module("transform")
            transform.transform_flow(arguments)
            update_status_file(task_id,'SUCCESS',file_path)
            audit(json_data, task_id,run_id,paths_data,'STATUS','COMPLETED',iter_value)
    except Exception as error:
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        update_status_file(task_id,'FAILED',file_path)
        task_logger.warning(FAIL_LOG_STATEMENT, task_id)
        task_logger.exception("error in  %s.", str(error))
        send_mail('Failed', error, 'engine_main from engine_code')
        raise error
