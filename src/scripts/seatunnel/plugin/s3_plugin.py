from . import SeaTunnelPlugin
SQL = "select * from {schema}.{table}"
S3_END_POINT = 'fs.s3a.endpoint'
S3_CREDS_PROVIDER = 'fs.s3a.aws.credentials.provider'

database_type = {
    "MySQL": {
        "driver": "com.mysql.cj.jdbc.Driver",
        "port": 3306,
        "url":"jdbc:mysql://{host}:{port}/{database}",
        "table": SQL
    },
    "PostgreSQL": {
        "driver": "org.postgresql.Driver",
        "port": 5432,
        "url":"jdbc:postgresql://{host}:{port}/{database}",
        "table": "select * from {database}.{schema}.{table}"
    },
    "MSSQL": {
        "driver": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
        "port": 1433,
        "url":"jdbc:sqlserver://{host}:{port}",
        "table": "select * from {database}.{schema}.{table}"
    },
    "Oracle": {
        "driver": "oracle.jdbc.OracleDriver",
        "port": 1521,
        "url":"jdbc:oracle:thin:@{host}:{port}/{database}",
        "table": SQL
    },
    "snowflake": {
        "driver": "net.snowflake.client.jdbc.SnowflakeDriver",
        "url":"jdbc:snowflake//<account_name>.snowflakecomputing.com",
        "table": SQL
    },
    "redshift": {
        "driver": "com.amazon.redshift.jdbc42.Driver",
        "port": 5439,
        "url":"jdbc:redshift://{host}:{port}/{database}",
        "table": SQL
    },
}

class S3FileINPlugin(SeaTunnelPlugin):
    """Class to create Fileout Plugin Parameters."""
    def __init__(
            self,
            s3_endpoint: str,
            s3_credentials_provider: str,
            bucket_name: str,
            access_key: str,
            secret_key: str,
            file_path: str,
            file_type: str,
            batchsize: int,
            schema: str,
            skip_header: int,
            *args, **kwargs):
        super().__init__(self.PluginType.OUT, type, *args, **kwargs)
        self.file_path = file_path
        self.file_type = file_type
        self.batchsize = batchsize
        self.bucket_name =bucket_name
        self.s3_endpoint = s3_endpoint
        self.s3_credentials_provider = s3_credentials_provider
        self.access_key = access_key
        self.secret_key = secret_key
        self.skip_header = skip_header
        self.schema = schema

    @property
    def config(self) -> dict:
        if self.file_type == 'parquet':
            config = {
            'plugin_name': 'S3File',
            'path': self.file_path,
            'file_format_type': self.file_type,
            'bucket':self.bucket_name,
            S3_END_POINT:self.s3_endpoint,
            S3_CREDS_PROVIDER:self.s3_credentials_provider,
            'access_key':self.access_key,
            'secret_key':self.secret_key,
            'batchsize': self.batchsize
        }
        else:
            config = {
            'plugin_name': 'S3File',
            'path': self.file_path,
            'file_format_type': self.file_type,
            'bucket':self.bucket_name,
            S3_END_POINT:self.s3_endpoint,
            S3_CREDS_PROVIDER:self.s3_credentials_provider,
            'access_key':self.access_key,
            'secret_key':self.secret_key,
            'skip_header_row_number' : self.skip_header,
            'schema': self.schema,
            'batchsize': self.batchsize
        }
        return config   

class S3FileOUTPlugin(SeaTunnelPlugin):
    """Class to create Fileout Plugin Parameters."""
    def __init__(
            self,
            s3_endpoint: str,
            s3_credentials_provider: str,
            bucket_name: str,
            access_key: str,
            secret_key: str,
            file_path: str,
            delimiter: None,
            file_type: str,
            file_name_expression: str,
            filename_time_format: str,
            type: str,
            batchsize: int,
            *args, **kwargs):
        super().__init__(self.PluginType.OUT, type, *args, **kwargs)
        self.file_path = file_path
        self.delimiter = delimiter
        self.file_type = file_type
        self.filename_time_format = filename_time_format
        self.batchsize = batchsize
        self.file_name_expression = file_name_expression
        self.bucket_name =bucket_name
        self.s3_endpoint = s3_endpoint
        self.s3_credentials_provider = s3_credentials_provider
        self.access_key = access_key
        self.secret_key = secret_key

    @property
    def config(self) -> dict:
        config = {
            'plugin_name': 'S3File',
            'path': self.file_path,
            'field_delimiter': self.delimiter,
            'file_format_type': self.file_type,
            'file_name_expression': f'{self.file_name_expression}_{self.filename_time_format}',
            'custom_filename': 'true',
            'batchsize': self.batchsize,
            'is_enable_transaction': 'false',
            'bucket':self.bucket_name,
            S3_END_POINT:self.s3_endpoint,
            S3_CREDS_PROVIDER:self.s3_credentials_provider,
            'access_key':self.access_key,
            'secret_key':self.secret_key
        }
        return config
