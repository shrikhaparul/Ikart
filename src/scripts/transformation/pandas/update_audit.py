"""contains audit functions"""

def audit_failure(arguments):
    """audits failure into audit table and updates status text file"""
    task_failed = arguments["task_failed"]
    task_failed(arguments['task_id'],arguments['text_file_path'],arguments['json_data'],
    arguments['run_id'],arguments['paths_data'],arguments['iter_value'])
