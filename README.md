# IngKart - NextGen Ingestion Framework

# Setting up Python backend code for IngKart - NextGen Ingestion Framework

## Prerequisites

1. **Setting up your system:**

   Assuming you have the following tools already set up in your system:
   
   - [WSL (Windows Subsystem for Linux)](https://docs.microsoft.com/en-us/windows/wsl/install)
   - [Python](https://www.python.org/downloads/)
   - [Docker](https://docs.docker.com/get-docker/)
   - [MySQL Workbench](https://www.mysql.com/products/workbench/)

    Publish the Sample Task to GitHub:

    Use the GitHub UI to publish your sample task to a GitHub repository.

2. **Create a virtual environment:**

   Run the following command in your Ubuntu terminal to create a virtual environment named `<yours_virtual_environment_name>` (replace `<yours_virtual_environment_name>` with your preferred name):
   
   ```bash
   python3 -m venv <yours_virtual_environment_name>

3. **Activate the virtual environment:**

   Activate the virtual environment by running the following command in your terminal (replace `<yours_virtual_environment_name>` with your preferred name):

   ```bash
   source <yours_virtual_environment_name>/bin/activate

4. **Install required libraries:**

    Download and install the required Python libraries listed in a requirements.txt file. Ensure you are within the activated virtual environment when you run this command.
    Use the following command to install the libraries:
    (The below command will install all the necessary Python packages specified in the requirements.txt file.)
    
   ```bash
   pip install -r requirements.txt

5. **Organize Files:**

   Create a folder on your Ubuntu system and place the following files inside it:

   1. config.json
   2. master.py
   3. .env
   4. requirements.txt

6. **Configure config.json:**

   Open config.json and replace the placeholder "folder_path" with the actual path where master.py is located in your Ubuntu folder.

7. **Execute the Job:**

   Run the following command to execute the job:
   (please make sure to replace the published project name and task name for the below command)
   ```bash
   python3 master.py -p <project name> -t <task name>  

8. **Additional Information:**

    For more details and options, you can type the following command:
    
    ```bash
    python3 master.py --help


