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
module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")
update_status_file=getattr(module, "update_status_file")
JSON = '.json'

def to_get_api_details(json_data: dict, json_section: str,config_file_path:str,paths_data):
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
            password = decrypt(connection_details["password"],paths_data)
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
        auth_type,url,access_token,username,password,_ = \
        to_get_api_details(json_data, "source",config_file_path,paths_data)
        timeout = json_data["task"]["source"]["timeout"]
        if timeout == "":
            timeout = 100
        else:
            timeout = int(timeout)
        query_params = json_data["task"]["source"]["query_params"]
        if query_params not in ("",None,"None"):
            url = url + query_params
            task_logger.info("url %s", url)
        if auth_type == "basic":
            # Create the HTTPBasicAuth object
            auth = HTTPBasicAuth(username, password)
            # Make a GET request to the API endpoint with authentication
            response = requests.get(url, auth=auth, timeout=timeout)
        elif auth_type == "access_token":
            # Create the headers dictionary with the access token
            headers = {'Authorization': f'Bearer {access_token}'}
            # Make a GET request to the API endpoint with the headers
            response = requests.get(url, headers=headers, timeout=timeout)
        if len(url) > 30:
            restricted_url = url[:30]+"..."
        else:
            restricted_url = url
        task_logger.info("URL specified in the config json is: %s", restricted_url)
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Extract the response data in JSON format
            data = response.json()
            # Convert the JSON data to a polars DataFrame
            datafram = pd.DataFrame(data)
            task_logger.info("number of records read from %s is: %s",restricted_url,
                             datafram.shape[0])
            audit(json_data, task_id,run_id,paths_data,'SRC_RECORD_COUNT',datafram.shape[0],
                iter_value)
        else:
            # Print an error message if the request was unsuccessful
            task_logger.error('Error: %s', response.text)
            update_status_file(task_id,'FAILED',file_path)
            audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
            sys.exit()
        yield datafram
    except Exception as error:
        update_status_file(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("error in rest_api read(), %s", error)
        raise error
