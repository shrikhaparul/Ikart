""" script for writing data to csv file"""
import logging
import os
import importlib
import sys
import requests
import pandas as pd
import numpy as np
from requests.auth import HTTPBasicAuth


task_logger = logging.getLogger('task_logger')
module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
JSON = '.json'
decrypt = getattr(module, "decrypt")

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
    """get the required config details"""
    try:
        connection_details = get_config_section(config_file_path+json_data["task"][json_section]\
        ["connection_name"]+JSON)
        auth_type = connection_details['authentication_type']
        url = connection_details["url"]
        if auth_type == "access_token":
            access_token = connection_details["access_token"]
            return auth_type, url, access_token, None, None, None
        if auth_type == "basic":
            username = connection_details["username"]
            password = decrypt(connection_details["password"])
            return auth_type, url, None, username, password, None
        if auth_type == "api_token":
            api_token = connection_details["api_token"]
            return auth_type, url, None, None, None, api_token
        else:
            # Handle the case when auth_type is unknown or not supported
            return None, None, None, None, None, None
    except Exception as error:
        task_logger.exception("error in to_get_api_details(), %s", str(error))
        raise error

def write (json_data,datafram,task_id,run_id,paths_data,file_path,iter_value):
    '''function to read the data from api'''
    try:
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        config_file_pathh = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "config_path"]
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        auth_type,url,access_token,username,password,_ = \
        to_get_api_details(json_data, 'source',config_file_pathh)
        datafram.replace({np.nan: None}, inplace=True)
        # Convert the DataFrame to a list of dictionaries
        records = datafram.to_dict(orient='records')
        task_logger.info("writing data to rest api")
        headers = {'Authorization': f'Bearer {access_token}'}
        if auth_type == "basic":
            # Create the HTTPBasicAuth object
            auth = HTTPBasicAuth(username, password)
            # Make a GET request to the API endpoint with authentication
            response = requests.post(url, auth=auth,json=records, timeout=100)
        elif auth_type == "access_token":
            # Create the headers dictionary with the access token
            headers = {'Authorization': f'Bearer {access_token}'}
            # Make a GET request to the API endpoint with the headers
            response = requests.get(url, headers=headers,json=records, timeout=100)
        if len(url) > 30:
            restricted_url = url[:30]
        else:
            restricted_url = url
        task_logger.info("URL specified in the config json is: %s", restricted_url)
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Extract the response data in JSON format
            task_logger.info("Rest_API Completed")
            task_logger.info("number of records present in %s is: %s",restricted_url,
                             datafram.shape[0])
            audit(json_data, task_id,run_id,'SRC_RECORD_COUNT',datafram.shape[0],
                iter_value)
        else:
            # Print an error message if the request was unsuccessful
            task_logger.info('Error: %s', response.text)
    except ConnectionError as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.exception("error in rest_api read(), %s", error)
        raise error
