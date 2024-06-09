
"""
This script manages bulk ingestion copying and moving operations from files to
files in all like AWS s3, remote and local file systems and vice versa.
"""
import os
import re
import subprocess
import json
import logging
from datetime import datetime
import stat
import importlib
import paramiko
import boto3
module = importlib.import_module("utility")
decrypt = getattr(module, "decrypt")
ERROR_MSG = "An error occurred:%s"
RCLONE_MSG = "Executing rclone command: %s"
SUCESS_MSG = "File %s task completed successfully"

LCL_SERVER = "Local Server"
AWS_S3 = "AWS S3"
RMT_SERVER = "Remote Server"
ERROR = "Invalid operation. Supported operations are 'copy' and 'move'."
CHECKS = "Above Checks Number Represents The Already Existing Files In The Given Destination...."
TRANSFERRED = "Above Transferred Number Represents The Total Pasted Files \
To The Given Destination...."
FILES = "Files are :"
REMOVED = "rclone configuration file removed."
NOTEXIST = "rclone configuration file does not exist."
task_logger = logging.getLogger('task_logger')

def get_conn_subtype_type(config_path:str) -> dict:
    """reads the connection file name and returns connection details as per
       connection name you pass it through the json"""
    try:
        with open(config_path,'r', encoding='utf-8') as jsonfile:
            task_logger.info("fetching connection details")
            json_data = json.load(jsonfile)
            task_logger.info("reading connection details completed")
            return json_data
    except Exception as error:
        task_logger.exception("get_config_section() is %s.", str(error))
        raise error

def copy_files(json_data,config_file_path,run_id,paths_data):
    """main function to read the parameters from the json and redirecting to the appropriate function or task based on the given parameters 
       copies files from one to the other"""
    try:
        src = json_data["task"]["details"][0]["source"]
        tgt = json_data["task"]["details"][0]["target"]
        src_file_path = None if "file_path" not in src or src["file_path"] in {None,"None","none",""} else \
        src["file_path"]
        tgt_file_path = None if "file_path" not in tgt or tgt["file_path"] in {None,"None","none",""} else \
        tgt["file_path"]
        file_name = None if "files_filter_name" not in src or src["files_filter_name"] in {None,"None","none",""} else \
        src["files_filter_name"]
        sub_folder = None if "subfolder_included" not in src or src["subfolder_included"] in {None,"None","none",""} else \
        src["subfolder_included"]
        operation = None if "operation" not in src or src["operation"] in {None,"None","none",""} else \
        src["operation"]
        tgt_prefix = None if "object_prefix_name" not in tgt or tgt["object_prefix_name"] in {None,"None","none",""} else \
        tgt["object_prefix_name"]
        tgt_sufix = None if "object_sufix_name" not in tgt or tgt["object_sufix_name"] in {None,"None","none",""} else \
        tgt["object_sufix_name"]
        src_connection_name = src["connection_name"]
        tgt_connection_name = tgt["connection_name"]
        source = get_conn_subtype_type(config_file_path+src_connection_name+".json")
        target = get_conn_subtype_type(config_file_path+tgt_connection_name+".json")
        if source['connection_subtype']== LCL_SERVER and target['connection_subtype'] == LCL_SERVER:
            value,source_count , copied_count = local_to_local_copy_files(src_file_path, tgt_file_path,
            file_name, sub_folder, tgt_prefix,tgt_sufix,operation)
        elif source['connection_subtype'] == LCL_SERVER and target['connection_subtype'] == AWS_S3:
            access_key = decrypt(target['connection_details']['access_key'],paths_data)
            secret_key = decrypt(target['connection_details']['secret_access_key'],paths_data)
            bucket_name = target['connection_details']['bucket_name']
            region = target['connection_details']['region_name']
            value,source_count,copied_count = local_to_aws3_copy_files(src_file_path, tgt_file_path, access_key,
            secret_key, region, bucket_name, file_name, sub_folder,
            tgt_prefix, tgt_sufix,operation,run_id)
        elif (source['connection_subtype'] == LCL_SERVER and target['connection_subtype'] == \
            RMT_SERVER):
            hostname = target['connection_details']['hostname']
            user = target['connection_details']['username']
            password = decrypt(target['connection_details']['password'],paths_data)
            port = target['connection_details']['port']
            value,source_count , copied_count = local_to_remote_copy_files(src_file_path, tgt_file_path,
            hostname, user, password, file_name, sub_folder, port, tgt_prefix,
            tgt_sufix,operation,run_id)
        elif source['connection_subtype'] == AWS_S3 and target['connection_subtype'] == AWS_S3:
            src_access_key = decrypt(source['connection_details']['access_key'],paths_data)
            src_secret_key = decrypt(source['connection_details']['secret_access_key'],paths_data)
            src_bucket_name = source['connection_details']['bucket_name']
            src_region = source['connection_details']['region_name']
            tgt_access_key = decrypt(target['connection_details']['access_key'],paths_data)
            tgt_secret_key = decrypt(target['connection_details']['secret_access_key'],paths_data)
            tgt_bucket_name = target['connection_details']['bucket_name']
            tgt_region = target['connection_details']['region_name']
            value,source_count,copied_count = aws3_to_aws3_copy_files(src_bucket_name, src_file_path,
            tgt_bucket_name, tgt_file_path, src_access_key, src_secret_key,
            src_region, tgt_access_key, tgt_secret_key, tgt_region, file_name,
            sub_folder, tgt_prefix, tgt_sufix,operation,run_id)
        elif source['connection_subtype'] == AWS_S3 and target['connection_subtype'] == LCL_SERVER:
            src_access_key = decrypt(source['connection_details']['access_key'],paths_data)
            src_secret_key = decrypt(source['connection_details']['secret_access_key'],paths_data)
            src_bucket_name = source['connection_details']['bucket_name']
            src_region = source['connection_details']['region_name']
            value,source_count , copied_count = aws3_to_local_copy_files(src_bucket_name, src_file_path,
            src_access_key, src_secret_key, src_region, file_name, sub_folder,
            tgt_file_path, tgt_prefix, tgt_sufix,operation, run_id)
        elif source['connection_subtype'] == AWS_S3 and target['connection_subtype'] == RMT_SERVER:
            src_access_key = decrypt(source['connection_details']['access_key'],paths_data)
            src_secret_key = decrypt(source['connection_details']['secret_access_key'],paths_data)
            src_bucket_name = source['connection_details']['bucket_name']
            src_region = source['connection_details']['region_name']
            hostname = target['connection_details']['hostname']
            user = target['connection_details']['username']
            password = decrypt(target['connection_details']['password'],paths_data)
            port = target['connection_details']['port']
            value,source_count , copied_count = aws3_to_remote_copy_files(src_bucket_name, src_access_key,
            src_secret_key, src_region,src_file_path, file_name,
            sub_folder,tgt_file_path , tgt_prefix, tgt_sufix,operation,hostname,
            user, password, port,run_id)
        elif (source['connection_subtype'] == RMT_SERVER and target['connection_subtype'] ==\
             LCL_SERVER):
            hostname = source['connection_details']['hostname']
            user = source['connection_details']['username']
            password = decrypt(source['connection_details']['password'],paths_data)
            port = source['connection_details']['port']
            value,source_count , copied_count = remote_to_local_copy_files(src_file_path, tgt_file_path,
            hostname, user, password,file_name, sub_folder, port, tgt_prefix,
            tgt_sufix,operation,run_id)
        elif source['connection_subtype'] == RMT_SERVER and target['connection_subtype'] == AWS_S3:
            hostname = source['connection_details']['hostname']
            user = source['connection_details']['username']
            password = decrypt(source['connection_details']['password'],paths_data)
            port = source['connection_details']['port']
            tgt_access_key = decrypt(target['connection_details']['access_key'],paths_data)
            tgt_secret_key = decrypt(target['connection_details']['secret_access_key'],paths_data)
            tgt_bucket_name = target['connection_details']['bucket_name']
            tgt_region = target['connection_details']['region_name']
            value,source_count , copied_count = remote_to_aws3_copy_files(tgt_access_key, tgt_secret_key,
            tgt_region, tgt_bucket_name,src_file_path, file_name, sub_folder,
            tgt_file_path , tgt_prefix, tgt_sufix, operation ,hostname, user,
            password, port,run_id)
        elif (source['connection_subtype'] == RMT_SERVER and target['connection_subtype'] ==\
            RMT_SERVER):
            src_hostname = source['connection_details']['hostname']
            src_user = source['connection_details']['username']
            src_password = decrypt(source['connection_details']['password'],paths_data)
            src_port = source['connection_details']['port']
            tgt_hostname = target['connection_details']['hostname']
            tgt_user = target['connection_details']['username']
            tgt_password = decrypt(target['connection_details']['password'],paths_data)
            tgt_port = target['connection_details']['port']
            value, source_count , copied_count = remote_to_remote_copy_files(src_hostname,src_port,
            src_user,tgt_hostname,tgt_port,tgt_user,src_password,tgt_password,
            src_file_path, file_name,sub_folder,tgt_file_path, tgt_prefix,
            tgt_sufix,operation,run_id)
        return value , source_count , copied_count
    except Exception as e:
        task_logger.error(ERROR_MSG, str(e))
        raise e

def local_get_files_in_directory(directory):
    """
    Get a list of files in the specified directory.
    """
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            files.append(os.path.join(root, filename))
    return files

def local_get_file_attributes(file_path):
    """
    Get file attributes such as size and modification time.
    """
    stat_info = os.stat(file_path)
    return stat_info.st_size, stat_info.st_mtime

def establish_s3_connection(access_key, secret_key, region):
    """
    Establish connection to AWS S3 using Boto3.
    """
    return boto3.client('s3', region_name=region, aws_access_key_id=access_key,
    aws_secret_access_key=secret_key)

def s3_get_files_in_directory(s3_client, bucket_name, directory):
    """
    Get a list of files in the specified directory of the S3 bucket.
    """
    files = []
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=directory)
    objects = response.get('Contents', [])
    for obj in objects:
        files.append(obj['Key'])
    return files

def s3_get_file_attributes(s3_client, bucket_name, file_key):
    """
    Get file size from S3 bucket.
    """
    response = s3_client.head_object(Bucket=bucket_name, Key=file_key)
    return response['ContentLength']

def establish_conn_for_remoteserver(hostname, user, password, port):
    """establishes connection for the snowflake database
    you pass it through the json"""
    try:
        # create ssh client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=hostname,port=port,username=user,password=password)
        return ssh_client
    except Exception as error:
        task_logger.error(ERROR_MSG, str(error))
        raise error

def remote_get_file_attributes(sftp_client, file_path):
    """
    Get file attributes such as size and modification time.
    """
    stat_info = sftp_client.stat(file_path)
    return {
        'path': file_path,
        'size': stat_info.st_size,
        'last_modified': stat_info.st_mtime
    }

def remote_get_files_in_directory(sftp, src_file_path):
    """
    Get a list of files in the specified directory and its subdirectories.
    """
    all_files = []
    def list_files_recursively(remote_path):
        files = sftp.listdir_attr(remote_path)
        for file_attr in files:
            file_path = os.path.join(remote_path, file_attr.filename)
            if stat.S_ISDIR(file_attr.st_mode):
                list_files_recursively(file_path)
            else:
                all_files.append(file_path)
    list_files_recursively(src_file_path)
    return all_files

def local_construct_new_filename(base_name, tgt_prefix, tgt_sufix):
    """local_construct_new_filename"""
    new_filename = base_name
    if tgt_prefix:
        new_filename = tgt_prefix + new_filename
    if tgt_sufix:
        sufix_date = datetime.now().strftime("%Y-%m-%d") if tgt_sufix == 'YY-MM-DD' else tgt_sufix
        new_filename = os.path.splitext(new_filename)[0] + sufix_date +\
         os.path.splitext(new_filename)[1]
    return new_filename

def local_rename_file(new_file, new_filename):
    """local_rename_file"""
    os.rename(new_file, os.path.join(os.path.dirname(new_file), new_filename))

def log_local_files_transferred( initial_files, initial_file_attributes,
    final_files, tgt_prefix, tgt_sufix):
    """log_local_files_transferred"""
    if tgt_prefix or tgt_sufix:
        for new_file in final_files:
            base_name = os.path.basename(new_file)
            if new_file not in initial_files:
                new_filename = local_construct_new_filename(base_name, tgt_prefix, tgt_sufix)
                local_rename_file(new_file, new_filename)
            else:
                new_attributes = local_get_file_attributes(new_file)
                initial_attributes = initial_file_attributes.get(new_file)
                if initial_attributes and new_attributes != initial_attributes:
                    new_filename = local_construct_new_filename(base_name, tgt_prefix, tgt_sufix)
                    local_rename_file(new_file, new_filename)

def s3_construct_new_filename(base_name, tgt_prefix, tgt_sufix):
    """s3_construct_new_filename"""
    new_filename = base_name
    if tgt_prefix:
        new_filename = tgt_prefix + new_filename
    if tgt_sufix:
        suffix_date = datetime.now().strftime("%Y-%m-%d") if tgt_sufix == 'YY-MM-DD' else tgt_sufix
        new_filename = os.path.splitext(new_filename)[0] + suffix_date +\
         os.path.splitext(new_filename)[1]
    return new_filename

def s3_rename_file(s3_client, bucket_name, old_file, new_file_key):
    """s3_rename_file"""
    s3_client.copy_object(Bucket=bucket_name, CopySource={'Bucket':
     bucket_name, 'Key': old_file}, Key=new_file_key)
    s3_client.delete_object(Bucket=bucket_name, Key=old_file)

def s3_handle_file_changes(s3_client, bucket_name, initial_files,
     initial_file_attributes, final_files, tgt_prefix, tgt_sufix):
    """s3_handle_file_changes"""
    for new_file in final_files:
        base_name = os.path.basename(new_file)
        file_dir = os.path.dirname(new_file)
        new_file_key = os.path.join(file_dir, s3_construct_new_filename(base_name,
        tgt_prefix, tgt_sufix))
        if new_file not in initial_files:
            s3_rename_file(s3_client, bucket_name, new_file, new_file_key)
        elif new_file in initial_files:
            new_size = s3_get_file_attributes(s3_client, bucket_name, new_file)
            initial_size = initial_file_attributes.get(new_file)
            if initial_size and new_size != initial_size:
                s3_rename_file(s3_client, bucket_name, new_file, new_file_key)

def s3_track_and_rename_files(s3_client, bucket_name, initial_files,
    initial_file_attributes, final_files, tgt_prefix, tgt_sufix):
    """s3_track_and_rename_files"""
    s3_handle_file_changes(s3_client, bucket_name, initial_files,
     initial_file_attributes, final_files, tgt_prefix, tgt_sufix)

def remote_construct_new_filename(base_name, tgt_prefix, tgt_sufix):
    """remote_construct_new_filename"""
    new_filename = base_name
    if tgt_prefix:
        new_filename = tgt_prefix + new_filename
    if tgt_sufix:
        suffix_date = datetime.now().strftime("%Y-%m-%d") if tgt_sufix == 'YY-MM-DD' else tgt_sufix
        new_filename = os.path.splitext(new_filename)[0] + suffix_date +\
        os.path.splitext(new_filename)[1]
    return new_filename

def remote_rename_file(sftp, new_file, target_file_path,_, final_files):
    """remote_rename_file"""
    if target_file_path in final_files:
        sftp.remove(target_file_path)
    sftp.rename(new_file, target_file_path)

def remote_track_and_rename_files(sftp, initial_files, initial_file_attributes,
    final_files, tgt_prefix, tgt_sufix):
    """remote_track_and_rename_files"""
    for new_file in final_files:
        base_name = os.path.basename(new_file)
        file_dir = os.path.dirname(new_file)
        new_filename = remote_construct_new_filename(base_name, tgt_prefix, tgt_sufix)
        target_file_path = os.path.join(file_dir, new_filename)
        if new_file not in initial_files:
            remote_rename_file(sftp, new_file, target_file_path, task_logger,final_files)
        else:
            initial_attributes = initial_file_attributes.get(new_file)
            new_attributes = remote_get_file_attributes(sftp, new_file)
            if initial_attributes and new_attributes != initial_attributes:
                remote_rename_file(sftp, new_file, target_file_path, task_logger,final_files)

def audit_count(stdout,command):
    # Initialize copied count and source file count
    copied_count = None
    source_count = None
    # Define regular expression patterns to match the transferred counts and checks counts
    transferred_pattern = r"Transferred:\s+(\d+)\s+/\s+(\d+)"

    try:
        if command == "copy":
            checks_pattern = r"Checks:\s+(\d+)\s+/\s+(\d+)"

            # Find all matches for transferred counts and checks counts
            transferred_matches = re.findall(transferred_pattern, stdout)
            checks_matches = re.findall(checks_pattern, stdout)

            # If Transferred: is present, extract the copied count from it
            if transferred_matches:
                copied_count, source_count = transferred_matches[-1]
                task_logger.info("Files Copied Count From Source: %s", source_count)
                task_logger.info("Files Pasted Count To Target : %s", copied_count)           

            # If neither Transferred: nor Checks: is present
            if not transferred_matches and checks_matches:
                _, source_count = checks_matches[-1]
                task_logger.info("Files Copied Count From Source: %s", source_count)
                copied_count = f"Files Are Not Pasted Because Those Files Are Aalready Present In The Target"
                task_logger.info("Files Pasted Count To Target : %s", copied_count) 

        elif command == "move":
            checks_pattern = r"Deleted:\s+(\d+)"

            # Find all matches for transferred counts and checks counts
            transferred_matches = re.findall(transferred_pattern, stdout)
            checks_matches = re.findall(checks_pattern, stdout)

            # If Transferred: is present, extract the copied count from it
            if transferred_matches:
                copied_count, source_count = transferred_matches[-1]
                task_logger.info("Selected Files Count To Move From Source : %s", source_count)
                task_logger.info("Files Moved count To Target : %s", copied_count)           

            # If neither Transferred: nor Checks: is present
            if not transferred_matches and checks_matches:
                source_count = checks_matches[-1]
                task_logger.info("Selected Files Count To Move From Source : %s", source_count)
                copied_count = f"Files Are Not Moved Or Transferred Because Those Files Are Aalready Present In The Target"
                task_logger.info("Files Moved count To Target : %s", copied_count)
        return source_count , copied_count
    except Exception as e:
        task_logger.error(ERROR_MSG, str(e))

def local_to_local_copy_files(src_path, tgt_path, file_name, sub_folder,
     tgt_prefix,tgt_sufix,operation):
    """local_to_local_copy_files"""
    try:
        # Get the list of files in the target directory before copying
        initial_files = local_get_files_in_directory(tgt_path)
        initial_file_attributes = {file: local_get_file_attributes(file) for file in initial_files}
        operation = operation.lower()
        if operation == "copy":
            command = "copy"
        elif operation == "move":
            command = "move"
        else:
            raise ValueError(ERROR)
        # Construct the rclone command
        rclone_cmd = [
            "rclone", command,
            "--include",  file_name,
            "--progress",
            "--stats", "1s",  # Show stats every second
        ]
        # If sub_folder is "no", limit recursion depth to 1
        if sub_folder.lower() == "no":
            rclone_cmd += ["--max-depth", "1"]
        rclone_cmd += [src_path, tgt_path]
        # Log the rclone command being executed
        task_logger.info(RCLONE_MSG, ' '.join(rclone_cmd))
        # Execute the rclone command
        completed_process = subprocess.run(rclone_cmd, check=True, capture_output=True, text=True)
        # Log the stdout of the completed process
        task_logger.info(completed_process.stdout)
        source_count , copied_count = audit_count(completed_process.stdout,command)
        task_logger.info(CHECKS)
        task_logger.info(TRANSFERRED)
        # Get the list of files in the target directory after copying
        final_files = local_get_files_in_directory(tgt_path)
        task_logger.info(FILES)
        for file_path in final_files:
            if file_path not in initial_files:
                task_logger.info(file_path)
        if tgt_prefix or tgt_sufix:
            # Log the files transferred or pasted
            log_local_files_transferred( initial_files,initial_file_attributes,
            final_files, tgt_prefix, tgt_sufix)
        task_logger.info(SUCESS_MSG,command)
        return True ,source_count , copied_count
    except subprocess.CalledProcessError as e:
        task_logger.error(ERROR_MSG, str(e))
        return False


def local_to_aws3_copy_files(src_path, tgt_path, access_key, secret_key,region,
    bucket_name,file_name,sub_folder,tgt_prefix, tgt_sufix,operation,run_id):
    """local_to_aws3_copy_files"""
    def generate_rclone_config(access_key, secret_key, region, bucket_name):
        config = f"""
        [{bucket_name}]
        type = s3
        provider = AWS
        env_auth = false
        access_key_id = {access_key}
        secret_access_key = {secret_key}
        region = {region}
        bucket = {bucket_name}
        """
        with open(f"rclone_config_local_aws_tgt_{run_id}.conf", "w", encoding = "utf-8") as f:
            f.write(config)
    try:
        # Generate Rclone configuration file
        generate_rclone_config(access_key, secret_key, region, bucket_name)
        # Establish connection to AWS S3
        s3_client = establish_s3_connection(access_key, secret_key, region)
        # Get the list of files in the target directory before copying
        initial_files = s3_get_files_in_directory(s3_client, bucket_name, tgt_path)
        initial_file_attributes = {file: s3_get_file_attributes(s3_client,
         bucket_name, file) for file in initial_files}
        operation = operation.lower()
        if operation == "copy":
            command = "copy"
        elif operation == "move":
            command = "move"
        else:
            raise ValueError(ERROR)
        # Construct the rclone command
        rclone_cmd = [
            "rclone", command,
            "--include", file_name,
            "--progress",
            "--stats", "1s",  # Show stats every second
            "--config", f"rclone_config_local_aws_tgt_{run_id}.conf"
        ]
        # If sub_folder is "no", limit recursion depth to 1
        if sub_folder.lower() == "no":
            rclone_cmd += ["--max-depth", "1"]
        rclone_cmd += [src_path, f'{bucket_name}:{bucket_name}/{tgt_path}']
        # Log the rclone command being executed
        task_logger.info(RCLONE_MSG, ' '.join(rclone_cmd))
        # Execute the rclone command
        completed_process = subprocess.run(rclone_cmd, check=True, capture_output=True, text=True)
        # Log the stdout of the completed process
        task_logger.info(completed_process.stdout)
        source_count , copied_count = audit_count(completed_process.stdout,command)
        task_logger.info(CHECKS)
        task_logger.info(TRANSFERRED)
        # Get the list of files in the target directory after copying
        final_files = s3_get_files_in_directory(s3_client, bucket_name, tgt_path)
        # Log the files transferred or pasted
        task_logger.info("Files pasted are:")
        for file_path in final_files:
            if file_path not in initial_files:
                task_logger.info(file_path)
        if tgt_prefix or tgt_sufix:
            # Track newly added files from the source in the target directory
            #  and rename them with tgt_prefix and tgt_sufix
            s3_track_and_rename_files(s3_client, bucket_name, initial_files,
            initial_file_attributes, final_files, tgt_prefix, tgt_sufix)
        # Remove the rclone configuration file after the operation is completed
        if os.path.exists(f"rclone_config_local_aws_tgt_{run_id}.conf"):
            os.remove(f"rclone_config_local_aws_tgt_{run_id}.conf")
            task_logger.info(REMOVED)
        else:
            task_logger.warning(NOTEXIST)
        task_logger.info(SUCESS_MSG,command)
        return True , source_count , copied_count 
    except Exception as e:
        task_logger.error(ERROR_MSG, str(e))
        return False


def local_to_remote_copy_files(src_path, tgt_path, hostname, user, password,
    file_name, sub_folder, port, tgt_prefix, tgt_sufix,operation,run_id):
    """local_to_remote_copy_files"""
    try:
        def generate_rclone_config_remote(hostname, user, password, port):
            obscured_password = subprocess.run(["rclone", "obscure", password],
            capture_output=True, text=True, check=False).stdout.strip()
            config = f"""
            [{hostname}]
            type = sftp
            host = {hostname}
            port = {port}
            user = {user}
            pass = {obscured_password}
            """
            with open(f"rclone_config_local_remote_tgt_{run_id}.conf", "w",encoding = "utf-8") as f:
                f.write(config)
        # Generate Rclone configuration file for remote server
        generate_rclone_config_remote(hostname, user, password, port)
        conn = establish_conn_for_remoteserver(hostname, user, password, port)
        sftp = conn.open_sftp()
        # Get the list of files in the target directory before copying
        initial_files = remote_get_files_in_directory(sftp, tgt_path)
        initial_file_attributes = {file: remote_get_file_attributes(sftp,
         file) for file in initial_files}
        operation = operation.lower()
        if operation == "copy":
            command = "copy"
        elif operation == "move":
            command = "move"
        else:
            raise ValueError(ERROR)
        # Construct the rclone command
        rclone_cmd = [
            "rclone", command,
            "--include", file_name,
            "--progress",
            "--stats", "1s",  # Show stats every second
            "--config", f"rclone_config_local_remote_tgt_{run_id}.conf"
        ]
        if sub_folder.lower() == "no":
            # If sub_folder is "no", limit recursion depth to 1
            rclone_cmd += ["--max-depth", "1"]
        rclone_cmd += [src_path, f'{hostname}:{tgt_path}']
        # Log the rclone command being executed
        task_logger.info(RCLONE_MSG, ' '.join(rclone_cmd))
        # Execute the rclone command
        completed_process = subprocess.run(rclone_cmd, check=True, capture_output=True, text=True)
        # Log the stdout of the completed process
        task_logger.info(completed_process.stdout)
        source_count , copied_count = audit_count(completed_process.stdout,command)
        task_logger.info(CHECKS)
        task_logger.info(TRANSFERRED)
        # Get the list of files in the target directory after copying
        final_files = remote_get_files_in_directory(sftp, tgt_path)
        # Log the files transferred or pasted
        task_logger.info(FILES)
        for file_path in final_files:
            if file_path not in initial_files:
                task_logger.info(file_path)
        if tgt_prefix or tgt_sufix:
            # Track newly added files from the source in the target
            # directory and rename them with tgt_prefix and tgt_sufix
            remote_track_and_rename_files(sftp, initial_files, initial_file_attributes,
             final_files, tgt_prefix, tgt_sufix)
        # Remove the rclone configuration file after the operation is completed
        if os.path.exists(f"rclone_config_local_remote_tgt_{run_id}.conf"):
            os.remove(f"rclone_config_local_remote_tgt_{run_id}.conf")
            task_logger.info("rclone configuration file for remote server removed.")
        else:
            task_logger.warning("rclone configuration file for remote server does not exist.")
        task_logger.info(SUCESS_MSG,command)
        return True, source_count , copied_count
    except subprocess.CalledProcessError as e:
        task_logger.error(ERROR_MSG, str(e))
        return False


def aws3_to_aws3_copy_files(src_bucket_name, src_file_path,tgt_bucket_name,
tgt_file_path, src_access_key, src_secret_key, src_region,tgt_access_key,
tgt_secret_key, tgt_region, file_name, sub_folder, tgt_prefix, tgt_sufix,
operation,run_id):
    """aws3_to_aws3_copy_files"""
    try:
        def generate_rclone_config(access_key, secret_key, region, bucket_name, config_filename):
            config = f"""
            [{bucket_name}]
            type = s3
            provider = AWS
            env_auth = false
            access_key_id = {access_key}
            secret_access_key = {secret_key}
            region = {region}
            bucket = {bucket_name}
            """
            with open(config_filename, "w", encoding = "utf-8") as f:
                f.write(config)
        # Generate Rclone configuration files for source and destination buckets
        generate_rclone_config(src_access_key, src_secret_key, src_region,
        src_bucket_name, f"rclone_config_aws_src_{run_id}.conf")
        generate_rclone_config(tgt_access_key, tgt_secret_key, tgt_region,
        tgt_bucket_name, f"rclone_config_aws_dest_{run_id}.conf")
        # Establish connection to AWS S3
        s3_client = establish_s3_connection(tgt_access_key, tgt_secret_key, tgt_region)
        # Get the list of files in the target directory before copying
        initial_files = s3_get_files_in_directory(s3_client, tgt_bucket_name, tgt_file_path)
        initial_file_attributes = {file: s3_get_file_attributes(s3_client,
         tgt_bucket_name, file) for file in initial_files}
        operation = operation.lower()
        if operation == "copy":
            command = "copy"
        elif operation == "move":
            command = "move"
        else:
            raise ValueError(ERROR)
        # Construct the rclone command
        rclone_cmd = [
            "rclone", command,
            "--include", file_name,
            "--progress",
            "--stats", "1s",  # Show stats every second
            "--config", f"rclone_config_aws_src_{run_id}.conf",
            "--config", f"rclone_config_aws_dest_{run_id}.conf",
            f'{src_bucket_name}:{src_bucket_name}/{src_file_path}',
            f'{tgt_bucket_name}:{tgt_bucket_name}/{tgt_file_path}'
        ]
        # If sub_folder is "no", limit recursion depth to 1
        if sub_folder.lower() == "no":
            rclone_cmd += ["--max-depth", "1"]
        # Log the rclone command being executed
        task_logger.info(RCLONE_MSG, ' '.join(rclone_cmd))
        # Execute the rclone command
        completed_process = subprocess.run(rclone_cmd, check=True, capture_output=True, text=True)
        # Log the stdout of the completed process
        task_logger.info(completed_process.stdout)
        source_count , copied_count = audit_count(completed_process.stdout,command)
        task_logger.info(CHECKS)
        task_logger.info(TRANSFERRED)
        # Get the list of files in the target directory after copying
        final_files = s3_get_files_in_directory(s3_client, tgt_bucket_name, tgt_file_path)
        # Log the files transferred or pasted
        task_logger.info(FILES)
        for file_path in final_files:
            if file_path not in initial_files:
                task_logger.info(file_path)
        if tgt_prefix or tgt_sufix:
            # Track newly added files from the source in the target directory
            #  and rename them with tgt_prefix and tgt_sufix
            s3_track_and_rename_files(s3_client, tgt_bucket_name, initial_files,
             initial_file_attributes, final_files, tgt_prefix, tgt_sufix)
        # Remove the temporary rclone configuration files after the operation is completed
        for config_file in [f"rclone_config_aws_src_{run_id}.conf",
            f"rclone_config_aws_dest_{run_id}.conf"]:
            if os.path.exists(config_file):
                os.remove(config_file)
                task_logger.info("%s removed.",config_file)
            else:
                task_logger.warning("%s does not exist.",config_file)
        task_logger.info(SUCESS_MSG,command)
        return True ,source_count , copied_count
    except Exception as e:
        task_logger.error(ERROR_MSG, str(e))
        return False


def aws3_to_local_copy_files(src_bucket_name, src_file_path, src_access_key,
    src_secret_key, src_region, file_name, sub_folder,tgt_path ,
    tgt_prefix, tgt_sufix,operation,run_id):
    """aws3_to_local_copy_files"""
    try:
        def generate_rclone_config(access_key, secret_key, region, bucket_name, config_filename):
            config = f"""
            [{bucket_name}]
            type = s3
            provider = AWS
            env_auth = false
            access_key_id = {access_key}
            secret_access_key = {secret_key}
            region = {region}
            bucket = {bucket_name}
            """
            with open(config_filename, "w", encoding = 'utf-8') as f:
                f.write(config)
        # Generate Rclone configuration files for source and destination buckets
        generate_rclone_config(src_access_key, src_secret_key, src_region,
         src_bucket_name, f"rclone_config_aws_to_local{run_id}.conf")
        # Get the list of files in the target directory before copying
        initial_files = local_get_files_in_directory(tgt_path)
        initial_file_attributes = {file: local_get_file_attributes(file) for file in initial_files}
        operation = operation.lower()
        if operation == "copy":
            command = "copy"
        elif operation == "move":
            command = "move"
        else:
            raise ValueError(ERROR)
        # Construct the rclone command
        rclone_cmd = [
            "rclone", command,
            "--include", file_name,
            "--progress",
            "--stats", "1s",  # Show stats every second
            "--config", f"rclone_config_aws_to_local{run_id}.conf"
        ]
        # If sub_folder is "no", limit recursion depth to 1
        if sub_folder.lower() == "no":
            rclone_cmd += ["--max-depth", "1"]
        rclone_cmd += [f'{src_bucket_name}:{src_bucket_name}/{src_file_path}',tgt_path]
        # Log the rclone command being executed
        task_logger.info(RCLONE_MSG, ' '.join(rclone_cmd))
        # Execute the rclone command
        completed_process = subprocess.run(rclone_cmd, check=True, capture_output=True, text=True)
        # Log the stdout of the completed process
        task_logger.info(completed_process.stdout)
        source_count , copied_count = audit_count(completed_process.stdout,command)
        task_logger.info(CHECKS)
        task_logger.info(TRANSFERRED)
        # Get the list of files in the target directory after copying
        final_files = local_get_files_in_directory(tgt_path)
        # Log the files transferred or pasted
        task_logger.info(FILES)
        for file_path in final_files:
            if file_path not in initial_files:
                task_logger.info(file_path)
        if tgt_prefix or tgt_sufix:
            # Log the files transferred or pasted
            log_local_files_transferred( initial_files,initial_file_attributes,
             final_files, tgt_prefix, tgt_sufix)
        # Remove the temporary rclone configuration files after the operation is completed
        if os.path.exists(f"rclone_config_aws_to_local{run_id}.conf"):
            os.remove(f"rclone_config_aws_to_local{run_id}.conf")
            task_logger.info(REMOVED)
        else:
            task_logger.warning(NOTEXIST)
        task_logger.info(SUCESS_MSG,command)
        return True , source_count , copied_count
    except Exception as e:
        task_logger.error(ERROR_MSG, str(e))
        return False


def aws3_to_remote_copy_files(src_bucket_name, src_access_key, src_secret_key,
    src_region,src_file_path, file_name, sub_folder,tgt_file_path , tgt_prefix,
    tgt_sufix,operation,hostname, user, password, port,run_id):
    """aws3_to_remote_copy_files"""
    try:
        def generate_rclone_config(access_key, secret_key, region,
            bucket_name, hostname, user, password, port, config_filename):
            obscured_password = subprocess.run(["rclone", "obscure", password
            ], capture_output=True, text=True, check=False).stdout.strip()

            config = f"""
            [{bucket_name}]
            type = s3
            provider = AWS
            env_auth = false
            access_key_id = {access_key}
            secret_access_key = {secret_key}
            region = {region}
            bucket = {bucket_name}
            [{hostname}]
            type = sftp
            host = {hostname}
            port = {port}
            user = {user}
            pass = {obscured_password}
            """
            with open(config_filename, "w", encoding = "utf-8") as f:
                f.write(config)
        # Generate Rclone configuration file
        generate_rclone_config(src_access_key, src_secret_key, src_region,
        src_bucket_name, hostname, user, password, port,
        f'combined_rclone_s3_to_remote_{run_id}.conf')
        conn = establish_conn_for_remoteserver(hostname, user, password, port)
        sftp = conn.open_sftp()
        # Get the list of files in the target directory before copying
        initial_files = remote_get_files_in_directory(sftp, tgt_file_path)
        initial_file_attributes = {file: remote_get_file_attributes(sftp, file)
         for file in initial_files}
        operation = operation.lower()
        if operation == "copy":
            command = "copy"
        elif operation == "move":
            command = "move"
        else:
            raise ValueError(ERROR)
        # Construct the rclone command
        rclone_cmd = [
            "rclone", command,
            "--include", file_name,
            "--progress",
            "--stats", "1s",  # Show stats every second
            "--config", f'combined_rclone_s3_to_remote_{run_id}.conf',
            f'{src_bucket_name}:{src_bucket_name}/{src_file_path}',
            f'{hostname}:{tgt_file_path}'
        ]
        # If sub_folder is "no", limit recursion depth to 1
        if sub_folder.lower() == "no":
            rclone_cmd += ["--max-depth", "1"]
        # Log the rclone command being executed
        task_logger.info(RCLONE_MSG, ' '.join(rclone_cmd))
        # Execute the rclone command
        completed_process = subprocess.run(rclone_cmd, check=True, capture_output=True, text=True)
        # Log the stdout of the completed process
        task_logger.info(completed_process.stdout)
        source_count , copied_count = audit_count(completed_process.stdout,command)
        task_logger.info(CHECKS)
        task_logger.info(TRANSFERRED)
        # Get the list of files in the target directory after copying
        final_files = remote_get_files_in_directory(sftp, tgt_file_path)
        # Log the files transferred or pasted
        task_logger.info(FILES)
        for file_path in final_files:
            if file_path not in initial_files:
                task_logger.info(file_path)
        if tgt_prefix or tgt_sufix:
            # Track newly added files from the source in the target
            #  directory and rename them with tgt_prefix and tgt_sufix
            remote_track_and_rename_files(sftp, initial_files,
             initial_file_attributes, final_files, tgt_prefix, tgt_sufix)
        # Remove the temporary rclone configuration files after the operation is completed
        if os.path.exists(f'combined_rclone_s3_to_remote_{run_id}.conf'):
            os.remove(f'combined_rclone_s3_to_remote_{run_id}.conf')
            task_logger.info(REMOVED)
        else:
            task_logger.warning(NOTEXIST)
        task_logger.info(SUCESS_MSG,command)
        return True , source_count , copied_count
    except Exception as e:
        task_logger.error(ERROR_MSG, str(e))
        return False


def remote_to_local_copy_files(src_path, tgt_path, hostname, user,
    password, file_name, sub_folder, port, tgt_prefix, tgt_sufix,
    operation,run_id):
    """remote_to_local_copy_files"""
    try:
        def generate_rclone_config_remote(hostname, user, password, port):
            obscured_password = subprocess.run(["rclone", "obscure", password],
             capture_output=True, text=True, check=False).stdout.strip()
            config = f"""
            [{hostname}]
            type = sftp
            host = {hostname}
            port = {port}
            user = {user}
            pass = {obscured_password}
            """
            with open(f"rclone_config_local_remote_src_{run_id}.conf", "w",encoding = 'utf-8') as f:
                f.write(config)
        # Generate Rclone configuration file for remote server
        generate_rclone_config_remote(hostname, user, password, port)
        # Get the list of files in the target directory before copying
        initial_files = local_get_files_in_directory(tgt_path)
        initial_file_attributes = {file: local_get_file_attributes(file) for file in initial_files}
        operation = operation.lower()
        if operation == "copy":
            command = "copy"
        elif operation == "move":
            command = "move"
        else:
            raise ValueError(ERROR)
        # Construct the rclone command
        rclone_cmd = [
            "rclone", command,
            "--include", file_name,
            "--progress",
            "--stats", "1s",  # Show stats every second
            "--config", f"rclone_config_local_remote_src_{run_id}.conf"
        ]
        if sub_folder.lower() == "no":
            # If sub_folder is "no", limit recursion depth to 1
            rclone_cmd += ["--max-depth", "1"]
        rclone_cmd += [f'{hostname}:{src_path}',tgt_path]
        # Log the rclone command being executed
        task_logger.info(RCLONE_MSG, ' '.join(rclone_cmd))
        # Execute the rclone command
        completed_process = subprocess.run(rclone_cmd, check=True, capture_output=True, text=True)
        # Log the stdout of the completed process
        task_logger.info(completed_process.stdout)
        source_count , copied_count = audit_count(completed_process.stdout,command)
        task_logger.info(CHECKS)
        task_logger.info(TRANSFERRED)
        # Get the list of files in the target directory after copying
        final_files = local_get_files_in_directory(tgt_path)
        # Log the files transferred or pasted
        task_logger.info(FILES)
        for file_path in final_files:
            if file_path not in initial_files:
                task_logger.info(file_path)
        if tgt_prefix or tgt_sufix:
            # Log the files transferred or pasted
            log_local_files_transferred( initial_files,initial_file_attributes,
             final_files, tgt_prefix, tgt_sufix)
        # Remove the rclone configuration file after the operation is completed
        if os.path.exists(f"rclone_config_local_remote_src_{run_id}.conf"):
            os.remove(f"rclone_config_local_remote_src_{run_id}.conf")
            task_logger.info("rclone configuration file for remote server removed.")
        else:
            task_logger.warning("rclone configuration file for remote server does not exist.")

        task_logger.info(SUCESS_MSG,command)
        return True , source_count , copied_count
    except subprocess.CalledProcessError as e:
        task_logger.error(ERROR_MSG, str(e))
        return False


def remote_to_aws3_copy_files(tgt_access_key, tgt_secret_key, tgt_region,
tgt_bucket_name,src_file_path, file_name, sub_folder,tgt_file_path , tgt_prefix,
tgt_sufix,operation,hostname, user, password, port,run_id):
    """remote_to_aws3_copy_files"""
    try:
        def generate_rclone_config(tgt_access_key, tgt_secret_key, tgt_region,
        tgt_bucket_name, hostname, user, password, port, config_filename):
            obscured_password = subprocess.run(["rclone", "obscure", password
            ], capture_output=True, text=True, check=False).stdout.strip()

            config = f"""
            [{hostname}]
            type = sftp
            host = {hostname}
            port = {port}
            user = {user}
            pass = {obscured_password}

            [{tgt_bucket_name}]
            type = s3
            provider = AWS
            env_auth = false
            access_key_id = {tgt_access_key}
            secret_access_key = {tgt_secret_key}
            region = {tgt_region}
            bucket = {tgt_bucket_name}
            """

            with open(config_filename, "w", encoding = "utf-8") as f:
                f.write(config)
        # Generate Rclone configuration file
        generate_rclone_config(tgt_access_key, tgt_secret_key, tgt_region,
        tgt_bucket_name, hostname, user, password, port,
        f'combined_rclone_remote_to_s3_{run_id}.conf')
        # Establish connection to AWS S3
        s3_client = establish_s3_connection(tgt_access_key, tgt_secret_key, tgt_region)
        # Get the list of files in the target directory before copying
        initial_files = s3_get_files_in_directory(s3_client, tgt_bucket_name, tgt_file_path)
        initial_file_attributes = {file: s3_get_file_attributes(s3_client,
        tgt_bucket_name, file) for file in initial_files}
        operation = operation.lower()
        if operation == "copy":
            command = "copy"
        elif operation == "move":
            command = "move"
        else:
            raise ValueError(ERROR)
        # Construct the rclone command
        rclone_cmd = [
            "rclone", command,
            "--include", file_name,
            "--progress",
            "--stats", "1s",  # Show stats every second
            "--config", f'combined_rclone_remote_to_s3_{run_id}.conf',
            f'{hostname}:{src_file_path}',
            f'{tgt_bucket_name}:{tgt_bucket_name}/{tgt_file_path}',
        ]
        # If sub_folder is "no", limit recursion depth to 1
        if sub_folder.lower() == "no":
            rclone_cmd += ["--max-depth", "1"]
        # Log the rclone command being executed
        task_logger.info(RCLONE_MSG, ' '.join(rclone_cmd))
        # Execute the rclone command
        completed_process = subprocess.run(rclone_cmd, check=True, capture_output=True, text=True)
        # Log the stdout of the completed process
        task_logger.info(completed_process.stdout)
        source_count , copied_count = audit_count(completed_process.stdout,command)
        task_logger.info(CHECKS)
        task_logger.info(TRANSFERRED)
        # Get the list of files in the target directory after copying
        final_files = s3_get_files_in_directory(s3_client, tgt_bucket_name, tgt_file_path)
        # Log the files transferred or pasted
        task_logger.info(FILES)
        for file_path in final_files:
            if file_path not in initial_files:
                task_logger.info(file_path)
        if tgt_prefix or tgt_sufix:
            # Track newly added files from the source in the target directory
            #  and rename them with tgt_prefix and tgt_sufix
            s3_track_and_rename_files(s3_client, tgt_bucket_name,
            initial_files, initial_file_attributes, final_files, tgt_prefix, tgt_sufix)
        # Remove the temporary rclone configuration files after the operation is completed
        if os.path.exists(f'combined_rclone_remote_to_s3_{run_id}.conf'):
            os.remove(f'combined_rclone_remote_to_s3_{run_id}.conf')
            task_logger.info(REMOVED)
        else:
            task_logger.warning(NOTEXIST)
        task_logger.info(SUCESS_MSG,command)
        return True , source_count , copied_count
    except Exception as e:
        task_logger.error(ERROR_MSG, str(e))
        return False

def remote_to_remote_copy_files(src_hostname,src_port, src_user,tgt_hostname,
tgt_port,tgt_user,src_password,tgt_password,src_file_path, file_name,
sub_folder,tgt_file_path , tgt_prefix, tgt_sufix,operation,run_id):
    """remote_to_remote_copy_files"""
    try:
        def generate_rclone_config(src_hostname,src_port, src_user,tgt_hostname,
        tgt_port,tgt_user,src_password,tgt_password,config_filename):
            src_obscured_password = subprocess.run(["rclone", "obscure", src_password
            ], capture_output=True, text=True, check=False).stdout.strip()
            tgt_obscured_password = subprocess.run(["rclone", "obscure", tgt_password
            ], capture_output=True, text=True, check=False).stdout.strip()

            config = f"""
            [{src_hostname}]
            type = sftp
            host = {src_hostname}
            port = {src_port}
            user = {src_user}
            pass = {src_obscured_password}

            [{tgt_hostname}]
            type = sftp
            host = {tgt_hostname}
            port = {tgt_port}
            user = {tgt_user}
            pass = {tgt_obscured_password}
            """
            with open(config_filename, "w", encoding = "utf-8") as f:
                f.write(config)
        # Generate Rclone configuration file
        generate_rclone_config(src_hostname,src_port, src_user,
        tgt_hostname,tgt_port,tgt_user,src_password,tgt_password,
        f'combined_rclone_remote_to_remote_{run_id}.conf')
        conn = establish_conn_for_remoteserver(tgt_hostname, tgt_user, tgt_password, tgt_port)
        sftp = conn.open_sftp()
        # Get the list of files in the target directory before copying
        initial_files = remote_get_files_in_directory(sftp, tgt_file_path)
        initial_file_attributes = {file: remote_get_file_attributes(sftp,
         file) for file in initial_files}
        operation = operation.lower()
        if operation == "copy":
            command = "copy"
        elif operation == "move":
            command = "move"
        else:
            raise ValueError(ERROR)
        # Construct the rclone command
        rclone_cmd = [
            "rclone", command,
            "--include", file_name,
            "--progress",
            "--stats", "1s",  # Show stats every second
            "--config", f'combined_rclone_remote_to_remote_{run_id}.conf',
            f'{src_hostname}:{src_file_path}',
            f'{tgt_hostname}:{tgt_file_path}'
        ]
        # If sub_folder is "no", limit recursion depth to 1
        if sub_folder.lower() == "no":
            rclone_cmd += ["--max-depth", "1"]
        # Log the rclone command being executed
        task_logger.info(RCLONE_MSG, ' '.join(rclone_cmd))
        # Execute the rclone command
        completed_process = subprocess.run(rclone_cmd, check=True, capture_output=True, text=True)
        # Log the stdout of the completed process
        task_logger.info(completed_process.stdout)
        source_count , copied_count = audit_count(completed_process.stdout,command)
        task_logger.info(CHECKS)
        task_logger.info(TRANSFERRED)
        # Get the list of files in the target directory after copying
        final_files = remote_get_files_in_directory(sftp, tgt_file_path)
        # Log the files transferred or pasted
        task_logger.info(FILES)
        for file_path in final_files:
            if file_path not in initial_files:
                task_logger.info(file_path)
        if tgt_prefix or tgt_sufix:
            # Track newly added files from the source in the
            # target directory and rename them with tgt_prefix and tgt_sufix
            remote_track_and_rename_files(sftp, initial_files,
            initial_file_attributes, final_files, tgt_prefix,
            tgt_sufix)
        # Remove the temporary rclone configuration files after the operation is completed
        if os.path.exists(f'combined_rclone_remote_to_remote_{run_id}.conf'):
            os.remove(f'combined_rclone_remote_to_remote_{run_id}.conf')
            task_logger.info(REMOVED)
        else:
            task_logger.warning(NOTEXIST)
        task_logger.info(SUCESS_MSG,command)
        return True , source_count , copied_count
    except Exception as e:
        task_logger.error(ERROR_MSG, str(e))
        return False
