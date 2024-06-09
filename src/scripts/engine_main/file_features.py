"""script that contains file related function which deals with compression, encryption
decryption, splitting, moving files"""
import os
import gzip
import bz2
import zipfile
import json
import xml.etree.ElementTree as ET
import logging
import tarfile
import shutil
import sys
import importlib
import gnupg
import pandas as pd
import boto3
import paramiko
import snappy

from tracking import bulk_subtask_failed,update_status_file,task_failed
task_logger = logging.getLogger('task_logger')

SPLITTING_FILE = "Splitting %s file initiated"

def audit_failure(arguments):
    """audits failure into audit table and updates status text file"""
    if arguments['json_data']['task_type'] == 'Ingestion':
        task_failed(arguments['task_id'],arguments['text_file_path'],arguments['json_data'],
        arguments['run_id'],arguments['paths_data'],arguments['iter_value'])
    if arguments['json_data']["task_type"] ==  'Bulk Ingestion':
        bulk_subtask_failed(arguments['task_id'],arguments['json_data'],
        arguments['run_id'],arguments['paths_data'],arguments['iter_value'],arguments['group_no'],
        arguments['subtask_no'])
        sys.exit()

def gpg_decrypt_file(file_path, passphrase, local_temp_path_dir):
    """function to decrypt the file using gpg"""
    try:
        # Initialize GPG object
        gpg = gnupg.GPG()
        base_name, ext = os.path.splitext(os.path.basename(file_path))
        # Check if the extension is .gpg and remove it
        if ext == '.gpg':
            final_name = base_name
        else:
            final_name = base_name + ext

        local_temp_path = os.path.join(local_temp_path_dir,final_name)
        with open(file_path, 'rb') as f:
            status = gpg.decrypt_file(f, passphrase=passphrase, output=local_temp_path)
        if status.ok:
            logging.info('decryption successful. decrypted file saved as %s',
            # file_path.rstrip('.gpg')
            local_temp_path)
            # os.remove(file_path.rstrip('.gpg'))
        else:
            # Handle incorrect passphrase here, you can raise a specific
            # exception or take appropriate action.
            logging.warning('decryption failed. Provided passphrase is incorrect.')
        return local_temp_path, status.ok
    except Exception as error:
        logging.exception("gpg_decrypt_file: %s.", str(error))
        raise error


def gpg_encrypt_file(file_path, public_key_path):
    """function to encrypt the file using gpg"""
    try:
        # Initialize GPG object
        gpg = gnupg.GPG()
        # import
        with open(public_key_path, encoding = 'utf-8') as f:
            key_data = f.read()
            import_result = gpg.import_keys(key_data)

        # Read the file content and Encrypt the file using the recipient's public key
        with open(file_path, 'rb') as f:
            status = gpg.encrypt_file(f, recipients =import_result.fingerprints,
            output = file_path + '.gpg')

        if status.ok:
            logging.info('Encryption successful. Encrypted file saved as: %s', file_path + '.gpg')
            os.remove(file_path)
        else:
            # Handle incorrect passphrase here, you can raise a specific
            # exception or take appropriate action.
            logging.warning('encryption failed. \
            Provided public key is incorrect.')
        return status.ok,file_path + '.gpg'
    except Exception as error:
        logging.exception("gpg_encrypt_file: %s.", str(error))
        raise error


def write_json_split(arguments, data, split_number, output_directory,
    compression, target,target_sub_type):
    """Write JSON split to file."""
    try:
        out_file_path = f"{output_directory}_part_{split_number:03}.json"
        task_logger.info("Writing JSON split to file: %s", out_file_path)
        # Write data to JSON file
        try:
            with open(out_file_path, 'w', encoding='utf-8') as split_file:
                json.dump(data, split_file, indent=4)
            task_logger.info("Successfully wrote JSON split to file: %s", out_file_path)
        except (IOError, OSError) as e:
            task_logger.error("Failed to write JSON split to file %s: %s", out_file_path, str(e))
            raise
        # Handle compression and encryption
        try:
            handle_compression_and_encryption(arguments, out_file_path,
            compression, target,target_sub_type)
            task_logger.info("Successfully handled compression and encryption \
            for file: %s", out_file_path)
        except Exception as e:
            task_logger.error("Failed to handle compression and encryption for \
            file %s: %s", out_file_path, str(e))
            raise
    except Exception as e:
        task_logger.exception("write_json_split() encountered an error: %s", str(e))
        audit_failure(arguments)
        raise

def write_parquet_split(arguments, dataframe, split_number, output_directory,
    compression, target,target_sub_type):
    """Write Parquet split to file with error handling."""
    try:
        # Generate the output file path
        out_file_path = f"{output_directory}_part_{split_number:03}.parquet"
        # Write the dataframe to a Parquet file
        dataframe.to_parquet(out_file_path, index=False)
        task_logger.info("Successfully wrote Parquet split to file: %s", out_file_path)
        # Handle compression and encryption if needed
        handle_compression_and_encryption(arguments, out_file_path, compression,
        target,target_sub_type)
    except IOError as e:
        task_logger.error("IO error occurred while writing Parquet file: %s", str(e))
        audit_failure(arguments)
        raise
    except ValueError as e:
        task_logger.error("Value error occurred while writing Parquet file: %s", str(e))
        audit_failure(arguments)
        raise
    except Exception as e:
        task_logger.error("Unexpected error occurred while writing Parquet file: %s", str(e))
        audit_failure(arguments)
        raise

def write_excel_split(arguments, dataframe, split_number, output_directory,
    compression, target,target_sub_type):
    """Write Excel split to file."""
    try:
        out_file_path = f"{output_directory}_part_{split_number:03}.xlsx"
        dataframe.to_excel(out_file_path, index=False)
        handle_compression_and_encryption(arguments, out_file_path, compression,
                                          target,target_sub_type)
    except Exception as e:
        task_logger.error("Failed to write Excel split: %s", str(e))
        audit_failure(arguments)
        raise e

def write_csv_split(arguments, dataframe, split_number, output_directory,
    compression, target, header_value,target_sub_type):
    """Write CSV split to file."""
    try:
        out_file_path = f"{output_directory}_part_{split_number:03}.csv"
        dataframe.to_csv(out_file_path, index=False, header=header_value)
        handle_compression_and_encryption(arguments, out_file_path, compression,
        target,target_sub_type)
    except Exception as e:
        task_logger.error("Failed to write CSV split: %s", str(e))
        audit_failure(arguments)
        raise e

def write_xml_split(arguments,root_element, records, split_number,
    output_directory, compression, target,target_sub_type):
    """Write XML split to file."""
    try:
        split_file_path = f"{output_directory}_part_{split_number:03}.xml"
        split_root = ET.Element(root_element.tag)
        split_root.extend(records)
        tree = ET.ElementTree(split_root)
        tree.write(split_file_path, encoding='utf-8', xml_declaration=True)
        handle_compression_and_encryption(arguments,split_file_path, compression,
        target,target_sub_type)
    except Exception as e:
        task_logger.error("Unexpected error in write_xml_split: %s", str(e))
        audit_failure(arguments)
        raise

def split_json(arguments,input_file, output_directory, records_per_split,
    compression, target,target_sub_type):
    """Split JSON file."""
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            data = json.load(infile)
            total_records = len(data)
            task_logger.info(SPLITTING_FILE,input_file)
            for i in range(0, total_records, records_per_split):
                split_data = data[i:i + records_per_split]
                write_json_split(arguments,split_data, i // records_per_split + 1,
                output_directory, compression, target,target_sub_type)
    except Exception as e:
        task_logger.error("Unexpected error in split_json: %s", str(e))
        audit_failure(arguments)
        raise

def split_parquet(arguments,input_file, output_directory, records_per_split,
    compression, target,target_sub_type):
    """Split Parquet file."""
    try:
        df = pd.read_parquet(input_file)
        total_records = len(df)
        task_logger.info(SPLITTING_FILE,input_file)
        for i in range(0, total_records, records_per_split):
            split_df = df.iloc[i:i + records_per_split]
            write_parquet_split(arguments,split_df, i // records_per_split + 1,
            output_directory, compression, target,target_sub_type)
    except Exception as e:
        task_logger.error("Unexpected error in split_excel: %s", str(e))
        audit_failure(arguments)
        raise

def split_excel(arguments,input_file, output_directory, records_per_split,
    compression, target,target_sub_type):
    """Split Excel file."""
    try:
        df = pd.read_excel(input_file,)
        total_records = len(df)
        task_logger.info(SPLITTING_FILE,input_file)
        for i in range(0, total_records, records_per_split):
            split_df = df.iloc[i:i + records_per_split]
            write_excel_split(arguments,split_df, i // records_per_split + 1,
            output_directory, compression, target,target_sub_type)
    except Exception as e:
        task_logger.error("Unexpected error in split_excel: %s", str(e))
        audit_failure(arguments)
        raise

def split_csv(arguments,input_file, output_directory, records_per_split,
    compression, target, header_value,target_sub_type):
    """Split CSV file."""
    try:
        df = pd.read_csv(input_file, escapechar='\\')
        total_records = len(df)
        task_logger.info(SPLITTING_FILE,input_file)
        for i in range(0, total_records, records_per_split):
            split_df = df.iloc[i:i + records_per_split]
            write_csv_split(arguments,split_df, i // records_per_split + 1,output_directory,
            compression, target, header_value,target_sub_type)
    except Exception as e:
        task_logger.error("Unexpected error in split_csv: %s", str(e))
        audit_failure(arguments)
        raise

def split_xml(arguments, input_file, output_directory, records_per_split,
    compression, target, target_sub_type):
    """Split XML file."""
    try:
        tree = ET.parse(input_file)
        root = tree.getroot()
        total_records = len(root)
        task_logger.info(SPLITTING_FILE,input_file)
        for i in range(0, total_records, records_per_split):
            split_records = root[i:i + records_per_split]
            write_xml_split(arguments, root, split_records, i // records_per_split + 1,
            output_directory, compression, target,target_sub_type)
    except ET.ParseError as e:
        task_logger.error("Error parsing XML file %s: %s",input_file,e)
        audit_failure(arguments)
        return

def split_text(arguments, input_file, output_directory, records_per_split, ext,
               compression, header_value):
    """Split plain text file into smaller parts based on the number of records per split.

    Args:
        arguments (dict): Additional arguments for handling the task.
        input_file (str): Path to the input text file to be split.
        output_directory (str): Directory where the split files will be saved.
        records_per_split (int): Number of records per split file. Use 0 for no splitting.
        ext (str): Extension for the split files.
        compression (str): Compression method to use (if any).
        target (str): Target configuration for the split process.
        header_value (bool): Whether to include the header in each split file.
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            header = read_header_if_needed(infile, header_value)
            split_number = 1

            while True:
                split_file_path = create_split_file_path(output_directory,
                split_number, ext, records_per_split)
                lines_written = write_split_file(infile, split_file_path,
                records_per_split, header)
                if lines_written == 0:
                    break
                handle_compression(arguments, split_file_path, compression)
                split_number += 1
    except Exception as e:
        task_logger.error("Unexpected error in split_text: %s", str(e))
        audit_failure(arguments)
        raise

def read_header_if_needed(infile, header_value):
    """Read the header from the input file if specified.

    Args:
        infile (file object): The input file object.
        header_value (bool): Whether to read the header.

    Returns:
        str: The header line if header_value is True, otherwise None.
    """
    if header_value:
        return infile.readline()
    return None

def create_split_file_path(output_directory, split_number, ext, records_per_split):
    """Create the file path for the split file.

    Args:
        output_directory (str): Directory where the split files will be saved.
        split_number (int): The current split file number.
        ext (str): Extension for the split files.
        records_per_split (int): Number of records per split file.

    Returns:
        str: The path for the split file.
    """
    if records_per_split > 0:
        return f"{output_directory}_part_{split_number:03}{ext}"
    else:
        return f"{output_directory}{ext}"

def write_split_file(infile, split_file_path, records_per_split, header):
    """Write records to the split file.

    Args:
        infile (file object): The input file object.
        split_file_path (str): Path to the split file.
        records_per_split (int): Number of records per split file.
        header (str): The header line to include in each split file if specified.

    Returns:
        int: The number of records written to the split file.
    """
    with open(split_file_path, 'w', encoding='utf-8') as split_file:
        if header:
            split_file.write(header)
        return write_records(infile, split_file, records_per_split)

def write_records(infile, split_file, records_per_split):
    """Write a specified number of records to the split file.

    Args:
        infile (file object): The input file object.
        split_file (file object): The split file object.
        records_per_split (int): Number of records per split file.

    Returns:
        int: The number of records written to the split file.
    """
    record_count = 0
    while record_count < records_per_split or records_per_split == 0:
        line = infile.readline()
        if not line:
            break
        split_file.write(line)
        record_count += 1
    return record_count

def handle_compression(arguments, split_file_path, compression):
    """Handle the compression of the split file if specified.

    Args:
        arguments (dict): Additional arguments for handling the task.
        split_file_path (str): Path to the split file.
        compression (str): Compression method to use (if any).
    """
    if compression:
        compress_file(arguments, split_file_path, compression)


def compress_file(arguments,file_path, compression):
    '''function to compress a file with options for zip, tar, gzip, and bzip'''
    try:
        if compression in ("", None):
            task_logger.info("compression not required")
        else:
            task_logger.info("compression of %s file started",file_path)
        if compression == 'zip':
            with zipfile.ZipFile(f"{file_path}.zip", 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(file_path, arcname=os.path.basename(file_path))
            os.remove(file_path)
            return f"{file_path}.zip"
        if compression == 'tar':
            with tarfile.open(f"{file_path}.tar", 'w') as tarf:
                tarf.add(file_path, arcname=os.path.basename(file_path))
            os.remove(file_path)
            return f"{file_path}.tar"
        if compression == 'bzip':
            with open(file_path, 'rb') as f_in:
                with bz2.BZ2File(f"{file_path}.bz2", 'wb') as f_out:
                    f_out.writelines(f_in)
            os.remove(file_path)
            return f"{file_path}.bz2"
        if compression == 'gzip':
            with open(file_path, 'rb') as f_in:
                with gzip.open(f"{file_path}.gz", 'wb') as f_out:
                    f_out.writelines(f_in)
            os.remove(file_path)
            return f"{file_path}.gz"
        if compression == 'snappy':
            with open(file_path, 'rb') as f_in:
                data = f_in.read()
                compressed_data = snappy.compress(data)
                snappy_file_path = f"{file_path}.snappy"
                with open(snappy_file_path, 'wb') as f_out:
                    f_out.write(compressed_data)
            os.remove(file_path)
            return snappy_file_path
        return file_path
    except Exception as e:
        task_logger.error("Unexpected error in compress_file: %s", str(e))
        audit_failure(arguments)
        raise

def handle_compression_and_encryption(arguments,file_path, compression,
    target,target_sub_type):
    """Handle file compression and encryption if specified."""
    try:
        if compression:
            file_path = compress_file(arguments,file_path, compression)
        if target.get("encryption") == "yes":
            task_logger.info("file encryption started: %s", file_path)
            response,file_path = gpg_encrypt_file(file_path, target["public_key_path"])
            if not response:
                task_logger.info("Encryption failed")
        move_file(arguments, file_path, target,target_sub_type)
        return file_path
    except Exception as e:
        task_logger.error("Unexpected error in handle_compression_and_encryption: %s", str(e))
        audit_failure(arguments)
        raise

def split_large_file_compress_encrypt(arguments,input_file,
    output_directory, records_per_split, ext, target_sub_type,compression=None,
    subtask_target_section = None, header_value=True):
    """Main function to split and optionally compress large files based on the number of records."""
    try:
        if arguments['json_data']["task_type"] ==  "Bulk Ingestion":
            target = subtask_target_section
        if arguments['json_data']["task_type"] ==  "Ingestion":
            target = arguments['json_data']["task"]["target"]
        if ext == '.json':
            split_json(arguments,input_file, output_directory, records_per_split,
            compression, target,target_sub_type)
        elif ext == '.parquet':
            split_parquet(arguments,input_file, output_directory, records_per_split,
            compression, target,target_sub_type)
        elif ext == '.xlsx':
            split_excel(arguments,input_file, output_directory, records_per_split,
            compression, target,target_sub_type)
        elif ext == '.csv':
            split_csv(arguments,input_file, output_directory, records_per_split,
            compression, target,header_value,target_sub_type)
        elif ext == '.xml':
            split_xml(arguments,input_file, output_directory, records_per_split,
            compression, target,target_sub_type)
        else:
            split_text(arguments,input_file, output_directory, records_per_split, ext,
            compression, header_value)
    except Exception as e:
        task_logger.error("Unexpected error in split_large_file_compress_encrypt: %s", str(e))
        audit_failure(arguments)
        raise

def establish_connection(arguments):
    """Establishes connection module dynamically."""
    try:
        paths_data =arguments["paths_data"]
        connection_path = os.path.expanduser(paths_data["folder_path"]) + \
        paths_data['src'] + paths_data["ingestion_path"]
        sys.path.insert(0, connection_path)
        connections = importlib.import_module("connections")
        return connections
    except ImportError as e:
        task_logger.error("Failed to import connections module: %s", str(e))
        bulk_subtask_failed(arguments['task_id'],arguments['json_data'],
        arguments['run_id'],arguments['paths_data'],arguments['iter_value'],arguments['group_no'],
        arguments['subtask_no'])
        update_status_file(arguments['task_id'],'SUCCESS',arguments['text_file_path'])
        raise
    except Exception as e:
        task_logger.error("Unexpected error in establish_connection: %s", str(e))
        audit_failure(arguments)
        raise

def move_file_local(arguments,temp_location, target_file_path,utility):
    """Moves file to local server path, overwriting if necessary."""
    try:
        target_file_name = os.path.basename(temp_location)
        target_file_name = utility.replace_date_placeholders(target_file_name)
        destination = os.path.join(target_file_path, target_file_name)
        if os.path.exists(destination):
            os.remove(destination)
        shutil.move(temp_location, target_file_path)
        task_logger.info("File moved to local server at: %s", destination)
    except FileNotFoundError as e:
        task_logger.error("File not found: %s", str(e))
        audit_failure(arguments)
        raise
    except PermissionError as e:
        task_logger.error("Permission denied: %s", str(e))
        audit_failure(arguments)
        raise
    except NotADirectoryError as e:
        task_logger.error("directory not found: %s", str(e))
        audit_failure(arguments)
        raise
    except Exception as e:
        task_logger.error("Unexpected error in move_file_local: %s", str(e))
        audit_failure(arguments)
        raise

def upload_file_to_s3(arguments,temp_location, target_file_path,utility):
    """Uploads file to AWS S3."""
    try:
        connections = establish_connection(arguments)
        s3_conn, connection_details = connections.establish_conn_for_s3(arguments['json_data'],
        'target', arguments['config_file_path'], arguments['paths_data'])
        bucket_name = connection_details["bucket_name"]
        target_file_name = os.path.basename(temp_location)
        target_file_name = utility.replace_date_placeholders(target_file_name)
        s3_conn.upload_file(temp_location, bucket_name,
        target_file_path + target_file_name)
        os.remove(temp_location)
        task_logger.info("File uploaded to S3 bucket: %s/%s",
        bucket_name, target_file_path + target_file_name)
    except boto3.exceptions.S3UploadFailedError as e:
        task_logger.error("S3 upload failed: %s", str(e))
        audit_failure(arguments)
        raise
    except Exception as e:
        task_logger.error("Unexpected error in upload_file_to_s3: %s", str(e))
        audit_failure(arguments)
        raise

def transfer_file_to_remote(arguments,temp_location,target_file_path,utility):
    """Transfers file to remote server using SFTP."""
    try:
        connections = establish_connection(arguments)
        sftp_conn, _ = connections.establish_conn_for_remoteserver(arguments['json_data'],
        'target', arguments['config_file_path'], arguments['paths_data'])
        sftp_client = sftp_conn.open_sftp()
        target_file_name = os.path.basename(temp_location)
        target_file_name = utility.replace_date_placeholders(target_file_name)
        destination = os.path.join(target_file_path, target_file_name)
        sftp_client.put(temp_location, destination)
        task_logger.info("File uploaded to remote server at: %s", destination)
        os.remove(temp_location)
    except paramiko.SSHException as e:
        task_logger.error("SSH connection error: %s", str(e))
        audit_failure(arguments)
        raise
    except IOError as e:
        task_logger.error("IO error: %s", str(e))
        audit_failure(arguments)
    except Exception as e:
        task_logger.error("Unexpected error in transfer_file_to_remote: %s", str(e))
        bulk_subtask_failed(arguments['task_id'],arguments['json_data'],
        arguments['run_id'],arguments['paths_data'],arguments['iter_value'],arguments['group_no'],
        arguments['subtask_no'])
        update_status_file(arguments['task_id'],'SUCCESS',arguments['text_file_path'])
        raise

def move_file(arguments, temp_location, target,target_sub_type):
    """Transfers the files from temp to target path based on target type."""
    try:
        utility_path=os.path.expanduser(arguments['paths_data']["folder_path"])+\
        arguments['paths_data']['src']+ \
        arguments['paths_data']["ingestion_path"]
        sys.path.insert(0, utility_path)
        utility = importlib.import_module("utility")
        task_logger.info("Transferring file from %s to target location started",temp_location)
        if arguments['json_data']["task_type"] ==  "Bulk Ingestion":
            target_type = target_sub_type
        if arguments['json_data']["task_type"] ==  "Ingestion":
            target_type = target.get("parameter_type")
        target_file_path = target.get("file_path")
        if target_type == "Local Server":
            move_file_local(arguments,temp_location, target_file_path,utility)
        elif target_type == "AWS S3":
            upload_file_to_s3(arguments,temp_location, target_file_path,utility)
        elif target_type == "Remote Server":
            transfer_file_to_remote(arguments,temp_location, target_file_path,utility)
        else:
            task_logger.error("Invalid target type. Supported types: Local Server, \
            AWS S3, Remote Server")
    except Exception as error:
        task_logger.exception("move_file() failed with error: %s", str(error))
        audit_failure(arguments)
        raise
