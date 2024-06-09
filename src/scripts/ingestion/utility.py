"""script for general purpose methods like log, audit, connections etc..."""
import logging
import json
import datetime
import re
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import pandas as pd
task_logger = logging.getLogger('task_logger')

# reading the connection.json file and passing the connection details as dictionary
def get_config_section(config_path:str) -> dict:
    """reads the connection file and returns connection details as dict for
       connection name you pass it through the json
    """
    try:
        with open(config_path,'r', encoding='utf-8') as jsonfile:
            logging.info("fetching connection details")
            json_data = json.load(jsonfile)
            logging.info("reading connection details completed")
            # print("connection established")
            return dict(json_data["connection_details"].items())
    except Exception as error:
        logging.exception("get_config_section() is %s.", str(error))
        raise error

def decrypt(data, paths_data):
    '''function to decrypt the data'''
    key = paths_data["key"].encode('utf-8')
    iv = paths_data["iv"].encode('utf-8')
    aesgcm = AESGCM(key)
    decrypted = aesgcm.decrypt(iv, bytes.fromhex(data), None)
    return decrypted.decode('utf-8')

def replace_date_placeholders(file_name):
    """function to replace the date and time placeholders in target filenames"""
    # Define the regular expression pattern to match date and time placeholders
    date_pattern = r"%[DdMmYyHhIiSs]+%"

    # Find all date and time placeholders in the input string
    date_time_placeholders = re.findall(date_pattern, file_name)

    # Get current date and time components
    current_datetime = datetime.datetime.now()
    year = current_datetime.strftime("%Y")
    month = current_datetime.strftime("%m")
    day = current_datetime.strftime("%d")
    hour = current_datetime.strftime("%H")
    minute = current_datetime.strftime("%M")
    second = current_datetime.strftime("%S")

    # Replace each date and time placeholder with the corresponding component
    for placeholder in date_time_placeholders:
        if "YYYY" in placeholder:
            file_name = file_name.replace(placeholder, year)
        elif "MM" in placeholder:
            file_name = file_name.replace(placeholder, month)
        elif "DD" in placeholder:
            file_name = file_name.replace(placeholder, day)
        elif "HH" in placeholder:
            file_name = file_name.replace(placeholder, hour)
        elif "MI" in placeholder:
            file_name = file_name.replace(placeholder, minute)
        elif "SS" in placeholder:
            file_name = file_name.replace(placeholder, second)

    return file_name

def update_status_file(task_id,status,file_path):
    """updates a text file with statuses for orchestration"""
    try:
        is_exist = os.path.exists(file_path)
        if is_exist is True:
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
        else:
            task_logger.error("status txt file does not exist")
    except Exception as error:
        task_logger.exception("update_status_file: %s.", str(error))
        raise error

def construct_file_name(target):
    """
    Constructs a file name based on the `target` dictionary and replaces date placeholders.
    Parameters:
    target (dict): Dictionary containing file naming components.
    replace_date_placeholders (func): Function to replace date placeholders in the file name.
    Returns:
    str: Constructed file name with date placeholders replaced.
    """
    # Determine the object prefix name
    object_prefix_name = "" if 'object_prefix_name' not in target or \
    target['object_prefix_name'] in (None, "None", "") else target['object_prefix_name']
    # Determine the object suffix name
    object_suffix_name = "" if 'object_sufix_name' not in target or \
    target['object_sufix_name'] in (None, "None", "") else target['object_sufix_name']
    # Construct the file name
    if target['target_file_format'] == "excel":
        extension = ".xlsx"  #
        file_name = object_prefix_name + target['object_name'] + object_suffix_name + extension
    else:
        file_name = object_prefix_name + target['object_name'] + object_suffix_name + '.' + \
        target['target_file_format']
    # Replace date placeholders in the file name
    file_name = replace_date_placeholders(file_name)
    task_logger.info("file_name:%s",file_name)
    return file_name
