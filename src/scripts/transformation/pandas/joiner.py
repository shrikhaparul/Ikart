"""
This module contains functions for orchestrating data processing tasks, including
fetching data from various sources,performing operations on the data, and storing
the results in different formats
"""

import logging
import pandas as pd
from update_audit import audit_failure
task_logger = logging.getLogger('task_logger')

NOT_COMPATIBLE="Source Type not compatible"


def join_operations(arguments,data_sources, operations):
    """
    Perform operations on data from multiple sources and merge them into a single DataFrame.

    Parameters:
        data_sources (dict): Dictionary containing DataFrames fetched from different sources.
        operations (dict): Dictionary containing details of merge operations.

    Returns:
        pandas.DataFrame: Merged DataFrame.

    Raises:
        Exception: If an error occurs during the merge operation.
    """

    try:
        left_source=data_sources[operations["left_input_df"]]
        right_source=data_sources[operations["right_input_df"]]
        left_source = left_source.rename(columns=lambda x: f"{x}_left")
        right_source = right_source.rename(columns=lambda x: f"{x}_right")

        task_logger.info("Join left source:%s",left_source)
        task_logger.info("Join right source:%s",right_source)
        join_condition=operations["join_condition"]
        if '=' not in join_condition or join_condition.count('=') != 1:
            raise ValueError("Condition not of right format")
        left_cond, right_cond = join_condition.split('=')
        left_cond = left_cond.strip()
        right_cond = right_cond.strip()
        left_col=""
        right_col=""
        if '.' not in left_cond:
            left_col = left_cond
        if '.' not in right_cond:
            right_col=right_cond
        if "." in right_cond:
            right_cond=right_cond.split('.')
            if right_cond[0]==operations["right_input_df"]:
                right_col=right_cond[1]
            elif right_cond[0]==operations["left_input_df"]:
                left_col=right_cond[1]
            else:
                raise ValueError("Table Name not written properly")
        if "." in left_cond:
            left_cond=left_cond.split('.')
            if left_cond[0]==operations["right_input_df"]:
                right_col=left_cond[1]
            elif left_cond[0]==operations["left_input_df"]:
                left_col=left_cond[1]
            else:
                raise ValueError("Table Name not written properly")
        if left_col =="" or right_col=="":
            raise ValueError("Condition not of right format")
        left_col+="_left"
        right_col+="_right"
        task_logger.info(left_source.columns)
        task_logger.info(right_source.columns)
        join_type=operations["join_type"]
        result = pd.merge(left_source, right_source, how=join_type,left_on=left_col,
        right_on=right_col, validate=None)
        result = result.loc[:, ~result.columns.duplicated()]
        return result
    except Exception as e:
        task_logger.error("Cannot join the table: %s", e)
        audit_failure(arguments)
        raise
