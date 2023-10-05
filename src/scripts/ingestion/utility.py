"""script for general purpose methods like log, audit, connections etc..."""
import logging
import json
import datetime
import os
from pathlib import Path
import re
import pandas as pd 
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# custom log function for framework
def initiate_logging(project: str, log_loc: str) -> bool:
    """Function to initiate log file which will be used across framework"""
    try:
        log_file_nm = project + '.log'
        new_file1 = log_loc + log_file_nm
        # create formatter & how we want ours logs to be formatted
        format_str = '%(asctime)s | %(name)-10s | %(processName)-12s | %(funcName)-22s |\
        %(levelname)-5s | %(message)s'
        formatter = logging.Formatter(format_str)
        logging.basicConfig(filename=new_file1, filemode='a',
                            level=logging.INFO, format=format_str)
        st_handler = logging.StreamHandler()  # create handler and set the log level
        st_handler.setLevel(logging.INFO)
        st_handler.setFormatter(formatter)
        logging.getLogger().addHandler(st_handler)
        return True
    except Exception as ex:
        logging.error('UDF Failed: initiate_logging failed')
        raise ex

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

def decrypt(data):
    '''function to decrypt the data'''
    KEY = b'8ookgvdIiH2YOgBnAju6Nmxtp14fn8d3'
    IV = b'rBEssDfxofOveRxR'
    aesgcm = AESGCM(KEY)
    decrypted = aesgcm.decrypt(IV, bytes.fromhex(data), None)
    return decrypted.decode('utf-8')

def replace_date_placeholders(file_name):
    """function to replace the date and time placeholders in target filenames"""
    # Define the regular expression pattern to match date and time placeholders
    date_pattern = r"%[DdMmYyHhMmIiSs]+%"

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
