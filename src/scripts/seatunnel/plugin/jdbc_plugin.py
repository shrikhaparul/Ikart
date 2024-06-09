"""JDBC and files plugin"""
from . import SeaTunnelPlugin

UPSERT = 'UPSERT'
SCHEMA_TABLE = "{schema}.{table}"
database_type = {
    "MySQL": {
        "driver": "com.mysql.cj.jdbc.Driver",
        "port": 3306,
        "url":"jdbc:mysql://{host}:{port}/{database}",
        "table": SCHEMA_TABLE
    },
    "PostgreSQL": {
        "driver": "org.postgresql.Driver",
        "port": 5432,
        "url":"jdbc:postgresql://{host}:{port}/{database}",
        "table": "{database}.{schema}.{table}"
    },
    "MSSQL": {
        "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
        "port": 1433,
        "url":"jdbc:sqlserver://{host}:{port}",
        "table": "{database}.{schema}.{table}"
    },
    "Oracle": {
        "driver": "oracle.jdbc.OracleDriver",
        "port": 1521,
        "url":"jdbc:oracle:thin:@{host}:{port}/{database}",
        "table": SCHEMA_TABLE
    },
    "snowflake": {
        "driver": "net.snowflake.client.jdbc.SnowflakeDriver",
        "url":"jdbc:snowflake//<account_name>.snowflakecomputing.com",
        "table": SCHEMA_TABLE
    },
    "redshift": {
        "driver": "com.amazon.redshift.jdbc42.Driver",
        "port": 5439,
        "url":"jdbc:redshift://{host}:{port}/{database}",
        "table": SCHEMA_TABLE
    },
}

class JDBCInPlugin(SeaTunnelPlugin):
    """Class to create JDBCIn Plugin Parameters."""

    def __init__(
            self,
            host: str,
            user: str,
            password: str,
            database: str,
            table: str,
            port: int,
            col_nm : str,
            type: str,
            clause: str,
            schema: str = 'public',
            fetchsize: int = 10000,
            *args, **kwargs):
        super().__init__(self.PluginType.IN, type, *args, **kwargs)
        self.user = user
        self.password = password
        self.database = database
        self.driver = database_type[self.type]['driver']
        self.complete_table = database_type[self.type]['table'].format(database= database,
                                                                       table=table, schema=schema)
        self.table = table
        self.col_nm = col_nm
        self.schema = schema
        self.url = database_type[self.type]['url'].format(host=host, port=port, database= database) 
        self.fetchsize = fetchsize
        self.clause = clause

    @property
    def config(self) -> dict:
        config = {
            'plugin_name': 'Jdbc',
            'url': self.url,
            'connection_check_timeout_sec' : 1000,
            'driver': self.driver,
            'user': self.user,
            'password': self.password,
            'database': self.database,
            'query': f"select {self.col_nm} from {self.complete_table} {self.clause}",
            'fetch_size': self.fetchsize,
        }
        return config

class JDBCOutPugin(SeaTunnelPlugin):
    """Class to create JDBCOut Plugin Parameters."""

    def __init__(
            self,
            host: str,
            user: str,
            password: str,
            database: str,
            table: str,
            type: int,
            prim: str,
            action: str,
            insert_query : str,
            audit : str,
            source : str,
            port: int = 5432,
            schema: str = 'public',
            batchsize: int = 100000,
            name: str = 'Jdbc',
            *args, **kwargs):

        super().__init__(self.PluginType.OUT, type, *args, **kwargs)
        self.user = user
        self.password = password
        self.database = database
        self.driver = database_type[self.type]['driver']
        self.table = table
        self.schema = schema
        self.insert_query = insert_query
        self.url = database_type[self.type]['url'].format(host=host, port=port, database= database)
        self.batchsize = batchsize
        self.plugin_name = name
        self.prim = prim
        self.action = action
        self.audit = audit
        self.source = source

    @property
    def config(self) -> dict:
        if self.action == UPSERT and ((self.source == 'DB') or (
            self.source == 'Files')) :
            config = {
                        'plugin_name': self.plugin_name,
                        'url': self.url,
                        'driver': self.driver,
                        'user': self.user,
                        'password': self.password,
                        'database': self.database,
                        'table': f"{self.schema}.{self.table}",
                        'batch_size': self.batchsize,
                        'support_upsert_by_query_primary_key_exist' : "true",
                        'primary_keys' : self.prim,
                        'generate_sink_sql': 'true'

                        }
        elif self.action != UPSERT and ((self.source == 'DB') or (
        self.source == 'Files' and self.audit == 'NO')) :
            config = {
                        'plugin_name': self.plugin_name,
                        'url': self.url,
                        'driver': self.driver,
                        'user': self.user,
                        'password': self.password,
                        'database': self.database,
                        'table': f"{self.schema}.{self.table}",
                        'batch_size': self.batchsize,
                        'generate_sink_sql': 'true'
            }
        elif self.action != UPSERT and self.source == 'Files' and self.audit == 'YES' :
            config = {
                        'plugin_name': self.plugin_name,
                        'url': self.url,
                        'driver': self.driver,
                        'user': self.user,
                        'password': self.password,
                        'batch_size': self.batchsize,
                        'query' : self.insert_query

            }
        return config

class FILEINPlugin(SeaTunnelPlugin):
    """Class to create Filein Plugin Parameters."""
    def __init__(
            self,
            file_path: str,
            file_type: str,
            skip_header: int,
            delimiter: None,
            schema : None,
            name: str = 'LocalFile',
            *args, **kwargs):

        super().__init__(self.PluginType.OUT, type, *args, **kwargs)
        self.file_path = file_path
        self.file_type = file_type
        self.skip_header = skip_header
        self.delimiter = delimiter
        self.schema = schema
        self.plugin_name = name

    @property
    def config(self) -> dict:
        if self.file_type == 'parquet':
            config = {
                'plugin_name': self.plugin_name,
                'path': self.file_path,
                'file_format_type' : self.file_type,
                'skip_header_row_number' : self.skip_header ,
                'fetch_size': 100000
            }
        else :
            print(self.schema )
            config = {
                'plugin_name': self.plugin_name,
                'path': self.file_path,
                'file_format_type' : self.file_type,
                'skip_header_row_number' : self.skip_header ,
                'delimiter': self.delimiter,
                'schema': self.schema  ,
                'fetch_size': 100000
            }
        return config

class FILEOUTPlugin(SeaTunnelPlugin):
    """Class to create Fileout Plugin Parameters."""
    def __init__(
            self,
            file_path: str,
            delimiter: None,
            file_type: str,
            file_name_expression: str,
            filename_time_format:str,
            batchsize: int ,
            type:str,
            name: str = 'LocalFile',
            *args, **kwargs):
        super().__init__(self.PluginType.OUT, type, *args, **kwargs)
        self.file_path = file_path
        self.delimiter = delimiter
        self.file_type = file_type
        self.filename_time_format = filename_time_format
        self.plugin_name = name
        self.batchsize = batchsize
        self.file_name_expression = file_name_expression
    @property
    def config(self) -> dict:

        config = {
            'plugin_name': self.plugin_name,
            'path': self.file_path,
            'field_delimiter': self.delimiter,
            'file_format_type': self.file_type,
            'file_name_expression':f"{self.file_name_expression}_{self.filename_time_format}"	,
            "custom_filename" : "true",
            "batchsize": self.batchsize,
            "is_enable_transaction" : "false",
            "enable_header_write": "true"
        }
        return config
    