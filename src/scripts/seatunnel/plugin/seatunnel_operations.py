"""Inporting modules."""
import logging
import json
import sys
import importlib
from sqlalchemy.exc import ProgrammingError
import re
task_logger = logging.getLogger("task_logger")

 
############################################################################################

def get_src_col_nm(data_pkg):
    """Function to get sorce column names"""
    try:
        engine, _ = connect_to_db(data_pkg['src_type'], data_pkg, 'source')
        src_connection = engine.raw_connection()
        src_cursor = src_connection.cursor()
        key_query = get_table_col_n_keys(data_pkg['src_type'],data_pkg['src_details']['object_name'],
        data_pkg['src_details']['schema_name'])
        src_cursor.execute(key_query)
        key_info = src_cursor.fetchall()
        my_list = []
        for col_name,_ in key_info:
            my_list.append(col_name)
        col_names = ','.join(my_list)
        return col_names
    except Exception as e:
        task_logger.exception("in get_src_col_nm function exception as: %s",e)
        raise e

def get_src_count(data_pkg):
    """Function to get sorce record count"""
    try:
        engine, _ = connect_to_db(data_pkg['src_type'], data_pkg, 'source')
        src_connection = engine.raw_connection()
        src_cursor = src_connection.cursor()
        key_query = f"select count(*) from {data_pkg['src_details']['schema_name']}."\
        f"{data_pkg['src_details']['object_name']}"
        src_cursor.execute(key_query)
        src_count = src_cursor.fetchall()
        return src_count
    except Exception as e:
        task_logger.exception("in get_src_count function exception as: %s",e)
        raise e

def get_tgt_col_nm(data_pkg):
    """Function to get target column names"""
    try:
        engine, _ = connect_to_db(data_pkg['tgt_type'], data_pkg, 'target')
        tgt_connection = engine.raw_connection()
        tgt_cursor = tgt_connection.cursor()
        print(data_pkg['tgt_type'],data_pkg['tgt_details']['object_name'],data_pkg['tgt_details']['schema_name'])
        query = get_table_col_n_keys(data_pkg['tgt_type'],data_pkg['tgt_details']['object_name'],
        data_pkg['tgt_details']['schema_name'])
        tgt_cursor.execute(query)
        key_info = tgt_cursor.fetchall()

        my_list = []
        value = []

        for col_name,_ in key_info:
            if col_name not in ('crtd_by', 'crtd_dttm', 'updt_by', 'updt_dttm','CRTD_BY','CRTD_DTTM',
                                'UPDT_BY','UPDT_DTTM'):
                my_list.append(col_name)

        for _ in range(len(my_list)):
            value.append("?")

        col_names = ','.join(my_list)
        val = ','.join(value)

        return col_names , val
    except Exception as e:
        task_logger.exception("in get_tgt_col_nm function exception as: %s",e)
        raise e

def get_tgt_count(data_pkg):
    """Function to get target record count"""
    try:
        engine, _ = connect_to_db(data_pkg['tgt_type'], data_pkg, 'target')
        tgt_connection = engine.raw_connection()
        tgt_cursor = tgt_connection.cursor()
        query = f" select count(*) from {data_pkg['tgt_details']['schema_name']}.{data_pkg['tgt_details']['object_name']}"
        tgt_cursor.execute(query)
        tgt_count = tgt_cursor.fetchall()
        return tgt_count
    except Exception as e:
        task_logger.exception("in get_tgt_count function exception as: %s",e)
        raise e
############################################################################################

def get_table_col_n_keys(src, table, schema):
    """Function to get  culumn details"""
    task_logger.info("getting the key details")
    if src in ('MySQL','MSSQL'):
        key_query = f""" select COLUMN_NAME,'val'
            from information_schema.columns
            WHERE TABLE_NAME = '{table}'
            AND TABLE_SCHEMA = '{schema}'
            order by ORDINAL_POSITION asc"""
    elif src in ('PostgreSQL'):
        table = table.lower()
        schema =  schema.lower()
        key_query = f""" select COLUMN_NAME,'val'
            from information_schema.columns
            WHERE TABLE_NAME = '{table}'
            AND TABLE_SCHEMA = '{schema}'
            order by ORDINAL_POSITION asc"""
    elif src == 'Oracle':
        table = table.upper()
        schema =  schema.upper()
        key_query = f"""SELECT COLUMN_NAME, 'val'
                    FROM ALL_TAB_COLUMNS
                    WHERE TABLE_NAME = '{table}' AND OWNER = '{schema}'
                    ORDER BY COLUMN_ID ASC"""
    return key_query
############################################################################################

def get_key_details(src_cursor,src,src_table,src_schema):
    """Function to get the keys in a table."""
    try:

        task_logger.info("getting the key details")
        if src in ('MySQL'):
            key_query = f""" select COLUMN_NAME,
                case when COLUMN_KEY in ('PRI') then 'primary_key'
                when COLUMN_KEY in ('UNI') then 'unique_key' end as key_info
                from information_schema.columns
                WHERE TABLE_NAME = '{src_table}'
                AND TABLE_SCHEMA = '{src_schema}'"""
        elif src in ('PostgreSQL','MSSQL'):
            key_query = f""" SELECT COLUMN_NAME ,
                case when CONSTRAINT_NAME like 'PK%' or CONSTRAINT_NAME like '%pkey'
                then 'primary_key'
                when CONSTRAINT_NAME like 'UQ%' or CONSTRAINT_NAME like '%key'
                then 'unique_key'
                end as key_info
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_NAME = '{src_table}'
                AND TABLE_SCHEMA = '{src_schema}'"""
        elif src == 'Oracle':
            key_query = f"""SELECT ac.column_name,
                                ' ' key_info
                            FROM all_tab_columns ac
                            LEFT JOIN all_cons_columns acc ON ac.table_name = acc.table_name
                            AND ac.column_name = acc.column_name
                            LEFT JOIN all_constraints acs ON acc.constraint_name = acs.constraint_name
                            WHERE ac.table_name = '{src_table.upper()}'
                            AND ac.owner = '{src_schema.upper()}'"""
        src_cursor.execute(key_query)
        key_info = src_cursor.fetchall()
        # task_logger.info(key_info)
        primary_keys=[]
        uni=[]
        for col_name,col_key in key_info:
            if col_key =='primary_key':
                primary_keys.append(col_name)
            elif col_key =='unique_key':
                uni.append(col_name)
        new_pri=''
        new_uniq=''
        if primary_keys  :
            pri = ", ".join(primary_keys)
            new_pri = f",PRIMARY KEY({pri})"
        if uni  :
            uniq = ", ".join(uni)
            new_uniq = f",Unique({uniq})"
        return new_pri,new_uniq
    except Exception as e:
        task_logger.exception("in get_key_details function exception as: %s",e)
        raise e
#################################################################################################
def get_columns_info_details(data_pkg):
    try:
        src_table = data_pkg['src_details']['object_name']
        src_schema = data_pkg['src_details']['schema_name']
        src_conn3,_ = connect_to_db(data_pkg['src_type'],data_pkg,'source')
        src_connection = src_conn3.raw_connection()
        src_cursor = src_connection.cursor()
        src=data_pkg['src_type']
        
        if src in ('MySQL','PostgreSQL','MSSQL'):
            src_query = f"""
                    select 
                    COLUMN_NAME,
                    case when DATA_TYPE in ('numeric','decimal')
                    then CONCAT(DATA_TYPE, '(', NUMERIC_PRECISION, ',', NUMERIC_SCALE, ')')
                    when DATA_TYPE in ('varchar','char','VARCHAR','CHAR','nvarchar','NVARCHAR','nchar','character varying')
                    THEN CONCAT(DATA_TYPE,'(',CHARACTER_MAXIMUM_LENGTH,')')
                    else DATA_TYPE end as new_data_type
                    from information_schema.columns
                    WHERE TABLE_NAME = '{src_table}'
                    AND TABLE_SCHEMA = '{src_schema}'
                    ORDER BY ORDINAL_POSITION ASC
                    """
        elif src == 'Oracle':
            src_query = f"""
                    SELECT 
                    COLUMN_NAME,
                    CASE
                        WHEN DATA_TYPE IN ('NUMBER', 'DECIMAL') THEN
                            CASE 
                                WHEN DATA_PRECISION IS NULL THEN DATA_TYPE || '(20,0)'
                                ELSE DATA_TYPE || '(' || DATA_PRECISION || ',' || DATA_SCALE || ')' 
                            END
                        WHEN DATA_TYPE IN ('CHAR', 'VARCHAR','NCHAR','NVARCHAR2','VARCHAR2')
                        THEN DATA_TYPE || '(' || CHAR_LENGTH || ')'
                        ELSE DATA_TYPE  
                    END AS new_data_type
                    FROM ALL_TAB_COLUMNS
                    WHERE TABLE_NAME = '{src_table.upper()}'
                    AND OWNER = '{src_schema.upper()}'
                    ORDER BY COLUMN_ID ASC
                    """
        else:
            raise ValueError("Unsupported database type")
        
        src_cursor.execute(src_query)
        columns_info_details = src_cursor.fetchall()
        task_logger.info("columns info details %s",columns_info_details)
        return columns_info_details, src_cursor
    except Exception :
        task_logger.error("Exception occured in get_column_info_details.")
#################################################################################################
def datatype_conversion_func(excel_file_path, value, columns_info_details, src):
    
    task_logger.info(columns_info_details)
    new_col_info = []
    if src == 'Oracle':
        for col_name, col_type in columns_info_details:
            if col_type.startswith("NUMBER"):  # Case-insensitive match for 'number'
            # Extract precision and scale within parentheses
                match = re.search(r"\((\d+),(\d+)\)", col_type)
                if match:
                    precision, scale = map(int, match.groups())
                    if scale >0 :
                        new_col_type = f"decimal({precision},{scale})"
                    elif precision <= 9 :
                        new_col_type = "number(9,0)"
                    elif (precision > 9 and precision <= 18) :
                        new_col_type = "number(18,0)"
                    elif precision > 18 :
                        new_col_type = f"decimal({precision})"
                else:
                    new_col_type = col_type
            elif col_type.startswith("INTERVAL DAY"):
                new_col_type = "interval day(k) to second(r)"
            elif re.search( r"TIMESTAMP\((\d+)\) WITH TIME ZONE", col_type):
                new_col_type = "timestamp(k) with time zone"
            elif re.search( r"TIMESTAMP\((\d+)\) WITH LOCAL TIME ZONE", col_type):
                new_col_type = "timestamp with local time zone"
            elif re.search( r"TIMESTAMP\((\d+)\)", col_type):
                new_col_type = "timestamp"
            else:
                new_col_type = col_type
            d= (col_name,new_col_type)
            new_col_info.append(d)
    else:
        new_col_info = columns_info_details
    
    with open(excel_file_path,'r', encoding='utf-8') as jsonfile:
        task_logger.info("fetching connection details")
        json_data1 = json.load(jsonfile)
        task_logger.info("reading connection details completed")

    mappings = json_data1[value]
    result = {source_type.lower(): target_type.lower()
            for source_type, target_type in mappings.items()}
    
    task_logger.info(new_col_info)
    task_logger.info(result)
    
    converted_x = [(col_name.lower(), result.get(col_type.lower(), col_type.lower()))
                for col_name, col_type in new_col_info]
    
    task_logger.info("converted one: %s", converted_x)
    task_logger.info("result: %s", result)    
    return converted_x
#################################################################################################

def src_query_funct(data_pkg,type_change):
    """ function to query """
    try:
        src_inges_type = data_pkg['json_data']['source']

        if src_inges_type == 'DB':
            src=data_pkg['src_type']
            tgt=data_pkg['tgt_type']
            columns_info_details, _ = get_columns_info_details(data_pkg)
            paths_data=data_pkg['paths_data']
            excel_file_path=paths_data["folder_path"]+paths_data["seatunnel_mapping_file_path"]
            value = f"{src}_to_{tgt}"
            converted_x = datatype_conversion_func(excel_file_path, value, columns_info_details, src)
            return converted_x ," ", " " 
        else:
            task_logger.info(type_change)
            converted_list= [(x,y) for x, y  in type_change.items()]
            return converted_list , "" ,""
    except Exception as e:
        task_logger.exception("error ouccured in src_query_funct: %s",e)
        raise e
#################################################################################################

def tgt_query_funct(data_pkg,tgt_cursor,columns_info,pri,uni):
    """ target query function """
    tgt=data_pkg['tgt_type']
    if tgt in ('MySQL'):
        table_name = f"`{data_pkg['tgt_details']['schema_name']}`.`{data_pkg['tgt_details']['object_name']}`"
        create_table_query = f"CREATE TABLE {table_name} ("
        for column_info in columns_info:
            column_name, data_type = column_info
            create_table_query += f"`{column_name}` {data_type}, "
        create_table_query = create_table_query.rstrip(", ") + pri + uni + ")"
        
    elif tgt in ('PostgreSQL','MSSQL', 'Oracle'):
        table_name = f"{data_pkg['tgt_details']['schema_name']}.{data_pkg['tgt_details']['object_name']}"
        create_table_query = f"CREATE TABLE {table_name} ("
        for column_info in columns_info:
            column_name, data_type = column_info
            create_table_query += f"{column_name} {data_type}, "
        create_table_query = create_table_query.rstrip(", ") + pri + uni + ")"
    task_logger.warning(create_table_query)

    if data_pkg['json_data']['source'] == 'Files':
        if tgt == 'Oracle':
            create_table_query = create_table_query.replace("varchar", "varchar2(400)")
            create_table_query = create_table_query.replace("string", "varchar2(400)")
            create_table_query = create_table_query.replace("double", "Number(15,2)")
            create_table_query = create_table_query.replace(" int", "Number(10)")
            create_table_query = create_table_query.replace("bigint", "Number(19)")
        else:
            create_table_query = create_table_query.replace("varchar", "varchar(255)")
            create_table_query = create_table_query.replace("string", "varchar(255)")
            create_table_query = create_table_query.replace("float", "double")
            
            if tgt in ('PostgreSQL','MSSQL'):
                create_table_query = create_table_query.replace("double", "double precision")
    elif data_pkg['json_data']['source'] == 'DB':
        if tgt in ('PostgreSQL','MSSQL', 'MySQL'):
            create_table_query = create_table_query.replace("nchar", "char")
            create_table_query = create_table_query.replace("nvarchar2", "varchar")
            create_table_query = create_table_query.replace("nvarchar", "varchar")
            create_table_query = create_table_query.replace("varchar2", "varchar")
            create_table_query = create_table_query.replace("character varying", "varchar")
        elif tgt in ('Oracle'):
            create_table_query = create_table_query.replace("nvarchar(", "nvarchar2(")
            create_table_query = create_table_query.replace("character varying", "varchar2")
            
    task_logger.info("create table query : %s", create_table_query)
    
    # Execute the CREATE TABLE query
    tgt_cursor.execute(create_table_query)
    task_logger.info("Target Table created.")
    return True

################################################################################################

def connect_to_db(element,data_pkg, json_section):
    """ connecting to database """
    task_logger.info("Connecting to database.")
    dir_name = f"{data_pkg['paths_data']['folder_path']}src/scripts/ingestion/"
    sys.path.insert(0, dir_name)
    connections = importlib.import_module("connections")
    config_file_path = f"{data_pkg['paths_data']['folder_path']}repo/connections/"
    if element =='MySQL':
        try:
            engine,connection_details = connections.establish_conn_for_mysql(data_pkg['json_data'],
            json_section,config_file_path,data_pkg['paths_data'])
        except Exception as e:
            task_logger.error("exception occured while connecting to mysql :%s", e)
            raise e
    elif element =='PostgreSQL':
        try:
            engine,connection_details = connections.establish_conn_for_postgres(data_pkg['json_data'],
            json_section,config_file_path,data_pkg['paths_data'])
        except Exception as e:
            task_logger.error("exception occured while connecting to PostgreSQL:  %s", e)
            raise e
    elif element =='MSSQL':
        try:
            engine,connection_details = connections.establish_conn_for_sqlserver(data_pkg['json_data'],
            json_section,config_file_path,data_pkg['paths_data'])
        except Exception as e:
            task_logger.error("exception occured while connecting to mssql:  %s", e)
            raise e
    elif element =='Oracle':
        try:
            engine,connection_details = connections.establish_conn_for_oracle(data_pkg['json_data'],
            json_section,config_file_path, data_pkg['paths_data'])
        except Exception as e:
            task_logger.error("exception occured while connecting to oracle:  %s", e)
            raise e
    elif element =='AWS S3':
        try:
            engine,connection_details = connections.establish_conn_for_s3(data_pkg['json_data'],
            json_section,config_file_path, data_pkg['paths_data'])
        except Exception as e:
            task_logger.error("exception occured while connecting to s3:  %s", e)
    elif element =='Remote Server':
        try:
            engine,connection_details = connections.establish_conn_for_remoteserver(data_pkg['json_data'],
            json_section,config_file_path, data_pkg['paths_data'])
            task_logger.info("success")
        except Exception as e:
            task_logger.error("exception occured while connecting to Remote Server:  %s", e)
    else:
        task_logger.error("connection not available.")
        return False
    return engine,connection_details

###############################################################################################

def create(data_pkg,type_change):
    """ if table is not present , it will create"""
    task_logger.info("Creating table...")
    try:

        task_logger.info("In create function")
        # get the key details about source table
        columns_info,pri,uni=src_query_funct(data_pkg,type_change)

        if data_pkg['json_data']['source'] == 'Files':
            VARCHAR_VALUE = 'varchar'
        else:
            VARCHAR_VALUE = 'varchar(70)'
        if data_pkg['tgt_details']['audit_fields'] == 'YES':
            add_audit =  (('crtd_by',VARCHAR_VALUE),('crtd_dttm',VARCHAR_VALUE),
                          ('updt_by',VARCHAR_VALUE),('updt_dttm',VARCHAR_VALUE))
            columns_info = list(columns_info) + list(add_audit)

        tgt_conn3,_ = connect_to_db(data_pkg['tgt_type'],data_pkg,'target')
        tgt_connection = tgt_conn3.raw_connection()
        tgt_cursor = tgt_connection.cursor()
        # Construct CREATE TABLE query
        x=tgt_query_funct(data_pkg,tgt_cursor,columns_info,pri,uni)
        if x is True:
            tgt_connection.commit()
            return True
    except Exception as e:
        if re.search(r"(already used by an existing object|already exists|already an object)", str(e).lower()):
            task_logger.warning("Table already exists.")
            return True
        else:
            task_logger.exception("Exception occurred: %s", e)
            return False
################################################################################################

def operations_performed(operation,data_pkg,type_change):
    """operation to be performed"""
    task_logger.info("Executing the operation on table :%s", operation)
    if operation == 'INSERT':
        task_logger.info("In INSERT block. No changes required.")
        return True
    elif operation == 'TRUNCATE AND LOAD':
        try:
            # connect to the db, perform truncate on tgt table
            task_logger.info("In TRUNCATE AND LOAD block. No operations required.")
            conn3,connection_details = connect_to_db(data_pkg['tgt_type'],data_pkg,'target')
            task_logger.info(conn3,connection_details)
            ###########check if table exists#######
            task_logger.info("started truncating the table %s",data_pkg['tgt_details']['object_name'])
            connection = conn3.raw_connection()
            cursor = connection.cursor()
            truncate_query = f"""TRUNCATE TABLE
            {data_pkg['tgt_details']['schema_name']}.{data_pkg['tgt_details']['object_name']}"""
            task_logger.info(truncate_query)
            cursor.execute(truncate_query)
            connection.commit()
            # cursor.execute(truncate_query)
            task_logger.info("truncating table finished, started inserting data into "
            "table :%s", data_pkg['tgt_details']['object_name'])
            # exit(0)
            return True
        except Exception as e:
            task_logger.exception("Exception occured in truncate and load  : %s", e)
            raise e
    elif operation == 'CREATE IF NOT EXIST':
        try :
            task_logger.info("In Table CREATE block. No operations required.")
            # connect to the db, get the source table details,
            #create ddl for tgt and seatunnel_execute
            value = create(data_pkg,type_change)
            return True
        except Exception :
            task_logger.exception("Exception1 occured in create")
            return False
    elif  operation == 'DROP AND CREATE':
        try:
            # connect to the db, perform truncate on tgt table
            task_logger.info("In DROP AND CREATE block. ")
            conn3,connection_details = connect_to_db(data_pkg['tgt_type'],data_pkg,'target')
            task_logger.info(conn3,connection_details)
            ###########check if table exists#######
            # if_exists()
            connection = conn3.raw_connection()
            cursor = connection.cursor()
            truncate_query = f"""Drop TABLE
            {data_pkg['tgt_details']['schema_name']}.{data_pkg['tgt_details']['object_name']}"""
            cursor.execute(truncate_query)
            connection.commit()
            task_logger.info("dropping table finished, started inserting data into "
            "table :%s", data_pkg['tgt_details']['object_name'])
            task_logger.info("Creating the Table.")
            value = create(data_pkg,type_change)
            task_logger.info("value: %s",value)
            return value
        except Exception as e:
            task_logger.exception("Exception occured in drop and create : %s", e)
            return False
    elif  operation == 'UPSERT':
        try:
            task_logger.info("In UPDATE AND INSERT Block.")
            return True
        except Exception as e:
            task_logger.exception("Update and Insert Exception : %s" , e)
            return False
    else:
        task_logger.info("PLease select the Action on Table.")
        return False,'None'
