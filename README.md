# parser-acunetic360-csv
Custom stand alone parser for CSV files exported from Acunetix360. This script will bulk convert the CSV files from Acunetix360 into PTRAC files that can be manually imported into Plextrac.

# Requirements
- [Python 3+](https://www.python.org/downloads/)
- [pip](https://pip.pypa.io/en/stable/installation/)
- [pipenv](https://pipenv.pypa.io/en/latest/)

# Installing
After installing Python, pip, and pipenv, run the following commands to setup the Python virtual environment.
```bash
git clone this_repo
cd path/to/cloned/repo
pipenv install
```

# Setup
After setting up the Python environment, you will need to setup a few things before you can run the script.

## CSV Data to Import
In the `config.yaml` file, the `acunetic360_data_folder_path` should point to the folder where you place the Acunetix360 CSV files you're trying to convert to PTRAC files. The default directory is 'file_to_process'. You can either create this folder in the root directory where you cloned the project, or change the directory path in the config to where you want to pull files from.

## API Version
The Api Version of the Plextrac instance you plan to import .ptrac files to is required for successful .ptrac generation. The API Version can be found at the bottom right of the Account Admin page in Plextrac. This value can be entered in the `config.yaml` file after `api_version`.

# Usage
After setting everything up you can run the script with the following command. You should be in the folder where you cloned the repo when running the following.
```bash
pipenv run python main.py
```
You can also add values to the `config.yaml` file to simplify providing the script with the data needed to run. Values not in the config will be prompted for when the script is run.

## Required Information
The following values can either be added to the `config.yaml` file or entered when prompted for when the script is run.
- API version
- Folder path to directory containing Acunetix360 CSV file(s) to import

## Script Execution Flow
When the script starts it will load in config values and try to:
- Read files in the specified directory

For each file found in the directory it will:
- Read and verify CSV file data is from a valid Acunetix360 export
- Create a temporary data structure for easier data parsing
- It will then start looping through each row in the newly created temporary data structure and parse the row into the finding structure Plextrac can import

After parsing the CSV, the script will save a .ptrac file that was parsed from the CSV.

Generated .ptrac files can be imported into an existing report in Plextrac, to import the findings it contains.
- Go to the Findings tab of a report
- Click 'Add findings' > 'File Imports'
- Select 'PlexTrac' from 'Import source' dropdown
- Select PTRAC file to import

## Logging
The script is run in INFO mode so you can see progress on the command line. A log file will be created when the script is run and saved to the root directory where the script is. You can search this file for "WARNING" or "ERROR" to see if something did not get parsed or imported correctly. Any critical level issue will stop the script immediately.
