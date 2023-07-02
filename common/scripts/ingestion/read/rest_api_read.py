'''importing required modules'''
import logging
import os
import sys
import importlib
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

task_logger = logging.getLogger('task_logger')
ITERATION='%s iteration'
task_logger = logging.getLogger('task_logger')
module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")
JSON = '.json'

def write_to_txt(task_id,status,file_path):
    """Generates a text file with statuses for orchestration"""
    try:
        is_exist = os.path.exists(file_path)
        if is_exist is True:
            # task_logger.info("txt getting called")
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
        else:
            task_logger.error("pipeline txt file does not exist")
    except Exception as error:
        task_logger.exception("write_to_txt: %s.", str(error))
        raise error

def to_get_api_details(json_data: dict, json_section: str,config_file_path:str):
    """establishes connection for the mysql database
       you pass it through the json"""
    try:
        connection_details = get_config_section(config_file_path+json_data["task"][json_section]\
        ["connection_name"]+JSON)
        auth_type = connection_details['authentication_type']
        access_token = connection_details["access_token"]
        username = connection_details["username"]
        password = decrypt(connection_details["password"])
        api_token = connection_details["api_token"]
        url = connection_details["url"]
        return auth_type,access_token,username,password,api_token,url
    except Exception as error:
        task_logger.exception("error in to_get_api_details(), %s", str(error))
        raise error

def read (json_data,task_id,run_id,paths_data,file_path,iter_value):
    '''function to read the data from api'''
    try:
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        config_file_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "config_path"]
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        auth_type,access_token,username,password,_,url = \
        to_get_api_details(json_data, 'source',config_file_path)
        if auth_type == "basic":
            # Create the HTTPBasicAuth object
            auth = HTTPBasicAuth(username, password)
            # Make a GET request to the API endpoint with authentication
            response = requests.get(url, auth=auth, timeout=100)
        elif auth_type == "access_token":
            # Create the headers dictionary with the access token
            headers = {'Authorization': f'Bearer {access_token}'}
            # Make a GET request to the API endpoint with the headers
            response = requests.get(url, headers=headers, timeout=100)
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Extract the response data in JSON format
            data = response.json()
            # Convert the JSON data to a polars DataFrame
            datafram = pd.DataFrame(data)
            audit(json_data, task_id,run_id,'SRC_RECORD_COUNT',datafram.shape[0],
                iter_value)
        else:
            # Print an error message if the request was unsuccessful
            task_logger('Error:', response.status_code)
        return datafram
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger("error in rest_api read(), %s", error)
        raise error
