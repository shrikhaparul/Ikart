from . import SeaTunnelPlugin

class SFTPFILEINPlugin(SeaTunnelPlugin):
    """Class to create Fileout Plugin Parameters."""
    def __init__(
            self,
            host: str,
            port: int,
            user_name: str,
            password: str,
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
        self.host = host
        self.port = port
        self.user_name = user_name
        self.password = password
        self.skip_header = skip_header
        self.schema = schema

    @property
    def config(self) -> dict:
        if self.file_type == 'parquet':
            config = {
            'plugin_name': 'SftpFile',
            'host' : self.host,
            'port' : self.port,
            'user' : self.user_name,
            'password'  : self.password,
            'path': self.file_path,
            'file_format_type': self.file_type,
            'batchsize': self.batchsize
        }
        else:
            config = {
            'plugin_name': 'SftpFile',
            'host' : self.host,
            'port' : self.port,
            'user' : self.user_name,
            'password'  : self.password,
            'path': self.file_path,
            'file_format_type': self.file_type,
            'skip_header_row_number' : self.skip_header,
            'schema': self.schema,
            'batchsize': self.batchsize
        }
        return config   

class SFTPFileOUTPlugin(SeaTunnelPlugin):
    """Class to create Fileout Plugin Parameters."""
    def __init__(
            self,
            host: str,
            port: int,
            user: str,
            password: str,
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
        self.host =host
        self.port = port
        self.user = user
        self.password = password

    @property
    def config(self) -> dict:
        config = {
            'plugin_name': 'SftpFile',
            'path': self.file_path,
            'field_delimiter': self.delimiter,
            'file_format_type': self.file_type,
            'file_name_expression': f'{self.file_name_expression}_{self.filename_time_format}',
            'custom_filename': 'true',
            'batchsize': self.batchsize,
            'is_enable_transaction': 'false',
            'host':self.host,
            'port':self.port,
            'user':self.user,
            'password':self.password
        }
        return config