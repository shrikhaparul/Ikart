""" script for converting data to xml"""
import logging

log2 = logging.getLogger('log2')

def write(json_data: dict, chunk) -> bool:
    """ function for converting csv  to xml"""
    try:
        log2.info("converting data to xml initiated")
        chunk.to_xml(json_data["task"]["target"]["file_path"] + \
        json_data["task"]["target"]["file_name"],
                index=True)
        log2.info("csv to xml conversion completed")
        return True
    except Exception as error:
        log2.exception("convert_csv_to_xml() is %s", str(error))
        raise error
