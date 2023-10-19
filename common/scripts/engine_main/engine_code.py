""" importing modules """
import json
import logging
import sys
import os
from datetime import datetime
import zipfile
import subprocess
import importlib
import requests
import pandas as pd
from sqlalchemy.orm import sessionmaker
import mysql.connector

task_logger = logging.getLogger('task_logger')
FAIL_LOG_STATEMENT = "%s got failed engine"
TASK_LOG = 'Task %s Execution Completed'

def write_to_txt1(task_id,status,file_path):
    """Generates a text file with statuses for orchestration"""
    try:
        is_exist = os.path.exists(file_path)
        if is_exist is True:
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
        else:
            task_logger.error("pipeline txt file does not exist")
    except pd.errors.EmptyDataError as error:
        task_logger.error("The file is empty or has no columns to parse.")
        raise error
    except Exception as error:
        task_logger.exception("write_to_txt: %s.", str(error))
        raise error

def audit(json_data, task_name,run_id,status,value,itervalue,seq_no=None):
    """ create audit json file and audits event records into it"""
    try:
        url = "http://localhost:8080/api/audit"
        audit_data = [{
                    "pipeline_id": json_data["pipeline_id"],
                    "task/pipeline_name": task_name,
                    "run_id": run_id,
                    "sequence": seq_no,
                    "iteration": itervalue,
                    "audit_type": status,
                    "audit_value": value,
                    "process_dttm" : datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                }]
        response = requests.post(url, json=audit_data, timeout=60)
        task_logger.info("audit status code:%s",response.status_code)
    except Exception as error:
        task_logger.exception("error in audit %s.", str(error))
        raise error

def download_audit_conn_json(path_data:str):
    """Function to download audit config JSON from Github to server"""
    try:
        # print("downloading audit_conn.json from Github started..")
        audit_conn_json_path= os.path.expanduser(path_data["folder_path"])
        # print("path:%s",audit_conn_json_path)
        path_check = audit_conn_json_path+path_data["mysql_audit_json_conn_nm"]
        is_exist = os.path.exists(path_check)
        # print('audit_conn.json file exists: %s', is_exist)
        if is_exist is False:
            git_url=path_data["GH_audit_conn_json_path"]
            response1 = requests.get(git_url,timeout=60)
            if response1.status_code != 200:
                logging.error("The audit config json file %s DOES NOT exists in the GITHUB "
                "repository \n PROCESS got ABORTED",path_data["mysql_audit_json_conn_nm"])
                sys.exit()
            else:
                dwn_json = ['curl', '-o',audit_conn_json_path+path_data["mysql_audit_json_conn_nm"],
                path_data["GH_audit_conn_json_path"]]
                subprocess.call(dwn_json)
    except Exception as error1:
        logging.exception("error in download_pipeline_json %s.", str(error1))
        raise error1

def task_json_read(paths_data,task_id,prj_nm):
    """function to read task json"""
    try:
        with open(r""+os.path.expanduser(paths_data["folder_path"])+paths_data["Program"]+prj_nm+\
        paths_data["task_json_path"]+task_id+".json","r",encoding='utf-8') as jsonfile:
            task_logger.info("reading TASK JSON data started %s",task_id)
            json_data = json.load(jsonfile)
            task_logger.info("reading TASK JSON data completed")
        return json_data
    except Exception as error:
        task_logger.exception("error in task_json_read %s.", str(error))
        raise error

def checks_mapping_read(paths_data):
    """function to read checks_mapping json"""
    try:
        with open(r""+os.path.expanduser(paths_data["folder_path"])+paths_data["dq_scripts_path"]+\
        "checks_mapping.json","r",encoding='utf-8') as json_data_new:
            task_logger.info("reading checks mapping json data started")
            json_checks = json.load(json_data_new)
            task_logger.info("reading checks mapping data completed")
        return json_checks
    except Exception as error:
        task_logger.exception("error in checks_mapping_read %s.", str(error))
        raise error

def read_write_imports(paths_data,json_data):
    """function for importing read and write functions"""
    try:
        source = json_data["task"]["source"]
        target = json_data["task"]["target"]
        py_scripts_path=os.path.expanduser(paths_data["folder_path"])+paths_data["ingestion_path"]
        #task_logger.info(py_scripts_path)
        sys.path.insert(0, py_scripts_path)
        task_logger.info("read imports started")
        module_name = source["source_type"]
        task_logger.info("write imports started")
        module_name1 = target["target_type"]
        module = importlib.import_module(module_name)
        module1 = importlib.import_module(module_name1)
        read = getattr(module, "read")
        write = getattr(module1, "write")
        return read,write
    except Exception as error:
        task_logger.exception("error in read_write_imports %s.", str(error))
        raise error

def task_failed(task_id,file_path,json_data,run_id,iter_value):
    """function to log and audit if task is failed"""
    try:
        write_to_txt1(task_id,'FAILED',file_path)
        audit(json_data,task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.warning(FAIL_LOG_STATEMENT, task_id)
    except Exception as error:
        task_logger.exception("error in task_failed %s.", str(error))
        raise error

def task_success(task_id,file_path,json_data,run_id,iter_value):
    """function to log and audit if task is success"""
    try:
        write_to_txt1(task_id,'SUCCESS',file_path)
        audit(json_data,task_id,run_id,'STATUS','COMPLETED',
                iter_value)
        task_logger.info(TASK_LOG,task_id)
    except Exception as error:
        task_logger.exception("error in task_success %s.", str(error))
        raise error

def data_quality_features(json_data,definitions_qc):
    """function for executing data quality features based on pre and post checks"""
    try:
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
        raise error

def postcheck_status(paths_json_data,task_json_data,run_id):
    '''function to check whether all the checks has been passed
    or failed at target level'''
    try:
        download_audit_conn_json(paths_json_data)
        utility_ing_path=paths_json_data["folder_path"]+paths_json_data[
            "ingestion_path"]
        sys.path.insert(0, utility_ing_path)
        module = importlib.import_module("utility")
        decrypt = getattr(module, "decrypt")
        get_config_section = getattr(module, "get_config_section")
        config_file_path = os.path.expanduser(paths_json_data["folder_path"])+\
        paths_json_data["mysql_audit_json_conn_nm"]
        conn_details = get_config_section(config_file_path)
        pass_word = decrypt(conn_details["password"])
        mydb = mysql.connector.connect(
            host=conn_details["hostname"],
            user=conn_details["username"],
            password=pass_word,
            database=conn_details["database"])
        # Create cursor object
        cursor = mydb.cursor()
        seq_nos = [item['seq_no'] for item in task_json_data['task'][
            'data_quality'] if item['type'] == 'post_check']
        query = f"SELECT audit_value FROM config.tbl_etl_audit WHERE\
        run_id = '{run_id}' AND audit_type = 'RESULT' AND sequence IN ({','.join(seq_nos)});"
        cursor.execute(query)
        result = cursor.fetchall()
        # Close cursor and database connection
        cursor.close()
        mydb.close()
        return result
    except mysql.connector.Error as err:
        if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
            task_logger.error("Something is wrong with audit config username or password")
        elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            task_logger.error("Database does not exist")
        else:
            task_logger.error("Error:%s ", err)
        raise err
    except Exception as error1:
        task_logger.exception("execute_query() is %s.", str(error1))
        raise error1

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
    finally:
        zipf.close()
        task_logger.info("Archiving file end time: %s",
                         datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        task_logger.info("Archiving of file ended")

def begin_transaction(paths_data,json_data,config_file_path):
    '''function to start the transaction'''
    connections_path=os.path.expanduser(paths_data["folder_path"])+paths_data["ingestion_path"]
    sys.path.insert(0, connections_path)
    module = importlib.import_module("connections")
    target = json_data['task']['target']
    if target['target_type']=='mysql_write':
        establish_conn_for_mysql = getattr(module, "establish_conn_for_mysql")
        engine,_ = establish_conn_for_mysql(json_data,'target',config_file_path)
    elif target['target_type']=='snowflake_write':
        establish_conn_for_snowflake = getattr(module, "establish_conn_for_snowflake")
        engine,_ = establish_conn_for_snowflake(json_data,'target',config_file_path)
    elif target['target_type']=='postgres_write':
        establish_conn_for_postgres = getattr(module, "establish_conn_for_postgres")
        engine,_ = establish_conn_for_postgres(json_data,'target',config_file_path)
    elif target['target_type']=='sqlserver_write':
        establish_conn_for_sqlserver = getattr(module, "establish_conn_for_sqlserver")
        engine,_ = establish_conn_for_sqlserver(json_data,'target',config_file_path)
    # Create a session object
    ssession = sessionmaker(bind=engine)
    session = ssession()
    # Start a transaction
    session.begin()
    task_logger.info("=================================================================")
    task_logger.info("Transaction Started")
    return session

def engine_main(prj_nm,task_id,paths_data,run_id,file_path,iter_value):
    """function consists of pre_checks,conversion,ingestion,post_checks, qc report"""
    try:
        task_logger.info("entered into engine_main")
        json_data = task_json_read(paths_data,task_id,prj_nm)
        write_to_txt1(task_id,'STARTED',file_path)
        audit(json_data, task_id,run_id,'STATUS','STARTED',iter_value)
        json_checks = checks_mapping_read(paths_data)
        config_file_path = os.path.expanduser(paths_data["folder_path"])+paths_data["config_path"]
        dq_scripts_path=os.path.expanduser(paths_data["folder_path"])+paths_data["dq_scripts_path"]
        sys.path.insert(0, dq_scripts_path)
        definitions_qc = importlib.import_module("definitions_qc")
        dq_execution = json_data["task"]["data_quality_execution"]
        source = json_data["task"]["source"]
        target = json_data["task"]["target"]
        if target['target_type'] in {'mysql_write','postgres_write','snowflake_write',
                                     'sqlserver_write'}:
            session = begin_transaction(paths_data,json_data,config_file_path)

        # Precheck script execution starts here
        if dq_execution["pre_check_enable"] == 'Y' and\
        source["source_type"] in ('csv_read','postgres_read','mysql_read',
        'snowflake_read','mssql_read','sqlserver_read','aws_s3_read'):
            pre_check = definitions_qc.qc_pre_check(prj_nm,json_data,json_checks,
            paths_data,config_file_path,task_id,run_id,file_path,iter_value)
        elif source["source_type"] == "csv_read" and \
        (dq_execution['pre_check_enable'] == 'N' and \
        dq_execution['post_check_enable'] == 'N'):
            data_quality_features(json_data,definitions_qc)

        # ingestion execution starts here
        read, write =read_write_imports(paths_data,json_data)
        if source["source_type"] in ("postgres_read","mysql_read",
        "snowflake_read","sqlserver_read", "aws_s3_read"):
            data_fram = read(json_data,config_file_path,task_id,run_id,paths_data,
            file_path,iter_value)
            counter=0
            for i in data_fram :
                counter+=1
                if target["target_type"] != "csv_write":
                    value=write(json_data, i,counter,config_file_path,task_id,run_id,
                    paths_data,file_path,iter_value,session)
                    if value is False:
                        task_failed(task_id,file_path,json_data,run_id,iter_value)
                        return False
                    if value is True:
                        task_success(task_id,file_path,json_data,run_id,iter_value)
                        return False
                else:
                    value=write(json_data, i,counter)
                    if value is False:
                        task_failed(task_id,file_path,json_data,run_id,iter_value)
                        return False
        elif source["source_type"] == "csv_read":
            data_fram=read(json_data,task_id,run_id,paths_data,file_path,iter_value)
            counter=0
            for i in data_fram :
                counter+=1
                if target["target_type"] != "csv_write":
                    value=write(json_data, i,counter,config_file_path,task_id,run_id,
                    paths_data,file_path,iter_value,session)
                    if value is False:
                        task_failed(task_id,file_path,json_data,run_id,iter_value)
                        return False
                    if value is True:
                        task_success(task_id,file_path,json_data,run_id,iter_value)
                        return False
                else:
                    value=write(json_data, i,counter)
                    if value is False:
                        task_failed(task_id,file_path,json_data,run_id,iter_value)
                        return False
        elif source["source_type"] in ("csvfile_read"
            ,"json_read" ,"xml_read","parquet_read","excel_read"):
            data_fram=read(json_data,task_id,run_id,paths_data,file_path,iter_value)
            counter=0
            for i in data_fram :
                # task_logger.info(i)
                counter+=1
                if target["target_type"] == "csvfile_write":
                    value=write(json_data, i,counter)
                    if value=='Fail':
                        task_failed(task_id,file_path,json_data,run_id,iter_value)
                        return False
                elif target["target_type"] == "aws_s3_write":
                    value=write(json_data, i,config_file_path,task_id,run_id,
                    paths_data,file_path,iter_value)
                    if value=='Fail':
                        task_failed(task_id,file_path,json_data,run_id,iter_value)
                        return False
                else:
                    value=write(json_data, i)
        else:
            task_logger.info("only ingestion available currently")

        # postcheck script execution starts here
        if target["target_type"] in ('csv_write') and \
        dq_execution["post_check_enable"] == 'Y':
            # post check code
            post_check=definitions_qc.qc_post_check(prj_nm,json_data, json_checks,paths_data,
            config_file_path,task_id,run_id,file_path,iter_value,None)
        elif target["target_type"] in ('postgres_write' ,'mysql_write',
            "snowflake_write",'sqlserver_write' ) and \
        dq_execution["post_check_enable"] == 'Y':
            post_check=definitions_qc.qc_post_check(prj_nm,json_data, json_checks,paths_data,
            config_file_path,task_id,run_id,file_path,iter_value,session)
        #qc report generation
        new_path=os.path.expanduser(paths_data["folder_path"])+paths_data["Program"]+prj_nm+\
        paths_data["qc_reports_path"]
        if dq_execution["pre_check_enable"] == 'Y' and dq_execution["post_check_enable"] == 'N':
            post_check = pd.DataFrame()
            definitions_qc.qc_report(pre_check,post_check,new_path,file_path,
                         json_data,task_id,run_id,iter_value)
        elif dq_execution["pre_check_enable"] == 'N' and dq_execution["post_check_enable"] == 'Y':
            pre_check = pd.DataFrame()
            definitions_qc.qc_report(pre_check,post_check,new_path,file_path,
                         json_data,task_id,run_id,iter_value)
        elif dq_execution["pre_check_enable"] == 'Y' and dq_execution["post_check_enable"] == 'Y':
            definitions_qc.qc_report(pre_check,post_check,new_path,file_path,
                         json_data,task_id,run_id,iter_value)
        #session related script execution starts here
        if target['target_type'] in {'mysql_write',
            'snowflake_write','postgres_write', 'csv_write','sqlserver_write'}:
            if dq_execution['post_check_enable'] == 'Y':
                result = postcheck_status(paths_data,json_data,run_id)
                # Checking if all results are 'PASS'
                all_pass = all(item[0] == 'PASS' for item in result)
                if all_pass:
                    if target['target_type'] in {'mysql_write',
                    'snowflake_write','postgres_write','sqlserver_write'}:
                        session.commit()
                        task_logger.info("Transaction commited successfully!")
                else:
                    if target['target_type'] in {'csv_write'}:
                        folder_path = os.path.expanduser(paths_data['folder_path'])
                        tgt_file_name = target['file_name']
                        inp_file_names = [os.path.join(folder_path+paths_data[
                        'Program']+prj_nm+paths_data['target_files_path']+tgt_file_name)]
                        task_logger.info(inp_file_names)
                        out_zip_file = os.path.join(folder_path+paths_data[
                        'Program']+prj_nm+paths_data['archive_path']+'target/'+str(
                        json_data['id'])+'_'+ json_data['task_name']+'.zip')
                        task_logger.info(out_zip_file)
                        archive_files(inp_file_names, out_zip_file)
                        os.remove(os.path.join(folder_path+paths_data[
                        'Program']+prj_nm+paths_data['target_files_path']+tgt_file_name))
                    task_logger.warning("Transaction Rolled back due to Some of the dq" \
                              "checks got failed on target level")
                    audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
                    write_to_txt1(task_id,'FAILED',file_path)
                    sys.exit()
            else:
                if target['target_type'] not in {'csv_write'}:
                    session.commit()
                    task_logger.info("Transaction commited successfully!")
        task_logger.info(TASK_LOG,task_id)
        write_to_txt1(task_id,'SUCCESS',file_path)
        audit(json_data, task_id,run_id,'STATUS','COMPLETED',iter_value)
    except Exception as error:
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        write_to_txt1(task_id,'FAILED',file_path)
        task_logger.warning(FAIL_LOG_STATEMENT, task_id)
        task_logger.exception("error in  %s.", str(error))
        raise error
