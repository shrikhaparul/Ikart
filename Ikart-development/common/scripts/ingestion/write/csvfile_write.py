""" script for writing data to csv file"""
import logging
from datetime import datetime
from ast import literal_eval

log2 = logging.getLogger('log2')

def write(json_data: dict,datafram, counter) -> bool:
    """ function for writing data to csv file"""
    try:
        log2.info("writing data to csv file")
        if counter ==1: # if it is first iteration
            # if audit_columns are active
            if json_data["task"]["target"]["audit_columns"] == "active":
                datafram['CRTD_BY']="etl_user"
                datafram['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datafram['UPDT_BY']= " "
                datafram['UPDT_DTTM']= " "
                datafram.to_csv(json_data["task"]["target"]["file_path"]+
                json_data["task"]["target"]["file_name"],
                sep=json_data["task"]["target"]["delimiter"], header=literal_eval(
                json_data["task"]["target"]["header"]),
                index=literal_eval(json_data["task"]["target"]["index"]), mode='w',\
                encoding=json_data["task"]["target"]["encoding"])
            else:
                # if audit_columns are not active
                datafram.to_csv(json_data["task"]["target"]["file_path"]+
                json_data["task"]["target"]["file_name"],
                sep=json_data["task"]["target"]["delimiter"], header=literal_eval(
                json_data["task"]["target"]["header"]),
                index=literal_eval(json_data["task"]["target"]["index"]), mode='w',\
                encoding=json_data["task"]["target"]["encoding"])
        else: # if it is iteration other than first
            if json_data["task"]["target"]["audit_columns"] == "active":
                # if audit_columns are active
                datafram['CRTD_BY']="etl_user"
                datafram['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datafram['UPDT_BY']= " "
                datafram['UPDT_DTTM']= " "
                datafram.to_csv(json_data["task"]["target"]["file_path"]+
                json_data["task"]["target"]["file_name"],
                sep=json_data["task"]["target"]["delimiter"], header=False,\
                index=literal_eval(json_data["task"]["target"]["index"]),
                mode='w', encoding=json_data["task"]["target"]["encoding"])
            else:
                # if audit_columns are not active
                datafram.to_csv(json_data["task"]["target"]["file_path"]+
                json_data["task"]["target"]["file_name"],
                sep=json_data["task"]["target"]["delimiter"], header=False,\
                index=literal_eval(json_data["task"]["target"]["index"]),
                mode='w', encoding=json_data["task"]["target"]["encoding"])
        return True
    except Exception as error:
        log2.exception("ingest_data_to_csv() is %s", str(error))
        raise error
