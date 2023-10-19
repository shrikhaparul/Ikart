""" script for convrting data to json"""
import logging

log2 = logging.getLogger('log2')

def write(json_data: dict, datafram) -> bool:
    """ function for converting csv  to  json"""
    try:
        log2.info("converting data to json initiated")
        datafram.to_json(json_data["task"]["target"]["file_path"] + \
        json_data["task"]["target"]["file_name"],orient='records',
                index=True)
        log2.info("csv to json conversion completed")
        return True
    except Exception as error:
        log2.exception("convert_csv_to_json() is %s", str(error))
        raise error
