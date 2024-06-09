""" importing modules """
import json
import logging
import time
import sys
import os
import glob
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
import re
import multiprocessing as mp
import pandas as pd
import requests
import download

STATUS_LIST=[]

main_logger = logging.getLogger('main_logger')
JSON = ".json"
TASK_TRIGGER='triggering the task run %s'
START_PROCESS = 'Starting process %s'
TASK_OR_PIPE_LINE_NM = "taskorpipeline_name"
BULK_ING = 'Bulk Ingestion'

def execute_job(prj_nm,paths_data,task_id,run_id,file_path,iter_value):
    """function for master_executor calling"""
    try:
        logging_path= os.path.expanduser(paths_data["folder_path"])+paths_data["local_repo"]+\
        paths_data["programs"]+prj_nm+paths_data["task_log_path"]
        logging.info(logging_path)
        logging.info("inside master executor")
        download.execute_engine(prj_nm,task_id,paths_data,run_id,file_path,iter_value)
    except Exception as error:
        logging.exception("error in master_executor file %s.", str(error))
        raise error

def pipeline_json_read(path_data,proj_nm,pip_nm):
    """function to load pipeline json data to a variable"""
    try:
        new_path= os.path.expanduser(path_data["folder_path"])+path_data["local_repo"]+\
        path_data["programs"]+proj_nm+path_data["pipeline_json_path"]+ pip_nm+ JSON
        with open(r""+new_path,"r", encoding='utf-8') as jsonfile:
            json_data1 = json.load(jsonfile)
        return json_data1
    except Exception as error:
        main_logger.exception("error in pipeline_json_read %s.", str(error))
        raise error

def task_json_read(path_data, proj_nm, task_nm):
    """Function to load pipeline JSON data to a variable."""
    try:
        new_path= os.path.expanduser(path_data["folder_path"])+path_data["local_repo"]+\
        path_data["programs"]+proj_nm+path_data["task_json_path"]+ task_nm + JSON
        with open(r""+new_path,"r", encoding='utf-8') as jsonfile:
            json_data1 = json.load(jsonfile)
        return json_data1
    except FileNotFoundError as fnf_error:
        main_logger.warning("File not found: %s", str(fnf_error))
        return None
    except Exception as error:
        main_logger.exception("Error in task_json_read %s.", str(error))
        return None

def orc_get_log_status(file_path,new_dep_task_list):
    """reading the orchestration text file for getting the statuses"""
    try:
        df_2 =pd.read_csv(file_path, sep='\t')
        # loop for independent tasks
        for i, row in df_2.iterrows():
            if str(row['task_depended_on'])=='0':
                main_logger.info(str(row['task_name']+" task is "+row['Job_Status']))

        pipeline_status_list = df_2['Job_Status'].to_list()
        #loop for dependent tasks
        # dependent_task =set(df_2[df_2['task_depended_on'] != 0]['task_name'].to_list())
        for i in new_dep_task_list:
            status = df_2[df_2['task_name'] == i]['Job_Status'].to_list()
            if 'FAILED' in status:
                main_logger.info("%s task is FAILED", i)
            elif 'STARTED' in status:
                main_logger.info("%s task is STARTED", i)
            elif 'Start' in status:
                main_logger.info("%s task is NOT STARTED", i)
            else :
                main_logger.info("%s task is SUCCESS", i)
        return pipeline_status_list
    except Exception as error:
        main_logger.exception("error in orc_get_log_status %s.", str(error))
        raise error

def dependent_task_loop(dependent_task,file_path,prj_nm,paths_data,run_id,iter_value):
    """function for executing dependent tasks"""
    try:
        #Running the dependent jobs in a loop
        length = int(len(dependent_task))
        is_break='N'
        dep_processes = []
        while length>0:
            dependent_task1 =  dependent_task
            for row in dependent_task1:
                df_2 =pd.read_csv(file_path, sep='\t')
                success_ls=df_2[df_2['Job_Status'] == 'SUCCESS']['task_name'].to_list()
                failed_ls=df_2[df_2['Job_Status'] == 'FAILED']['task_name'].to_list()
                task_depend=df_2[df_2['task_name'] == row]['task_depended_on'].to_list()
                # if there are failed tasks in failed_ls and
                # if failed tasks is subset of tasks depended on
                # if tasks depended on are subset of failed  list
                if (len(failed_ls) != 0) & (set(failed_ls).issubset(set(task_depend)) |\
                set(task_depend).issubset(set(failed_ls)) is True ):
                    main_logger.warning("Task failed so stopping execution of %s", row )
                    is_break='Y'
                    break
                # if tasks depended on are subset of success list
                if set(task_depend).issubset(set(success_ls)) is False:
                    time.sleep(3)
                else:
                    main_logger.info(TASK_TRIGGER, row)
                    dep_task = mp.Process(target = execute_job, args = [prj_nm,paths_data,row,
                    run_id,file_path,iter_value], name = 'Process_' + str(row))
                    dep_processes.append(dep_task)
                    main_logger.info(START_PROCESS ,str(dep_task.name))
                    dep_task.start()
                    dependent_task.remove(row)
                    length=length-1
                    for process in dep_processes:
                        process.join()
            if is_break=='Y':
                break
    except Exception as error:
        main_logger.exception("error in dependent_loop %s.", str(error))
        raise error

def independent_task_loop(independent_task,prj_nm,paths_data,run_id,
            file_path,iter_value):
    """unction for independent task execution"""
    try:
        #Running the independent jobs in a loop###
        ind_processes = []
        for i in independent_task:
            main_logger.info(TASK_TRIGGER, i)
            ind_task = mp.Process(target = execute_job, args = [prj_nm,paths_data,i,run_id,
            file_path,iter_value],name = 'Process_' + str(i))
            ind_processes.append(ind_task)
            main_logger.info(START_PROCESS ,str(ind_task.name))
            ind_task.start()
            # time.sleep(3)
        for process in ind_processes:
            process.join()
    except Exception as error:
        main_logger.exception("error in independent_loop %s.", str(error))
        raise error


def orchestration_execution(prj_nm,paths_data,pip_nm,run_id,iter_value):
    """function for executing orchestration process"""
    # Readding Pipeline json file
    json_data = pipeline_json_read(paths_data,prj_nm,pip_nm)
    task_details=json_data['tasks_details'].items()

    main_logger.info('Pipeline execution initiated')
    #Script starts here
    independent_task=[]
    dependent_task=[]
    new_dep_task_list=[]
    for key, value in task_details:
        if value == 0:
            independent_task.append(key)
        elif value != 0:
            dependent_task.append(key)
            new_dep_task_list.append(key)
    file_path=os.path.expanduser(paths_data["folder_path"])+paths_data["local_repo"
    ]+paths_data["programs"]+prj_nm+\
    paths_data["status_txt_file_path"]+pip_nm+'_Pipeline_'+run_id+".txt"
    #Running the independent jobs in a loop###
    independent_task_loop(independent_task,prj_nm,paths_data,run_id,
            file_path,iter_value)
    #Running the dependent jobs in a loop
    dependent_task_loop(dependent_task,file_path,prj_nm,paths_data,run_id,iter_value)
    #for logging all statuses in pipeline log
    pipeline_status_list= orc_get_log_status(file_path,new_dep_task_list)
    return pipeline_status_list

def restart_orchestration_execution(prj_nm,paths_data,pip_nm,run_id,iter_value):
    """function for executing orchestration process"""
    # Readding Pipeline json file
    json_data = pipeline_json_read(paths_data,prj_nm,pip_nm)
    task_details=json_data['tasks_details'].items()
    main_logger.info('Pipeline execution initiated')
    #Script starts here
    independent_task=[]
    dependent_task=[]
    new_dep_task_list=[]
    text_filepath=os.path.expanduser(paths_data["folder_path"])+paths_data["local_repo"]+\
    paths_data["programs"]+prj_nm+paths_data["status_txt_file_path"]
    list_of_files = glob.glob(text_filepath+pip_nm+'*'+".txt")
    latest_file = max(list_of_files, key=os.path.getctime)
    main_logger.info("current txt file path:%s", latest_file)
    #reading previous run text file
    df_2 =pd.read_csv(latest_file, sep='\t')
    success_lss=df_2[df_2['Job_Status'] == 'SUCCESS']['task_name'].to_list()
    for key, value in task_details:
        if value == 0:
            independent_task.append(key)
        elif value != 0:
            dependent_task.append(key)
            new_dep_task_list.append(key)
    file_path=os.path.expanduser(paths_data["folder_path"])+paths_data["local_repo"]+\
    paths_data["programs"]+prj_nm+paths_data["status_txt_file_path"]+pip_nm+'_Pipeline_'+\
    run_id+".txt"
    independent_task=list(set(independent_task) - set(success_lss))
    main_logger.info("independent_tasks running:%s",independent_task)
    dependent_task=list(set(dependent_task) - set(success_lss))
    main_logger.info("dependent_tasks running:%s",dependent_task)
    #Running the independent jobs in a loop###
    independent_task_loop(independent_task,prj_nm,paths_data,run_id,
            file_path,iter_value)
    #Running the dependent jobs in a loop
    dependent_task_loop(dependent_task,file_path,prj_nm,paths_data,run_id,iter_value)
    pipeline_status_list= orc_get_log_status(file_path,new_dep_task_list)
    return pipeline_status_list

###################################################################################################
#   This Function flatten the table to 1:1
#   Means if the `task_depended_on` has multiple jobs, then `task_name` will have multiple rows
#   Run the function and check the source and output result.
###################################################################################################

def df_flatten(df_process):
    'This function flatten the composite dataframe to contain parent and child job'
    df_flat = pd.DataFrame(columns=["task_name","task_depended_on"])
    for _, row in df_process.iterrows():
        if row[1]==0:
            x_1=list(str(row[1]))
        else:
            x_1=row[1]
        if len(x_1) == 1 or x_1==0:
            df_flat.loc[df_flat.shape[0]] = [row[0], x_1[0]]
        else:
            for i in x_1:
                df_flat.loc[df_flat.shape[0]] = [row[0], i]
    return df_flat

##################################################################################################
#   This Function will traverse the all task_name -> task_depended_on -> task_name ->
# on and on till end
#   Means if the `task_depended_on` has multiple jobs, then `task_name` will have
# multiple rows
#   while traversing, If a node is already discovered then exception `Cyclic decteded`,
#  else success.
#   This is a recusion function to find last node or already visited node.
#################################################################################################

def node_visit(df_flat, u_1, discovered, finished):
    """checking cyclic dependency"""
    discovered.add(u_1)
    next_tasks = df_flat[df_flat['task_depended_on'] == u_1]['task_name'].to_list()
    for v_1 in next_tasks:
        # Detect cycles
        if v_1 in discovered:
            raise ValueError(f"Cycle detected: found a back edge from {u_1} to {v_1}.")
        # Recurse into DFS tree
        if v_1 not in finished:
            node_visit(df_flat, v_1, discovered, finished)
    discovered.remove(u_1)
    finished.add(u_1)
    return discovered, finished

#################################################################################################
#   This Function warapper function to check for Cyclic from start of flow.
#   Means if the `task_depended_on` has multiple jobs, then `task_name` will have multiple rows
#   while traversing,If a node is already discovered then exception `Cyclic decteded`,else success.
#   This is a recusion function to find last node or already visited node.
##################################################################################################
def check_for_cyclic(df_flat):
    """cyclic dependency checks"""
    discovered = set()
    finished = set()
    starting_jobs = df_flat[df_flat['task_depended_on'] == '0']['task_name'].tolist()
    dependent_job=df_flat[df_flat['task_depended_on'] != '0']['task_name'].tolist()
    try:
        for u_1 in starting_jobs:
            if u_1 not in discovered and u_1 not in finished:
                discovered, finished = node_visit(df_flat, u_1, discovered, finished)
        for u_1 in dependent_job:
            if u_1 not in discovered and u_1 not in finished:
                discovered, finished = node_visit(df_flat, u_1 , discovered, finished)
    except Exception as exp:
        return "error",exp
    return "success", finished

##############################################################################################
#   This Function check for
#   Means if the `task_depended_on` has multiple jobs, then `task_name` will have multiple rows
#   while traversing, If a node is already discovered then exception `Cyclic decteded`,else success
#   This is a recusion function to find last node or already visited node.
###############################################################################################

def job_check(df_flat):
    'This function validates the struction for job and parent job structure.'
    v_err_status = 'success'
    v_err_msg = ''
    # Checking all parent jobs are subset of children jobs.
    set_childjob = set(df_flat['task_name'])
    set_parentjob = set(df_flat['task_depended_on'])
    if  '0' not in set_parentjob:
        v_err_status = 'failure'
        v_err_msg = 'Error: Entry point Job not found'
        return v_err_status, v_err_msg
    # Checking all parent jobs are subset of children jobs.
    set_parentjob.remove('0') # removing parent=0
    if set_parentjob.issubset(set_childjob) is False:
        v_err_status = 'failure'
        v_err_msg = 'Error: Depended on (parent task) should be part of Jobs (all task).'
        return v_err_status, v_err_msg
    # Check for cyclic dependency between jobs.
    v_error_status, v_err_msg = check_for_cyclic(df_flat)
    if v_error_status == 'error':
        v_err_status = 'failure'
        v_err_msg = 'Error: Cyclic dependendcy found in pipeline.'
        return v_err_status, v_err_msg
    return v_err_status, v_err_msg


def main_job(prj_nm,paths_data,pip_nm):
    """pipeline execution"""
    # Read the csv file
    json_data = pipeline_json_read(paths_data,prj_nm,pip_nm)
    df_3=pd.DataFrame(json_data['tasks_details'].items())
    df_return = df_flatten(df_3)
    # set(df_return['task_name'])
    status,msg=job_check(df_return)
    main_logger.info(status)
    main_logger.info(msg)
    if status=='failure':
        main_logger.error("Issue with the Pipeline json")
        sys.exit()
    else:
        main_logger.info("reading pipeline json completed")

def audit(json_data, task_name,run_id,status,value,itervalue,paths_data):
    """ create audit json file and audits event records into it"""
    try:
        url = paths_data['audit_api_url']
        audit_data = [{
                    "pipeline_id": json_data["pipeline_id"],
                    TASK_OR_PIPE_LINE_NM: task_name,
                    "run_id": run_id,
                    "iteration": itervalue,
                    "audit_type": status,
                    "audit_value": value,
                    "process_dttm" : datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                }]
        requests.post(url, json=audit_data, timeout=60)
    except Exception as error:
        main_logger.exception("error in audit %s.", str(error))
        raise error

def get_time(log_file_path1,log_file_name1):
    """function to get start and end times from log files"""
    # Open the log file
    with open(log_file_path1+log_file_name1, 'r', encoding="utf-8") as file:
        log_data = file.read()
    # Define a regular expression pattern to match the date and time format in the log file
    pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
    # Find all matches of the pattern in the log data
    matches = re.findall(pattern, log_data)
    # Check if the matches list is not empty
    if matches:
        # Convert the first and last match to datetime objects
        starting_time = datetime.strptime(matches[0], '%Y-%m-%d %H:%M:%S')
        ending_time = datetime.strptime(matches[-1], '%Y-%m-%d %H:%M:%S')
    else:
        main_logger.info("matches not found")
    return starting_time,ending_time


def html_email_code(msg,message,paths_data,prj_nm,log_file_path,log_file_name,
    name,run_id,exe_type,task_type,iter_value):
    """html code for email in started, failed and completed cases"""
    try:
        url = (f"{paths_data['audit_api_url']}"
            f"/getTaskAndPipeline/{run_id}")
        main_logger.info("URL from API: %s", url[:30]+"...")
        response = requests.get(url, timeout=100)
        if response.status_code == 200:
            data = response.json()
        else:
            main_logger.error("Request failed with status code: %s", response.status_code)
        msg['From'] = paths_data["from_addr"]
        msg['To'] = paths_data["to_addr"]
        msg['Cc'] = paths_data["cc_addr"]
        i,j =get_time(log_file_path,log_file_name)
        if exe_type == 'pipeline':
            distinct_values = {}
            # Extracting distinct values
            for item in data:
                task_name = item['taskorpipeline_name']
                audit_type = item['audit_type']
                audit_value = item['audit_value']
                if task_name not in distinct_values:
                    distinct_values[task_name] = {}
                if audit_type not in distinct_values[task_name]:
                    distinct_values[task_name][audit_type] = audit_value
                else:
                    # If audit_type already exists, append it as a new key-value pair
                    distinct_values[task_name][audit_type + '1'] = audit_value
            # Organizing the distinct values into the desired format
            output = []
            for task_name, values in distinct_values.items():
                task_data = {"taskorpipeline_name": task_name}
                task_data.update(values)
                output.append(task_data)
            # Convert the output to JSON format
            output_json = json.dumps(output, indent=4)
            pipeline_nme = None
            output_data = json.loads(output_json)  # Convert back to list of dictionaries
            for entry in output_data:
                if entry['STATUS'] == "INITIATED":
                    pipeline_nme = entry.get('taskorpipeline_name')
                    break
            task_names = [item['taskorpipeline_name'] for item in output_data \
             if item['STATUS'] != 'INITIATED']
            homepath = str(Path(paths_data['folder_path']).expanduser())
            logging_path= homepath+"/"+paths_data["local_repo"]+ \
            paths_data["programs"]+prj_nm+paths_data["task_log_path"]
            for task_name in task_names:
                task_log_file = os.path.join(logging_path, 
                f"{task_name}_taskLog_{run_id}_{iter_value}.log")
                try:
                    with open(task_log_file, "rb") as log_data:
                        attachment = MIMEApplication(log_data.read(), _subtype="txt")
                        attachment.add_header('Content-Disposition', 'attachment',
                        filename=f"{task_name}_taskLog_{run_id}_{iter_value}.log")
                        msg.attach(attachment)
                except FileNotFoundError:
                    # main_logger.error("File not found: %s. Continuing execution.",task_log_file)
                    pass
            if message == "STARTED": # if job Started
                msg['Subject'] = f"STARTED: IKART: {pipeline_nme}"
                body = f"""<p>Hi all,</p>
                        <p style="color:green;"> The Pipeline execution has Started.</p>
                        <p style="color:black;"><b>Run ID</b> : {run_id}</p>
                        <p style="color:black;"><b>Project</b> : {prj_nm}</p>
                        <p style="color:black;"><b>Pipeline</b> : {pipeline_nme}</p>
                        <p>Thanks and Regards,</p>
                        <p>{paths_data["team_nm"]}</p>
                        <p><strong>*Note: This is an auto-generated mail. Please do not reply.*</strong></p>
                        """
            elif message == "COMPLETED": # if job completed
                task_rows = ""
                sl_no = 0
                for item in output_data:
                    if item.get("STATUS") != "INITIATED":
                        # This is a task
                        unique_task = item['taskorpipeline_name']
                        json_data = task_json_read(paths_data, prj_nm, item['taskorpipeline_name'])
                        injection_type = json_data["task_type"]

                        # Check if injection_type is Bulk Ingestion
                        if injection_type == BULK_ING:
                            distinct_values = {}
                            # Extracting distinct values
                            for item in data:
                                task_name = item['taskorpipeline_name']
                                audit_type = item['audit_type']
                                audit_value = item['audit_value']
                                task_group = item['task_group']
                                sequence = item['sequence']
                                if task_name not in distinct_values:
                                    distinct_values[task_name] = {}
                                if task_group not in distinct_values[task_name]:
                                    distinct_values[task_name][task_group] = {}
                                if sequence is not None:
                                    if 'sequence' not in distinct_values[task_name][task_group]:
                                        distinct_values[task_name][task_group]['sequence'] = {}
                                    if sequence not in distinct_values[task_name][task_group]['sequence']:
                                        distinct_values[task_name][task_group]['sequence'][sequence] = {}
                                    distinct_values[task_name][task_group]['sequence'][sequence][audit_type] = audit_value
                                else:
                                    if audit_type not in distinct_values[task_name][task_group]:
                                        distinct_values[task_name][task_group][audit_type] = audit_value
                                    else:
                                        distinct_values[task_name][task_group][audit_type + '1'] = audit_value

                            # Organizing the distinct values into the desired format
                            output = {"task_groups": {}}
                            for task_name, groups in distinct_values.items():
                                output["task_groups"][task_name] = groups

                            # Convert the output to JSON format
                            output_json = json.dumps(output, indent=4)
                            output_data = json.loads(output_json)
                            task_groups = output_data['task_groups']
                            task_group_name = unique_task
                            tasks = task_groups[task_group_name]

                            for task_id, task_details in tasks.items():
                                if task_id == "null":
                                    continue

                                if 'sequence' in task_details:
                                    for seq_id, seq_details in task_details['sequence'].items():
                                        src_count = seq_details.get('SRC_RECORD_COUNT', 'NA')
                                        trgt_count = seq_details.get('TRGT_RECORD_COUNT', 'NA')
                                        status = seq_details.get('STATUS', 'NA')
                                        bg_color = '#3cb371' if status == 'COMPLETED' else 'red' if status == 'FAILED' else 'transparent'
                                        task_rows += f"""
                                        <tr style="border:1px solid gray;">
                                            <td style="border:1px solid gray;">{task_group_name}</td>
                                            <td style="border:1px solid gray;">{injection_type}</td>
                                            <td style="border:1px solid gray;">{task_id}</td>
                                            <td style="border:1px solid gray;">{seq_id}</td>
                                            <td style="border:1px solid gray;">{src_count}</td>
                                            <td style="border:1px solid gray;">{trgt_count}</td>
                                            <td style="border:1px solid gray;">{i}</td>
                                            <td style="border:1px solid gray;">{j}</td>
                                            <td style="border:1px solid gray; background-color: {bg_color};">{status}</td>
                                        </tr>
                                        """

                        else:
                            # If injection_type is not Bulk Ingestion, continue with the original task_rows generation
                            task_rows += f"""
                            <tr style="border:1px solid gray;">
                                <td style="border:1px solid gray;">{item['taskorpipeline_name']}</td>
                                <td style="border:1px solid gray;">{injection_type}</td>
                                <td style="border:1px solid gray;">NA</td>
                                <td style="border:1px solid gray;">NA</td>
                                <td style="border:1px solid gray;">{item.get('SRC_RECORD_COUNT')}</td>
                                <td style="border:1px solid gray;">{item.get('TRGT_RECORD_COUNT')}</td>
                                <td style="border:1px solid gray;">{i}</td>
                                <td style="border:1px solid gray;">{j}</td>
                                <td id="T_cc241_row0_col7" style="border:1px solid gray; background-color: { 'red' if 'FAILED' in [item.get('STATUS'), item.get('STATUS1')] else ('#3cb371' if any(status in ['COMPLETED', 'SKIPPED'] for status in [item.get('STATUS'), item.get('STATUS1')]) else '') };">{ next((status for status in [item.get('STATUS'), item.get('STATUS1')] if status in ['COMPLETED', 'SKIPPED', 'FAILED']), '') }</td>
                            </tr>
                            """

                    sl_no += 1

                # Close the tbody and table tags
                task_rows += "</tbody></table>"

                msg['Subject'] = f"SUCCESS: IKART Summary Report: {pipeline_nme}"
                body = f"""<p>Hi all,</p>
                    <p style="color:green;"> The Pipeline execution has completed Sucessfully.</p>
                    <p style="color:black;"><b>Run ID</b> : {run_id}</p>
                    <p style="color:black;"><b>Project</b> : {prj_nm}</p>
                    <p style="color:black;"><b>Pipeline</b> : {pipeline_nme}</p>
                    """

                body += f"""
                    <table style="border:1px solid black; border-collapse: collapse;">
                    <thead style="border:1px solid black;">
                    <tr>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">TASK_NAME</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">JOB_TYPE</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">GROUP</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">SEQ</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">SRC_CNT</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">TGT_CNT</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">START_TIME</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">END_TIME</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">STATUS</th>
                    </tr>
                    </thead>
                    <tbody>
                    {task_rows}
                    </tbody>
                    </table>"""
                body += f"""<p style="color:black;"><b>Log Path</b> : {log_file_path+log_file_name}</p>"""
                # Loop to add additional task log paths
                for task_name in task_names:
                    task_log_file = os.path.join(logging_path, f"{task_name}_taskLog_{run_id}_{iter_value}.log")
                    body += f"""<p style="color:black;"><b>{task_name} Log Path</b> : {task_log_file}</p>"""

                body += """
                    <p>Thanks and Regards,</p>
                    <p>{paths_data["team_nm"]}</p>
                    <p><strong>*Note: This is an auto-generated mail. Please do not reply.*</strong></p>
                    """
            elif message == "FAILED": # if job Failed

                task_rows = ""
                sl_no = 0
                for item in output_data:
                    if item.get("STATUS") != "INITIATED":
                        # This is a task
                        unique_task = item['taskorpipeline_name']
                        json_data = task_json_read(paths_data, prj_nm, item['taskorpipeline_name'])
                        injection_type = json_data["task_type"]

                        # Check if injection_type is Bulk Ingestion
                        if injection_type == BULK_ING:
                            distinct_values = {}
                            # Extracting distinct values
                            for item in data:
                                task_name = item['taskorpipeline_name']
                                audit_type = item['audit_type']
                                audit_value = item['audit_value']
                                task_group = item['task_group']
                                sequence = item['sequence']

                                if task_name not in distinct_values:
                                    distinct_values[task_name] = {}

                                if task_group not in distinct_values[task_name]:
                                    distinct_values[task_name][task_group] = {}

                                if sequence is not None:
                                    if 'sequence' not in distinct_values[task_name][task_group]:
                                        distinct_values[task_name][task_group]['sequence'] = {}
                                    if sequence not in distinct_values[task_name][task_group]['sequence']:
                                        distinct_values[task_name][task_group]['sequence'][sequence] = {}
                                    distinct_values[task_name][task_group]['sequence'][sequence][audit_type] = audit_value
                                else:
                                    if audit_type not in distinct_values[task_name][task_group]:
                                        distinct_values[task_name][task_group][audit_type] = audit_value
                                    else:
                                        distinct_values[task_name][task_group][audit_type + '1'] = audit_value

                            # Organizing the distinct values into the desired format
                            output = {"task_groups": {}}
                            for task_name, groups in distinct_values.items():
                                output["task_groups"][task_name] = groups

                            # Convert the output to JSON format
                            output_json = json.dumps(output, indent=4)
                            output_data = json.loads(output_json)
                            task_groups = output_data['task_groups']
                            task_group_name = unique_task
                            tasks = task_groups[task_group_name]

                            for task_id, task_details in tasks.items():
                                if task_id == "null":
                                    continue

                                if 'sequence' in task_details:
                                    for seq_id, seq_details in task_details['sequence'].items():
                                        src_count = seq_details.get('SRC_RECORD_COUNT', 'NA')
                                        trgt_count = seq_details.get('TRGT_RECORD_COUNT', 'NA')
                                        status = seq_details.get('STATUS', 'NA')
                                        bg_color = '#3cb371' if status == 'COMPLETED' else 'red' if status == 'FAILED' else 'transparent'
                                        task_rows += f"""
                                        <tr style="border:1px solid gray;">
                                            <td style="border:1px solid gray;">{task_group_name}</td>
                                            <td style="border:1px solid gray;">{injection_type}</td>
                                            <td style="border:1px solid gray;">{task_id}</td>
                                            <td style="border:1px solid gray;">{seq_id}</td>
                                            <td style="border:1px solid gray;">{src_count}</td>
                                            <td style="border:1px solid gray;">{trgt_count}</td>
                                            <td style="border:1px solid gray;">{i}</td>
                                            <td style="border:1px solid gray;">{j}</td>
                                            <td style="border:1px solid gray; background-color: {bg_color};">{status}</td>
                                        </tr>
                                        """

                        else:
                            # If injection_type is not Bulk Ingestion, continue with the original task_rows generation
                            # <td style="border:1px solid gray; width:20px; text-align:center">{sl_no}</td>
                            task_rows += f"""
                            <tr style="border:1px solid gray;">
                                <td style="border:1px solid gray;">{item['taskorpipeline_name']}</td>
                                <td style="border:1px solid gray;">{injection_type}</td>
                                <td style="border:1px solid gray;">NA</td>
                                <td style="border:1px solid gray;">NA</td>
                                <td style="border:1px solid gray;">{item.get('SRC_RECORD_COUNT')}</td>
                                <td style="border:1px solid gray;">{item.get('TRGT_RECORD_COUNT')}</td>
                                <td style="border:1px solid gray;">{i}</td>
                                <td style="border:1px solid gray;">{j}</td>
                                <td id="T_cc241_row0_col7" style="border:1px solid gray; background-color: { 'red' if 'FAILED' in [item.get('STATUS'), item.get('STATUS1')] else ('#3cb371' if any(status in ['COMPLETED', 'SKIPPED'] for status in [item.get('STATUS'), item.get('STATUS1')]) else '') };">{ next((status for status in [item.get('STATUS'), item.get('STATUS1')] if status in ['COMPLETED', 'SKIPPED', 'FAILED']), '') }</td>
                            </tr>
                            """

                    sl_no += 1

                # Close the tbody and table tags
                task_rows += "</tbody></table>"

                msg['Subject'] = f"FAILURE: IKART Summary Report: {pipeline_nme}"
                body = f"""<p>Hi all,</p>
                    <p style="color:red;"> The Pipeline execution has Failed.</p>
                    <p style="color:black;"><b>Run ID</b> : {run_id}</p>
                    <p style="color:black;"><b>Project</b> : {prj_nm}</p>
                    <p style="color:black;"><b>Pipeline</b> : {pipeline_nme}</p>
                    <p style="color:black;"><b>Log Path</b> : {log_file_path+log_file_name}</p>
                    <table style="border:1px solid black; border-collapse: collapse;">
                    <thead style="border:1px solid black;">
                    <tr>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">TASK_NAME</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">JOB_TYPE</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">GROUP</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">SEQ</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">SRC_CNT</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">TGT_CNT</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">START_TIME</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">END_TIME</th>
                    <th style="border:1px solid gray; background-color: #C0C2C9;">STATUS</th>
                    </tr>
                    </thead>
                    <tbody>
                    {task_rows}
                    </tbody>
                    </table>"""

                body+=f"""<p style="color:black;"><b>Log Path</b> : {log_file_path+log_file_name}</p>"""

                # Loop to add additional task log paths
                for task_name in task_names:
                    task_log_file = os.path.join(logging_path, f"{task_name}_taskLog_{run_id}_{iter_value}.log")
                    body += f"""<p style="color:black;"><b>{task_name} Log Path</b> : {task_log_file}</p>"""
                    # <th style="border:1px solid gray; background-color: #C0C2C9; width:20px">Sl.No.</th>

                body +="""
                    <p>Thanks and Regards,</p>
                    <p>{paths_data["team_nm"]}</p>
                    <p><strong>*Note: This is an auto-generated mail. Please do not reply.*</strong></p>
                    """

            msg.attach(MIMEText(body, 'html'))
        else:
            ################################# task execution ###############################
            if task_type == BULK_ING:
                homepath = str(Path(paths_data['folder_path']).expanduser())
                logging_path= homepath+"/"+paths_data["local_repo"]+ \
                paths_data["programs"]+prj_nm+paths_data["task_log_path"]
                task_log_file = os.path.join(logging_path, f"{name}_taskLog_{run_id}_{iter_value}.log")
                try:
                    with open(task_log_file, "rb") as log_data:
                        attachment = MIMEApplication(log_data.read(), _subtype="txt")
                        attachment.add_header('Content-Disposition', 'attachment',
                                            filename=f"{name}_taskLog_{run_id}_{iter_value}.log")
                        msg.attach(attachment)
                except FileNotFoundError:
                    # main_logger.error(f"File not found: {task_log_file}. Continuing execution.")
                    pass
                distinct_values = {}
                # Extracting distinct values
                for item in data:
                    task_name = item['taskorpipeline_name']

                    audit_type = item['audit_type']
                    audit_value = item['audit_value']
                    task_group = item['task_group']
                    sequence = item['sequence']

                    if task_name not in distinct_values:
                        distinct_values[task_name] = {}

                    if task_group not in distinct_values[task_name]:
                        distinct_values[task_name][task_group] = {}

                    if sequence is not None:
                        if 'sequence' not in distinct_values[task_name][task_group]:
                            distinct_values[task_name][task_group]['sequence'] = {}
                        if sequence not in distinct_values[task_name][task_group]['sequence']:
                            distinct_values[task_name][task_group]['sequence'][sequence] = {}
                        distinct_values[task_name][task_group]['sequence'][sequence][audit_type] = audit_value
                    else:
                        if audit_type not in distinct_values[task_name][task_group]:
                            distinct_values[task_name][task_group][audit_type] = audit_value
                        else:
                            distinct_values[task_name][task_group][audit_type + '1'] = audit_value
                # Organizing the distinct values into the desired format
                output = {"task_groups": {}}
                for task_name, groups in distinct_values.items():
                    output["task_groups"][task_name] = groups

                # Convert the output to JSON format
                output_json = json.dumps(output, indent=4)
                pipeline_nme = None
                output_data = json.loads(output_json)
                json_data = task_json_read(paths_data,prj_nm,name)
                injestion_type = json_data["task_type"]
                if message == "COMPLETED": # if job completed
                    msg['Subject'] = f"SUCCESS: IKART Summary Report: {name}"
                    task_groups = output_data['task_groups']
                    task_group_name = list(task_groups.keys())[0]
                    tasks = task_groups[task_group_name]

                    body = f"""<p>Hi all,</p>
                        <p style="color:green;"> The Task execution has completed Successfully</p>
                        <p style="color:black;"><b>Run ID</b> : {run_id}</p>
                        <p style="color:black;"><b>Project</b> : {prj_nm}</p>
                        <p style="color:black;"><b>Task</b> : {name}</p>

                        <table style="border:1px solid black; border-collapse: collapse;">
                        <thead style="border:1px solid black;">
                        <tr>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">TASK_NAME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">JOB_TYPE</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">GROUP</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">SEQ</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">SRC_CNT</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">TGT_CNT</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">START_TIME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">END_TIME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">STATUS</th>
                        </tr>
                        </thead>
                        <tbody>
                    """

                    sl_no = 1
                    for task_id, task_details in tasks.items():
                        if task_id == "null":
                            continue

                        if 'sequence' in task_details:
                            for seq_id, seq_details in task_details['sequence'].items():
                                src_count = seq_details.get('SRC_RECORD_COUNT', 'NA')
                                trgt_count = seq_details.get('TRGT_RECORD_COUNT', 'NA')
                                status = seq_details.get('STATUS', 'NA')
                                bg_color = '#3cb371' if status == 'COMPLETED' else 'red' if status == 'FAILED' else 'transparent'
                                body += f"""
                                <tr style="border:1px solid gray;">
                                <td style="border:1px solid gray;">{task_group_name}</td>
                                <td style="border:1px solid gray;">{injestion_type}</td>
                                <td style="border:1px solid gray;">{task_id}</td>
                                <td style="border:1px solid gray;">{seq_id}</td>
                                <td style="border:1px solid gray;">{src_count}</td>
                                <td style="border:1px solid gray;">{trgt_count}</td>
                                <td style="border:1px solid gray;">{i}</td>
                                <td style="border:1px solid gray;">{j}</td>
                                <td style="border:1px solid gray; background-color: {bg_color};">{status}</td>
                                </tr>
                                """
                                sl_no += 1
                    task_log_file = os.path.join(logging_path, f"{name}_taskLog_{run_id}_{iter_value}.log")
                    body += f"""
                    <p style="color:black;"><b>Log Path</b> : {log_file_path+log_file_name}</p>
                    <p style="color:black;"><b>{name} Log Path</b> : {task_log_file}</p>"""
                    body += f"""
                        </tbody>
                        </table>
                        <p>Thanks and Regards,</p>
                        <p>{paths_data["team_nm"]}</p>
                        <p><strong>*Note: This is an auto-generated mail. Please do not reply.*</strong></p>
                        """
                elif message == "FAILED": # if job Failed
                    msg['Subject'] = f"FAILURE: IKART Summary Report: {name}"
                    task_groups = output_data['task_groups']
                    task_group_name = list(task_groups.keys())[0]
                    tasks = task_groups[task_group_name]

                    body = f"""<p>Hi all,</p>
                        <p style="color:red;"> Task:{name} execution has Failed.</p>
                        <p style="color:black;"><b>Run ID</b> : {run_id}</p>
                        <p style="color:black;"><b>Project</b> : {prj_nm}</p>
                        <table style="border:1px solid black; border-collapse: collapse;">
                        <thead style="border:1px solid black;">
                        <tr>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">TASK_NAME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">JOB_TYPE</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">GROUP</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">SEQ</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">SRC_CNT</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">TGT_CNT</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">START_TIME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">END_TIME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">STATUS</th>
                        </tr>
                        </thead>
                        <tbody>
                    """

                    sl_no = 1
                    for task_id, task_details in tasks.items():
                        if task_id == "null":
                            continue

                        if 'sequence' in task_details:
                            for seq_id, seq_details in task_details['sequence'].items():
                                src_count = seq_details.get('SRC_RECORD_COUNT', 'NA')
                                trgt_count = seq_details.get('TRGT_RECORD_COUNT', 'NA')
                                status = seq_details.get('STATUS', 'NA')
                                bg_color = '#3cb371' if status == 'COMPLETED' else 'red' if status == 'FAILED' else 'transparent'
                                body += f"""
                                <tr style="border:1px solid gray;">
                                <td style="border:1px solid gray;">{task_group_name}</td>
                                <td style="border:1px solid gray;">{injestion_type}</td>
                                <td style="border:1px solid gray;">{task_id}</td>
                                <td style="border:1px solid gray;">{seq_id}</td>
                                <td style="border:1px solid gray;">{src_count}</td>
                                <td style="border:1px solid gray;">{trgt_count}</td>
                                <td style="border:1px solid gray;">{i}</td>
                                <td style="border:1px solid gray;">{j}</td>
                                <td style="border:1px solid gray; background-color: {bg_color};">{status}</td>
                                </tr>
                                """
                                sl_no += 1
                    task_log_file = os.path.join(logging_path, f"{name}_taskLog_{run_id}_{iter_value}.log")
                    body += f"""
                    <p style="color:black;"><b>Log Path</b> : {log_file_path+log_file_name}</p>
                    <p style="color:black;"><b>{name} Log Path</b> : {task_log_file}</p>"""
                    body += f"""
                        </tbody>
                        </table>
                        <p>Thanks and Regards,</p>
                        <p>{paths_data["team_nm"]}</p>
                        <p><strong>*Note: This is an auto-generated mail. Please do not reply.*</strong></p>
                        """
                elif message == "STARTED": # if job Started
                    msg['Subject'] = f"STARTED: IKART: {name}"
                    body = f"""<p>Hi all,</p>
                            <p style="color:green;"> The Task execution has Started.</p>
                            <p style="color:black;"><b>Run ID</b> : {run_id}</p>
                            <p style="color:black;"><b>Project</b> : {prj_nm}</p>
                            <p style="color:black;"><b>Task</b> : {name}</p>
                            <p>Thanks and Regards,</p>
                            <p>{paths_data["team_nm"]}</p>
                            <p><strong>*Note: This is an auto-generated mail. Please do not reply.*</strong></p>
                            """

                msg.attach(MIMEText(body, 'html'))
            else:
                homepath = str(Path(paths_data['folder_path']).expanduser())
                logging_path= homepath+"/"+paths_data["local_repo"]+ \
                paths_data["programs"]+prj_nm+paths_data["task_log_path"]
                task_log_file = os.path.join(logging_path, 
                f"{name}_taskLog_{run_id}_{iter_value}.log")
                try:
                    with open(task_log_file, "rb") as log_data:
                        attachment = MIMEApplication(log_data.read(), _subtype="txt")
                        attachment.add_header('Content-Disposition', 'attachment',
                                            filename=f"{name}_taskLog_{run_id}_{iter_value}.log")
                        msg.attach(attachment)
                except FileNotFoundError:
                    # main_logger.error(f"File not found: {task_log_file}. Continuing execution.")
                    pass
                distinct_values = {}
                # Extracting distinct values
                for item in data:
                    task_name = item['taskorpipeline_name']
                    audit_type = item['audit_type']
                    audit_value = item['audit_value']

                    if task_name not in distinct_values:
                        distinct_values[task_name] = {}

                    if audit_type not in distinct_values[task_name]:
                        distinct_values[task_name][audit_type] = audit_value
                    else:
                        # If audit_type already exists, append it as a new key-value pair
                        distinct_values[task_name][audit_type + '1'] = audit_value

                # Organizing the distinct values into the desired format
                output = []
                for task_name, values in distinct_values.items():
                    task_data = {"taskorpipeline_name": task_name}
                    task_data.update(values)
                    output.append(task_data)

                # Convert the output to JSON format
                output_json = json.dumps(output, indent=4)
                pipeline_nme = None
                output_data = json.loads(output_json)  # Convert back to list of dictionaries
                for entry in output_data:
                    if entry['STATUS'] == "INITIATED":
                        pipeline_nme = entry.get('taskorpipeline_name')
                        break
                if message == "STARTED": # if job Started
                    msg['Subject'] = f"STARTED: IKART: {name}"
                    body = f"""<p>Hi all,</p>
                            <p style="color:green;"> The Task execution has Started.</p>
                            <p style="color:black;"><b>Run ID</b> : {run_id}</p>
                            <p style="color:black;"><b>Project</b> : {prj_nm}</p>
                            <p style="color:black;"><b>Task</b> : {name}</p>
                            <p>Thanks and Regards,</p>
                            <p>{paths_data["team_nm"]}</p>
                            <p><strong>*Note: This is an auto-generated mail. Please do not reply.*</strong></p>
                            """
                elif message == "COMPLETED": # if job completed
                    task_rows = ""
                    sl_no = 1
                    for item in output_data:
                        if "SRC_RECORD_COUNT" in item and "TRGT_RECORD_COUNT" in item:
                            # This is a task
                            json_data = task_json_read(paths_data,prj_nm,item['taskorpipeline_name'])
                            injestion_type = json_data["task_type"]
                            task_rows += f"""
                            <tr style="border:1px solid gray;">
                                <td style="border:1px solid gray;">{item['taskorpipeline_name']}</td>
                                <td style="border:1px solid gray;">{injestion_type}</td>
                                <td style="border:1px solid gray;">{item.get('SRC_RECORD_COUNT')}</td>
                                <td style="border:1px solid gray;">{item.get('TRGT_RECORD_COUNT')}</td>
                                <td style="border:1px solid gray;">{i}</td>
                                <td style="border:1px solid gray;">{j}</td>
                                <td id="T_cc241_row0_col7" style="border:1px solid gray; background-color: { 'red' if 'FAILED' in [item.get('STATUS'), item.get('STATUS1')] else ('#3cb371' if any(status in ['COMPLETED', 'SKIPPED'] for status in [item.get('STATUS'), item.get('STATUS1')]) else '') };">{ next((status for status in [item.get('STATUS'), item.get('STATUS1')] if status in ['COMPLETED', 'SKIPPED', 'FAILED']), '') }</td>
                            </tr>
                            """
                            sl_no += 1
                    msg['Subject'] = f"SUCCESS: IKART Summary Report: {name}"
                    body = f"""<p>Hi all,</p>
                        <p style="color:green;"> The Task execution has completed Sucessfully.</p>
                        <p style="color:black;"><b>Run ID</b> : {run_id}</p>
                        <p style="color:black;"><b>Project</b> : {prj_nm}</p>
                        <p style="color:black;"><b>Task</b> : {name}</p>
                        <p style="color:black;"><b>Log Path</b> : {log_file_path+log_file_name}</p>"""
                    task_log_file = os.path.join(logging_path, f"{name}_taskLog_{run_id}_{iter_value}.log")
                    body += f"""<p style="color:black;"><b>{name} Log Path</b> : {task_log_file}</p>
                        <table style="border:1px solid black; border-collapse: collapse;">
                        <thead style="border:1px solid black;">
                        <tr>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">JOB_NAME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">JOB_TYPE</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">SOURCE_COUNT</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">TARGET_COUNT</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">START_TIME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">END_TIME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">STATUS</th>
                        </tr>
                        </thead>
                        <tbody>
                        {task_rows}
                        </tbody>
                        </table>
                        <p>Thanks and Regards,</p>
                        <p>{paths_data["team_nm"]}</p>
                        <p><strong>*Note: This is an auto-generated mail. Please do not reply.*</strong></p>
                        """
                elif message == "FAILED": # if job Failed
                    task_rows = ""
                    sl_no = 1
                    for item in output_data:
                        # if "SRC_RECORD_COUNT" in item and "TRGT_RECORD_COUNT" in item:
                        if item.get("STATUS") != "INITIATED":
                            # This is a task
                            json_data = task_json_read(paths_data,prj_nm,item['taskorpipeline_name'])
                            injestion_type = json_data["task_type"]
                            task_rows += f"""
                            <tr style="border:1px solid gray;">
                                <td style="border:1px solid gray;">{item['taskorpipeline_name']}</td>
                                <td style="border:1px solid gray;">{injestion_type}</td>
                                <td style="border:1px solid gray;">{item.get('SRC_RECORD_COUNT')}</td>
                                <td style="border:1px solid gray;">{item.get('TRGT_RECORD_COUNT')}</td>
                                <td style="border:1px solid gray;">{i}</td>
                                <td style="border:1px solid gray;">{j}</td>
                                <td id="T_cc241_row0_col7" style="border:1px solid gray; background-color: { 'red' if 'FAILED' in [item.get('STATUS'), item.get('STATUS1')] else ('#3cb371' if any(status in ['COMPLETED', 'SKIPPED'] for status in [item.get('STATUS'), item.get('STATUS1')]) else '') };">{ next((status for status in [item.get('STATUS'), item.get('STATUS1')] if status in ['COMPLETED', 'SKIPPED', 'FAILED']), '') }</td>
                            </tr>
                            """
                            sl_no += 1
                    msg['Subject'] = f"FAILURE: IKART Summary Report: {name}"
                    body = f"""<p>Hi all,</p>
                        <p style="color:red;"> The Task:{name} execution has Failed.</p>
                        <p style="color:black;"><b>Run ID</b> : {run_id}</p>
                        <p style="color:black;"><b>Project</b> : {prj_nm}</p>
                        <p style="color:black;"><b>Log Path</b> : {log_file_path+log_file_name}</p>"""
                    task_log_file = os.path.join(logging_path, f"{name}_taskLog_{run_id}_{iter_value}.log")
                    body += f"""<p style="color:black;"><b>{name} Log Path</b> : {task_log_file}</p>
                        <table style="border:1px solid black; border-collapse: collapse;">
                        <thead style="border:1px solid black;">
                        <tr>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">JOB_NAME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">JOB_TYPE</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">SOURCE_COUNT</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">TARGET_COUNT</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">START_TIME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">END_TIME</th>
                        <th style="border:1px solid gray; background-color: #C0C2C9;">STATUS</th>
                        </tr>
                        </thead>
                        <tbody>
                        {task_rows}
                        </tbody>
                        </table>
                        <p>Thanks and Regards,</p>
                        <p>{paths_data["team_nm"]}</p>
                        <p><strong>*Note: This is an auto-generated mail. Please do not reply.*</strong></p>
                        """
                msg.attach(MIMEText(body, 'html'))
    except Exception as error:
        main_logger.exception("html_email_code %s", str(error))
        raise error

def send_mail(message, prj_nm,run_id,paths_data,name,log_file_path,log_file_name,
    exe_type,task_type,iter_value):
    """Function to send emails for notyfying users on job status"""
    try:
        msg = MIMEMultipart()
        html_email_code(msg,message,paths_data,prj_nm,log_file_path,
        log_file_name,name,run_id,exe_type,task_type,iter_value)
        if message != "STARTED":
            with open(log_file_path+log_file_name, "rb") as log_data:
                attachment = MIMEApplication(log_data.read(), _subtype="txt")
                attachment.add_header('Content-Disposition', 'attachment',
                                      filename=log_file_name)
                msg.attach(attachment)
        server = smtplib.SMTP(paths_data["EMAIL_SMTP"],paths_data["EMAIL_PORT"])
        server.starttls()
        text = msg.as_string()
        server.login(paths_data["email_user_name"],paths_data["email_password"])
        server.sendmail(paths_data["from_addr"], paths_data["to_addr"].split(',')+ \
                        paths_data["cc_addr"].split(','), text)
        main_logger.info('mail sent')
        server.quit()
    except Exception as error:
        main_logger.exception("Connection to mail server failed %s", str(error))
        raise error

def create_status_txt_file(paths_data1,task_name,proj_nm,run_id1):
    """creating status text file"""
    try:
        df_1 = pd.DataFrame(columns=["task_name","task_depended_on","Job_Status"],index = [1])
        df_1['task_name']= task_name
        df_1['task_depended_on']= 0
        df_1['Job_Status']= 'Start'
        file_path1=os.path.expanduser(paths_data1["folder_path"])+paths_data1["local_repo"]+\
        paths_data1["programs"]+proj_nm+paths_data1["status_txt_file_path"]+task_name+'_Task_'+\
        run_id1+".txt"
        df_1.to_csv(file_path1,mode='w', sep='\t',index = False, header=True)
        return file_path1
    except Exception as error:
        main_logger.exception("create_status_txt_file %s", str(error))
        raise error

def pipeline_execution(proj_nm,path_data,pipe_nm,run_id1,log_file_path1,log_file_name1,
    mode,iter_val):
    """pipeline execution"""
    try:
        exe_type = 'pipeline'
        json_data = pipeline_json_read(path_data,proj_nm,pipe_nm) #pipeline json read
        task_type = json_data.get("task_type", None)
        if json_data["is_active"] == 'N':
            main_logger.warning("%s pipeline is inactive, Process got Aborted!", pipe_nm)
            sys.exit()
        else:
            audit(json_data, pipe_nm,run_id1,'STATUS','INITIATED',iter_val,path_data)
            df_2=pd.DataFrame(json_data['tasks_details'].items())
            df_1 = df_flatten(df_2)
            df_1['Job_Status']= 'Start'
            file_path=os.path.expanduser(path_data["folder_path"])+path_data["local_repo"]+\
            path_data["programs"]+proj_nm+path_data["status_txt_file_path"]+pipe_nm+'_Pipeline_'+\
            run_id1+".txt"
            main_logger.info("execution at pipeline level")
            send_mail('STARTED', proj_nm,run_id1,path_data,pipe_nm,log_file_path1,
            log_file_name1,exe_type,task_type,iter_val)
            main_job(proj_nm,path_data,pipe_nm) #this checks for cyclic dependency
            text_filepath=os.path.expanduser(path_data["folder_path"])+path_data["local_repo"]+\
            path_data["programs"]+proj_nm+path_data["status_txt_file_path"]
            # * means all if need specific format then *.csv
            list_of_prev_files = glob.glob(text_filepath+pipe_nm+'*'+".txt")
            if len(list_of_prev_files) != 0:
                main_logger.info("entered inside existing previous files")
                latest_file = max(list_of_prev_files, key=os.path.getctime)
                main_logger.info("previous txt file path:%s", latest_file)
                if mode =='RESTART':
                    main_logger.info("execution of pipeline in RESTART mode")
                    # reading previous run text file
                    df_2 =pd.read_csv(latest_file, sep='\t')
                    success_ls=df_2[df_2['Job_Status'] == 'SUCCESS']['task_name'].to_list()
                    main_logger.info("list of tasks that are success in previous run:%s",success_ls)
                    # creating new text file
                    df_1.to_csv(file_path,mode='w', sep='\t',index = False, header=True)
                    list_of_files = glob.glob(text_filepath+pipe_nm+'*'+".txt")
                    latest_file1 = max(list_of_files, key=os.path.getctime)
                    main_logger.info("current txt file path:%s", latest_file1)
                    df_3 =pd.read_csv(latest_file1, sep='\t')
                    for i in success_ls:
                        df_3.loc[df_3['task_name'] == i, 'Job_Status'] = 'SUCCESS'
                        # audit(json_data,i,run_id1,'STATUS','SKIPPED',iter_val,path_data)
                    main_logger.info(df_3)
                    df_3.to_csv(latest_file1,mode='w', sep='\t',index = False, header=True)
                    status_list=restart_orchestration_execution(proj_nm,path_data,pipe_nm,
                    run_id1,iter_val)
                else:
                    main_logger.info("execution of pipeline in NORMAL mode")
                    df_1.to_csv(file_path,mode='w', sep='\t',index = False, header=True)
                    status_list=orchestration_execution(proj_nm,path_data,pipe_nm,run_id1,iter_val)
            else:
                main_logger.info("entered inside does not exist previous files block")
                main_logger.info("execution of pipeline in Normal mode")
                df_1.to_csv(file_path,mode='w', sep='\t',index = False, header=True)
                status_list=orchestration_execution(proj_nm,path_data,pipe_nm,run_id1,iter_val)
            return status_list
    except Exception as error:
        main_logger.exception("pipeline_execution %s", str(error))
        raise error

def get_ind_task_status(file_path):
    """function to get status from text"""
    try:
        task_status_list = []
        df_2 =pd.read_csv(file_path, sep='\t')
        for _,row in df_2.iterrows():
            if row['task_depended_on']==0:
                main_logger.info(row['task_name']+" task is "+row['Job_Status'])
                task_status_list.append(row['Job_Status'])
        return task_status_list
    except Exception as error:
        main_logger.exception("get_ind_task_status %s", str(error))
        raise error

def get_not_started_task_status(json_data,run_id,file_path,iter_value,paths_data):
    """function to get status from text"""
    try:
        df_2 =pd.read_csv(file_path, sep='\t')
        for _,row in df_2.iterrows():
            if row['Job_Status'] == 'Start':
                #log and audit for tasks not started
                # main_logger.info("not started task name:%s",row['task_name'])
                audit(json_data,row['task_name'],run_id,
                'STATUS','NOT STARTED',iter_value,paths_data)
    except Exception as error:
        main_logger.exception("get_not_started_task_status %s", str(error))
        raise error

def task_orc_execution(prj_nm,paths_data,task_nm,run_id,log_file_path,log_file_name,
iter_value):
    """task_execution block"""
    exe_type = 'task'
    task_type = None
    try:
        file_path = create_status_txt_file(paths_data,task_nm,prj_nm,run_id)
        # main_logger.info("entered into task")
        main_logger.info("execution at task level")
        send_mail('STARTED', prj_nm,run_id,paths_data,task_nm,log_file_path,
        log_file_name,exe_type,task_type,iter_value)
        execute_job(prj_nm,paths_data,task_nm,run_id,file_path,iter_value)
    except Exception as error:
        main_logger.exception("error in orchestrate_task_calling %s.", str(error))
        raise error
    finally:
        # entered into task
        task_status_list = get_ind_task_status(file_path)
        json_data = task_json_read(paths_data,prj_nm,task_nm) #pipeline json read
        task_type = json_data.get("task_type")
        result = all(x == "SUCCESS" for x in task_status_list)
        if result is False:
            main_logger.info("Task %s Execution failed.",task_nm)
            send_mail("FAILED",prj_nm,run_id,paths_data,task_nm,log_file_path,
            log_file_name,exe_type,task_type,iter_value)
        else:
            main_logger.info("Task %s Execution ended successfully.",task_nm)
            send_mail("COMPLETED", prj_nm,run_id,paths_data,task_nm,log_file_path,
            log_file_name,exe_type,task_type,iter_value)
        main_logger.handlers.clear()

def pipeline_orc_execution(prj_nm,paths_data,pip_nm,run_id,log_file_path,log_file_name,
mode,iter_value):
    """pipeline execution block"""
    global STATUS_LIST
    exe_type = 'pipeline'
    try:
        # main_logger.info("entered into pip")
        STATUS_LIST = pipeline_execution(prj_nm,paths_data,pip_nm,run_id,log_file_path,
        log_file_name,mode,iter_value)
    except Exception as error:
        main_logger.exception("error in orchestrate_calling %s.", str(error))
        raise error
    finally:
        file_path=os.path.expanduser(paths_data["folder_path"])+paths_data["local_repo"]+\
        paths_data["programs"]+prj_nm+paths_data["status_txt_file_path"]+pip_nm+\
        '_Pipeline_'+run_id+".txt"
        json_data = pipeline_json_read(paths_data,prj_nm,pip_nm)
        task_type = json_data.get("task_type", None)
        if len(STATUS_LIST)==0:
            audit(json_data, pip_nm,run_id,'STATUS',
            'ABORTED',iter_value,paths_data)
            main_logger.info("pipeline %s Execution FAILED", pip_nm)
            send_mail("FAILED", prj_nm,run_id,paths_data,pip_nm,log_file_path,
            log_file_name,exe_type,task_type,iter_value)
            main_logger.handlers.clear()
        else:
            result = all(x == "SUCCESS" for x in STATUS_LIST)
            if result is False:
                # main_logger.info("entered into false")
                get_not_started_task_status(json_data,run_id,file_path,iter_value,paths_data)
                #calling audit or pipeline failure
                audit(json_data, pip_nm,run_id,'STATUS','ABORTED',iter_value,paths_data)
                main_logger.info("pipeline %s Execution failed.", pip_nm)
                send_mail("FAILED", prj_nm,run_id,paths_data,pip_nm,log_file_path,
                log_file_name,exe_type,task_type,iter_value)
                sys.exit()
            else:
                #calling audit or pipeline success
                audit(json_data, pip_nm,run_id,'STATUS','FINISHED',iter_value,paths_data)
                main_logger.info("pipeline %s Execution ended successfully.", pip_nm)
                send_mail("COMPLETED",prj_nm,run_id,paths_data,pip_nm,log_file_path,
                log_file_name,exe_type,task_type,iter_value)
            main_logger.handlers.clear()

def orchestrate_calling(prj_nm,paths_data,task_nm,pip_nm,run_id,log_file_path,log_file_name,
mode,iter_value):
    """executes the orchestration at task or
    pipeline level based on the command given"""
    try:
        if task_nm is not None:
            task_orc_execution(prj_nm,paths_data,task_nm,run_id,log_file_path,log_file_name,
            iter_value)
        elif pip_nm is not None:
            pipeline_orc_execution(prj_nm,paths_data,pip_nm,run_id,log_file_path,log_file_name,
            mode,iter_value)
        else:
            main_logger.info("Please enter the correct command")
    except Exception as error:
        main_logger.exception("error in orchestrate_calling %s.", str(error))
        raise error
