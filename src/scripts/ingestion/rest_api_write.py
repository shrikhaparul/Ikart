""" script for writing data to csv file"""
import logging
import os
import importlib
import sys
import requests
import numpy as np
from requests.auth import HTTPBasicAuth
import cryptography


task_logger = logging.getLogger('task_logger')
module = importlib.import_module("utility")
update_status_file=getattr(module, "update_status_file")
get_config_section = getattr(module, "get_config_section")
JSON = '.json'
decrypt = getattr(module, "decrypt")

def to_get_api_details(json_data: dict, json_section: str,config_file_path:str,task_id,
                       run_id,paths_data,file_path,iter_value):
    """get the required config details"""
    try:
        connection_details = get_config_section(config_file_path+json_data["task"][json_section]\
        ["connection_name"]+JSON)
        engine_code_path = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "ingestion_path"]
        sys.path.insert(0, engine_code_path)
        #importing audit function from orchestrate script
        module1 = importlib.import_module("engine_code")
        audit = getattr(module1, "audit")
        auth_type = connection_details['authentication_type']
        url = connection_details["url"]
        if auth_type == "access_token":
            access_token = connection_details["access_token"]
            print(access_token)
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
    except cryptography.exceptions.InvalidTag:
        audit = getattr(module1, "audit")
        task_logger.exception("Invalid Token")
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        sys.exit()

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
        to_get_api_details(json_data, 'target',config_file_pathh,task_id,
                           run_id,paths_data,file_path,iter_value)
        datafram.replace({np.nan: None}, inplace=True)
        # Convert the DataFrame to a list of dictionaries
        records = datafram.to_dict(orient='records')
        print(records)
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
            response = requests.post(url, headers=headers,json=records, timeout=100)
            print(response)
        if len(url) > 30:
            restricted_url = url[:30]+"..."
        else:
            restricted_url = url
        task_logger.info("URL specified in the config json is: %s", restricted_url)
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Extract the response data in JSON format
            task_logger.info("Rest_API Completed")
            task_logger.info("number of records present in %s is: %s",restricted_url,
                             datafram.shape[0])
            audit(json_data, task_id,run_id,paths_data,'TGT_RECORD_COUNT',datafram.shape[0],
                iter_value)
        else:
            # Print an error message if the request was unsuccessful
            task_logger.error('Error: %s', response.text)
            update_status_file(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
            sys.exit()
    except ConnectionError as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("error in rest_api read(), %s", error)
        raise error
