""" importing modules """
import json
import logging
import sys
import os
from datetime import datetime
import requests
import pandas as pd

log2 = logging.getLogger('log2')
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
            return None
        else:
            log2.error("pipeline txt file does not exist")
            return None
    except Exception as error:
        log2.exception("write_to_txt: %s.", str(error))
        raise error

def audit(json_data, task_name,run_id,status,value,itervalue):
    """ create audit json file and audits event records into it"""    
    try:
        url = "http://localhost:8080/api/audit"
        audit_data = [{
                    "pipeline_id": json_data["pipeline_id"],
                    "task/pipeline_name": task_name,
                    "run_id": run_id,
                    "iteration": itervalue,
                    "audit_type": status,
                    "audit_value": value,
                    "process_dttm" : datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                }]
        response = requests.post(url, json=audit_data, timeout=60)
        log2.info("audit status code:%s",response.status_code)
    except Exception as error:
        log2.exception("error in audit %s.", str(error))
        raise error

def engine_main(prj_nm,task_id,paths_data,run_id,file_path,iter_value):
    """function consists of pre_checks,conversion,ingestion,post_checks, qc report"""
    log2.info("entered into engine_main")
    config_file_path = paths_data["folder_path"]+paths_data["config_path"]
    dq_scripts_path=paths_data["folder_path"]+paths_data["dq_scripts_path"]
    sys.path.insert(0, dq_scripts_path)
    import definitions_qc as dq
    try:
        with open(r""+paths_data["folder_path"]+paths_data["Program"]+prj_nm+\
        paths_data["task_json_path"]+task_id+".json","r",encoding='utf-8') as jsonfile:
            log2.info("reading TASK JSON data started %s",task_id)
            json_data = json.load(jsonfile)
            log2.info("reading TASK JSON data completed")
            write_to_txt1(task_id,'STARTED',file_path)
            audit(json_data, task_id,run_id,'STATUS','STARTED',iter_value)
    except Exception as error:
        log2.exception("error in reading json %s.", str(error))
        raise error
    try:
        with open(r""+paths_data["folder_path"]+paths_data["dq_scripts_path"]+\
        "checks_mapping.json","r",encoding='utf-8') as json_data_new:
            log2.info("reading checks mapping json data started")
            json_checks = json.load(json_data_new)
            log2.info("reading checks mapping data completed")

        dq_scripts_path=paths_data["folder_path"]+paths_data["dq_scripts_path"]
        sys.path.insert(0, dq_scripts_path)
        # from definitions_qc import auto_correction,data_masking,data_encryption

        # Precheck script execution starts here
        if json_data["task"]["data_quality_execution"]["pre_check_enable"] == 'Y' and\
        (json_data["task"]["source"]["source_type"] == 'csv_read' or\
        json_data["task"]["source"]["source_type"] == 'postgres_read' or\
        json_data["task"]["source"]["source_type"] == 'mysql_read' or\
	    json_data["task"]["source"]["source_type"] == 'snowflake_read'or\
        json_data["task"]["source"]["source_type"] == 'mssql_read'):
            pre_check = dq.qc_pre_check(prj_nm,json_data,json_checks,paths_data,config_file_path,
            task_id,run_id,file_path,iter_value)
        # elif json_data["task"]["source"]["source_type"] == "csv_read" and \
        # (json_data['task']['data_quality_execution']['pre_check_enable'] == 'N' and \
        # json_data['task']['data_quality_execution']['post_check_enable'] == 'N'):
        #     if json_data['task']['data_quality_features']['dq_auto_correction_required'] == 'Y' \
        #     and json_data['task']['data_quality_features']['data_masking_required'] == 'Y':
        #         auto_correction(json_data)
        #         data_masking(json_data)
        #     elif json_data['task']['data_quality_features']['dq_auto_correction_required'] == 'Y' \
        #     and json_data['task']['data_quality_features']['data_encryption_required'] == 'Y':
        #         auto_correction(json_data)
        #         data_encryption(json_data)
        #     elif json_data['task']['data_quality_features']['dq_auto_correction_required'] == 'Y' \
        #     and json_data['task']['data_quality_features']['data_masking_required'] == 'Y' \
        #     and json_data['task']['data_quality_features']['data_encryption_required'] == 'Y':
        #         auto_correction(json_data)
        #         data_masking(json_data)
        #         data_encryption(json_data)
        #     elif json_data['task']['data_quality_features']['dq_auto_correction_required'] == 'Y':
        #         auto_correction(json_data)
        #     elif json_data['task']['data_quality_features']['data_masking_required'] == 'Y':
        #         data_masking(json_data)
        #     elif json_data['task']['data_quality_features']['data_encryption_required'] == 'Y':
        #         data_encryption(json_data)

        py_scripts_path=paths_data["folder_path"]+paths_data["ingestion_path"]
        #log2.info(py_scripts_path)
        sys.path.insert(0, py_scripts_path)
        #file conversion code and ingestion code
        log2.info("read imports started")
        #file conversion code and ingestion code
        if json_data["task"]["source"]["source_type"] == "csv_read":
            from csv_read import read
        elif json_data["task"]["source"]["source_type"] == "postgres_read":
            from postgres_read import read
        elif json_data["task"]["source"]["source_type"] == "snowflake_read":
            from snowflake_read import read
        elif json_data["task"]["source"]["source_type"] == "mysql_read":
            from mysql_read import read
        elif json_data["task"]["source"]["source_type"] == "csvfile_read":
            from csvfile_read import read
        elif json_data["task"]["source"]["source_type"] == "parquetfile_read":
            from parquet_read import read
        elif json_data["task"]["source"]["source_type"] == "excelfile_read":
            from excel_read import read
        elif json_data["task"]["source"]["source_type"] == "jsonfile_read":
            from json_read import read
        elif json_data["task"]["source"]["source_type"] == "xmlfile_read":
            from xml_read import read
        elif json_data["task"]["source"]["source_type"] == "textfile_read":
            from text_read import read
        elif json_data["task"]["source"]["source_type"] == "sqlserver_read":
            from sqlserver_read import read


        if json_data["task"]["target"]["target_type"] == "postgres_write":
            from postgres_write import write
        elif json_data["task"]["target"]["target_type"] == "mysql_write":
            from mysql_write import write
        elif json_data["task"]["target"]["target_type"] == "snowflake_write":
            from snowflake_write import write
        elif json_data["task"]["target"]["target_type"] == "parquetfile_write":
            from parquet_write import write
        elif json_data["task"]["target"]["target_type"] == "csv_write":
            from csv_write import write
        elif json_data["task"]["target"]["target_type"] == "csvfile_write":
            from csvfile_write import write
        elif json_data["task"]["target"]["target_type"] == "excelfile_write":
            from excel_write import write
        elif json_data["task"]["target"]["target_type"] == "jsonfile_write":
            from json_write import write
        elif json_data["task"]["target"]["target_type"] == "xmlfile_write":
            from xml_write import write
        elif json_data["task"]["target"]["target_type"] == "textfile_write":
            from text_write import write
        elif json_data["task"]["target"]["target_type"] == "sqlserver_write":
            from sqlserver_write import write
        elif json_data["task"]["target"]["target_type"] == "s3_write":
            from s3_write import write


        # main script execution starts here
        if json_data["task"]["source"]["source_type"] == "postgres_read" or \
            json_data["task"]["source"]["source_type"] == "mysql_read" or\
	        json_data["task"]["source"]["source_type"] == "snowflake_read" or\
            json_data["task"]["source"]["source_type"] == "sqlserver_read":
            data_fram = read(json_data,config_file_path,task_id,run_id,paths_data,
            file_path,iter_value)
            counter=0
            for i in data_fram :
                counter+=1
                if json_data["task"]["target"]["target_type"] != "csv_write":
                    value=write(json_data, i,counter,config_file_path,task_id,run_id,
                    paths_data,file_path,iter_value)
                    if value is False:
                        write_to_txt1(task_id,'FAILED',file_path)
                        audit(json_data,task_id,run_id,'STATUS','FAILED',iter_value)
                        log2.warning(FAIL_LOG_STATEMENT, task_id)
                        return False
                    if value is True:
                        write_to_txt1(task_id,'SUCCESS',file_path)
                        audit(json_data,task_id,run_id,'STATUS','COMPLETED',
                              iter_value)
                        log2.info(TASK_LOG,task_id)
                        return False
                else:
                    value=write(json_data, i,counter)
                    if value is False:
                        write_to_txt1(task_id,'FAILED',file_path)
                        audit(json_data,task_id,run_id,'STATUS','FAILED',iter_value)
                        log2.warning(FAIL_LOG_STATEMENT, task_id)
                        return False
        elif json_data["task"]["source"]["source_type"] == "csv_read":
            data_fram=read(json_data,task_id,run_id,paths_data,file_path,iter_value)
            counter=0
            for i in data_fram :
                counter+=1
                if json_data["task"]["target"]["target_type"] != "csv_write":
                    value=write(json_data, i,counter,config_file_path,task_id,run_id,
                    paths_data,file_path,iter_value)
                    if value is False:
                        write_to_txt1(task_id,'FAILED',file_path)
                        audit(json_data,task_id,run_id,'STATUS','FAILED',iter_value)
                        log2.warning(FAIL_LOG_STATEMENT, task_id)
                        return False
                    if value is True:
                        write_to_txt1(task_id,'SUCCESS',file_path)
                        audit(json_data,task_id,run_id,'STATUS','COMPLETED',
                              iter_value)
                        log2.info(TASK_LOG,task_id)
                        return False
                else:
                    log2.info("enter ...")
                    value=write(json_data, i,counter)
                    if value is False:
                        write_to_txt1(task_id,'FAILED',file_path)
                        audit(json_data,task_id,run_id,'STATUS','FAILED',iter_value)
                        log2.warning(FAIL_LOG_STATEMENT, task_id)
                        return False
        elif json_data["task"]["source"]["source_type"] == "csvfile_read" or \
            json_data["task"]["source"]["source_type"] == "jsonfile_read" or \
            json_data["task"]["source"]["source_type"] == "xmlfile_read" or \
            json_data["task"]["source"]["source_type"] == "parquetfile_read" or \
            json_data["task"]["source"]["source_type"] == "excelfile_read":
            data_fram=read(json_data,task_id,run_id,paths_data,file_path,iter_value)
            counter=0
            for i in data_fram :
                # log2.info(i)
                counter+=1
                if json_data["task"]["target"]["target_type"] == "csvfile_write":
                    value=write(json_data, i,counter)
                    if value=='Fail':
                        audit(json_data,task_id,run_id,'STATUS','FAILED',iter_value)
                        write_to_txt1(task_id,'FAILED',file_path)
                        log2.warning(FAIL_LOG_STATEMENT, task_id)
                        return False
                elif json_data["task"]["target"]["target_type"] == "s3_write":
                    value=write(json_data, i,config_file_path,task_id,run_id,
                    paths_data,file_path,iter_value)
                    if value=='Fail':
                        write_to_txt1(task_id,'FAILED',file_path)
                        audit(json_data,task_id,run_id,'STATUS','FAILED',iter_value)
                        log2.warning(FAIL_LOG_STATEMENT, task_id)
                        return False
                else:
                    value=write(json_data, i)
        else:
            log2.info("only ingestion available currently")

        # postcheck script execution starts here
        if (json_data["task"]["target"]["target_type"] == 'csv_write' or\
        json_data["task"]["target"]["target_type"] == 'postgres_write' or \
        json_data["task"]["target"]["target_type"] == 'mysql_write' or\
        json_data["task"]["target"]["target_type"] == "snowflake_write" or\
        json_data["task"]["target"]["target_type"] == 'mssql_write' ) and \
        json_data["task"]["data_quality_execution"]["post_check_enable"] == 'Y':
            # post check code
            post_check=dq.qc_post_check(prj_nm,json_data, json_checks,paths_data,
            config_file_path,task_id,run_id,file_path,iter_value)
            #qc report generation
        new_path=paths_data["folder_path"]+paths_data["Program"]+prj_nm+\
        paths_data["qc_reports_path"]
        if json_data["task"]["data_quality_execution"]["pre_check_enable"] == 'Y' and \
            json_data["task"]["data_quality_execution"]["post_check_enable"] == 'N':
            post_check = pd.DataFrame()
            dq.qc_report(pre_check,post_check,new_path,file_path,
                         json_data,task_id,run_id,iter_value)
        elif json_data["task"]["data_quality_execution"]["pre_check_enable"] == 'N' and \
            json_data["task"]["data_quality_execution"]["post_check_enable"] == 'Y':
            pre_check = pd.DataFrame()
            dq.qc_report(pre_check,post_check,new_path,file_path,
                         json_data,task_id,run_id,iter_value)
        elif json_data["task"]["data_quality_execution"]["pre_check_enable"] == 'Y' and \
            json_data["task"]["data_quality_execution"]["post_check_enable"] == 'Y':
            dq.qc_report(pre_check,post_check,new_path,file_path,
                         json_data,task_id,run_id,iter_value)
        log2.info(TASK_LOG,task_id)
        write_to_txt1(task_id,'SUCCESS',file_path)
        audit(json_data, task_id,run_id,'STATUS','COMPLETED',iter_value)
    except Exception as error:
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        write_to_txt1(task_id,'FAILED',file_path)
        log2.warning(FAIL_LOG_STATEMENT, task_id)
        log2.exception("error in  %s.", str(error))
        raise error
