"""below script is to download and create folder structure"""
import sys
import logging
import os
import json
import importlib
from pathlib import Path
import master
from master import downlaod_file_from_git as download_file_from_github
from master import setup_logger,downlaod_latest_file_from_git,gitdata_query

args = master.parse_arguments()
GIT_BRANCH = args.git_branch
main_logger = logging.getLogger('main_logger')
task_logger = logging.getLogger('task_logger')
JSON = ".json"
FILE_NOT_FOUND = "%s not found in the github repository"
PROCESS_ABORT = "Process Aborted."
project_name = args.project_name
password=args.password
login_id=args.user
def create_folder_structure(prj_nm, path: str, paths_data: str):
    """Function to create program folder structure in server"""
    try:
        path = os.path.expanduser(path)
        repo_path = os.path.join(path, paths_data["local_repo"])
        program_path = os.path.join(repo_path, paths_data["programs"], prj_nm)
        task_path = os.path.join(program_path, paths_data["pipelines"])
        folder_structure = [
            (repo_path, [paths_data["programs"]]),
            (program_path, []),
            (os.path.join(task_path, paths_data["tasks"]),
             [paths_data["archive"], paths_data["json"],
            paths_data["logs"], paths_data["rejected"],
            paths_data["source_files"], paths_data["target_files"],
            paths_data["reports"]]),
            (os.path.join(task_path, paths_data["json"]), []),
            (os.path.join(task_path, paths_data["logs"]), []),
            (os.path.join(task_path, paths_data["text"]), []),
            (os.path.join(repo_path, paths_data["connections"]), []),
            (os.path.join(path, paths_data["src"], paths_data["scripts"],
                          paths_data["engine_main"]), []),
            (os.path.join(path, paths_data["src"], paths_data["scripts"],
                          paths_data["dq_scripts"]), []),
            (os.path.join(path, paths_data["src"], paths_data["scripts"],
                          paths_data["ingestion"]), []),
            (os.path.join(path, paths_data["src"], paths_data["scripts"],
                          paths_data["orchestration"]), [])
        ]
        for folder, subfolders in folder_structure:
            os.makedirs(folder, exist_ok=True)
            for subfolder in subfolders:
                os.makedirs(os.path.join(folder, subfolder), exist_ok=True)
    except Exception as error:
        main_logger.exception("error in create_folder_structure %s.", str(error))
        raise error


def required_files_download(paths_data:str,repo_name,branch):
    """Function to download engine_code.py,checks_mapping.json,mapping.json,
    definitions_qc,utility from Github to server"""
    try:
        home_path = str(Path(paths_data["folder_path"]).expanduser())
        home_path = home_path+"/"
        path_src = home_path+paths_data["src"]
        ########## To download engine_code from git ############
        if not Path(home_path+paths_data["src"]+paths_data["engine_path"]+
                    'engine_code.py').exists():
            try:
                main_logger.info("downloading of engine_code started...")
                download_file_from_github(repo_name,branch, file_path=paths_data["gh_engine_path"],
                                    save_dir=path_src+paths_data["engine_path"])
            except Exception as error:
                main_logger.info("error in downloading of engine_code %s", str(error))
                raise error
        # else:
        #     downlaod_latest_file_from_git(repo_name,branch,paths_data["gh_engine_path"],
        #     path_src+paths_data["engine_path"]+'engine_code.py',"engine_code.py",main_logger)
        ########### To download checks_mapping json from git ##########
        if not Path(path_src+ paths_data["dq_scripts_path"]+'checks_mapping.json').exists():
            main_logger.info("downloading of checks_mapping json started...")
            download_file_from_github(repo_name,branch, file_path=paths_data[
            "gh_checks_mapping_path"],save_dir =path_src+ paths_data["dq_scripts_path"])
            main_logger.info("downloading of checks_mapping json completed!")
        # else:
        #     downlaod_latest_file_from_git(repo_name,branch,paths_data["gh_checks_mapping_path"],
        #     path_src+ paths_data["dq_scripts_path"]+'checks_mapping.json',"checks_mapping.json",
        #     main_logger)
        ########### To download mapping json from git ############
        if not Path(path_src+paths_data["engine_path"]+'mapping'+JSON).exists():
            main_logger.info("downloading of mapping json started...")
            download_file_from_github(repo_name,branch, file_path=paths_data[
                "gh_mapping_path"],save_dir =path_src+paths_data["engine_path"])
            main_logger.info("downloading of mapping json completed!")
        # else:
        #     downlaod_latest_file_from_git(repo_name,branch,paths_data["gh_mapping_path"],
        #     path_src+paths_data["engine_path"]+'mapping'+JSON,"mapping.json",main_logger)
        ########### To download definitions_qc from git ##########
        if not Path(path_src+paths_data["dq_scripts_path"]+'definitions_qc.py').exists():
            main_logger.info("downloading of definitions_qc code started...")
            download_file_from_github(repo_name,branch, file_path=paths_data[
                "gh_definitions_qc_path"],save_dir =path_src+paths_data["dq_scripts_path"])
            main_logger.info("downloading of definitions_qc code completed!")
        # else:
        #     downlaod_latest_file_from_git(repo_name,branch,paths_data["gh_definitions_qc_path"],
        #     path_src+paths_data["dq_scripts_path"]+'definitions_qc.py',"definitions_qc.py",
        #     main_logger)
        ########### To download utility code from git ###############
        if not Path(path_src+paths_data["ingestion_path"]+'utility.py').exists():
            try:
                main_logger.info("downloading of utility code started...")
                download_file_from_github(repo_name,branch, file_path=paths_data[
                    "gh_utility_path"],save_dir =path_src+paths_data["ingestion_path"])
                main_logger.info("downloading of utility code completed!")
            except Exception as error:
                main_logger.info("error in downloading of utility code %s", str(error))
                raise error
        # else:
        #     downlaod_latest_file_from_git(repo_name,branch,paths_data["gh_utility_path"],
        #     path_src+paths_data["ingestion_path"]+'utility.py',"utility.py",main_logger)
        ############ To download connections code from git ############
        if not Path(path_src+paths_data["ingestion_path"]+'connections.py').exists():
            try:
                main_logger.info("downloading of connections code started...")
                download_file_from_github(repo_name,branch, file_path=paths_data[
                    "gh_connections_path"],save_dir =path_src+paths_data["ingestion_path"])
                main_logger.info("downloading of connections code completed!")
            except Exception as error:
                main_logger.info("error in downloading of connections code %s", str(error))
                raise error
        # else:
        #     downlaod_latest_file_from_git(repo_name,branch,paths_data["gh_connections_path"],
        #     path_src+paths_data["ingestion_path"]+'connections.py',"connections.py",main_logger)
        ############# To download orchestration code from git ##############
        if not Path(path_src+paths_data["orchestration_path"]+'orchestrate.py').exists():
            main_logger.info("downloading of orchestarte code started...")
            download_file_from_github(repo_name,branch, file_path=paths_data[
                "gh_orchestrate_path"],save_dir =path_src+paths_data["orchestration_path"])
            main_logger.info("downloading of orchestarte code completed!")
        # else:
        #     downlaod_latest_file_from_git(repo_name,branch,paths_data["gh_orchestrate_path"],
        #     path_src+paths_data["orchestration_path"]+'orchestrate.py',"orchestrate.py",
        # main_logger)
    except Exception as error:
        main_logger.exception("error in common_downloads %s.", str(error))
        raise error

def extract_bulk_connection_names(json_data):
    """will fetch the source and target connection details"""
    try:
        source_connection_name = json_data["task"]["details"][0]["source"]["connection_name"]
        target_connection_name = json_data["task"]["details"][0]["target"]["connection_name"]
        return source_connection_name, target_connection_name
    except KeyError as e:
        task_logger.info("KeyError: %s Make sure the JSON structure is as expected.", str(e))
        return None, None

def get_conn_subtype_type(config_path:str) -> dict:
    """reads the connection file and returns connection_subtype details as per
       connection name you pass it through the json
    """
    try:
        with open(config_path,'r', encoding='utf-8') as jsonfile:
            logging.info("fetching connection details")
            json_data = json.load(jsonfile)
            logging.info("reading connection details completed")
            return json_data["connection_subtype"]
    except Exception as error:
        logging.exception("get_config_section() is %s.", str(error))
        raise error

def download_task_files(prj_nm,task_name:str, config_path:str, repo_name,branch):
    """function to download source_connection, target_connection, source.py, target.py
    files from github to server for execution"""
    try:
        homepath = str(Path(config_path['folder_path']).expanduser())
        task_logger.info("entered into downloading task related files")
        #to download task json from git
        try:
            # if not Path(f'{homepath}{"/"}{config_path["local_repo"]}{config_path["programs"]}'
            # f'{prj_nm}{config_path["task_json_path"]}{task_name}{JSON}').exists():
            download_file_from_github(repo_name, branch,
            file_path=f'{config_path["programs"]}{prj_nm}{config_path["gh_tasks_path"]}'
            f'{task_name}{JSON}',
            save_dir = f'{homepath}{"/"}{config_path["local_repo"]}'
            f'{config_path["programs"]}{prj_nm}{config_path["task_json_path"]}')
        except Exception:
            main_logger.error("Task name not found in the git hub: %s",task_name)
            main_logger.warning(PROCESS_ABORT)
            sys.exit()

        #to read the task json that is downloaded
        try:
            with open(r""+os.path.expanduser(config_path["folder_path"])+config_path[
            "local_repo"]+config_path["programs"]+prj_nm+config_path["task_json_path"]+
            task_name+JSON,"r",
            encoding='utf-8') as jsonfile:
                task_json = json.load(jsonfile)
        except FileNotFoundError as exc:
            task_logger.warning("the %s.json path or folder specified does not exists",task_name)
            raise exc

        if task_json["is_active"] == 'N':
            task_logger.warning("%s task is inactive, Process got Aborted!", task_name)
            sys.exit()
        else:
            #to download SQL Execution task connection file
            if task_json['task_type'] == "SQL Execution":
                source_conn_file_name = task_json['sql_execution']['connection_name']
                try:
                    download_file_from_github(repo_name, branch,
                    file_path = f'{config_path["gh_connections_json_path"]}'
                    f'{source_conn_file_name}{JSON}',
                    save_dir = f'{config_path["folder_path"]}{config_path["conn_path"]}')
                except Exception:
                    task_logger.error(FILE_NOT_FOUND, source_conn_file_name)
                    task_logger.warning(PROCESS_ABORT)
                    sys.exit()

            #to download Ingestion task source connection file and target connection file
            if task_json['task_type'] == "Ingestion":
                # if (task_json['task']['source']['source_type']) not in ("csv_read","csvfile_read",
                # "excel_read","parquet_read","json_read","xml_read","text_read"):
                if (task_json['task']['source']['connection_name'])  not in ('localserver'):
                    source_conn_file_name = task_json['task']['source']['connection_name']
                    # if not Path(f'{config_path["folder_path"]}{config_path["conn_path"]}'
                    # f'{source_conn_file_name}{JSON}').exists():
                    try:
                        download_file_from_github(repo_name, branch,
                        file_path = f'{config_path["gh_connections_json_path"]}'
                        f'{source_conn_file_name}{JSON}',
                        save_dir = f'{config_path["folder_path"]}{config_path["conn_path"]}')
                    except Exception:
                        task_logger.error(FILE_NOT_FOUND, source_conn_file_name)
                        task_logger.warning(PROCESS_ABORT)
                        sys.exit()

                if (task_json['task']['target']['connection_name'])  not in ('localserver'):
                    target_conn_file_name = task_json['task']['target']['connection_name']
                    try:
                        download_file_from_github(repo_name, branch,
                        file_path = f'{config_path["gh_connections_json_path"]}'
                        f'{target_conn_file_name}{JSON}',
                        save_dir = f'{config_path["folder_path"]}{config_path["conn_path"]}')
                    except Exception:
                        task_logger.error(FILE_NOT_FOUND, target_conn_file_name)
                        task_logger.warning(PROCESS_ABORT)
                        sys.exit()

                #to download the read and write .py scripts
                source_type = task_json['task']['source']['source_type']
                target_type = task_json['task']['target']['target_type']
                with open(r""+homepath+"/"+config_path['src']+config_path[
                "engine_path"]+'mapping.json',"r",encoding='utf-8') as mapjson:
                    config_new_json = json.load(mapjson)
                source_file_name=config_new_json["mapping"][source_type]
                target_file_name= config_new_json["mapping"][target_type]
                homepath = homepath + "/"
                path_src = homepath+config_path["src"]

                if not Path(path_src+config_path["ingestion_path"]+source_file_name).exists():
                    try:
                        download_file_from_github(repo_name, branch,
                        file_path = config_path["gh_source_ingestion_path"]+source_file_name,
                        save_dir = path_src+config_path["ingestion_path"])
                    except Exception as error:
                        main_logger.error(FILE_NOT_FOUND,source_file_name)
                        raise error
                if not Path(path_src+config_path["ingestion_path"]+target_file_name).exists():
                    try:
                        download_file_from_github(repo_name, branch,
                        file_path = config_path["gh_target_ingestion_path"]+target_file_name,
                        save_dir = path_src+config_path["ingestion_path"])
                    except Exception as error:
                        main_logger.error(FILE_NOT_FOUND,target_file_name)
                        raise error

            elif task_json['task_type'] == "Bulk Ingestion":
                #fetching source and target connection names from task json
                source_conn_file_name,target_conn_file_name=extract_bulk_connection_names(task_json)

                if source_conn_file_name is not None and target_conn_file_name is not None:
                    task_logger.info("Source Connection Name:%s", source_conn_file_name)
                    task_logger.info("Target Connection Name:%s", target_conn_file_name)
                else:
                    task_logger.info("Error extracting connection names from task_json.")
                    sys.exit()

                try:
                    download_file_from_github(repo_name, branch,
                    file_path = f'{config_path["gh_connections_json_path"]}'
                    f'{source_conn_file_name}{JSON}',
                    save_dir = f'{config_path["folder_path"]}{config_path["conn_path"]}')
                except Exception:
                    task_logger.error(FILE_NOT_FOUND, source_conn_file_name)
                    task_logger.warning(PROCESS_ABORT)
                    sys.exit()

                try:
                    download_file_from_github(repo_name, branch,
                    file_path = f'{config_path["gh_connections_json_path"]}'
                    f'{target_conn_file_name}{JSON}',
                    save_dir = f'{config_path["folder_path"]}{config_path["conn_path"]}')
                except Exception:
                    task_logger.error("target connection file not found in the git hub: %s",
                                    target_conn_file_name)
                    task_logger.warning(PROCESS_ABORT)
                    sys.exit()

                #to download the read and write .py scripts
                src_conn_json_path = f'{config_path["folder_path"]}{config_path["conn_path"]}'\
                f'{source_conn_file_name}{JSON}'
                trgt_conn_json_path =  f'{config_path["folder_path"]}{config_path["conn_path"]}'\
                f'{target_conn_file_name}{JSON}'
                task_logger.info("src_conn_json_path:%s",src_conn_json_path)
                task_logger.info("trgt_conn_json_path:%s",trgt_conn_json_path)

                source_sub_type = get_conn_subtype_type(src_conn_json_path)
                target_sub_type = get_conn_subtype_type(trgt_conn_json_path)

                if task_json['job_execution'] == "SeaTunnel":
                    task_logger.info("No need to download task files for sea tunnel job type.")
                else:
                    if task_json['source_type'] not in "Files" and task_json['target_type'] not in "Files": 
                        with open(r""+homepath+"/"+config_path['src']+config_path[
                        "engine_path"]+'subtype_mapping.json',"r",encoding='utf-8') as subtype_mapjson:
                            subtype_mapping = json.load(subtype_mapjson)
                        if source_sub_type not in ("Local Server","Remote Server"):
                            source_file_name=subtype_mapping[source_sub_type]["source"]
                        else:
                            source_file_format = task_json["task"]["details"][0]["source"]\
                            ["source_file_format"]
                            source_file_name=subtype_mapping[source_sub_type][source_file_format]["source"]

                        if target_sub_type not in ("Local Server","Remote Server"):
                            target_file_name=subtype_mapping[target_sub_type]["target"]
                        else:
                            target_file_format = task_json["task"]["details"][0]["target"]\
                            ["target_file_format"]
                            # Retrieve target file name based on target_file_format and target_sub_type
                            if target_sub_type in subtype_mapping:
                                if target_file_format in subtype_mapping[target_sub_type]:
                                    target_file_name = subtype_mapping[target_sub_type][target_file_format]\
                                    ["target"]
                                    task_logger.info(target_file_name)
                                else:
                                    task_logger.info("Target file format %s not found for %s.",
                                    target_file_format,target_sub_type)
                            else:
                                task_logger.info("Target sub-type %s not found.",target_sub_type)
                    else:
                        source_file_name = "bulk_file_copy.py"
                        target_file_name = "bulk_file_copy.py"    

                    homepath = homepath + "/"
                    path_src = homepath+config_path["src"]

                    if not Path(path_src+config_path["ingestion_path"]+source_file_name).exists():
                        try:
                            download_file_from_github(repo_name, branch,
                            file_path = config_path["gh_source_ingestion_path"]+source_file_name,
                            save_dir = path_src+config_path["ingestion_path"])
                        except Exception as error:
                            main_logger.error(FILE_NOT_FOUND,source_file_name)
                            raise error
                    if not Path(path_src+config_path["ingestion_path"]+target_file_name).exists():
                        try:
                            download_file_from_github(repo_name, branch,
                            file_path = config_path["gh_target_ingestion_path"]+target_file_name,
                            save_dir = path_src+config_path["ingestion_path"])
                        except Exception as error:
                            main_logger.error(FILE_NOT_FOUND,target_file_name)
                            raise error
    except Exception as error:
        task_logger.exception("error in download_task_files %s.", str(error))
        raise error

def execute_pipeline_download(prj_nm,config_path:str,task_name:str,pipeline_name:str,run_id:str,
    log_file_path,log_file_name,mode,git_branch,iter_value = "1"):
    """executes pipeline flow"""
    try:
        homepath = str(Path(config_path['folder_path']).expanduser())
        homepath = homepath + "/"
        path_src = homepath+config_path["src"]
        github_repo_name = gitdata_query(config_path["audit_api_url"], project_name, login_id,password)
        repo_name = github_repo_name
        main_logger.info("calling the create_folder_structure function")
        create_folder_structure(prj_nm,os.path.expanduser(
            config_path["folder_path"]),config_path)
        if task_name is None :
            download_file_from_github(repo_name, git_branch,
            file_path= f'{config_path["programs"]}{prj_nm}'
            f'{config_path["gh_pipeline_path"]}{pipeline_name}{JSON}',
            save_dir =f'{homepath}{"/"}{config_path["local_repo"]}'
            f'{config_path["programs"]}{prj_nm}{config_path["task_pipeline_path"]}')
        main_logger.info("calling the common_files_downloads function")
        required_files_download(config_path,repo_name,git_branch)
        orchestration_script=path_src+config_path["orchestration_path"]
        sys.path.insert(0, orchestration_script)
        orchestrate =  importlib.import_module("orchestrate")
        main_logger.info("calling the orchestrate_calling function")
        orchestrate.orchestrate_calling(prj_nm,config_path,task_name,pipeline_name,run_id,
        log_file_path,log_file_name,mode,iter_value)
    except Exception as error:
        main_logger.exception("error in execute_pipeline_download %s.", str(error))
        raise error

def execute_engine(prj_nm,task_name:str,config_path:str,run_id:str,file_path,iter_value):
    """engine execution code"""
    try:
        homepath = str(Path(config_path['folder_path']).expanduser())
        logging_path= homepath+"/"+config_path["local_repo"]+ \
        config_path["programs"]+prj_nm+config_path["task_log_path"]
        setup_logger('task_logger', logging_path+task_name+"_taskLog_"+run_id+'_'+iter_value+'.log')
        github_repo_name = gitdata_query(config_path["audit_api_url"], project_name, login_id,password)
        repo_name = github_repo_name
        # repo_name = 'madhushree211999/Ikart_UI'
        task_logger.info("entered into execute_engine")
        new_path = homepath+"/"+config_path["src"] +config_path["engine_path"]
        task_logger.info("calling the task_json_download function")
        download_task_files(prj_nm,task_name, config_path, repo_name,GIT_BRANCH)
        task_logger.info("calling the download_task_files function")
        sys.path.insert(0, new_path)
        engine_code =  importlib.import_module("engine_code")
        task_logger.info("#####################################################")
        task_logger.info("calling the engine_main")
        engine_code.engine_main(prj_nm,task_name,config_path,run_id,file_path,iter_value)
        task_logger.info("#####################################################")
    except Exception as error:
        task_logger.exception("error in executing engine %s.", str(error))
        raise error
