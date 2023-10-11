""" script for writing data to S3"""
import logging
from datetime import datetime
import os
import importlib
import sys
import io
import xml.etree.ElementTree as ET
import pyarrow
import pyarrow.parquet as pq
import pyarrow as pa
from ast import literal_eval
import json
import pandas as pd
import boto3
from utility import replace_date_placeholders

module = importlib.import_module("utility")
get_config_section = getattr(module, "get_config_section")
decrypt = getattr(module, "decrypt")

task_logger = logging.getLogger('task_logger')
folder_timestamp = datetime.now().strftime("%Y%m%d")
file_timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
CSV = '.csv'
XLSX = '.xlsx'
JSON = '.json'
PARQUET ='.parquet'
XML = '.xml'
REPLACE_OPERATION= "S3 target operation is REPLACE \n target path: %s"
APPEND_OPERATION="S3 target operation is APPEND"
OBJECT_EXISTS ="%s object already exists in the target location"
OBJECT_NOT_EXISTS = "%s object does not exists in the target location"
CREATE_OBJECT = "creating new object %s"

def establish_conn(json_data: dict, json_section: str,config_file_path:str):
    """establishes connection for the mysql database
       you pass it through the json"""
    try:
        connection_details = get_config_section(config_file_path+json_data["task"][json_section]\
        ["connection_name"]+JSON)
        # task_logger.info("aws access key id %s", decrypt(connection_details["aws_access_key_id"]))
        d_aws_access_key_id = decrypt(connection_details["access_key"])
        d_aws_secret_access_key = decrypt(connection_details["secret_access_key"])
        conn = boto3.client( service_name= 's3',region_name=
        connection_details["region_name"],aws_access_key_id=d_aws_access_key_id,
        aws_secret_access_key=d_aws_secret_access_key)
        logging.info("connection established")
        return conn,connection_details
    except Exception as error:
        task_logger.exception("establish_conn() is %s", str(error))
        raise error

def write_to_txt(task_id,status,file_path):
    """Generates a text file with statuses for orchestration"""
    try:
        is_exist = os.path.exists(file_path)
        if is_exist is True:
            # task_logger.info("txt getting called")
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
        else:
            task_logger.error("pipeline txt file does not exist")
    except Exception as error:
        task_logger.exception("write_to_txt: %s.", str(error))
        raise error

def split_large_s3csv_file(conn,bucket_name,object_key,output_prefix, records_per_split,ext):
    '''function to split a large S3 file based on the number of records'''
    # Initialize S3 client

    # Read the header from the source S3 object
    s3_response = conn.get_object(Bucket=bucket_name, Key=object_key)
    header = s3_response['Body'].readline().decode('utf-8')

    split_number = 1
    record_count = 0
    split_object_key = f"{output_prefix}_part_000{split_number}{ext}" \
    if records_per_split > 0 else f"{output_prefix}{ext}"
    split_file_contents = header

    if records_per_split > 0:
        for line in s3_response['Body'].iter_lines():
            line = line.decode('utf-8')
            split_file_contents += line + '\n'
            record_count += 1

            if record_count >= records_per_split:
                # Upload the current split to S3
                conn.put_object(Bucket=bucket_name, Key=split_object_key,
                                Body=split_file_contents.encode('utf-8'))

                # Reset variables for the next split
                split_number += 1
                split_object_key = f"{output_prefix}_part_000{split_number}{ext}"
                split_file_contents = header
                record_count = 0

        # Upload the final split to S3
        conn.put_object(Bucket=bucket_name, Key=split_object_key,
                        Body=split_file_contents.encode('utf-8'))

    # Delete the original S3 object (optional)
    conn.delete_object(Bucket=bucket_name, Key=object_key)


def split_large_s3_file(conn, bucket_name, object_key, output_prefix, records_per_split, ext):
    '''to split s3 files into multiple files based on target record count'''
    # Read the header from the source S3 object
    s3_response = conn.get_object(Bucket=bucket_name, Key=object_key)

    # Determine the file format based on the file extension
    if ext.lower() == '.csv' or ext.lower() == '.txt':
        file_format = 'text'
    elif ext.lower() == '.json':
        file_format = 'json'
    elif ext.lower() == '.xml':
        file_format = 'xml'
    elif ext.lower() == '.parquet':
        file_format = 'parquet'
        # header = s3_response['Body'].readline().decode('Latin-1')
    elif ext.lower() == '.xlsx':
        file_format = 'excel'
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    header = s3_response['Body'].readline().decode('utf-8')
    # header = s3_response['Body'].read(4)  # Adjust the number of bytes as needed


    split_number = 1
    record_count = 0
    split_object_key = f"{output_prefix}_part_000{split_number}{ext}" \
    if records_per_split > 0 else f"{output_prefix}{ext}"
    split_file_contents = header

    if records_per_split > 0:
        if file_format == 'text':
            for line in s3_response['Body'].iter_lines():
                line = line.decode('utf-8')
                split_file_contents += line + '\n'
                record_count += 1

                if record_count >= records_per_split:
                    # Upload the current split to S3
                    conn.put_object(Bucket=bucket_name, Key=split_object_key,
                                    Body=split_file_contents.encode('utf-8'))

                    # Reset variables for the next split
                    split_number += 1
                    split_object_key = f"{output_prefix}_part_000{split_number}{ext}"
                    split_file_contents = header
                    record_count = 0
        elif file_format == 'json':
            # Read the entire JSON file and split it based on records_per_split
            json_data = json.loads(s3_response['Body'].read().decode('utf-8'))
            records = json_data  # Assumes JSON contains an array of records
            for record in records:
                split_file_contents += json.dumps(record) + '\n'
                record_count += 1

                if record_count >= records_per_split:
                    # Upload the current split to S3
                    conn.put_object(Bucket=bucket_name, Key=split_object_key,
                                    Body=split_file_contents.encode('utf-8'))

                    # Reset variables for the next split
                    split_number += 1
                    split_object_key = f"{output_prefix}_part_000{split_number}{ext}"
                    split_file_contents = header
                    record_count = 0
        elif file_format == 'xml':
            # Parse XML and split it based on records_per_split
            xml_data = ET.fromstring(s3_response['Body'].read().decode('utf-8'))
            records = list(xml_data)  # Assumes XML has a root element with multiple records
            for record in records:
                split_file_contents += ET.tostring(record).decode('utf-8') + '\n'
                record_count += 1

                if record_count >= records_per_split:
                    # Upload the current split to S3
                    conn.put_object(Bucket=bucket_name, Key=split_object_key,
                                    Body=split_file_contents.encode('utf-8'))

                    # Reset variables for the next split
                    split_number += 1
                    split_object_key = f"{output_prefix}_part_000{split_number}{ext}"
                    split_file_contents = header
                    record_count = 0
        elif file_format == 'parquet':
            # Read the Parquet file using a library like PyArrow
            # parquet_data = pd.read_parquet(io.BytesIO(s3_response['Body'].read()))
            s3_response = conn.get_object(Bucket=bucket_name, Key=object_key)
            parquet_data = s3_response['Body'].read()

            # Create a PyArrow buffer from the binary data
            buffer = pyarrow.BufferReader(parquet_data)

            # Read the Parquet file using PyArrow
            parquet_data = pq.read_table(buffer)
            for _, row in parquet_data.iterrows():
                split_file_contents += row.to_json() + '\n'
                record_count += 1

                if record_count >= records_per_split:
                    # Upload the current split to S3
                    conn.put_object(Bucket=bucket_name, Key=split_object_key,
                                    Body=split_file_contents.encode('utf-8'))

                    # Reset variables for the next split
                    split_number += 1
                    split_object_key = f"{output_prefix}_part_000{split_number}{ext}"
                    split_file_contents = header
                    record_count = 0
        elif file_format == 'excel':
            # Read the Excel file using a library like Pandas
            excel_data = pd.read_excel(s3_response['Body'])
            for _, row in excel_data.iterrows():
                split_file_contents += row.to_json() + '\n'
                record_count += 1

                if record_count >= records_per_split:
                    # Upload the current split to S3
                    conn.put_object(Bucket=bucket_name, Key=split_object_key,
                                    Body=split_file_contents.encode('utf-8'))

                    # Reset variables for the next split
                    split_number += 1
                    split_object_key = f"{output_prefix}_part_000{split_number}{ext}"
                    split_file_contents = header
                    record_count = 0

    # Upload the final split to S3
    conn.put_object(Bucket=bucket_name, Key=split_object_key,
                    Body=split_file_contents.encode('utf-8'))

    # Delete the original S3 object (optional)
    conn.delete_object(Bucket=bucket_name, Key=object_key)

def split_large_json_file_s3(conn,bucket_name, input_key, output_prefix, records_per_split, ext):
    '''function to split the large JSON files stored in an S3 bucket based on the number of records'''

    # Download the input JSON file from S3
    response = conn.get_object(Bucket=bucket_name, Key=input_key)
    input_data = json.loads(response['Body'].read().decode('utf-8'))

    split_number = 1
    record_count = 0

    if records_per_split <= 0:
        # If records_per_split is zero or negative, write the entire JSON content to one file
        split_file_key = f"{output_prefix}{ext}"
        conn.put_object(Bucket=bucket_name, Key=split_file_key, Body=json.dumps(input_data, indent=4))
    else:
        # Initialize an empty list to hold the records for each split
        split_records = []

        for record in input_data:
            split_records.append(record)
            record_count += 1

            if record_count >= records_per_split:
                # Write the records to a split file in S3
                split_file_key = f"{output_prefix}_part_000{split_number}{ext}"
                conn.put_object(Bucket=bucket_name, Key=split_file_key, Body=json.dumps(split_records, indent=4))

                # Reset the record count and clear the split_records list
                record_count = 0
                split_records = []
                split_number += 1

        # Write any remaining records to the final split file in S3
        if record_count > 0:
            split_file_key = f"{output_prefix}_part_000{split_number}{ext}"
            conn.put_object(Bucket=bucket_name, Key=split_file_key, Body=json.dumps(split_records, indent=4))

    # Optionally, you can delete the original input JSON file from S3
    conn.delete_object(Bucket=bucket_name, Key=input_key)

def split_large_parquet_file_s3(conn, bucket_name, input_key, output_prefix, records_per_split, ext):
    '''function to split the large Parquet files stored in an S3 bucket based on the number of records'''

    # Download the input Parquet file from S3
    response = conn.get_object(Bucket=bucket_name, Key=input_key)
    parquet_data = response['Body'].read()

    # Read the Parquet data into a PyArrow table
    table = pq.read_table(parquet_data)

    split_number = 1
    record_count = 0

    if records_per_split <= 0:
        # If records_per_split is zero or negative, write the entire Parquet content to one file
        split_file_key = f"{output_prefix}{ext}"
        conn.put_object(Bucket=bucket_name, Key=split_file_key, Body=parquet_data)
    else:
        # Initialize an empty list to hold the Parquet rows for each split
        split_records = []

        for row in table:
            split_records.append(row)
            record_count += 1

            if record_count >= records_per_split:
                # Write the records to a split file in S3
                split_file_key = f"{output_prefix}_part_000{split_number}{ext}"
                pq.write_table(pa.Table.from_pandas(pd.concat(split_records, axis=1).T),
                               split_file_key, filesystem=conn)

                # Reset the record count and clear the split_records list
                record_count = 0
                split_records = []
                split_number += 1

        # Write any remaining records to the final split file in S3
        if record_count > 0:
            split_file_key = f"{output_prefix}_part_000{split_number}{ext}"
            pq.write_table(pa.Table.from_pandas(pd.concat(split_records, axis=1).T),
                           split_file_key, filesystem=conn)

    # Optionally, you can delete the original input Parquet file from S3
    conn.delete_object(Bucket=bucket_name, Key=input_key)

def check_path(con,file_path,connection_details):
    "function to check whether table object in s3 exists or not"
    result = con.list_objects(Bucket=connection_details["bucket_name"], Prefix=file_path )
    exists=False
    if 'Contents' in result:
        exists=True
    return exists

# def write_csv(json_data,datafram,conn,target_path,connection_details):
#     """function for s3 write for csv filetype"""
#     task_logger.info("s3 write operation for CSV filetype started")
#     csv_buf = io.StringIO()
#     datafram.to_csv(csv_buf, header=True, index=False)
#     csv_buf.seek(0)
#     conn.put_object(Bucket=connection_details["bucket_name"],Body=
#     csv_buf.getvalue(), Key=target_path,ServerSideEncryption='AES256')
#     task_logger.info("Successfully wrote %s records to S3.", len(datafram))

def write_csv(json_data: dict,conn,s3_bucket_name,s3_key, datafram, counter) -> bool:
    """Function for writing data to an S3 bucket"""
    try:
        task_logger.info("writing data to S3 bucket")
        target = json_data['task']['target']
        created_by = json_data.get('created_by', 'etl_user')

        if counter == 1:  # for the first iteration
            # if target["audit_columns"] == "active":
            #     # If audit_columns are active
            #     datafram['CRTD_BY'] = created_by
            #     datafram['CRTD_DTTM'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            #     datafram['UPDT_BY'] = " "
            #     datafram['UPDT_DTTM'] = " "

            # csv_buffer = datafram.to_csv(index=literal_eval(target["index"]), sep=target["delimiter"],
            #                              encoding=target["encoding"], header=literal_eval(target["header"]))

            csv_buffer = datafram.to_csv(sep=target["delimiter"],
            encoding=target["encoding"])


            # Upload the DataFrame as a CSV file to S3
            conn.put_object(Bucket=s3_bucket_name, Key=s3_key, Body=csv_buffer)

        else:  # for iterations other than one
            # if target["audit_columns"] == "active":
            #     # If audit_columns are active
            #     datafram['CRTD_BY'] = created_by
            #     datafram['CRTD_DTTM'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            #     datafram['UPDT_BY'] = " "
            #     datafram['UPDT_DTTM'] = " "

            csv_buffer = datafram.to_csv(sep=target["delimiter"],
                                        encoding=target["encoding"], header=False)

            # Upload the DataFrame as a CSV file to S3
            conn.put_object(Bucket=s3_bucket_name, Key=s3_key, Body=csv_buffer)

        return True
    except Exception as error:
        task_logger.exception("write_to_s3() error: %s", str(error))
        raise error

def write_excel(json_data,datafram,conn,target_path,connection_details):
    """function for s3 write for csv filetype"""
    task_logger.info("s3 write operation for EXCEL filetype started")
    target=json_data["task"]["target"]
    with io.BytesIO() as output:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer: # pylint: disable=abstract-class-instantiated
            datafram.to_excel(writer,header=True, index=False)
        data = output.getvalue()
    if target["operation"] == "replace":
        task_logger.info(REPLACE_OPERATION,target_path+XLSX)
        conn.put_object(Bucket=connection_details["bucket_name"],Body=
        data, Key=target_path+XLSX,ServerSideEncryption='AES256')
    elif target["operation"] == "append":
        # if operation is append
        task_logger.info(APPEND_OPERATION)
        object_exists = check_path(conn,target_path+XLSX,connection_details)
        # checking whether object exists or not
        if object_exists is True:
            #if object in s3 already exists
            task_logger.info(OBJECT_EXISTS,\
            target["file_name"]+XLSX)
            task_logger.info(CREATE_OBJECT,target_path+'_'+file_timestamp+XLSX)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            data, Key=target_path+'_'+file_timestamp+XLSX,
            ServerSideEncryption='AES256')
        else:
            #if object in s3 does not exists
            task_logger.info(OBJECT_NOT_EXISTS,\
            target["file_name"]+XLSX)
            task_logger.info(CREATE_OBJECT,target_path+XLSX)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            data, Key=target_path+XLSX,ServerSideEncryption='AES256')

def write_json(json_data,datafram,conn,target_path,connection_details):
    """function for s3 write for JSON filetype"""
    task_logger.info("s3 write operation for JSON filetype started")
    target=json_data["task"]["target"]
    json_buffer = io.StringIO()
    datafram.to_json(json_buffer,orient='records', index=True)
    # if target["operation"] == "replace":
    #     #if operation is replace
    #     task_logger.info(REPLACE_OPERATION,target_path+JSON)
    conn.put_object(Bucket=connection_details["bucket_name"],Body=
    json_buffer.getvalue(), Key=target_path,ServerSideEncryption='AES256')
    # elif target["operation"] == "append":
    #     # if operation is append
    #     task_logger.info(APPEND_OPERATION)
    #     object_exists = check_path(conn,target_path+JSON,connection_details)
    #     # checking whether object exists or not
    #     if object_exists is True:
    #         #if object in s3 already exists
    #         task_logger.info(OBJECT_EXISTS,\
    #         target["file_name"]+JSON)
    #         task_logger.info(CREATE_OBJECT,target_path+'_'+file_timestamp+JSON)
    #         conn.put_object(Bucket=connection_details["bucket_name"],Body=
    #         json_buffer.getvalue(), Key=target_path+'_'+file_timestamp+JSON,
    #         ServerSideEncryption='AES256')
    #     else:
    #         #if object in s3 does not exists
    #         task_logger.info(OBJECT_NOT_EXISTS,\
    #         target["file_name"]+JSON)
    #         task_logger.info(CREATE_OBJECT,target_path+JSON)
    #         conn.put_object(Bucket=connection_details["bucket_name"],Body=
    #         json_buffer.getvalue(), Key=target_path+JSON,ServerSideEncryption='AES256')

def write_parquet(json_data,datafram,conn,target_path,connection_details):
    """function for s3 write for parquet filetype"""
    task_logger.info("s3 write operation for PARQUET filetype started")
    target=json_data["task"]["target"]
    parquet_buffer = io.BytesIO()
    datafram.astype(str).to_parquet(parquet_buffer,engine='auto', index=False)
    # if target["operation"] == "replace":
        #if operation is replace
    conn.put_object(Bucket=connection_details["bucket_name"],Body=
    parquet_buffer.getvalue(), Key=target_path,ServerSideEncryption='AES256')

# def write_parquet(json_data: dict,conn,s3_bucket_name,s3_key, dataframe, counter) -> bool:
#     """function for s3 write for parquet filetype"""
#     try:
#         target = json_data["task"]["target"]
#         task_logger.info("converting data to Parquet format and uploading to S3")

#         # check = True if target['index'] == "False" else False
#         # # Reset the index and create an 'index' column
#         # dataframe.reset_index(drop=check, inplace=True)

#         if counter == 1:  # If it's the first chunk, write the data to a new Parquet file
#             # if target["audit_columns"] == "active":
#             #     # if audit_columns are active
#             #     dataframe['CRTD_BY'] = "etl_user"
#             #     dataframe['CRTD_DTTM'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#             #     dataframe['UPDT_BY'] = " "
#             #     dataframe['UPDT_DTTM'] = " "

#             # table = pa.Table.from_pandas(dataframe)
#             # pq.write_table(table, s3_key, version='2.0', compression='snappy')
#             table = pa.Table.from_pandas(dataframe)

#             # Write the Parquet file directly to S3
#             with pa.OSFile(s3_key, 'wb') as sink:
#                 pq.write_table(table, sink, version='2.0', compression='snappy')

#         else:  # If it's not the first chunk, read the existing Parquet file and append the new data
#             # if target["audit_columns"] == "active":
#             #     # if audit_columns are active
#             #     dataframe['CRTD_BY'] = "etl_user"
#             #     dataframe['CRTD_DTTM'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#             #     dataframe['UPDT_BY'] = " "
#             #     dataframe['UPDT_DTTM'] = " "

#             # table = pa.Table.from_pandas(dataframe)

#             # # Read the existing Parquet file from S3
#             # existing_table = pq.read_table(s3_key)
#             # updated_table = pa.concat_tables([existing_table, table])
#             # pq.write_table(updated_table, s3_key, version='2.0', compression='snappy')

#             table = pa.Table.from_pandas(dataframe)

#             # Read the existing Parquet file from S3
#             existing_table = pq.read_table(s3_key)
#             updated_table = pa.concat_tables([existing_table, table])

#             # Write the updated Parquet file back to S3
#             with pa.OSFile(s3_key, 'wb') as sink:
#                 pq.write_table(updated_table, sink, version='2.0', compression='snappy')

#         task_logger.info("Parquet conversion and upload to S3 completed")
#         return True
#     except Exception as error:
#         task_logger.exception("write_to_s3_parquet() error: %s", str(error))
#         raise error   

def write_xml(json_data,datafram,conn,target_path,connection_details):
    """function for s3 write for XML filetype"""
    task_logger.info("s3 write operation for XML filetype started")
    target=json_data["task"]["target"]
    xml_buffer = io.BytesIO()
    datafram.to_xml(xml_buffer,index=True)
    if target["operation"] == "replace":
        #if operation is replace
        task_logger.info(REPLACE_OPERATION,target_path+XML)
        conn.put_object(Bucket=connection_details["bucket_name"],Body=
        xml_buffer.getvalue(), Key=target_path+XML,ServerSideEncryption='AES256')
    elif target["operation"] == "append":
        # if operation is append
        task_logger.info(APPEND_OPERATION)
        object_exists = check_path(conn,target_path+XML,connection_details)
        # checking whether object exists or not
        if object_exists is True:
            #if object in s3 already exists
            task_logger.info(OBJECT_EXISTS,\
            target["file_name"]+XML)
            task_logger.info(CREATE_OBJECT,target_path+'_'+file_timestamp+XML)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            xml_buffer.getvalue(), Key=target_path+'_'+file_timestamp+XML,
            ServerSideEncryption='AES256')
        else:
            #if object in s3 does not exists
            task_logger.info(OBJECT_NOT_EXISTS,\
            target["file_name"]+XML)
            task_logger.info(CREATE_OBJECT,target_path+XML)
            conn.put_object(Bucket=connection_details["bucket_name"],Body=
            xml_buffer.getvalue(), Key=target_path+XML,ServerSideEncryption='AES256')

def write(json_data,datafram,config_file_path,task_id,run_id,paths_data,
          file_path,iter_value,counter):
    """ function for ingesting data to S3 bucket based on the inputs in task json"""
    engine_code_path = paths_data["folder_path"]+paths_data["ingestion_path"]
    sys.path.insert(0, engine_code_path)
    #importing audit function from orchestrate script
    module1 = importlib.import_module("engine_code")
    audit = getattr(module1, "audit")
    target=json_data["task"]["target"]
    target["file_name"] = replace_date_placeholders(target['file_name'])
    target["file_path"] = replace_date_placeholders(target['file_path'])
    try:
        task_logger.info("ingest data to S3 initiated")
        conn,connection_details = establish_conn(json_data,'target',config_file_path)
        bucket_name = connection_details['bucket_name']
        status="Pass"
        target_path = target["file_path"]+target["file_name"]
        file_name = target["file_name"]
        filename_wo_ext = os.path.splitext(file_name)[0]
        extension = os.path.splitext(file_name)[1]
        records_per_split = target['target_max_record_count']
        if target["file_type"]=="csv":
            # write_csv(json_data,datafram,conn,target_path,connection_details)
            write_csv(json_data,conn,bucket_name,target_path, datafram, counter)
        elif target["file_type"]=="excel":
            write_excel(json_data,datafram,conn,target_path,connection_details)
            if records_per_split > 0:
                split_large_s3csv_file(conn,bucket_name,target_path,target["file_path"], records_per_split,'.csv')
        elif target["file_type"]=="json":
            write_json(json_data,datafram,conn,target_path,connection_details)
            # if records_per_split > 0:
            #     split_large_json_file_s3(conn,connection_details['bucket_name'], target_path, target["file_path"],
            #                          records_per_split, extension)
        elif target["file_type"]=="parquet":
            write_parquet(json_data,datafram,conn,target_path,connection_details)
            split_large_parquet_file_s3(conn, bucket_name, target_path, target["file_path"], records_per_split, '.parquet')
        elif target["file_type"]=="xml":
            write_xml(json_data,datafram,conn,target_path,connection_details)

        # if records_per_split > 0:
        #     split_large_s3_file(conn,connection_details['bucket_name'],
        #     target_path,target["file_path"]+filename_wo_ext, records_per_split, extension)
        return status
    except Exception as error:
        write_to_txt(task_id,'FAILED',file_path)
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.exception("write() is %s", str(error))
        raise error
