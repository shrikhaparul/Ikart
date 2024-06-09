"""importing modules"""
import os
import subprocess
import uuid
import logging
import json
import re
from plugin import SeaTunnelPlugin

# Initialize logger
seatunnel_task_logger = logging.getLogger('seatunnel_task_logger')
task_logger = logging.getLogger("task_logger")


class SeaTunnel(object):
    """Creating a class for SeaTunnel."""
    def __init__(
        self,
        name: str,
        config_dir: str,
        seatunnel_path: str = "seatunnel.sh",
        parallelism: int = 1,
        mode: str = "BATCH",
    ):
        self.seatunnel_path = seatunnel_path
        self.config_dir = (
            config_dir
            if config_dir
            else os.path.join(os.path.dirname(__file__), "config")
        )
        self.execution_parallelism = parallelism
        self.job_mode = mode
        self.job_name = name

    def exec(
        self,
        in_plug: SeaTunnelPlugin,
        out_plug: SeaTunnelPlugin,
        config_name: str = None,
        cluster_name: str = None,
        timeout: int = None,

        remove_config: bool = True
    ) -> tuple:
        """Function to create and execute the seatunnel command. """
        config_fp = config_name or str(uuid.uuid4())
        config_fp = config_fp.lower()
        config_fp = os.path.join(self.config_dir, config_fp)

        if not os.path.isdir(self.config_dir):
            os.mkdir(self.config_dir)
        try:
            template = {
                "env": {
                    "job.name": self.job_name,
                    "execution.parallelism": self.execution_parallelism,
                    "job.mode": self.job_mode,
                },
                "source": [in_plug.config],
                "sink": [out_plug.config],
            }
            config = json.dumps(template, ensure_ascii=False, indent=2)
            with open(config_fp, "wt", encoding='utf-8') as f:
                f.write(config)
            # Logging: Config file creation
            task_logger.info("Config file created at: %s",config_fp)
            cmd = f"{self.seatunnel_path} -cn {cluster_name} --config {config_fp}"
            task_logger.info("Executing command: %s ",cmd)
            x, total_read_count, total_write_count = self.__shell(cmd)
            return x, total_read_count, total_write_count
        except Exception as e:
            task_logger.error("Error executing task: %s ",e)
            raise
        finally:
            if os.path.isfile(config_fp) and remove_config:
                os.remove(config_fp)
                # Logging: Config file removal
                task_logger.info("Config file removed: %s ", config_fp)

    def __shell(self, cmd: str) -> tuple:

        try:
            # Run the command
            seatunnel_task_logger.info("Executing shell command: %s ",cmd)
            result = subprocess.run(
                cmd, shell=True, check=True, text=True, capture_output=True
            )
            output = result.stdout
            lines = output.split('\n')

            # Remove the line containing "Parsed config file:"
            filtered_lines = [line for line in lines if "bucket" not in line
                  and "access_key" not in line.lower()
                  and "secret_key" not in line.lower()
                  and "user" not in line.lower()
                  and "password" not in line.lower()
                  and "url" not in line.lower()
                  and "fs.s3a.endpoint" not in line.lower()
                  and "fs.s3a.aws.credentials.provider" not in line.lower()
                  ]

            # Join the filtered lines back into a single string
            filtered_text = '\n'.join(filtered_lines)
            seatunnel_task_logger.info("Command output: %s ", filtered_text)

            read_count_pattern = r"Total Read Count\s+:\s+(\d+)"
            write_count_pattern = r"Total Write Count\s+:\s+(\d+)"

            # Extracting total read count
            read_count_match = re.search(read_count_pattern, filtered_text)
            total_read_count = int(read_count_match.group(1)) if read_count_match else None

            # Extracting total write count
            write_count_match = re.search(write_count_pattern, filtered_text)
            total_write_count = int(write_count_match.group(1)) if write_count_match else None

            task_logger.info("total read count %s",total_read_count)
            task_logger.info("total write count %s",total_write_count)
            
            return result.returncode, total_read_count, total_write_count

        # Handle if the command returns a non-zero exit code
        except subprocess.CalledProcessError as e:
            table_check = (r"Caused by: java\.sql\.SQLSyntaxErrorException:"
                           r"Table '.*?' doesn't exist")
            tab_check = (r'Caused by: org\.postgresql\.util\.PSQLException:'
                         r'ERROR: relation ".*?" does not exist')
            db_check= r"Caused by: java\.sql\.SQLSyntaxErrorException: Unknown database"
            avro_check = r"Caused by: org\.apache\.seatunnel\.shade\.connector\.file\.org\.apache\.avro\.AvroRuntimeException:"
            io_error_check = r"Caused by: java\.io\.IOException: No space left on device"
            if re.search(table_check, e.stderr) or re.search(tab_check, e.stderr):
                task_logger.error("Table doesn't exist")
            elif re.search(db_check, e.stderr):
                task_logger.error("Database doesn't exist")
            elif re.search("Unable to connect to any cluster",e.stderr):
                task_logger.error("Cluster currently unavailable.")
            elif re.search("API-01",e.stderr) or re.search("JDBC-04",e.stderr):
                task_logger.error("Check the connection. Connectivity Error.")
            elif re.search(avro_check, e.stderr):
                task_logger.error("Duplicate field error occurred in Avro record.")
            elif re.search(io_error_check, e.stderr):
                task_logger.info("No space left on device error occurred.")
            else:
                task_logger.error("Exception Occured.Please refer to the seatunnel logs.")
                seatunnel_task_logger.error(e.stderr)
            return 1 , "No src count","No tgt count"
        except Exception as e:
            task_logger.error("Error executing shell command: %s ",e)
            return 1, "No src count","No tgt count"