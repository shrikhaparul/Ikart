""" script for convrting data to excel"""
import logging

log2 = logging.getLogger('log2')

def write(json_data: dict, datafram) -> bool:
    """ function for converting csv  to  excel"""
    try:
        log2.info("converting data to excel initiated")
        datafram.to_excel(json_data["task"]["target"]["file_path"] + \
        json_data["task"]["target"]["file_name"],
                index=False)
        log2.info("csv to excel conversion completed")
        return True
    except Exception as error:
        log2.exception("convert_csv_to_excel() is %s", str(error))
        raise error
