from operator import itemgetter
from typing import Union, List
import yaml
import os
import csv

import utils.log_handler as logger
log = logger.log
import settings
from utils.auth_handler import Auth
from csv_parser import CSVParser
import utils.input_utils as input
from utils.input_utils import LoadedCSVData, LoadedJSONData
import utils.general_utils as utils
import api


# determines type of script execution
# can either take in a dynamic header CSV file that determines data mapping outside script
# otherwise can have static mapping defined in script, but only works for a single type of data file
predefined_csv_headers_mapping = True

# TEMPLATE checklist
# rewrite
# - load_data_file
# - verify_data_file
# - create_temp_data_csv

# confirm
# - load_parser_mappings_from_data_file

# write
# - CSVParser > csv_headers_mapping_template


def handle_load_api_version(api_version:str, parser:CSVParser) -> None:
    """
    Handles prompting the user and setting the API version in the CSVParser. This is required for PTRAC generation.

    :param api_version: version of Plextrac instance a generated PTRAC will be importing into
    :type api_version: str
    :param parser: instance of CSVParser
    :type parser: CSVParser
    """
    if api_version == "":
        api_version = input.prompt_user(f'The Api Version of the PT instance you want to import a .ptrac to is required for successful generation.\nEnter the API Version of your instance. This can be found at the bottom right of the Account Admin page in PT')
    if len(api_version.split(".")) == 3:
        parser.doc_version = api_version
        return
    else:
        if input.retry(f'The entered value {api_version} was not a valid version'):
            return handle_load_api_version("", parser)


def load_data_file(data_file_path:str = "") -> LoadedCSVData|None:
    """
    Loads the file containing data to be imported in the script

    TEMPLATE
    When using this script as a base template, need to rewrite this function based on the file of data needing to import

    :param data_file_path: filepath to file containing data to import, defaults to ""
    :type data_file_path: str, optional - will prompt user if filepath is not supplied
    :return: raw data loaded from file
    :rtype: LoadedCSVData if CSV, LoadedJSONData if Json, custom object if another filetype
    """
    # return input.load_csv_data("Enter file path to Acunetix360 CSV data to import", csv_file_path=data_file_path)

    if data_file_path == "":
        log.exception(f'Cannot load file with empty file path')
        return None

    if not os.path.exists(data_file_path):
        log.exception(f'Specified CSV file at \'{data_file_path}\' does not exist')
        return None

    try:
        with open(data_file_path, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)

            csv_complete = []
            for row in reader:
                csv_complete.append(row)
            csv_headers = csv_complete[0]

            # depending on encoding, empty cells at the end of a row might be counted as empty strings "" or not added
            # (i.e. each row of the CSV might be a different length array)
            # the following processing makes sure each row of the CSV is the same length
            for row in csv_complete[1:]:
                if len(row) < len(csv_headers):
                    for i in range(len(csv_headers) - len(row)):
                        row.append("")

            csv_data = csv_complete[1:]

            return LoadedCSVData(file_path=data_file_path, csv=csv_complete, headers=csv_headers, data=csv_data)

    except Exception as e:
        log.exception(f'Error loading file: {e}')
        return None


def verify_data_file(loaded_file_data:LoadedCSVData, csv_parser:CSVParser) -> bool:
    """
    Checks that the loaded data file is valid for the script
    
    TEMPLATE
    When using this script as a base template, can add custom validation to make sure the data file is valid
    - correct report fields
    - correct finding fields
    - file contains findings

    :param loaded_file_data: object of returned loaded data from `load_data_file()`
    :type loaded_file_data: LoadedCSVData if CSV, LoadedJSONData if Json, custom object if another filetype
    :param csv_parser: instance of CSVParser - used to validate against data mapping loaded in the `csv_headers_mapping_template` dict in the CSVParser
    :type csv_parser: CSVParser
    :return: whether the file is valid
    :rtype: bool
    """    
    # has correct field/headers
    if loaded_file_data.headers != csv_parser.get_csv_headers():
        log.warning(f'CSV headers read from file\n{loaded_file_data.headers}')
        log.warning(f'Expected headers\n{csv_parser.get_csv_headers()}')
        return False
    
    # has findings
    if len(loaded_file_data.data) < 1:
        log.error(f'Did not find any findings in loaded data file')
        return False
    
    return True
    
    
def load_parser_mappings_from_data_file(csv:List[list], parser:CSVParser) -> bool:
    """
    There are 2 cases of loading mapping data in CSVParser based on `predefined_csv_headers_mapping`
    1) `csv_headers_mapping_template` dict in the CSVParser is empty
    2) `csv_headers_mapping_template` dict in the CSVParser is pre-populated and only needs to have indexes matched

    Function for case 2:
    Data mapping will be parsed from a temp CSV file. This CSV file is generated in `create_temp_data_csv()` to emulate
    the additional headers CSV file that could be used in the script
    
    For each mapping a pre-existing object in `csv_headers_mapping_template` will be updated. This method of not predefining
    the `col_index` allows the mapping to be defined in the script, but the order of columns on the CSV can still be variable.

    :param csv: array with 2 arrays - 2 row generated temp CSV with headers on row 1 and mapping keys on row 2
    :type csv: List[list] - [List[headers], List[mapping_keys]]
    :param parser: instance of CSVParser that data mapping will be loaded into
    :type parser: CSVParser
    :return: did the function update `predefined_csv_headers_mapping` objects - will still return True if some keys were invalid
    :rtype: bool
    """
    headers = csv[0]

    for index, header in enumerate(headers):
        mapping_key = parser.get_mapping_key_from_header(header)
        if mapping_key in parser.get_data_mapping_ids():
            if parser.csv_headers_mapping[header].get("matched") == None: # if there are dup column headers, use the first col found and don't override when looking at the dup
                parser.csv_headers_mapping[header]["col_index"] = index
                parser.csv_headers_mapping[header]["matched"] = True
        else:
            log.error(f'Invalid mapping key \'{mapping_key}\' for header \'{header}\'. Check csv_parser.py > csv_headers_mapping_template to correct or add. Marking as \'no_mapping\'')
            parser.csv_headers_mapping[header]["mapping_key"] = "no_mapping"

    log.success(f'Loaded column headings from temp CSV')
    return True


def create_temp_data_csv(loaded_file_data:LoadedCSVData, parser:CSVParser) -> List[list]:
    """
    To be able to handle non CSV data files, this function converts the inputted data file into
    a temp CSV that can be handled by CSVParser.

    TEMPLATE
    When using this script as a base template, can customize this function to create a CSV like
    list from the data file the script needs to parse.

    :param loaded_file_data: object of returned loaded data from `load_data_file()`
    :type loaded_file_data: LoadedCSVData
    :param parser: instance of CSVParser that data will be loaded into
    :type parser: CSVParser
    :return: temp generated CSV
    :rtype: List[list]
    """
    # turning the Acunetix360 CSV into a different CSV to handle certain data changes
    temp_csv = []

    # determine temp CSV headers - client, report, finding, and asset headers
    headers = parser.get_csv_headers()
    temp_csv.append(headers)
    
    # get finding info
    for finding in loaded_file_data.data:
        # seed row with number of possible columns determined from number of headers
        row = []
        for i in range(len(headers)):
            row.append("")

        # parse finding fields from data file
        for index, value in enumerate(finding):
            # severity
            if index == 1 and value == "BestPractice":
                row[index] = "Low"
                continue
            if index == 1 and value == "Information":
                row[index] = "Low"
                continue
            # status
            if index == 9:
                row[index] = "Open"
                continue

            row[index] = value

        # add parsed list of fields to CSV
        temp_csv.append(row)

    # DEBUG - save generated CSV to file
    # with open("temp_csv.csv",'w', newline="") as file:
    #     writer = csv.writer(file)
    #     writer.writerows(temp_csv)
    
    return temp_csv


def load_data_into_parser(csv:List[list], parser:CSVParser) -> None:
    """
    Loads CSV like data into the instance of the CSVParser that will parser and transform the data into a format that Plextrac can import.

    CSV data file or temp generated CSV data file to import data from

    :param csv: CSV like data to import data from
    :type csv: List[list]
    :param parser: instance of CSVParser to load data into
    :type parser: CSVParser
    """
    parser.csv_data = csv[1:]
    log.success(f'Loaded data into parser instance')


def handle_add_report_template_name(report_template_name:str, parser:CSVParser) -> None:
    """
    Checks if the given the report_template_name value from the config.yaml file matches the name of an existing
    Report Template in Plextrac. If the template exists in platform, adds this report template UUID to the template
    for reports created with this script. The result being a Report Template is selected in the proper dropdown
    in platform for all reports created.
    """
    report_templates = []

    try:
        response = api._templates.report_templates.list_report_templates(auth.base_url, auth.get_auth_headers(), auth.tenant_id)
    except Exception as e:
        log.exception(e)
    if type(response.json) == list:
        report_templates = list(filter(lambda x: x['data']['template_name'] == report_template_name, response.json))

    if len(report_templates) > 1:
        if not input.continue_anyways(f'report_template_name value \'{report_template_name}\' from config matches {len(report_templates)} Report Templates in platform. No Report Template will be added to reports.'):
            exit()
        return

    if len(report_templates) == 1:
        parser.report_template['template'] = report_templates[0]['data']['doc_id']
        return
    
    if not input.continue_anyways(f'report_template_name value \'{report_template_name}\' from config does not match any Report Templates in platform. No Report Template will be added to reports.'):
        exit()


def handle_add_findings_template_name(findings_template_name:str, parser:CSVParser) -> None:
    """
    Checks if the given the findings_template_name value from the config.yaml file matches the name of an existing
    Finding Layouts in Plextrac. If the layout exists in platform, adds this findings template UUID to the template
    for reports created with this script. The result being a Finding Layout is selected in the proper dropdown
    in platform for all reports created.
    """
    findings_templates = []

    try:
        response = api._templates.findings_templateslayouts.list_findings_templates(auth.base_url, auth.get_auth_headers())
    except Exception as e:
        log.exception(e)
    if type(response.json) == list:
        findings_templates = list(filter(lambda x: x['data']['template_name'] == findings_template_name, response.json))

    if len(findings_templates) > 1:
        if not input.continue_anyways(f'findings_template_name value \'{findings_template_name}\' from config matches {len(findings_templates)} Finding Layouts in platform. No Findings Layout will be added to reports.'):
            exit()
        return

    if len(findings_templates) == 1:
        parser.report_template['fields_template'] = findings_templates[0]['data']['doc_id']
        return
    
    if not input.continue_anyways(f'findings_template_name value \'{findings_template_name}\' from config does not match any Finding Layouts in platform. No Finding Layout will be added to reports.'):
        exit()



if __name__ == '__main__':
    for i in settings.script_info:
        print(i)
    
    with open("config.yaml", 'r') as f:
        args = yaml.safe_load(f)

    export_folder_path = "exported_ptracs"
    try:
        os.mkdir(export_folder_path)
    except FileExistsError as e:
        log.debug(f'Could not create directory {export_folder_path}, already exists')

    auth = Auth(args)
    auth.handle_authentication()

    # get API version from config
    api_version = ""
    if args.get('api_version') != None and args.get('api_version') != "":
        api_version = str(args.get('api_version'))
        log.info(f'Set API Version to \'{api_version}\' from config...')
    # get data folder path
    acunetic360_data_folder_path = ""
    if args.get('acunetic360_data_folder_path') != None and args.get('acunetic360_data_folder_path') != "":
        acunetic360_data_folder_path = args.get('acunetic360_data_folder_path')
        log.info(f'Using csv data file path \'{acunetic360_data_folder_path}\' from config...')

    # load all file from directory
    file_list = []
    if os.path.exists(acunetic360_data_folder_path) and os.path.isdir(acunetic360_data_folder_path):
        files = os.listdir(acunetic360_data_folder_path)
        file_list = [file for file in files if os.path.isfile(os.path.join(acunetic360_data_folder_path, file))]
        if len(file_list) > 0:
            log.success(f'Found {len(file_list)} file(s) to process')
        else:
            log.critical(f'Could not find any files in \'{acunetic360_data_folder_path}\'. Exiting...')
            exit()
    else:
        log.critical(f'Could not find directory \'{acunetic360_data_folder_path}\'. Exiting...')
        exit()

    failed_files = []
    for file_name in file_list:
        # create parser instance
        log.info(f'Processing file \'{file_name}\'...')
        file_path = f'{acunetic360_data_folder_path}/{file_name}'
        parser = CSVParser()
        handle_load_api_version(api_version, parser)
    
        # switch 2: no header file - mapping already in parser, just need to find columns
        if predefined_csv_headers_mapping:
            log.info(f'Running script for Acunetix360 CSV (data mapping defined in script)...')

            # load file
            loaded_file = load_data_file(file_path)
            if loaded_file == None:
                log.exception(f'Could not load file \'{file_path}\'. Skipping...')
                failed_files.append(file_name)
                continue

            # verify file
            if not verify_data_file(loaded_file, parser):
                log.exception(f'\'{file_name}\' doesn\'t appear to be a Acunetix360 CSV file. This script can only parse Acunetix360 CSV files. Skipping...')
                failed_files.append(file_name)
                continue

            # create temp csv data file
            temp_csv = create_temp_data_csv(loaded_file, parser)

            # load temp CSV file headers into parser
            load_parser_mappings_from_data_file(temp_csv, parser)

            # load temp CSV file data into parser
            load_data_into_parser(temp_csv, parser)

        # handle report templates
        report_template_name = ""
        if args.get('report_template_name') != None and args.get('report_template_name') != "":
            report_template_name = args.get('report_template_name')
            log.info(f'Using report template \'{report_template_name}\' from config...')
            handle_add_report_template_name(report_template_name, parser)

        # handle finding layouts
        findings_layout_name = ""
        if args.get('findings_layout_name') != None and args.get('findings_layout_name') != "":
            findings_layout_name = args.get('findings_layout_name')
            log.info(f'Using findings layout \'{findings_layout_name}\' from config...')
            handle_add_findings_template_name(findings_layout_name, parser)

        # parser data
        if not parser.parse_data():
            log.exception(f'Ran into error and cannot parse data. Skipping...')
            failed_files.append(file_name)
            continue

        # print result
        parser.display_parser_results()

        # save file
        existing_files = [os.path.splitext(file)[0] for file in os.listdir(export_folder_path)]

        base_name = os.path.basename(loaded_file.file_path)
        export_file_name = utils.increment_file_name(base_name, existing_files)
        
        parser.save_data_as_ptrac(folder_path=export_folder_path, file_name=export_file_name) 


    log.success(f'\n\nProcessed and created PTRAC files for {len(file_list)-len(failed_files)}/{len(file_list)} files in \'{acunetic360_data_folder_path}\'. New PTRAC file(s) can be found in \'{export_folder_path}\' folder.')
    if len(failed_files) > 0:
        failed_files_str = "\n".join(failed_files)
        log.exception(f'Could not successfully process all files in the directory \'{acunetic360_data_folder_path}\'. Failed files:\n{failed_files_str}')
    if settings.save_logs_to_file:
        log.info(f'Additional logs were added to {log.LOGS_FILE_PATH}')