""" script for converting data to xml"""
import logging
import os
from datetime import datetime
import xml.etree.ElementTree as ET
import importlib
import sys
from utility import replace_date_placeholders,update_status_file

task_logger = logging.getLogger('task_logger')

def write(json_data,task_id,run_id,iter_value,paths_data,text_file_path,
    datafram, counter,local_temp_path):
    """ function for writing to XML """
    try:
        engine_code_path = paths_data["folder_path"]+paths_data["src"]+paths_data["ingestion_path"]
        sys.path.insert(0, engine_code_path)
        audit_module = importlib.import_module("engine_code")
        audit = getattr(audit_module, "audit")
        target = json_data["task"]["target"]
        file_path = local_temp_path
        file_name = target["file_name"]
        file_name = replace_date_placeholders(target['file_name'])
        task_logger.info("converting data to XML initiated")
        created_by = json_data['created_by'] if 'created_by' in json_data else "etl_user"
        # include_header = target.get("header", "Y") == "Y"
        # Remove spaces in column names (due to below mentioned xml rules)
        datafram.columns = datafram.columns.str.replace(' ', '')
        # Check if it's the first chunk
        if counter == 1:
            if os.path.exists(file_path + file_name):
                os.remove(file_path + file_name)

            # Create the root of the XML tree
            root = ET.Element('data')

            if target["audit_columns"] == "active":
                # If audit_columns are active, add the audit columns
                for _, row in datafram.iterrows():
                    xml_row = ET.SubElement(root, 'row')
                    for column_name, value in row.items():
                        element = ET.SubElement(xml_row, column_name)
                        element.text = str(value)

                # Add audit columns
                for xml_row in root:
                    ET.SubElement(xml_row, 'CRTD_BY').text = created_by
                    ET.SubElement(xml_row, 'CRTD_DTTM').text = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S")
                    ET.SubElement(xml_row, 'UPDT_BY').text = " "
                    ET.SubElement(xml_row, 'UPDT_DTTM').text = " "
            else:
                # If audit_columns are not active, directly add rows
                for _, row in datafram.iterrows():
                    xml_row = ET.SubElement(root, 'row')
                    for column_name, value in row.items():
                        element = ET.SubElement(xml_row, column_name)
                        element.text = str(value)

            # Write the XML to a file
            tree = ET.ElementTree(root)
            tree.write(file_path + file_name, encoding=target['encoding'])

        else:
            # If it's not the first chunk, read the existing XML file and append the new data
            tree = ET.ElementTree(file=file_path + file_name)
            root = tree.getroot()

            if target["audit_columns"] == "active":
                # If audit_columns are active, add the audit columns
                for _, row in datafram.iterrows():
                    xml_row = ET.SubElement(root, 'row')
                    for column_name, value in row.items():
                        element = ET.SubElement(xml_row, column_name)
                        element.text = str(value)

                    ET.SubElement(xml_row, 'CRTD_BY').text = created_by
                    ET.SubElement(xml_row, 'CRTD_DTTM').text = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S")
                    ET.SubElement(xml_row, 'UPDT_BY').text = " "
                    ET.SubElement(xml_row, 'UPDT_DTTM').text = " "
            else:
                # If audit_columns are not active, directly add rows
                for _, row in datafram.iterrows():
                    xml_row = ET.SubElement(root, 'row')
                    for column_name, value in row.items():
                        element = ET.SubElement(xml_row, column_name)
                        element.text = str(value)
            # Write the updated XML to the file
            tree.write(file_path + file_name, encoding=target['encoding'])
        task_logger.info("XML conversion completed")
        return True,file_path,file_name
    except Exception as error:
        update_status_file(task_id,'FAILED',text_file_path)
        audit(json_data, task_id,run_id,paths_data,'STATUS','FAILED',iter_value)
        task_logger.exception("converting_to_xml() is %s", str(error))
        raise error
    