""" script for convrting data to excel"""
import logging
import os
from datetime import datetime
import pandas as pd
from utility import replace_date_placeholders

task_logger = logging.getLogger('task_logger')

def split_large_excel_file(input_file, output_directory, rows_per_split, ext):
    """splitting the large excel files into multiple files"""
    # Read the Excel file into a DataFrame
    df = pd.read_excel(input_file)

    split_number = 1
    row_count = 0

    if rows_per_split <= 0:
        # If rows_per_split is zero or negative, write the entire Excel content to one file
        output_file_path = os.path.join(output_directory, f"{ext}")
        df.to_excel(output_file_path, index=False)
    else:
        start_row = 0

        while start_row < len(df):
            end_row = start_row + rows_per_split
            if end_row > len(df):
                end_row = len(df)

            # Create a new DataFrame with the selected rows
            split_df = df[start_row:end_row]

            # Write the DataFrame to a split Excel file
            output_file_path = os.path.join(output_directory, 
                                            f"{output_directory}_part_000{split_number}{ext}")
            split_df.to_excel(output_file_path, index=False)

            # Update start_row and split_number
            start_row = end_row
            split_number += 1
    os.remove(input_file)

def write(json_data: dict, dataframe, counter) -> bool:
    """ function for writing to Excel """
    try:
        target = json_data["task"]["target"]
        file_path = target["file_path"]
        file_name = target["file_name"]
        file_name = replace_date_placeholders(target['file_name'])
        task_logger.info("converting data to Excel initiated")
        check = True if target['index'] == "False" else False
        # Reset the index and create an 'index' column
        dataframe.reset_index(drop=check, inplace=True)
        if counter == 1: # If it's the first chunk, write the data to a new Excel file
            if os.path.exists(target["file_path"]+file_name):
                os.remove(target["file_path"]+file_name)
            if target["audit_columns"] == "active":
                # if audit_columns are active
                dataframe['CRTD_BY']="etl_user"
                dataframe['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dataframe['UPDT_BY']= " "
                dataframe['UPDT_DTTM']= " "
                dataframe.to_excel(file_path + file_name, index=False)
            else:
                dataframe.to_excel(file_path + file_name, index=False)
        else: # If it's not the first chunk, read the existing Excel file and append the new data
            if target["audit_columns"] == "active":
                # if audit_columns are active
                dataframe['CRTD_BY']="etl_user"
                dataframe['CRTD_DTTM']= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dataframe['UPDT_BY']= " "
                dataframe['UPDT_DTTM']= " "
                existing_dataframe = pd.read_excel(file_path + file_name)
                updated_dataframe = pd.concat([existing_dataframe, dataframe], ignore_index=True)
                updated_dataframe.to_excel(file_path + file_name, index=False)
            else:
                existing_dataframe = pd.read_excel(file_path + file_name)
                updated_dataframe = pd.concat([existing_dataframe, dataframe], ignore_index=True)
                updated_dataframe.to_excel(file_path + file_name, index=False)
        task_logger.info("Excel conversion completed")

        records_per_split = target['target_max_record_count']
        filename_wo_ext = os.path.splitext(file_name)[0]
        records_per_split = 0 if 'target_max_record_count' not in target or \
        target['target_max_record_count'] in (None,"None","") else \
        target['target_max_record_count']
        if records_per_split > 0:
            split_large_excel_file(file_path + filename_wo_ext + '.xlsx',
            file_path + filename_wo_ext, records_per_split, '.xlsx')
        return True
    except Exception as error:
        task_logger.exception("converting_to_excel() is %s", str(error))
        raise error
