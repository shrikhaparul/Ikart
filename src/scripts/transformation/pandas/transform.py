"""script to execute transfomation json"""
import os
import re
import time
from collections import defaultdict, deque
import logging
import concurrent.futures
from filter import filter_data
from expression import expression
from joiner import join_operations
from fetch import fetch_data
from store import store_data

import pandas as pd
task_logger = logging.getLogger('task_logger')

def find_index_from_array(data, key_name):
    """Finds the index of the first dictionary in the list containing the key_name."""
    for i, item in enumerate(data):
        if key_name in item:
            return i
    return -1  # Return -1 if the key_name is not found in any dictionary


def update_status_file(task_id,status,file_path):
    """updates a text file with statuses for orchestration"""
    try:
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

def convert_dict(dict1):
    """Convert a dictionary"""
    # Initialize the resulting dictionary
    dict2 = {}

    # Iterate over the items in dict1
    for key, value in dict1.items():
        # Split the value by comma and strip any extra whitespace
        values = [item.strip() for item in value.split(',')]
        # Store the list in dict2
        dict2[key] = values

    return dict2

def convert_task_graph_to_dataframe(task_graph):
    """
    Converts the given task dependency graph to a pandas DataFrame.

    Args:
    task_graph (dict): The task dependency graph.

    Returns:
    pandas.DataFrame: A pandas DataFrame representing the task dependency graph.
    """
    tasks = list(task_graph.keys())
    data = []
    for task in tasks:
        for dep in task_graph[task]:
            data.append({'task_name': task, 'task_depended_on': dep})
    df = pd.DataFrame(data)
    return df

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

    # print(set_parentjob)
    # Checking all parent jobs are subset of children jobs.
    set_parentjob.remove('0') # removing parent=0
    # print(set_parentjob)

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

def topological_sort(tasks):
    """Sort tasks"""
    # Create a graph from the list of tasks
    graph = defaultdict(list)
    in_degree = defaultdict(int)  # Track in-degrees of nodes

    # Build the graph and in-degree dictionary
    all_tasks = set()
    for task, dependency in tasks:
        all_tasks.add(task)
        if dependency != '0':
            graph[dependency].append(task)
            in_degree[task] += 1
        if dependency != '0':
            all_tasks.add(dependency)

    # Initialize the queue with tasks having zero in-degrees
    queue = deque([task for task in all_tasks if in_degree[task] == 0])
    sorted_tasks = []

    while queue:
        task = queue.popleft()
        sorted_tasks.append(task)

        for dependent_task in graph[task]:
            in_degree[dependent_task] -= 1
            if in_degree[dependent_task] == 0:
                queue.append(dependent_task)

    # Ensure all tasks are included in the result
    if len(sorted_tasks) != len(all_tasks):
        missing_tasks = all_tasks - set(sorted_tasks)
        raise ValueError(f"The input contains a cycle or unresolved dependency: {missing_tasks}")

    return sorted_tasks

def process_task(task_name,data_sources,arguments):
    """"Process a task"""
    # data=arguments["json_data"]["details"]
    pattern = re.compile(r'(^[A-Za-z0-9]+)_([\w]+)$')
    match = re.match(pattern, task_name)
    if match:
        process1 = match.group(1).strip()# Use group(1) to get the first capturing group
        # print("process:",process1)
        process_name=match.group(2).strip()
        # print("process_name:",process_name)
        # data_details=data["details"]["details"]

        source_name ,df_data=handle_process(arguments, data_sources, process1, process_name)
        return source_name,df_data
    if not match:
        raise SyntaxError("Not according to the task_Syntax")

def get_details(data_details,process, process_name):
    """Get details"""
    details = data_details[find_index_from_array(data_details, process)][process]
    return details[find_index_from_array(details, process_name)][process_name]



def handle_process(arguments, data_sources, process, process_name):
    """ Handle processing"""
    data_details=arguments["json_data"]["task"]["details"]
    source_details = get_details(data_details,process, process_name)
    if process != "Output":
        source_name = source_details["output_df"]

    if process == "Input":
        return source_name, fetch_data(source_details,arguments)
    if process == "Joiner":
        return source_name, join_operations(data_sources, source_details)
    if process == "Filter":
        return source_name, filter_data(data_sources[source_details["input_df"]], source_details)
    if process == "Expression":
        return source_name, expression(data_sources[source_details["input_df"]], source_details)
    if process == "Output":
        # print(data_sources[source_details["input_df"]])
        store_data(data_sources[source_details["input_df"]], source_details,arguments)
        message = f"{process_name} data stored successfully"
        return "message", message
    if process not in ("Input","Joiner","Filter","Expression", "Output"):
        raise KeyError("process != 'Input'|'Output'|'Filter'|'Expression'|'Joiner'")

def transform_flow(arguments):
    """
    Main function to orchestrate the data processing.
    """
    start_time = time.time()
    try:
        data=arguments["json_data"]["task"]
        flow=data["flow"]
        flatten_flow=convert_dict(flow)
        df_flat=convert_task_graph_to_dataframe(flatten_flow)
        status,msg=job_check(df_flat)
        task_logger.info("status:%s,msg:%s",status,msg) #check for cylic

        # task_name = df_flat['task_name'].unique().tolist()
        # task_depended_on = df_flat['task_depended_on'].unique().tolist()
        # output= [value for value in task_name if value not in task_depended_on]
        task_list = [(row['task_name'], row['task_depended_on']) for _, row in df_flat.iterrows()]
        sorted_tasks = topological_sort(task_list)
        task_logger.info("sorted_task: %s",sorted_tasks)
        # print(sorted_tasks)

        independant_task = df_flat[df_flat['task_depended_on'] == '0']['task_name'].tolist()
        dependant_task =[item for item in sorted_tasks if item not in independant_task]
        data_sources = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submit tasks to be executed in parallel
            futures = [executor.submit(process_task, task_name, data_sources.copy(),
            arguments) for task_name in independant_task]
            # Wait for all tasks to complete
            data_sources = {future.result()[0]: future.result()[1] for future in 
            concurrent.futures.as_completed(futures)}
        for task in dependant_task:
            df_name ,df_data = process_task(task,data_sources,arguments)
            data_sources[df_name]=df_data

        task_logger.info(data_sources["message"])

    except FileNotFoundError as e:
        task_logger.error("File not found: %s", e)
    except Exception as e:
        task_logger.error("Failed to complete data processing: %s", e)
        raise e
    print("Program has ended.")
    end_time = time.time()
    elapsed_time = end_time - start_time
    task_logger.info("Total elapsed time: %.4f seconds",elapsed_time)
