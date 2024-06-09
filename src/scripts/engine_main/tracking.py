"""script contains auditing related functions like update_status_file,audit"""
import logging
import os
import sys
from datetime import datetime
import pandas as pd
import urllib3
import requests
from master import send_mail

task_logger = logging.getLogger('task_logger')

def update_status_file(task_id,status,file_path):
    """updates a text file with statuses for orchestration"""
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
        send_mail('Failed', error, 'update_status_file from engine_code')
        raise error

def audit(json_data, task_name,run_id,paths_data,status,value,itervalue,task_group= None,\
    seq_no= None):
    """ create audit json file and audits event records into it"""
    try:
        url = paths_data['audit_api_url']
        audit_data = [{
                    "pipeline_id": json_data["pipeline_id"],
                    "taskorpipeline_name": task_name,
                    "run_id": run_id,
                    "sequence": seq_no,
                    "task_group" : task_group,
                    "iteration": itervalue,
                    "audit_type": status,
                    "audit_value": value,
                    "process_dttm" : datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                }]
        task_logger.info("audit_data:%s",audit_data)
        requests.post(url, json=audit_data, timeout=100)
    except (urllib3.exceptions.NewConnectionError, requests.exceptions.ConnectionError) as err:
        # Exception handling code goes here
        task_logger.error(
        "Please Make sure the server is running to post the audit values: %s",str(err))
        sys.exit()
    except Exception as error:
        task_logger.exception("error in audit %s.", str(error))        
        send_mail('Failed', error, 'audit from engine_code')
        raise error

def task_failed(task_id,file_path,json_data,run_id,paths_data,iter_value,subtask=None):
    """function to log and audit if task is failed"""
    try:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data,task_id,run_id,paths_data,'STATUS','FAILED',iter_value,None,subtask)
        task_logger.warning("%s got failed engine", task_id)
        sys.exit()
    except Exception as error:
        task_logger.exception("error in task_failed %s.", str(error))
        send_mail('Failed', error, 'task_failed from engine_code')
        raise error

def task_success(task_id,file_path,json_data,run_id,paths_data,iter_value):
    """function to log and audit if task is success"""
    try:
        update_status_file(task_id,'SUCCESS',file_path)
        audit(json_data,task_id,run_id,paths_data,'STATUS','COMPLETED',
                iter_value)
        task_logger.info('Task %s Execution Completed',task_id)
    except Exception as error:
        task_logger.exception("error in task_success %s.", str(error))
        send_mail('Failed', error, 'task_success from engine_code')
        raise error

def bulk_subtask_failed(task_id,json_data,run_id,paths_data,iter_value,group_no,subtask_no=None):
    """function to log and audit if subtask is failed in bulk ingestion"""
    try:
        audit(json_data,task_id,run_id,paths_data,'STATUS','FAILED',iter_value,group_no,subtask_no)
        task_logger.warning("Transaction for subtask: %s failed!",subtask_no)
    except Exception as error:
        task_logger.exception("error in task_failed %s.", str(error))
        send_mail('Failed', error, 'bulk_subtask_success from engine_code')
        raise error

def bulk_subtask_success(task_id,json_data,run_id,paths_data,iter_value,group_no,subtask_no=None):
    """function to log and audit if subtask is success in bulk ingestion"""
    try:
        audit(json_data,task_id,run_id,paths_data,'STATUS','COMPLETED',
                iter_value,group_no,subtask_no)
    except Exception as error:
        task_logger.exception("error in task_success %s.", str(error))        
        send_mail('Failed', error, 'bulk_subtask_failed from engine_code')
        raise error