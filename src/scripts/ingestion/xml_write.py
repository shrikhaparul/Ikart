""" script for converting data to xml"""
import logging
import os
from datetime import datetime
import xml.etree.ElementTree as ET
import pandas as pd
from utility import replace_date_placeholders

task_logger = logging.getLogger('task_logger')

def split_large_xml_file(input_file, output_directory, records_per_split, ext):
    """To split the large xml file to multiple files"""
    default_encoding = 'utf-8'

    # Parse the input XML file
    tree = ET.parse(input_file)
    root = tree.getroot()
    records = list(root)  # Assuming each element is a record

    split_number = 1
    record_count = 0

    if records_per_split <= 0:
        # If records_per_split is zero or negative, write the entire XML content to one file
        split_file_path = os.path.join(output_directory, f"{ext}")
        tree.write(split_file_path, encoding=default_encoding)
    else:
        # Initialize an empty list to hold the records for each split
        split_records = []

        for record in records:
            split_records.append(record)
            record_count += 1

            if record_count >= records_per_split:
                # Create a new XML tree and add the records to it
                split_tree = ET.ElementTree(ET.Element("root"))
                split_root = split_tree.getroot()
                split_root.extend(split_records)

                # Write the XML content to a split file
                split_file_path = os.path.join(output_directory, 
                                               f"{output_directory}_part_000{split_number}{ext}")
                split_tree.write(split_file_path, encoding=default_encoding)

                # Reset the record count and clear the split_records list
                record_count = 0
                split_records = []
                split_number += 1

        # Write any remaining records to the final split file
        if record_count > 0:
            split_tree = ET.ElementTree(ET.Element("root"))
            split_root = split_tree.getroot()
            split_root.extend(split_records)

            split_file_path = os.path.join(output_directory, f"{output_directory}_part_000{split_number}{ext}")
            split_tree.write(split_file_path, encoding=default_encoding)

    # # Remove the original input XML file
    os.remove(input_file)


def write(json_data: dict, dataframe, counter) -> bool:
    """ function for writing to XML """
    try:
        target = json_data["task"]["target"]
        file_path = target["file_path"]
        file_name = target["file_name"]
        file_name = replace_date_placeholders(target['file_name'])
        task_logger.info("converting data to XML initiated")
        check = True if target['index'] == "False" else False
        # Reset the index and create an 'index' column
        dataframe.reset_index(drop=check, inplace=True)
        # Remove spaces in column names (due to below mentioned xml rules)
        #Element names must start with a letter or underscore.
        # Element names can only contain letters, numbers, hyphens, underscores, and periods.
        # Element names cannot contain spaces.
        dataframe.columns = dataframe.columns.str.replace(' ', '')

        if counter == 1: # If it's the first chunk, write the data to a new XML file
            if os.path.exists(target["file_path"]+file_name):
                os.remove(target["file_path"]+file_name)
            if target["audit_columns"] == "active":
                # if audit_columns are active
                dataframe['CRTD_BY']="etl_user"
                dataframe['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dataframe['UPDT_BY']= " "
                dataframe['UPDT_DTTM']= " "
                dataframe.to_xml(file_path + file_name,
                                root_name='data', row_name='row',encoding = target['encoding'])
            else:
                dataframe.to_xml(file_path + file_name,
                                root_name='data', row_name='row',encoding = target['encoding'])
        else: # If it's not the first chunk, read the existing XML file and append the new data
            if target["audit_columns"] == "active":
                # if audit_columns are active
                dataframe['CRTD_BY']="etl_user"
                dataframe['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dataframe['UPDT_BY']= " "
                dataframe['UPDT_DTTM']= " "
                existing_dataframe = pd.read_xml(file_path + file_name)
                updated_dataframe = pd.concat([existing_dataframe, dataframe], ignore_index=True)
                updated_dataframe.to_xml(file_path + file_name, root_name='data', row_name='row',
                                    index=False, encoding = target['encoding'])
            else:
                existing_dataframe = pd.read_xml(file_path + file_name)
                updated_dataframe = pd.concat([existing_dataframe, dataframe], ignore_index=True)
                updated_dataframe.to_xml(file_path + file_name, root_name='data', row_name='row',
                                    index=False, encoding = target['encoding'])
        task_logger.info("XML conversion completed")
        records_per_split = target['target_max_record_count']
        filename_wo_ext = os.path.splitext(file_name)[0]
        records_per_split = 0 if 'target_max_record_count' not in target or \
        target['target_max_record_count'] in (None,"None","") else \
        target['target_max_record_count']
        if records_per_split > 0:
            split_large_xml_file(file_path + filename_wo_ext + '.xml',
            file_path + filename_wo_ext, records_per_split, '.xml')

        return True
    except Exception as error:
        task_logger.exception("converting_to_xml() is %s", str(error))
        raise error
