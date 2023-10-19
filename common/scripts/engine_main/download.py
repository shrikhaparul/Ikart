"""script which has all the definitions for master_executor"""
import sys
import subprocess
import logging
import os
import json
import importlib
import requests


main_logger = logging.getLogger('main_logger')
task_logger = logging.getLogger('task_logger')
JSON = ".json"
PROGRAM = 'Program/'
DASH = '#####################################################'
PROCESS_ABORTED = "PROCESS got ABORTED"

def setup_logger(logger_name, log_file, level=logging.INFO):
    """Function to initiate log file"""
    try:
        logger = logging.getLogger(logger_name)
        formatter = logging.Formatter('%(asctime)s | %(name)-10s | %(processName)-12s |\
        %(funcName)-22s | %(levelname)-5s | %(message)s')
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setFormatter(formatter)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.setLevel(level)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        logger.propagate = False
        logging.getLogger('snowflake.connector').setLevel(logging.WARNING)
        logging.getLogger('great_expectations.experimental.datasources').setLevel(logging.WARNING)
    except Exception as ex:
        logging.error('UDF Failed: setup_logger failed')
        raise ex

def create_common_folder_structure(path: str):
    """Function to create common folder stucture in server"""
    main_logger.info("started creating the folder structure")
    try:
        os.path.expanduser(path)
        os.chdir(path)
        if not os.path.exists('Common'):
            os.makedirs('Common')
        os.chdir(path+'Common/')
        if not os.path.exists('Config'):
            os.makedirs('Config')
        if not os.path.exists('Scripts'):
            os.makedirs('Scripts')
        os.chdir(path+'Common/Scripts/')
        if not os.path.exists('engine_main'):
            os.makedirs('engine_main')
        if not os.path.exists('dq_scripts'):
            os.makedirs('dq_scripts')
        if not os.path.exists('ingestion'):
            os.makedirs('ingestion')
        if not os.path.exists('orchestration'):
            os.makedirs('orchestration')
    except Exception as error:
        main_logger.exception("error in create_common_folder_structure %s.", str(error))
        raise error

def create_task_folder_structure(prj_nm,path: str):
    """Function to create task folder stucture in server"""
    try:
        os.chdir(path+PROGRAM+prj_nm+'/Pipeline/Task/')
        if not os.path.exists('archive'):
            os.makedirs('archive')
        if not os.path.exists('json'):
            os.makedirs('json')
        if not os.path.exists('logs'):
            os.makedirs('logs')
        if not os.path.exists('rejected'):
            os.makedirs('rejected')
        if not os.path.exists('source_files'):
            os.makedirs('source_files')
        if not os.path.exists('target_files'):
            os.makedirs('target_files')
        if not os.path.exists('reports'):
            os.makedirs('reports')
        main_logger.info("completed creating the folder structure")
    except Exception as error:
        main_logger.exception("error in create_task_folder_structure %s.", str(error))
        raise error

def create_folder_structure(prj_nm,path: str):
    """Function to create program folder stucture in server"""
    try:
        create_common_folder_structure(os.path.expanduser(path))
        os.chdir(path)
        if not os.path.exists('Program'):
            os.makedirs('Program')
        os.chdir(path+PROGRAM)
        if not os.path.exists(prj_nm):
            os.makedirs(prj_nm)
        os.chdir(path+PROGRAM+prj_nm+'/')
        if not os.path.exists('Pipeline'):
            os.makedirs('Pipeline')
        os.chdir(path+PROGRAM+prj_nm+'/Pipeline')
        if not os.path.exists('Task'):
            os.makedirs('Task')
        if not os.path.exists('json'):
            os.makedirs('json')
        if not os.path.exists('logs'):
            os.makedirs('logs')
        if not os.path.exists('text'):
            os.makedirs('text')
        create_task_folder_structure(prj_nm,os.path.expanduser(path))
    except Exception as error:
        main_logger.exception("error in create_folder_structure %s.", str(error))
        raise error

def download_pipeline_json(prj_nm,pipeline_name:str,paths_data:str):
    """Function to download pipeline JSON from Github to server"""
    try:
        main_logger.info("downloading pipeline.json from Github started..")
        pipeline_json_path= os.path.expanduser(paths_data["folder_path"])+ \
        paths_data["Program"]+prj_nm+paths_data["pipeline_json_path"]
        main_logger.info("path:%s",pipeline_json_path)
        main_logger.info("pipeline.json location: %s", pipeline_json_path)
        path_check = pipeline_json_path+pipeline_name+JSON
        is_exist = os.path.exists(path_check)
        main_logger.info('pipeline.json file exists: %s', is_exist)
        main_logger.info("pipeline_path:%s",paths_data["projects"][prj_nm]["GH_pipeline_path"]+
        pipeline_name+JSON)
        if is_exist is False:
            dwn_json = ['curl', '-o',pipeline_json_path+pipeline_name+JSON,
            paths_data["projects"][prj_nm]["GH_pipeline_path"]+pipeline_name+JSON]
            subprocess.call(dwn_json)
            main_logger.info("downloading pipeline.json:%s from Github completed", pipeline_name)
            main_logger.info(DASH)
    except Exception as error:
        main_logger.exception("error in download_pipeline_json %s.", str(error))
        raise error

def download_engine_code(paths_data:str):
    """Function to download engine_code.py from Github to server"""
    try:
        main_logger.info("downloading engine_code.py from Github started..")
        engine_path= os.path.expanduser(paths_data["folder_path"])+paths_data["engine_path"]
        main_logger.info("engine_code.py location: %s", engine_path)
        engine_path_check = engine_path+'engine_code.py'
        is_exist = os.path.exists(engine_path_check)
        main_logger.info('engine file exists: %s', is_exist)
        if is_exist is False:
            engine = ['curl', '-o', paths_data["folder_path"]+paths_data["engine_path"]+
            'engine_code.py', paths_data["GH_engine_path"]]
            subprocess.call(engine)
            main_logger.info("downloading engine_code.py from Github completed..")
            main_logger.info(DASH)
    except Exception as error:
        main_logger.exception("error in download_engine_code %s.", str(error))
        raise error

def download_checks_mapping(paths_data:str):
    """Function to download checks_mapping.json from Github to server"""
    try:
        main_logger.info("downloading checks_mapping.json from Github started..")
        checks_mapping_check = os.path.expanduser(paths_data["folder_path"])+ \
        paths_data["dq_scripts_path"]+'checks_mapping.json'
        # Check whether the specified path exists or not
        is_exist = os.path.exists(checks_mapping_check)
        main_logger.info('checks_mapping.json file exists: %s', is_exist)
        if is_exist is False:
            checks_mapping = ['curl', '-o', checks_mapping_check,
            paths_data["GH_checks_mapping_path"]]
            subprocess.call(checks_mapping)
            main_logger.info("downloading the checks_mapping.json from Github completed")
            main_logger.info(DASH)
    except Exception as error:
        main_logger.exception("error in download_checks_mapping %s.", str(error))
        raise error

def download_mapping(paths_data:str):
    """Function to download mapping.json from Github to server"""
    try:
        main_logger.info("downloading mapping.json from Github started..")
        mapping_path_check = os.path.expanduser(paths_data["folder_path"])+paths_data[
            "engine_path"]+'mapping.json'
        # Check whether the specified path exists or not
        is_exist = os.path.exists(mapping_path_check)
        main_logger.info('mapping.json file exists: %s', is_exist)
        if is_exist is False:
            mapping_file = ['curl', '-o', mapping_path_check,
            paths_data["GH_mapping_path"]]
            subprocess.call(mapping_file)
            main_logger.info("downloading the mapping.json completed")
            main_logger.info(DASH)
    except Exception as error:
        main_logger.exception("error in download_mapping %s.", str(error))
        raise error

def download_definitions_qc(paths_data:str):
    """Function to download definitions_qc from Github to server"""
    try:
        qc_py = ['curl', '-o', os.path.expanduser(paths_data["folder_path"])+paths_data[
        "dq_scripts_path"]+'definitions_qc.py', paths_data["GH_definitions_qc_path"]]
        qc_check_path_check = os.path.expanduser(paths_data["folder_path"])+paths_data[
        "dq_scripts_path"]+'definitions_qc.py'
        main_logger.info("downloading definitions_qc.py from Github started..")
        is_exist = os.path.exists(qc_check_path_check)
        main_logger.info('definitions_qc file exists: %s', is_exist)
        if is_exist is False:
            subprocess.call(qc_py)
            main_logger.info("downloading the definitions_qc.py from github completed")
            main_logger.info(DASH)
    except Exception as error:
        main_logger.exception("error in download_definitions_qc %s.", str(error))
        raise error

def download_utility(paths_data:str):
    """Function to download utility from Github to server"""
    try:
        utility_path_check = os.path.expanduser(paths_data["folder_path"])+paths_data[
        "ingestion_path"]+'utility.py'
        main_logger.info("downloading utility.py from Github started..")
        is_exist = os.path.exists(utility_path_check)
        main_logger.info('utility file exists: %s', is_exist)
        utility_py = ['curl', '-o', utility_path_check,
        paths_data["GH_utility_path"]]
        if is_exist is False:
            main_logger.info("downloading the utility.py file form gihub completed")
            subprocess.call(utility_py)
            main_logger.info(DASH)
    except Exception as error:
        main_logger.exception("error in download_utility %s.", str(error))
        raise error

def download_connections(paths_data:str):
    """Function to download utility from Github to server"""
    try:
        connection_path_check = os.path.expanduser(paths_data["folder_path"])+paths_data[
        "ingestion_path"]+'connections.py'
        main_logger.info("downloading connections.py from Github started..")
        is_exist = os.path.exists(connection_path_check)
        main_logger.info('connection file exists: %s', is_exist)
        connections_py = ['curl', '-o', connection_path_check,
        paths_data["GH_connections_path"]]
        if is_exist is False:
            main_logger.info("downloading the connections.py file form gihub completed")
            subprocess.call(connections_py)
            main_logger.info(DASH)
    except Exception as error:
        main_logger.exception("error in download_connections %s.", str(error))
        raise error

def download_orchestrate(paths_data:str):
    """Function to download orchestrate from Github to server"""
    try:
        orchestrate_path_check = os.path.expanduser(paths_data["folder_path"])+paths_data[
        "orchestration_path"]+'orchestrate.py'
        main_logger.info("downloading orchestrate.py from Github started..")
        is_exist = os.path.exists(orchestrate_path_check)
        main_logger.info('orchestrate file exists: %s', is_exist)
        orchestrate_py = ['curl', '-o',orchestrate_path_check,paths_data["GH_orchestrate_path"]]
        if is_exist is False:
            main_logger.info("downloading the orchestrate.py form Github completed")
            subprocess.call(orchestrate_py)
            main_logger.info(DASH)
    except Exception as error:
        main_logger.exception("error in download_orchestrate %s.", str(error))
        raise error

def common_files_downloads(paths_data:str):
    """Function to download engine_code.py,checks_mapping.json,mapping.json,
    definitions_qc,utility from Github to server"""
    try:
        download_engine_code(paths_data)
        download_checks_mapping(paths_data)
        download_mapping(paths_data)
        download_definitions_qc(paths_data)
        download_utility(paths_data)
        download_connections(paths_data)
        download_orchestrate(paths_data)
    except Exception as error:
        main_logger.exception("error in common_downloads %s.", str(error))
        raise error

def task_json_download(prj_nm,task_name:str, paths_data:str):
    """Function to download Task JSON from Github to server"""
    try:
        task_logger.info("downloading %s.json from Github started..", task_name)
        url=paths_data["projects"][prj_nm]["GH_task_jsons_path"]+task_name+JSON
        response = requests.get(url,timeout=60)
        if response.status_code == 200:
            url_exists = bool(response.status_code)
            main_logger.info("The json file exists in the  GITHUB repository.")
        else:
            url_exists = bool(not response.status_code)
            main_logger.info("The json file DOES NOT exists in the  GITHUB repository")
        if url_exists is False  :
            main_logger.info(PROCESS_ABORTED)
            sys.exit()
        json_path= os.path.expanduser(paths_data["folder_path"])+paths_data["Program"]+prj_nm+\
        paths_data["task_json_path"]
        task_logger.info("%s.json location: %s", task_name,json_path)
        path_check = json_path+task_name+JSON
        is_exist = os.path.exists(path_check)
        task_logger.info('%s.json exists: %s', task_name,is_exist)
        if is_exist is False:
            dwn_json =  ['curl', '-o', json_path+task_name+JSON,paths_data["projects"][prj_nm]
            ["GH_task_jsons_path"]+task_name+JSON]
            subprocess.call(dwn_json)
            task_logger.info("downloading %s.json from Github completed",task_name)
            task_logger.info(DASH)
    except Exception as error:
        task_logger.exception("error in task_downloads %s.", str(error))
        raise error

def download_task_source_conn_files(config_json1,paths_data1):
    """function to download source_connection
    file from github to server for execution"""
    try:
        if (config_json1['task']['source']['source_type'])  not in ("csv_read","csvfile_read",
        "excel_read","parquet_read","json_read","xml_read","text_read"):
            source_conn_file = config_json1['task']['source']['connection_name']
            url=paths_data1["GH_config_file_path"]+source_conn_file+JSON
            response = requests.get(url,timeout=60)
            if response.status_code == 200:
                url_exists = bool(response.status_code)
                main_logger.info(
                    "The source connection json file exists in the  GITHUB repository.")
            else:
                url_exists = bool(not response.status_code)
                main_logger.info(
                    "The source connection file DOES NOT exists in the GITHUB repository")
            if url_exists is False  :
                main_logger.info(PROCESS_ABORTED)
                sys.exit()
            source_path_check = os.path.expanduser(paths_data1["folder_path"])+paths_data1[
                "config_path"]+source_conn_file+JSON
            is_exist = os.path.exists(source_path_check)
            task_logger.info("downloading the source connection file: %s.json operation started",
            source_conn_file)
            task_logger.info('source_conn_file.json exists: %s', is_exist)
            if is_exist is False:
                src_json = ['curl', '-o',os.path.expanduser(paths_data1["folder_path"])+paths_data1[
                "config_path"]+source_conn_file+JSON,
                paths_data1["GH_config_file_path"]+source_conn_file+JSON]
                subprocess.call(src_json)
                task_logger.info(
                    "downloading source connection file: %s.json from Github completed..",
                source_conn_file)
                task_logger.info(DASH)
    except Exception as error:
        task_logger.exception("error in download_task_source_conn_files %s.", str(error))
        raise error

def download_task_target_conn_files(config_json1,paths_data1):
    """function to download source_connection
    file from github to server for execution"""
    try:
        if (config_json1['task']['target']['target_type'])  not in ("csv_write","csvfile_write",
        "parquet_write","excel_write","json_write","xml_write","text_write"):
            #curl command for downloading the target connection JSON
            target_conn_file = config_json1['task']['target']['connection_name']
            url=paths_data1["GH_config_file_path"]+target_conn_file+JSON
            response = requests.get(url,timeout=60)
            if response.status_code == 200:
                url_exists = bool(response.status_code)
                main_logger.info(
                    "The target connection json file exists in the  GITHUB repository.")
            else:
                url_exists = bool(not response.status_code)
                main_logger.info(
                    "The target connection file DOES NOT exists in the GITHUB repository")
            if url_exists is False  :
                main_logger.info(PROCESS_ABORTED)
                sys.exit()
            target_path_check = os.path.expanduser(paths_data1["folder_path"])+paths_data1[
            "config_path"]+target_conn_file+JSON
            # Check whether the specified path exists or not
            is_exist = os.path.exists(target_path_check)
            task_logger.info("downloading the target connection file: %s.json "
            "operation started", target_conn_file)
            task_logger.info('target_conn_file.json file exists: %s', is_exist)
            if is_exist is False:
                trgt_json = ['curl', '-o', os.path.expanduser(paths_data1[
                "folder_path"])+paths_data1["config_path"]+
                target_conn_file+JSON,paths_data1["GH_config_file_path"]+target_conn_file+JSON]
                subprocess.call(trgt_json)
                task_logger.info("downloading target connection %s.json from Github completed",
                target_conn_file)
                task_logger.info(DASH)
    except Exception as error:
        task_logger.exception("error in download_task_target_conn_files %s.", str(error))
        raise error

def download_task_source_target_files(config_json1,paths_data1):
    """function to download source.py, target.py
    files from github to server for execution"""
    try:
        source_type = config_json1['task']['source']['source_type']
        target_type = config_json1['task']['target']['target_type']
        with open(r""+os.path.expanduser(paths_data1["folder_path"])+paths_data1[
        "engine_path"]+'mapping.json',"r",encoding='utf-8') as mapjson:
            config_new_json = json.load(mapjson)
        source_file_name=config_new_json["mapping"][source_type]
        target_file_name= config_new_json["mapping"][target_type]
        src_py = ['curl', '-o',os.path.expanduser(paths_data1["folder_path"])+paths_data1[
        "ingestion_path"]+source_file_name, paths_data1["GH_source_ingestion_path"]+ \
        source_file_name]
        trgt_py = ['curl', '-o', os.path.expanduser(paths_data1["folder_path"])+
        paths_data1["ingestion_path"]+target_file_name, paths_data1[
        "GH_target_ingestion_path"]+target_file_name]
        src_py_path_check = os.path.expanduser(paths_data1["folder_path"])+paths_data1[
        "ingestion_path"]+source_file_name
        task_logger.info("src_py_path_check %s", src_py_path_check)
        is_exist = os.path.exists(src_py_path_check)
        task_logger.info('source read file exists: %s', is_exist)
        if is_exist is False:
            task_logger.info("downloading the  source read file: %s", source_file_name)
            subprocess.call(src_py)
            task_logger.info(DASH)
        trg_py_path_check = os.path.expanduser(paths_data1["folder_path"])+paths_data1[
        "ingestion_path"]+target_file_name
        is_exist = os.path.exists(trg_py_path_check)
        task_logger.info('target write file exists: %s', is_exist)
        if is_exist is False:
            task_logger.info("downloading the  target write file: %s", target_file_name)
            subprocess.call(trgt_py)
            task_logger.info(DASH)
    except Exception as error:
        task_logger.exception("error in download_task_source_target_files %s.", str(error))
        raise error

def download_task_files(prj_nm,task_name:str, paths_data:str):
    """function to download source_connection, target_connection, source.py, target.py
    files from github to server for execution"""
    try:
        task_logger.info("entered into downloading task related files")
        try:
            with open(r""+os.path.expanduser(paths_data["folder_path"])+paths_data[
            "Program"]+prj_nm+paths_data["task_json_path"]+task_name+JSON,"r",
            encoding='utf-8') as jsonfile:
                config_json = json.load(jsonfile)
        except FileNotFoundError as exc:
            task_logger.warning("the %s.json path or folder specified does not exists",task_name)
            raise exc
        #function calls for downloads
        download_task_source_conn_files(config_json,paths_data)
        download_task_target_conn_files(config_json,paths_data)
        download_task_source_target_files(config_json,paths_data)
    except Exception as error:
        task_logger.exception("error in download_task_files %s.", str(error))
        raise error

def execute_pipeline_download(prj_nm,paths_data:str,task_name:str,pipeline_name:str,run_id:str,
    log_file_path,log_file_name,mode,iter_value = "1"):
    """executes pipeline flow"""
    try:
        main_logger.info("calling the create_folder_structure function")
        create_folder_structure(prj_nm,os.path.expanduser(os.path.expanduser(
            paths_data["folder_path"])),)
        if task_name == -9999 :
            download_pipeline_json(prj_nm,pipeline_name,paths_data)
        main_logger.info("calling the common_files_downloads function")
        common_files_downloads(paths_data)
        orchestration_script=os.path.expanduser(paths_data["folder_path"])+paths_data[
            "orchestration_path"]
        sys.path.insert(0, orchestration_script)
        orchestrate =  importlib.import_module("orchestrate")
        main_logger.info("calling the orchestrate_calling function")
        orchestrate.orchestrate_calling(prj_nm,paths_data,task_name,pipeline_name,run_id,
        log_file_path,log_file_name,mode,iter_value)
    except Exception as error:
        main_logger.exception("error in execute_pipeline_download %s.", str(error))
        raise error

def execute_engine(prj_nm,task_name:str,paths_data:str,run_id:str,file_path,iter_value):
    """engine execution code"""
    try:
        logging_path= os.path.expanduser(paths_data["folder_path"])+paths_data["Program"]+prj_nm+\
        paths_data["task_log_path"]
        setup_logger('task_logger', logging_path+task_name+"_TaskLog_"+run_id+'_'+iter_value+'.log')
        task_logger.info("entered into execute_engine")
        new_path = os.path.expanduser(paths_data["folder_path"]) +paths_data["engine_path"]
        task_logger.info("calling the task_json_download function")
        task_json_download(prj_nm,task_name,paths_data)
        print("calling the download_task_files function")
        download_task_files(prj_nm,task_name,paths_data)
        sys.path.insert(0, new_path)
        engine_code =  importlib.import_module("engine_code")
        task_logger.info(DASH)
        task_logger.info("calling the engine_main")
        engine_code.engine_main(prj_nm,task_name,paths_data,run_id,file_path,iter_value)
        task_logger.info(DASH)
    except Exception as error:
        task_logger.exception("error in executing engine %s.", str(error))
        raise error
