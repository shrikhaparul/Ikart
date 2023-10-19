""" importing modules """
import json
import logging
import sys
import os
from datetime import datetime
import zipfile
import importlib
import re
import requests
import urllib3
import pandas as pd
import sqlalchemy
from sqlalchemy.orm import sessionmaker

#import download
#from utility import get_config_section, decrypt
JSON = ".json"
#LOGGER = logging.getLogger()
task_logger = logging.getLogger('task_logger')
FAIL_LOG_STATEMENT = "%s got failed engine"
TASK_LOG = 'Task %s Execution Completed'

def write_to_txt1(task_id,status,file_path):
    """Generates a text file with statuses for orchestration"""
    try:
        # # Acquire the lock before reading from the file
        # lock.acquire()
        is_exist = os.path.exists(file_path)
        if is_exist is True:
            data_fram =  pd.read_csv(file_path, sep='\t')
            data_fram.loc[data_fram['task_name']==task_id, 'Job_Status'] = status
            data_fram.to_csv(file_path ,mode='w', sep='\t',index = False, header=True)
        else:
            task_logger.error("pipeline txt file does not exist")
    except pd.errors.EmptyDataError as error:
        task_logger.error("The file is empty or has no columns to parse.")
        raise error
    except Exception as error:
        task_logger.exception("write_to_txt: %s.", str(error))
        raise error

def audit(json_data, task_name,run_id,status,value,itervalue,seq_no= None):
    """ create audit json file and audits event records into it"""
    #task_logger.info(json_data, task_name,run_id,status,value,itervalue)
    try:
        url = "http://localhost:8080/api/audit"
        audit_data = [{
                    "pipeline_id": json_data["pipeline_id"],
                    "taskorpipeline_name": task_name,
                    "run_id": run_id,
                    "sequence": seq_no,
                    "iteration": itervalue,
                    "audit_type": status,
                    "audit_value": value,
                    "process_dttm" : datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                }]

        response = requests.post(url, json=audit_data, timeout=100)
        task_logger.info("audit status code:%s",response.status_code)
        

    except Exception as error:
        task_logger.error("error in audit %s.", str(error))
        raise error

def task_json_read(paths_data,task_id,prj_nm):
    """function to read task json"""
    try:
        with open(r""+os.path.expanduser(paths_data["folder_path"])+paths_data[
            "local_repo"]+paths_data["programs"]+prj_nm+\
        paths_data["task_json_path"]+task_id+".json","r",encoding='utf-8') as jsonfile:
            task_logger.info("reading TASK JSON data started %s",task_id)
            json_data = json.load(jsonfile)
            task_logger.info("reading TASK JSON data completed")
        return json_data
    except Exception as error:
        task_logger.exception("error in task_json_read %s.", str(error))
        raise error

def checks_mapping_read(paths_data):
    """function to read task json"""
    try:
        with open(r""+os.path.expanduser(paths_data["folder_path"])+paths_data[
            'src']+paths_data["dq_scripts_path"]+\
        "checks_mapping.json","r",encoding='utf-8') as json_data_new:
            task_logger.info("reading checks mapping json data started")
            json_checks = json.load(json_data_new)
            task_logger.info("reading checks mapping data completed")
        return json_checks
    except Exception as error:
        task_logger.exception("error in checks_mapping_read %s.", str(error))
        raise error

def read_write_imports(paths_data,json_data):
    """function for importing read and write functions"""
    try:
        py_scripts_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
            'src']+paths_data["ingestion_path"]
        #task_logger.info(py_scripts_path)
        sys.path.insert(0, py_scripts_path)
        task_logger.info("read imports started")
        module_name = json_data["task"]["source"]["source_type"]
        task_logger.info("write imports started")
        module_name1 = json_data["task"]["target"]["target_type"]
        module = importlib.import_module(module_name)
        module1 = importlib.import_module(module_name1)
        read = getattr(module, "read")
        write = getattr(module1, "write")
        return read,write
    except Exception as error:
        task_logger.exception("error in read_write_imports %s.", str(error))
        raise error

def task_failed(task_id,file_path,json_data,run_id,iter_value):
    """function to log and audit if task is failed"""
    try:
        write_to_txt1(task_id,'FAILED',file_path)
        audit(json_data,task_id,run_id,'STATUS','FAILED',iter_value)
        task_logger.warning(FAIL_LOG_STATEMENT, task_id)
    except Exception as error:
        task_logger.exception("error in task_failed %s.", str(error))
        raise error

def task_success(task_id,file_path,json_data,run_id,iter_value):
    """function to log and audit if task is success"""
    try:
        write_to_txt1(task_id,'SUCCESS',file_path)
        audit(json_data,task_id,run_id,'STATUS','COMPLETED',
                iter_value)
        task_logger.info(TASK_LOG,task_id)
    except Exception as error:
        task_logger.exception("error in task_success %s.", str(error))
        raise error

def data_quality_features(json_data,definitions_qc):
    """function for executing data quality features based on pre and post checks"""
    try:
        if "task" in json_data and "data_quality_features" in json_data["task"]:
            if json_data['task']['data_quality_features']['dq_auto_correction_required'] == 'Y' \
            and json_data['task']['data_quality_features']['data_masking_required'] == 'Y':
                definitions_qc.auto_correction(json_data)
                definitions_qc.data_masking(json_data)
            elif json_data['task']['data_quality_features']['dq_auto_correction_required'] == 'Y' \
            and json_data['task']['data_quality_features']['data_encryption_required'] == 'Y':
                definitions_qc.auto_correction(json_data)
                definitions_qc.data_encryption(json_data)
            elif json_data['task']['data_quality_features']['dq_auto_correction_required'] == 'Y' \
            and json_data['task']['data_quality_features']['data_masking_required'] == 'Y' \
            and json_data['task']['data_quality_features']['data_encryption_required'] == 'Y':
                definitions_qc.auto_correction(json_data)
                definitions_qc.data_masking(json_data)
                definitions_qc.data_encryption(json_data)
            elif json_data['task']['data_quality_features']['dq_auto_correction_required'] == 'Y':
                definitions_qc.auto_correction(json_data)
            elif json_data['task']['data_quality_features']['data_masking_required'] == 'Y':
                definitions_qc.data_masking(json_data)
            elif json_data['task']['data_quality_features']['data_encryption_required'] == 'Y':
                definitions_qc.data_encryption(json_data)
    except Exception as error:
        task_logger.exception("error in data_quality_features %s.", str(error))
        raise error
    

def precheck_status(paths_json_data,task_json_data,run_id):
    '''function to check whether all the checks has been passed
    or failed at target level'''
    try:
        seq_nos = [item['seq_no'] for item in task_json_data['task']['data_quality']
                   if item['type'] == 'pre_check']
        seq_nos_str = ','.join(seq_nos)
        taskorpipelinename = task_json_data['task_name']
        url = f"{paths_json_data['audit_api_url']}/getPostCheckResult/{taskorpipelinename}/{run_id}/{seq_nos_str}"
        task_logger.info("URL from API: %s", url[:30]+"...")
        response = requests.get(url, timeout=100)
        if response.status_code == 200:
            result = response.json()
        else:
            task_logger.info("Request failed with status code: %s", response.status_code)
        return result
    except Exception as error:
        task_logger.exception("precheck_status() is %s.", str(error))
        raise error

def postcheck_status(paths_json_data,task_json_data,run_id):
    '''function to check whether all the checks has been passed
    or failed at target level'''
    try:
        seq_nos = [item['seq_no'] for item in task_json_data['task']['data_quality']
                   if item['type'] == 'post_check']
        seq_nos_str = ','.join(seq_nos)
        taskorpipelinename = task_json_data['task_name']
        url = f"{paths_json_data['audit_api_url']}/getPostCheckResult/{taskorpipelinename}/{run_id}/{seq_nos_str}"
        task_logger.info("URL from API: %s", url[:30]+" ...")
        response = requests.get(url, timeout=100)
        if response.status_code == 200:
            result = response.json()
        else:
            task_logger.info("Request failed with status code: %s", response.status_code)
        return result
    except Exception as error:
        task_logger.exception("postcheck_status() is %s.", str(error))
        raise error

def archive_files(inp_file_names, out_zip_file):
    """Function to Archive files"""
    task_logger.info("Archiving file start time: %s", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    compression = zipfile.ZIP_DEFLATED
    task_logger.info("Archiving of file started %s-", inp_file_names)
    # create the zip file first parameter path/name, second mode
    zipf = zipfile.ZipFile(out_zip_file, mode="w")
    try:
        for file_to_write in inp_file_names:
            zipf.write(file_to_write, file_to_write, compress_type=compression)
    except FileNotFoundError as error:
        task_logger.error("Exception occurred during Archiving process %s-", error)
    finally:
        zipf.close()
        task_logger.info("Archiving file end time: %s",
                         datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        task_logger.info("Archiving of file ended")

def begin_transaction(paths_data,json_data,config_file_path):
    '''function to start the transaction'''
    connections_path=os.path.expanduser(paths_data["folder_path"])+paths_data['src']+ \
    paths_data["ingestion_path"]
    sys.path.insert(0, connections_path)
    module = importlib.import_module("connections")
    target = json_data['task']['target']
    if target['target_type']=='mysql_write':
        establish_conn_for_mysql = getattr(module, "establish_conn_for_mysql")
        engine,_ = establish_conn_for_mysql(json_data,'target',config_file_path)
    elif target['target_type']=='snowflake_write':
        establish_conn_for_snowflake = getattr(module, "establish_conn_for_snowflake")
        engine,_ = establish_conn_for_snowflake(json_data,'target',config_file_path)
    elif target['target_type']=='postgres_write':
        establish_conn_for_postgres = getattr(module, "establish_conn_for_postgres")
        engine,_ = establish_conn_for_postgres(json_data,'target',config_file_path)
    elif target['target_type']=='mssql_write':
        establish_conn_for_sqlserver = getattr(module, "establish_conn_for_sqlserver")
        engine,_ = establish_conn_for_sqlserver(json_data,'target',config_file_path)
    # Create a session object
    ssession = sessionmaker(bind=engine)
    session = ssession()
    # Start a transaction
    session.begin()
    task_logger.info("=================================================================")
    task_logger.info("Transaction Started")
    return session



def read_task_json(paths_data,prj_nm,task_name):
    try:
        with open(r""+paths_data["folder_path"]+paths_data["local_repo"]+paths_data["programs"]+prj_nm+\
            paths_data["task_json_path"]
            +task_name+JSON,"r",
            encoding='utf-8') as jsonfile:
            json_data = json.load(jsonfile)
        task_logger.info("reading query json completed")
        return json_data
    except FileNotFoundError as exc:
        task_logger.warning("the %s.json path or folder specified does not exists",task_name)
        raise exc
    
def establish_conn(paths_data,prj_nm,task_name):
    """establishes connection for the mysql database
       you pass it through the json"""
    try:
        new_path = os.path.expanduser(paths_data["folder_path"])+paths_data['src']+paths_data[ "ingestion_path"]
        sys.path.insert(0, new_path)
        utility_code =  importlib.import_module("utility")
        json_data = read_task_json(paths_data,prj_nm,task_name)
        config_path = paths_data["folder_path"]+paths_data["config_path"]+json_data["sql_execution"]["connection_name"]+JSON
        connection_details = utility_code.get_config_section(config_path)
        password = utility_code.decrypt(connection_details["password"])
        connection = sqlalchemy.create_engine(f'mysql+pymysql://{connection_details["username"]}'
        f':{password.replace("@", "%40")}@{connection_details["hostname"]}'
        f':{int(connection_details["port"])}/{connection_details["database"]}')
        task_logger.info("connection established")    
        return connection
       
    except Exception as error:
        task_logger.exception("establish_conn() is %s", str(error))
        raise error
    
def execute_query(prj_nm,paths_data:str,task_name:str,json_data,run_id,query_iteration:int,restart_point=None,task_iteration=None):
    try:
        print("query_iteration",query_iteration)
        print("restart point value is",(restart_point))
        print("type of restart_point",type(restart_point))
        #task_logger.info("restart_point value is: %s",restart_point)
        restart_mode = json_data['sql_execution']['restart']
        sql_list = json_data["sql_list"]
        #task_logger.info(sql_list)
        sorted_queries = sorted(sql_list, key=lambda x: int(x["seq_no"]))
        #task_logger.info(sorted_queries)
        # If restart_point is provided, skip queries until restart_point
        all_queries_passed = True
        if restart_mode == "normal" or restart_mode == "":
            # if restart_point is not None  : 
            sorted_queries = [query for query in sorted_queries if int(query["seq_no"]) >= int(restart_point)]
            task_logger.info(sorted_queries)
            if restart_point == 1:
                itervalue = 1
            else:
                itervalue = task_iteration 

        elif restart_mode == "skip":
            sorted_queries = [query for query in sorted_queries if int(query["seq_no"]) > int(restart_point)]
            task_logger.info(sorted_queries)
            if restart_point == 1 or restart_point == 0:
                itervalue = 1
            else:
                itervalue = task_iteration 

        elif restart_mode == "begin":
            task_logger.info("going inside begin")
            if restart_point == 1:
                itervalue = 1
            else:
                itervalue = task_iteration 
        else:
            itervalue = 1
        audit(json_data, task_name,run_id,'STATUS','STARTED',itervalue)
        # pass_quries = []  # List to store the sequence numbers of executed queries
        # query_iteration_values = {}
        for query in sorted_queries:
            seq_no = query["seq_no"]
            print(seq_no)
            print("type of seq_no",type(seq_no))
        #     if seq_no in query_iteration_values:  
        #         query_iteration = query_iteration_values[seq_no]
        #     else:
        #         query_iteration = 0
            # query_iteration += 1
            # query_iteration_values[seq_no] = query_iteration
            # print("before try query iteration",query_iteration,"for seq_no",seq_no)
            sql_query = query["sql_query"]
            s_query = sql_query[:30]
            task_logger.info("Sequence number: %s",seq_no)
            task_logger.info("Sql query: %s",sql_query[:30]+"...")
            task_logger.info("Sequence number %s belongs to the query (%s)",seq_no, sql_query[:30]+"...")
            connection=establish_conn(paths_data,prj_nm,task_name)
            connection = connection.raw_connection()
            cursor = connection.cursor()  
            try:
                #if restart_mode=="normal":
                print("seq_no in try condition",seq_no)
                print("query iteration",query_iteration,"for seq_no",seq_no)
                # if restart_mode != "" and int(restart_point) < seq_no:
                    # iter_value = query_iteration + 1 
                    # audit(json_data, task_name,run_id,"SQL QUERY",s_query,itervalue, restart_point)
                    # audit(json_data,task_name,run_id,'ROWS AFFECTED',variable,itervalue, restart_point)
                    # audit(json_data, task_name, run_id, "RESULT", "PASS", iter_value, restart_point)
                task_logger.info("variable is %s",sql_query)
                variable = cursor.execute(sql_query)
                sql_commit = "Commit"
                cursor.execute(sql_commit) 
                print("seq_no in after commit",seq_no)
                # pass_quries.append(seq_no)  # Add the sequence number to the list of  PASS executed queries
                # task_logger.info("Sequence numbers of pass executed queries: %s", pass_quries)
                # found = False
                # if restart_mode != "":
                #     if seq_no in pass_quries:
                #         print("Queries present in pass:", pass_quries)
                #         itervalue = query_iteration + 1
                #     else:
                #         print("Queries not present in pass")
                #         itervalue = 1


                # previous_restart_point = int(restart_point) - 1
                if restart_point is not None:
                 if restart_mode  != "no restart":
                    if int(restart_point) == seq_no:
                        # index_to_increment = 0 # Index of the element you want to increment
                        # query_iteration[index_to_increment] += 1
                        # itervalue = query_iteration[index_to_increment]
                        itervalue = task_iteration
                    elif int(restart_point) < seq_no:
                        itervalue = 1   
                 else:
                        itervalue = task_iteration
               
                audit(json_data, task_name,run_id,"SQL QUERY",s_query,itervalue,seq_no)
                audit(json_data,task_name,run_id,'ROWS AFFECTED',variable,itervalue,seq_no)
                audit(json_data, task_name,run_id,"RESULT","PASS",itervalue,seq_no)
               

            except Exception as e:
                logging.error("Error executing SQL query for sequence number %s: %s", seq_no, str(e))
                if restart_mode !="no restart":
                    if restart_point == 1 or restart_point == 0:
                        itervalue = 1      
                    else:
                        itervalue = task_iteration
                    
                    if int(restart_point) < seq_no:         # if fail query executing for the first time
                        iter_value = 1
                        
                    else:                                   # fail query executing for multiple time
                        # index_to_increment = 0  # Index of the element you want to increment
                        # query_iteration[index_to_increment] += 0
                        # itervalue = query_iteration[index_to_increment]     
                        itervalue = query_iteration 
            
                else:
                    iter_value = 1
                    itervalue =  1
                # if iter_value > 1:   # The query failed previously and is now passing
                   
                
                audit(json_data, task_name,run_id,"RESULT","FAIL",itervalue,seq_no)
                audit(json_data, task_name,run_id,'STATUS','FAILED',itervalue,seq_no)
                all_queries_passed = False 
                break
        if all_queries_passed :
            if restart_mode =="no restart":
                itervalue = 1
            else:
                if restart_point == 1 or restart_point == 0:   
                    itervalue = 1    
                else:
                   itervalue = task_iteration
            audit(json_data, task_name,run_id,'STATUS','COMPLETED',itervalue)
        return all_queries_passed    # Return True if all queries executed successfully    
    except Exception as error:
        task_logger.exception("error in sql_execution_task_download %s.", str(error))
        raise error
    


def latest_audit_status(task_nm):
    """gets audit status from audit table for given task"""
    try:
        task_logger.info("task name from api:%s",task_nm)
        url = "http://localhost:8080/api/audit/executequery/" + task_nm
        task_logger.info("url from api :%s",url)
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            json_data = response.json()
            if isinstance(json_data, list):
                column_values = json_data  # Assuming the response is already a list of column values
                print("Column Values:", column_values)      
            else:
                print("Invalid response format. Expected a list.")
                    # url_exists = bool(response.status_code)
                    # task_logger.info("The config json file exists in the  GITHUB repository.")
        else:
            print("Request failed with status code:", response.status_code)
        # if url_exists is False  :
        #     task_logger.info("PROCESS_ABORTED")
        #     sys.exit()
        task_logger.info("audit status code:%s",response.status_code)
        return column_values

    except mysql.connector.Error as err:
        if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
            logging.error("Something is wrong with audit config username or password")
        elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
            logging.error("Database does not exist")
        else:
            logging.error("Error:%s ", err)
        raise err
    except Exception as error1:
        logging.exception("execute_query() is %s.", str(error1))
        raise error1

def restart_sql_query(prj_nm, paths_data: str, task_name: str, json_data, run_id, query_iteration):
    restart_mode = json_data['sql_execution']['restart']
    restart_point = 0  # Set a default value for restart_point

    if restart_mode == "begin":
        # Handle the "begin" restart mode
        task_logger.info("Starting execution from the beginning.")
        restart_point = 1
        query_iteration = 0
        task_iteration = 1
        return execute_query(prj_nm, paths_data, task_name, json_data, run_id, restart_point, query_iteration, task_iteration=task_iteration)

    if restart_mode != "begin":
        # Handle other restart modes
        result = latest_audit_status(task_name)
        task_logger.info(result)

        if result and len(result) > 0:
            # Check if the result is not empty and has at least one element
            first_dict = result[0]
            second_dict = result[0]
            audit_value_task = first_dict['audit_value']
            task_logger.info("audit value from first dictionary: %s", audit_value_task)
            task_iteration = first_dict['iteration']
            audit_value_query = second_dict['audit_value']
            sequence = second_dict['sequence']

            # Rest of your code for handling the non-empty result
        else:
            # Handle the case when result is empty
            task_logger.info("Starting Execution of: %s", task_name)
            restart_point = 1
            query_iteration = 0
            task_iteration = 1
            # You may want to add additional error handling or return an appropriate response here
            return execute_query(prj_nm, paths_data, task_name, json_data, run_id, restart_point, query_iteration, task_iteration=task_iteration)

    # Assign a value to restart_point before the return statement


       

    if audit_value_task != "COMPLETED":
        url = "http://localhost:8080/api/audit/executequery/" + task_name
        task_logger.info("url from api :%s",url)
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            res_data = response.json()
            if isinstance(res_data, list):
                audited_data = res_data  # Assuming the response is already a list of column values
                print("Column Values:", audited_data)
                query_iteration = []

                    # Iterate over the list of dictionaries
                for dictionary in audited_data:
                        # Check if key1 exists in the dictionary
                    if "iteration" in dictionary:
                            # Retrieve the value of key1 and append it to the list
                        query_iteration.append(dictionary["iteration"])

                    # Print the values of qyery_iteration
                        print("results of query_iteration", query_iteration)
                        print(type(query_iteration))
            # run_id = second_dict['run_id']
            # query_iteration = second_dict['iteration']
            if audit_value_query == "FAIL":
                if restart_mode == "normal" or "":
                    task_logger.info("restarting the code in normal mode as query got failed at seq_no.: %s", sequence)
                elif restart_mode == "skip":
                    task_logger.info("restarting the code in skip mode as query got failed at seq_no.: %s", sequence)
                restart_point = sequence
                return execute_query(prj_nm, paths_data, task_name, json_data, run_id, query_iteration,restart_point=restart_point, task_iteration =task_iteration)
                
            else:
                task_logger.info("audit value is equal to fail that condition is not present ")
                task_iteration = task_iteration 
                audit(res_data, task_name,run_id,'STATUS','STARTED',task_iteration)
                audit(res_data, task_name,run_id,'STATUS','FAILED',task_iteration)
                                
    else:
            task_logger.info("Previous task got completed so starting execution from the beginning.")
            restart_point = 1
            query_iteration = 0
            if restart_mode =="skip":
                restart_point = 0 
            # Calling the execute_query function without restart_point
            return execute_query(prj_nm, paths_data, task_name, json_data, run_id,restart_point,query_iteration,task_iteration =task_iteration)


def engine_main(prj_nm,task_id,paths_data,run_id,file_path,iter_value):
    """function consists of pre_checks,conversion,ingestion,post_checks, qc report"""
    try:
        task_logger.info("entered into engine_main")
        json_data = task_json_read(paths_data,task_id,prj_nm)
        if json_data['task_type']=="Ingestion":    
            write_to_txt1(task_id,'STARTED',file_path)
            audit(json_data, task_id,run_id,'STATUS','STARTED',iter_value)
            json_checks = checks_mapping_read(paths_data)
            config_file_path = os.path.expanduser(paths_data["folder_path"])+paths_data["config_path"]
            dq_scripts_path=os.path.expanduser(paths_data["folder_path"])+paths_data['src']+ \
            paths_data["dq_scripts_path"]
            sys.path.insert(0, dq_scripts_path)
            definitions_qc = importlib.import_module("definitions_qc")
            dq_execution = json_data["task"]["data_quality_execution"]
            source = json_data["task"]["source"]
            target = json_data["task"]["target"]
            if target['target_type'] in {'mysql_write','postgres_write','snowflake_write',
                                        'mssql_write'}:
                session = begin_transaction(paths_data,json_data,config_file_path)

            

            # Precheck script execution starts here
            if dq_execution["pre_check_enable"] == 'Y' and\
            source["source_type"] in ('csv_read','parquet_read','postgres_read','mysql_read',
            'snowflake_read','mssql_read','mssql_read','aws_s3_read'):
                pre_check = definitions_qc.qc_pre_check(prj_nm,json_data,json_checks,
                paths_data,config_file_path,task_id,run_id,file_path,iter_value)
            elif source["source_type"] == "csv_read" and \
            (dq_execution['pre_check_enable'] == 'N' and \
            dq_execution['post_check_enable'] == 'N'):
                data_quality_features(json_data,definitions_qc)

            if dq_execution["pre_check_enable"] == 'Y':
                result = precheck_status(paths_data,json_data,run_id)
                all_pass = all(item.get('audit_value', '') == 'PASS' for item in result)
                if not all_pass:
                    task_logger.info("Qc has been failed in pre_check level")
                    task_logger.warning("Process Aborted")
                    audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
                    write_to_txt1(task_id,'FAILED',file_path)
                    sys.exit()

            # ingestion execution starts here
            read, write =read_write_imports(paths_data,json_data)
            if json_data["task"]["source"]["source_type"] in ("postgres_read","mysql_read",
            "snowflake_read","sqlserver_read"):
                data_fram = read(json_data,config_file_path,task_id,run_id,paths_data,
                file_path,iter_value)
                counter=0
                for i in data_fram :
                    counter+=1
                    if json_data["task"]["target"]["target_type"] != "csv_write":
                        value=write(json_data, i,counter,config_file_path,task_id,run_id,
                        paths_data,file_path,iter_value)
                        if value is False:
                            task_failed(task_id,file_path,json_data,run_id,iter_value)
                            return False
                        if value is True:
                            task_success(task_id,file_path,json_data,run_id,iter_value)
                            return False
                    else:
                        value=write(json_data, i,counter)
                        if value is False:
                            task_failed(task_id,file_path,json_data,run_id,iter_value)
                            return False
            elif source["source_type"] in ("csv_read", "parquet_read", "json_read",
                                       "xml_read", "xlsx_read"):
                data_fram=read(json_data,task_id,run_id,paths_data,file_path,iter_value)
                counter=0
                for i in data_fram :
                    counter+=1
                    if target["target_type"] == "rest_api_write":
                        value=write(json_data,i,task_id,run_id,paths_data,file_path,iter_value)
                        if value is False:
                            task_failed(task_id,file_path,json_data,run_id,iter_value)
                            return False
                        if value is True:
                            task_success(task_id,file_path,json_data,run_id,iter_value)
                            return False
                    elif target["target_type"] == "aws_s3_write":
                        value=write(json_data, i,config_file_path,task_id,run_id,
                        paths_data,file_path,iter_value)
                        if value is False:
                            task_failed(task_id,file_path,json_data,run_id,iter_value)
                            return False
                        if value is True:
                            task_success(task_id,file_path,json_data,run_id,iter_value)
                            return False
                    elif target["target_type"] not in ("csv_write", "parquet_write", "json_write",
                                                    "xml_write", "xlsx_write"):
                        value=write(json_data, i,counter,config_file_path,task_id,run_id,
                        paths_data,file_path,iter_value,session)
                        if value is False:
                            task_failed(task_id,file_path,json_data,run_id,iter_value)
                            return False
                        if value is True:
                            task_success(task_id,file_path,json_data,run_id,iter_value)
                            return False
                    else:
                        # task_logger.info(type(i))
                        value=write(json_data, i,counter)
                        if value is False:
                            task_failed(task_id,file_path,json_data,run_id,iter_value)
                            return False
            elif json_data["task"]["source"]["source_type"] in ("csvfile_read"
                ,"json_read" ,"xml_read","parquet_read","excel_read"):
                data_fram=read(json_data,task_id,run_id,paths_data,file_path,iter_value)
                counter=0
                for i in data_fram :
                    # task_logger.info(i)
                    counter+=1
                    if json_data["task"]["target"]["target_type"] == "csvfile_write":
                        value=write(json_data, i,counter)
                        if value=='Fail':
                            task_failed(task_id,file_path,json_data,run_id,iter_value)
                            return False
                    elif json_data["task"]["target"]["target_type"] == "s3_write":
                        value=write(json_data, i,config_file_path,task_id,run_id,
                        paths_data,file_path,iter_value)
                        if value=='Fail':
                            task_failed(task_id,file_path,json_data,run_id,iter_value)
                            return False
                    else:
                        value=write(json_data, i)
            else:
                task_logger.info("only ingestion available currently")

            # postcheck script execution starts here
            if target["target_type"] in ('csv_write') and \
            dq_execution["post_check_enable"] == 'Y':
                # post check code
                post_check=definitions_qc.qc_post_check(prj_nm,json_data, json_checks,paths_data,
                config_file_path,task_id,run_id,file_path,iter_value,None)
            elif target["target_type"] in ('postgres_write' ,'mysql_write',
                "snowflake_write",'mssql_write' ) and \
            dq_execution["post_check_enable"] == 'Y':
                post_check=definitions_qc.qc_post_check(prj_nm,json_data, json_checks,paths_data,
                config_file_path,task_id,run_id,file_path,iter_value,session)
            #qc report generation
            new_path=os.path.expanduser(paths_data["folder_path"])+paths_data[
                "local_repo"]+paths_data["programs"]+prj_nm+\
            paths_data["qc_reports_path"]
            if dq_execution["pre_check_enable"] == 'Y' and dq_execution["post_check_enable"] == 'N':
                post_check = pd.DataFrame()
                definitions_qc.qc_report(pre_check,post_check,new_path,file_path,
                            json_data,task_id,run_id,iter_value)
            elif dq_execution["pre_check_enable"] == 'N' and dq_execution["post_check_enable"] == 'Y':
                pre_check = pd.DataFrame()
                definitions_qc.qc_report(pre_check,post_check,new_path,file_path,
                            json_data,task_id,run_id,iter_value)
            elif dq_execution["pre_check_enable"] == 'Y' and dq_execution["post_check_enable"] == 'Y':
                definitions_qc.qc_report(pre_check,post_check,new_path,file_path,
                            json_data,task_id,run_id,iter_value)

            # for item in json_data['task']['data_quality']:
            #     if item['type'] != 'post_check':
            #         task_logger.info("Post check is enabled although didn't have any postcheck")

            #session related script execution starts here
            if target['target_type'] in {'mysql_write',
                'snowflake_write','postgres_write', 'csv_write','mssql_write'}:
                if dq_execution['post_check_enable'] == 'Y':
                    result = postcheck_status(paths_data,json_data,run_id)
                    # Checking if all results are 'PASS'
                    # all_pass = all(item[0] == 'PASS' for item in result)
                    all_pass = all(item.get('audit_value', '') == 'PASS' for item in result)
                    if all_pass:
                        if target['target_type'] in {'mysql_write',
                        'snowflake_write','postgres_write','mssql_write'}:
                            session.commit()
                            task_logger.info("Transaction commited successfully!")
                    else:
                        if target['target_type'] in {'csv_write'}:
                            folder_path = os.path.expanduser(paths_data['folder_path'])
                            tgt_file_name = target['file_name']
                            inp_file_names = [os.path.join(folder_path+paths_data["local_repo"]+paths_data[
                            'programs']+prj_nm+paths_data['target_files_path']+tgt_file_name)]
                            task_logger.info(inp_file_names)
                            out_zip_file = os.path.join(folder_path+paths_data["local_repo"]+paths_data[
                            'programs']+prj_nm+paths_data['archive_path']+'target/'+str(
                            json_data['id'])+'_'+ json_data['task_name']+'.zip')
                            task_logger.info(out_zip_file)
                            archive_files(inp_file_names, out_zip_file)
                            os.remove(os.path.join(folder_path+paths_data["local_repo"]+paths_data[
                            'programs']+prj_nm+paths_data['target_files_path']+tgt_file_name))
                        task_logger.warning("Transaction Rolled back due to Some of the dq" \
                                "checks got failed on target level")
                        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
                        write_to_txt1(task_id,'FAILED',file_path)
                        sys.exit()
                else:
                    if target['target_type'] not in {'csv_write','aws_s3_write','parquet_write'}:
                        session.commit()
                        task_logger.info("Transaction commited successfully!")
            task_logger.info(TASK_LOG,task_id)
            write_to_txt1(task_id,'SUCCESS',file_path)
            audit(json_data, task_id,run_id,'STATUS','COMPLETED',iter_value)

        elif json_data['task_type']=="SQL Execution":
            if json_data ['sql_execution']['restart'] != "no restart":
            #if json_data ['sql_execution']['restart'] == "normal" or json_data ['sql_execution']['restart'] == "begin":
                #audit(json_data, task_id,run_id,'STATUS','STARTED',iter_value)
                value = restart_sql_query(prj_nm, paths_data, task_id, json_data, run_id,iter_value)
                #task_logger.info("value in fail condition: %s",value)
                
            else:
                #audit(json_data, task_id,run_id,'STATUS','STARTED',iter_value)
                value = execute_query(prj_nm,paths_data,task_id,json_data,run_id,iter_value)
                #task_logger.info("value in without restart condition: %s",value)
            if value :
                task_logger.info(TASK_LOG,task_id)
                write_to_txt1(task_id,'SUCCESS',file_path)
                #audit(json_data, task_id,run_id,'STATUS','COMPLETED',iter_value)
            else:
                task_logger.info("its going inside else condition")
                #audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
    except Exception as error:
        audit(json_data, task_id,run_id,'STATUS','FAILED',iter_value)
        write_to_txt1(task_id,'FAILED',file_path)
        task_logger.warning(FAIL_LOG_STATEMENT, task_id)
        task_logger.exception("error in  %s.", str(error))
        raise error
