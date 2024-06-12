"""
Python module to filter the dataframes based on the given Conditions
"""
import logging
import re
import pandas as pd
import pandasql as ps
from update_audit import audit_failure

task_logger = logging.getLogger('task_logger')

def process_condition(arguments,operation,df):
    """
    Process a condition based on the provided operation details and DataFrame.

    Args:
    - operation (dict): A dictionary containing 'column_name', 'operator', and 'field_value'.
    - df (pd.DataFrame): The pandas DataFrame on which the condition is applied.

    Returns:
    - str: The processed condition in string format to be used in a query.
    """
    try:
        column=operation["column_name"]
        op=operation["operator"]
        val=operation["field_value"]
        column_names = df.columns.tolist()
        if op == "between":
            op = f".{op}"
        elif op== "not_between" or op == "not between":
            if "(" in val and ")" in val:
                return f"~({column} .between {val})"
            else:
                return f"~({column} .between ({val}))"
        elif op in ["isnull", "notnull"]:
            op = f".{op}()"
            val = ""  # Value not required for isnull operation
            return f"{column} {op}{val}"
        elif op == "and":
            op="&"
        elif op== "or":
            op="|"
        elif any(keyword in op for keyword in ['any', 'some', 'all']):
            if "all" in op:
                logop=" & "
            else:
                logop=' | '
            op=op.replace("any",'')
            op=op.replace("all",'')
            op=op.replace("some",'')
            # print(op)
            query = "("
            values = val[1:-1].split(',')
            query += logop.join([f"{column} {op} {v.strip()}" for v in values])
            return query + ")"
        elif (str(df[column].dtype) == 'string[pyarrow]'
                or pd.api.types.is_string_dtype(df[column])) and val not in column_names:
            val = f"'{val}'"
        return f"{column} {op} {val}"
    except Exception as e:
        task_logger.exception("Error occured in process_condition function with error : %s", e)
        audit_failure(arguments)
        raise e

def find_endpoint(arguments,dependencies,tasks):
    """
    Identify the endpoint of a dependency flow and validate tasks.

    Args:
    - dependencies (dict): A dictionary where keys are tasks and values are lists 
        of tasks they depend on.
    - tasks (list): A list of all implemented tasks.

    Returns:
    - str: The endpoint task.

    Raises:
    - ValueError: If the flow does not end in a single point or if any task is not implemented.
    """
    try:

        all_dependent_tasks = set()
        all_tasks = set(dependencies.keys())

        for deps in dependencies.values():
            all_dependent_tasks.update(deps)
        potential_endpoints = all_tasks - all_dependent_tasks
        # print(potential_endpoints)
        if len(potential_endpoints) != 1:
            raise ValueError("The flow does not end in a single point.")
        endpoint = potential_endpoints.pop()
        for task in all_tasks.union(all_dependent_tasks):
            if task not in tasks:
                raise ValueError(f"Task '{task}' is not implemented in the provided task list.")
        return endpoint
    except Exception as e:
        task_logger.exception("Error occured in extract_columns function with error : %s", e)
        audit_failure(arguments)
        raise e

def apply_grouping(arguments,group_names,operations,filter_json,group_name,dependency):
    """
    Apply grouping operations based on provided conditions and dependencies.

    Args:
    - group_names (list): List of group names.
    - operations (dict): A dictionary of operations.
    - filter_json (dict): JSON object containing filter configurations.
    - group_name (str): Name of the current group to process.
    - dependency (dict): A dictionary to store dependencies.

    Returns:
    - tuple: Updated dependency and operations dictionaries.

    Raises:
    - SyntaxError: If an invalid query or operator is encountered.
    """
    try:

        group=filter_json[group_name]
        condition_1_name=group["Condition_01"]
        condition_2_name=group["Condition_02"]
        dependency[group_name]=[condition_1_name,condition_2_name]
        if condition_1_name in operations:
            condition_1=operations[condition_1_name]
        elif condition_1_name in group_names:
            dependency,operations=apply_grouping(arguments,group_names,operations,
            filter_json,condition_1_name,dependency)
        else:
            raise SyntaxError("InValid Query")
        if condition_2_name in operations:
            condition_2=operations[condition_2_name]
        elif condition_2_name in group_names:
            dependency,operations=apply_grouping(arguments,group_names,operations,
                filter_json,condition_2_name,dependency)
        else:
            raise SyntaxError("InValid Query")
        if group["operator"]== "&" or group["operator"]== "|":
            op=group["operator"]
        elif group["operator"] == "and":
            op="&"
        elif group["operator"] == "or":
            op="|"
        else:
            raise SyntaxError("Invalid operator used")
        operations[group_name]="("+condition_1+" "+op+" "+condition_2+")"
        return dependency,operations
    except Exception as e:
        task_logger.exception("Error occured in apply_grouping function with error : %s", e)
        audit_failure(arguments)
        raise e

def create_query(arguments,df,filter_json):
    """
    Apply filters to a DataFrame based on the provided filter JSON.

    Args:
    - df (pd.DataFrame): The DataFrame to apply filters on.
    - filter_json (dict): JSON object containing filter configurations.

    Returns:
    - str: The query string to filter the DataFrame.

    Raises:
    - SyntaxError: If the grouping is not done properly.
    """
    try:

        operations={}
        for operation_name,operation in filter_json.items():
            if "condition_type" in operation and operation["condition_type"]=="operation":

                operations[operation_name]=process_condition(arguments,operation,df)
        group_names=[]
        dependency={}
        for i in sorted(filter_json.keys()):
            #print(i)
            if "condition_type" in filter_json[i] and filter_json[i]["condition_type"]=="group":
                group_names.append(i)
        for group_name in group_names:
            if i not in operations:
                dependency,operations=apply_grouping(arguments,group_names,operations,filter_json,
                group_name,dependency)

        if dependency:
            end_point=find_endpoint(arguments,dependency, operations.keys())
        elif len(operations)==1:
            end_point=next(iter(operations.keys()))
        else:
            raise SyntaxError("Invalid Syntax. Grouping not done properly")

        return operations[end_point]
    except Exception as e:
        task_logger.exception("Error occured in create_query function with error : %s", e)
        audit_failure(arguments)
        raise e

def customquery(arguments, df, query):
    """
    Executes the custom sql query from user

    Args:
    - df (DataFrame): The pandas DataFrame to filter.
    - query (string): The custom query that has to be executed.

    Returns:
    - str: The constructed query string.
    """
    try:
        #replace table name
        query=replace_table_name(arguments,query)
        task_logger.info("query df:%s", df.shape[0])
        #execute the query
        return ps.sqldf(query)
    except ps.PandaSQLException as pe:
        task_logger.error("PandaSQLException executing custom query: %s", pe)
        audit_failure(arguments)
        raise
    except SyntaxError as se:
        # Log and handle SyntaxError
        task_logger.error("SyntaxError executing custom query: %s", se)
        audit_failure(arguments)
        raise
    except Exception as e:
        # Log and raise any other exception
        task_logger.error("Error executing custom query: %s", e)
        audit_failure(arguments)
        raise

def replace_table_name(arguments,sql_query):
    """
    Replaces the table with df

    Args:
    - sql_query (string): Sql query with some table name

    Returns:
    - Dataframe: The filtered dataframe after filtering.
    """
    try:
        table_pattern = r'FROM\s+([^\s,]+)'
        # Find all matches of table names in the SQL query
        table_names = re.findall(table_pattern, sql_query, re.IGNORECASE)
        # Replace each table name with 'df'
        for table_name in table_names:
            sql_query = re.sub(r'\b{}\b'.format(re.escape(table_name)),
                               'df',
                               sql_query,
                               flags=re.IGNORECASE)
        return sql_query
    except (re.error, TypeError, ValueError) as e:
        task_logger.error("Error in regex or type conversion: %s", e)
        audit_failure(arguments)
    except Exception as e:
        task_logger.error("Error Incorrect query: %s",e)
        audit_failure(arguments)

def filter_data(arguments,df, filters):
    """
    Filters a DataFrame based on the specified operations.

    Args:
    - df (DataFrame): The pandas DataFrame to filter.
    - filters (dict): A dictionary representing the filter operations.

    Returns:
    - DataFrame: The filtered DataFrame.
    """
    try:
        if "custom" in filters:
            filtered_df=customquery(arguments,df,filters["custom"])
        else:
            query = create_query(arguments,df,filters)
            task_logger.info(query)  # Log the query string for reference
            # Filter DataFrame using query string
            filtered_df = df.query(query)
        return filtered_df
    except ValueError as ve:
        # Log and handle specific exception
        task_logger.error("ValueError occurred: %s", ve)
        audit_failure(arguments)
        raise
    except Exception as e:
        # Log error if any exception occurs and raise it
        task_logger.error("Error filtering data: %s",e)
        audit_failure(arguments)
        raise
