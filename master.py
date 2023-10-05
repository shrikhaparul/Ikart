'''below code is to setup the logger and runs the code based on command'''
import logging
import argparse
import sys
import json
import os
import uuid
import importlib
from pathlib import Path
import hashlib
import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import github
from github import Github
from github import Auth
from dotenv import load_dotenv

JSON = ".json"

script_directory = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s | %(name)-10s | %(processName)-12s | "
                              "%(funcName)-22s | %(levelname)-5s | %(message)s")

# Construct the path to config.json using the script's directory
config_file_path = os.path.join(script_directory, 'config.json')

def setup_logger(logger_name, log_file, level=logging.INFO):
    """Function to initiate logging for framework by creating logger objects"""
    try:
        logger = logging.getLogger(logger_name)
        formatter = logging.Formatter('%(asctime)s | %(name)-10s | %(processName)-12s | '
                              '%(funcName)-22s | %(levelname)-5s | %(message)s')
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(logging.INFO)
        logger.setLevel(level)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        logger.propagate = False
        logging.getLogger('snowflake.connector').setLevel(logging.WARNING)
        logging.getLogger('great_expectations.experimental.datasources').setLevel(logging.WARNING)
        return logger
    except Exception as ex:
        logging.error('UDF Failed: setup_logger failed %s', ex)
        raise ex

def decrypt(data):
    '''function to decrypt the data'''
    KEY = b'8ookgvdIiH2YOgBnAju6Nmxtp14fn8d3'
    IV = b'rBEssDfxofOveRxR'
    aesgcm = AESGCM(KEY)
    decrypted = aesgcm.decrypt(IV, bytes.fromhex(data), None)
    return decrypted.decode('utf-8')


def get_config_section(config_path:str) -> dict:
    """reads the connection file and returns connection details as dict for
       connection name you pass it through the json
    """
    try:
        with open(config_path,'r', encoding='utf-8') as json_file:
            json_data = json.load(json_file)
            return dict(json_data["connection_details"].items())
    except Exception as err:
        logging.exception("get_config_section() is %s.", str(err))
        raise err

def execute_query(config_path, pip_nm):
    """Gets audit status from the audit table for the given pipeline."""
    result = None  # Initialize result variable outside the try block
    try:
        logging.info("task name from API: %s", pip_nm)
        url = f"{config_path['audit_api_url']}/executeTaskOrPiplineQuery/{pip_nm}"
        logging.info("URL from API: %s", url)
        response = requests.get(url, timeout=100)
        if response.status_code == 200:
            logging.info("Task name from API response: %s", response.json())
            result = response.json()
        else:
            logging.info("Request failed with status code: %s", response.status_code)
        return result
    except Exception as err:
        logging.exception("execute_query() error: %s", str(err))
        raise err


def get_file_in_gitrepo(repo, path, file_or_dir, branch):
    '''to get the files from git repo using pygithub'''
    try:
        auth_token = os.getenv("AUTH")
        auth = Auth.Token(auth_token)
        g = Github(auth=auth)
        repo=g.get_repo(repo)
        content_list = [file.name for file in repo.get_contents(path, ref=branch)
                        if file.type == file_or_dir]
        return content_list
    except github.GithubException as err:
        # Handle GitHub-related exceptions here
        if "Bad credentials" in str(err):
            print(f"Bad credentials exception: {err}")
            # You might want to re-authenticate or take corrective actions here.
        else:
            print(f"GitHub exception: {err}")
    except Exception as err:
        logging.exception("get_file_in_gitrepo() error: %s", str(err))
        raise err


def log_creation(logging_path, taskname, pipelinename, runid):
    """function to create run id and log"""
    try:
        main_logger.info("logging operation started.")
        if task_name:
            log_filename = str(taskname) + "_taskLog_" + runid + '.log'
        elif pipeline_name:
            log_filename = str(pipelinename) + "_pipelineLog_" + runid + '.log'
        setup_logger('main_logger', str(logging_path) + str(log_filename))
        logging.info("The json file %s exists in the GITHUB repository", taskname
                     or pipelinename)
    except Exception as err:
        logging.info("error in log_creation %s", str(err))
        raise err

def downlaod_file_from_git(repo,branch,file_path,save_dir):
    '''function to download the file from git'''
    auth_token = os.getenv("AUTH")
    auth = Auth.Token(auth_token)
    git = Github(auth=auth)
    repo = git.get_repo(repo)
    file_contents = repo.get_contents(file_path,ref=branch).decoded_content
    file_name = Path(file_path).name
    save_path = Path(save_dir).joinpath(file_name)
    with open(save_path, 'wb') as file:
        file.write(file_contents)
    return file

def downlaod_latest_file_from_git(repository_name,
    branch,file_path,local_file_path,filename,log_name):
    '''function to get the updated file from git'''
    try:
        if local_file_path.exists():
            auth_token = os.getenv("AUTH")
            auth = Auth.Token(auth_token)
            git = Github(auth=auth)
            repo = git.get_repo(repository_name)
            file_contents = repo.get_contents(file_path,ref=branch)
            # Get the SHA of the file on GitHub
            github_sha = hashlib.sha1(file_contents.decoded_content).hexdigest()
            # Calculate the sha of the local file (assuming it already exists)
            with open(local_file_path, "rb") as file:
                local_file_data = file.read()
                local_sha = hashlib.sha1(local_file_data).hexdigest()
            # Compare the shas
            if github_sha != local_sha:
                # File has been updated, proceed with downloading
                file_url = file_contents.download_url
                response = requests.get(file_url, timeout=60)
                with open(local_file_path, "wb") as file:
                    file.write(response.content)
                log_name.info(f"File: {filename} has been updated and downloaded.")
            else:
                log_name.info(f"File: {filename} is already up to date.")
    except Exception as err:
        main_logger.info("error in get_the_updated_file_from_git() %s",str(err))
        raise err


def get_download_from_git(configs_path,repo,homepath,branch):
    '''function to get the download.py from git'''
    try:
        file_path = configs_path['gh_download_file_path']
        save_dir = homepath
        downlaod_file_from_git(repo,branch,file_path,save_dir)
        main_logger.info("download.py file downloading completed")
    except Exception as err:
        logging.info("error in get_download_from_git %s", str(err))
        raise err

def parse_arguments():
    '''function to parse cli arguments'''
    parser = argparse.ArgumentParser(
        description="IngKart framework orchestration master execution cli.")
    parser.add_argument('-p', dest='project_name',required=True, type=str ,
                        help='Provide the PROJECT Name')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-t', dest='task_name', type=str ,
                       help='Provide the Task Name')
    group.add_argument('-b', dest='pipeline_name', type=str ,
                       help='Provide the Pipeline(Batch) Name')
    parser.add_argument('-gitbranch', dest='git_branch', type=str ,default='main',
                        help="Git Envirnoment to use.")
    parser.add_argument('-r', dest='restart',default=False, type=bool,
                        help="Provide the Restart values like : \
    ('true', 'True', 'TRUE', 'FALSE','false', 'False')")
    arguments = parser.parse_args()
    return arguments

if __name__ == "__main__":
    try:
        MODE = "NORMAL"
        args = parse_arguments()
        project_name = args.project_name
        git_branch = args.git_branch
        pipeline_name = args.pipeline_name
        task_name = args.task_name
        restart = args.restart
        RUNID= str(uuid.uuid4())

        try:
            with open(config_file_path,'r', encoding='utf-8') as jsonfile:
                # reading paths json data started
                config_paths = json.load(jsonfile)
                # reading paths json data completed
        except Exception as error:
            logging.exception("error in reading paths json %s.", str(error))
            raise error
        home_path=Path(config_paths["folder_path"]).expanduser()
        load_dotenv(f'{home_path}{"/"}{".env"}')
        github_repo_name=config_paths["github_repo_name"]
        repo_path=config_paths["repo_path"]
        if  project_name not in get_file_in_gitrepo(
            repo=github_repo_name, path = repo_path,file_or_dir='dir', branch=git_branch):
            print('Project not available. create a project and restart...')
            sys.exit()
        elif pipeline_name and (pipeline_name+JSON) not in get_file_in_gitrepo(
            repo=github_repo_name,path= f'{repo_path}/{project_name}/pipelines',file_or_dir='file',
            branch=git_branch):
            print('Pipeline not available. check pipeline job and restart...')
            sys.exit()
        elif task_name and (task_name+JSON) not in get_file_in_gitrepo(
            repo=github_repo_name, path=f'{repo_path}/{project_name}/pipelines/tasks',
            file_or_dir='file',branch=git_branch):
            print('Task not available. check task job and restart...')
            sys.exit()
        log_file_name = str(task_name)+"_taskLog_"+RUNID+'.log'
        main_logger = logging.getLogger('main_logger')
        # check if the task log path exists if not create log folder
        if not Path(f"{home_path}/{config_paths['local_repo']}"
                    f"{config_paths['programs']}{project_name}"
                    f"{config_paths['pipeline_log_path']}").exists():
            dir_path = Path(f"{home_path}{'/'}{config_paths['local_repo']}"
                            f"{config_paths['programs']}{project_name}"
                            f"{config_paths['pipeline_log_path']}")
            dir_path.mkdir(parents=True, exist_ok=True)
        pipeline_log_path = str(home_path)+"/"+config_paths['local_repo']+config_paths[ \
            "programs"] + project_name +config_paths['pipeline_log_path']

        # check if the task log path exists if not create log folder
        if not Path(f"{home_path}{'/'}{config_paths['local_repo']}"
                    f"{config_paths['programs']}{project_name}"
                    f"{config_paths['task_log_path']}").exists():
            dir_path = Path(f"{home_path}{'/'}{config_paths['local_repo']}"
                            f"{config_paths['programs']}{project_name}"
                            f"{config_paths['task_log_path']}")
            dir_path.mkdir(parents=True, exist_ok=True)
        task_log_path =str(home_path)+"/"+config_paths['local_repo']+config_paths[ \
            "programs"] + project_name +config_paths['task_log_path']

        # Download the download.py from git.
        if not Path(f'{home_path}{"/"}{"download.py"}').exists():
            print("download.py file downloading operation started...")
            get_download_from_git(config_paths,github_repo_name,str(home_path),git_branch)
            print("download.py file downloading operation Completed.")
        # else:
        #     downlaod_latest_file_from_git(github_repo_name,git_branch,
        # config_paths["gh_download_file_path"],f'{home_path}{"/"}{"download.py"}',
        # "download.py",main_logger)

        if task_name:
            log_creation(task_log_path, task_name, pipeline_name, RUNID)
            download = importlib.import_module("download")
            main_logger.info("Master execution started")
            download.execute_pipeline_download(project_name, config_paths, task_name, pipeline_name,
                                               RUNID, task_log_path, log_file_name, MODE,git_branch)
        elif pipeline_name:
            audit_state = execute_query(config_paths,pipeline_name)
            if audit_state:
                for audit_data in audit_state:
                    if audit_data['audit_value'] != 'COMPLETED' and restart is True:
                        run_id = audit_data['run_id']
                        ITER_VALUE = str(int(audit_data['iteration']) + 1)
                        MODE = "RESTART"
            log_creation(pipeline_log_path, task_name, pipeline_name, RUNID)
            download = importlib.import_module("download")
            main_logger.info("Master execution started")
            download.execute_pipeline_download(project_name, config_paths, task_name, pipeline_name,
                                            RUNID, task_log_path, log_file_name, MODE,git_branch)
    except Exception as error:
        main_logger.error("exception occured %s", error)
        raise error
    finally:
        sys.exit()
