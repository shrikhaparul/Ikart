""" script for writing data to parquet"""
import logging

log2 = logging.getLogger('log2')

def write(json_data: dict, datafram ) -> bool:
    """ function for writing to  parquet"""
    try:
        log2.info("converting data to parquet initiated")
        datafram.astype(str).to_parquet(json_data["task"]["target"]["file_path"] + \
        json_data["task"]["target"]["file_name"],engine='auto',
                index=False)
        log2.info(" parquet conversion completed")
        return True
    except Exception as error:
        log2.exception("converting_to_parquet() is %s", str(error))
        raise error
