__version__ = "0.1.0"

from perf import utils
from xml.etree import cElementTree

import numpy
import prettytable
import requests

import collections
import itertools
import logging
import os
import types
import urllib.parse


class ApiPerformance(object):

    def __init__(self, script_dir, api_spec_url, config, logger=None):
        # process constructor inputs
        self._logger = logger if logger else utils.get_logger()
        self.api_spec_url = api_spec_url
        self.config = config
        self.script_dir = script_dir

        # pull some items out of config for convenience
        self.avg_threshold_exceptions = self.config.get("Average_Threshold_Exceptions", {})
        self.avg_threshold_for_list = self.config.get("Average_Threshold_For_List", 6000)
        self.avg_threshold_for_object = self.config.get("Average_Threshold_For_Object", 1500)

        # these paths will not be tested - this is an "absolute" blacklist
        self.path_blacklist = self.config.get("Path_Blacklist", [])

        # if specified, only these paths will be tested (unless in blacklist)
        self.path_whitelist = self.config.get("Path_Whitelist", [])

        self.num_passes = self.config.get("Number_Of_Passes", 5)

        self.api_base_url = ''
        self.api_calls = []
        self.api_spec = {}

        self._set_api_url()

        # For the purposes of CI system (Jenkins) integration / supporting a "performance test"
        # build plan, we conveniently use the checkstyle paradigm.

        # account for the first 3 lines of prettytable output before counting lines in
        # checkstyle output
        self.check_file_line = 3
        self.checkstyle = cElementTree.Element('checkstyle', version="5.0")
        self.checkfile_tree = cElementTree.ElementTree(self.checkstyle)
        self.check_file_path = 'api_performance_checkstyle.txt'
        self.check_file = cElementTree.SubElement(self.checkstyle, "file",
                                                  name=self.check_file_path)
        self.checkstyle_output_file = f'{script_dir}/../../{self.check_file_path}'
        self.dry_run = False
        self.html_file_path = 'api_performance.html'
        self.html_output_file = f'{script_dir}/../../{self.html_file_path}'

        # tracks paths for which we should index the UUID of the first returned object
        self.indexable_paths = []

        self.results = []
        self.session = requests.Session()
        self.session.headers = self.config['Headers']
        self.session.verify = False

        # tracks the API call path and UUID to be used for single object retrieval calls
        self.single_object_index = {}

        self.summary_table = prettytable.PrettyTable()
        self.summary_table.field_names = ['Key', 'Value']
        self.summary_table.align['Key'] = 'l'
        self.summary_table.align['Value'] = 'r'

        self.table = prettytable.PrettyTable()
        self.table.field_names = ['API Call', 'Description', 'Objects', 'Status',
                                  'Avg (ms)', 'High (ms)', 'Low (ms)']
        self.table.align['API Call'] = 'l'
        self.table.align['Description'] = 'l'

    def _set_api_url(self):
        api_spec_resp = requests.get(self.api_spec_url)
        api_spec_resp.raise_for_status()
        self.api_spec = api_spec_resp.json()

        # assemble the base API URL based on parsing the original API spec URL and the basePath
        # defined in the OpenAPI schema.
        api_spec_url_parsed = urllib.parse.urlparse(self.api_spec_url)
        self.api_base_url = f"{api_spec_url_parsed.scheme}://{api_spec_url_parsed.netloc}{self.api_spec['basePath']}"
        self._logger.info('Using base URL: %s', self.api_base_url)

    def _should_process_path(self, path):
        if path in self.path_blacklist:
            return False
        else:
            if not self.path_whitelist:
                return True

            for whitelist_path in self.path_whitelist:
                if path.startswith(whitelist_path):
                    return True
            return False

    def add_checkstyle_error(self, error):
        """Add a checkstyle error to the given element."""
        cElementTree.SubElement(self.check_file, "error", line=str(self.check_file_line),
                                severity="error",
                                message=error)

    def analyze_results(self):
        status_index = self.table.field_names.index('Status')
        api_call_index = self.table.field_names.index('API Call')
        for result in self.results:
            self.check_file_line += 1
            if result[status_index] != 'OK':
                self.add_checkstyle_error(f'{result[api_call_index]} is {result[status_index]}')

        self.checkfile_tree.write(os.path.join(self.script_dir, '../checkstyle-api-perf.log'))

    def build_api_calls(self):
        self._logger.debug(f"Loading OpenAPI schema from {self.api_spec_url}")
        paths = collections.OrderedDict(sorted(self.api_spec['paths'].items()))

        for path, methods in paths.items():
            if not self._should_process_path(path):
                self._logger.debug('skipping path: %s', path)
                continue

            for method, method_def in methods.items():
                if method == 'get':
                    # check if a complementary "single object retrieval path" exists in the API
                    # spec. if so, we'll cache the UUID of the first object retrieved so we have
                    # a reference to work with downrange.
                    single_object_path = path + '/{uuid}'
                    if ('{uuid}' not in path and
                            path not in self.path_blacklist and
                            single_object_path in paths and
                            'get' in paths[single_object_path]):
                        self.indexable_paths.append(path)

                    # iterate through query string params and build a list of possible parameters
                    if 'parameters' in method_def:

                        self._logger.debug('Processing definition of endpoint %s %s',
                                           method.upper(), path)
                        params_index = {}

                        for param in method_def['parameters']:
                            if param['in'] == 'query':
                                if param['type'] == 'boolean':
                                    params_index[param['name']] = {
                                        'x-param-conflicts-with': param.get(
                                            'x-param-conflicts-with', []),
                                        'values': [True]
                                    }
                                elif 'enum' in param:
                                    params_index[param['name']] = {
                                        'x-param-conflicts-with': param.get(
                                            'x-param-conflicts-with', []),
                                        'values': param['enum']
                                    }

                        # get the sorted set of param names (dict keys)
                        param_names_sorted = sorted(params_index)

                        # compile a list of compatible query parameter sets
                        param_sets = list()

                        # create sets using each parameter as a "base"
                        # with which all other applicable parameters could be used.
                        for param_name in param_names_sorted:

                            # drop any parameters which conflict with the base parameter
                            # simple logic provided the param is not listed as conflicting
                            # with itself...
                            param_set = {param for param in param_names_sorted
                                         if param not in
                                         params_index[param_name]['x-param-conflicts-with']}

                            # order the parameter set (transforming to list) for consistency and
                            # deduplication
                            param_set = sorted(param_set)

                            # track this parameter set if unique
                            if param_set not in param_sets:
                                param_sets.append(param_set)

                        # process the power sets of these parameter sets, yielding a list of all
                        # possible parameter combinations
                        self._logger.debug('Building parameter power sets')

                        param_combos = list()
                        for param_set in param_sets:
                            for param_combo in utils.get_power_set(param_set):
                                param_combo = sorted(param_combo)
                                if param_combo not in param_combos:
                                    self._logger.debug('Adding parameter combo: %s', param_combo)
                                    param_combos.append(param_combo)

                        # walk through each param set and eliminate any which contain conflicting
                        # parameters. this will leave us with the list of valid parameter combos.
                        self._logger.debug('Building a list of valid parameter combos')

                        valid_param_combos = []
                        for param_combo in param_combos:
                            has_conflict = False
                            for param in param_combo:
                                for param_to_compare in param_combo:
                                    if (param_to_compare in
                                            params_index[param]['x-param-conflicts-with']):
                                        has_conflict = True
                            if not has_conflict:
                                self._logger.debug('Adding valid parameter combo: %s',
                                                   ','.join(param_combo))
                                valid_param_combos.append(param_combo)

                        # Finally, add all combinations of values for each combination of
                        # parameters.
                        for param_combo in valid_param_combos:
                            self._logger.debug('Adding calls for param combo: %s', param_combo)

                            # generate the combos of possible values of parameters
                            param_values_combos = list(itertools.product(
                                *(params_index[key]['values']
                                  for key in param_combo)))

                            for param_value_combo in param_values_combos:

                                api_call_params = {}
                                for x, param in enumerate(param_combo):
                                    api_call_params[param] = param_value_combo[x]

                                api_call = {
                                    'path': path,
                                    'method': method.upper(),
                                    'params': api_call_params}

                                self._logger.debug('Adding call %s', api_call)
                                self.api_calls.append(api_call)

        # find all functions defined in the api_call_generators module and execute them
        # for module_item in dir(api_call_generators):
        #     module_item_instance = getattr(api_call_generators, module_item)
        #     if isinstance(module_item_instance, types.FunctionType):
        #         result = module_item_instance()
        #         if not result:
        #             self._logger.error('Could not generate API calls using %s() - exiting',
        #                                module_item_instance.__name__)
        #         for api_call in result:
        #             if self._should_process_path(api_call['path']):
        #                 self.api_calls.append(api_call)
        #             else:
        #                 self._logger.debug('skipping path %s from generated API call',
        #                                    api_call['path'])

        # this buys us free order of operations where "listing" calls are made first,
        # thus single object retrieval has a defined identifier to work with.
        self.api_calls = sorted(self.api_calls, key=lambda k: k['path'])

    def init_summary_table(self):
        self.summary_table.add_row(['API URL', self.api_base_url])
        self.summary_table.add_row(['Number of requests per API call', self.num_passes])
        self.summary_table.add_row(['Skipped API endpoints', '\n'.join(self.path_blacklist)])

    def print_results_table(self):
        """Output the results of the performance test."""
        print(self.summary_table)
        print(self.table)

    def run(self):
        qualifier = 'would' if self.dry_run else 'will'
        self._logger.info('Each API call %s be executed %s time(s)', qualifier, self.num_passes)

        for api_call in self.api_calls:

            api_call_object_count = 0
            api_call_data = api_call.get('data', None)

            if '{uuid}' in api_call['path']:
                api_call['type'] = 'single_object'
                if self.dry_run:
                    api_call['path'] = api_call['path'].replace('{uuid}', '_uuid_')
                else:
                    if api_call['path'] in self.single_object_index:
                        api_call['path'] = api_call['path'].replace(
                            '{uuid}', self.single_object_index[api_call['path']])
                    else:
                        self._logger.warning('Could not get a UUID for %s; skipping', api_call['path'])
                        continue
            else:
                api_call['type'] = 'object_list'

            # use a prepared request so we can save some overhead as well as get the formatted
            # URL before sending it
            api_endpoint = f"{self.api_base_url}{api_call['path']}"
            api_request = requests.Request(api_call['method'], api_endpoint,
                                           params=api_call['params'], data=api_call_data,
                                           headers=self.session.headers)
            api_prepared_request = api_request.prepare()

            # set the API call metadata

            # determine the API call path and parameter string (URL minus the protocol, domain name,
            # and port)
            api_call_parsed = urllib.parse.urlparse(api_prepared_request.url)
            api_call_path_and_params = f'{api_call_parsed.path}'
            if api_call_parsed.query:
                api_call_path_and_params += f'?{api_call_parsed.query}'
            api_call_label = f"{api_call['method']} {api_call_path_and_params}"
            api_call_description = api_call.get('description', '')

            if api_call_path_and_params in self.avg_threshold_exceptions:
                api_call_description += '\n' if api_call_description else ''
                api_call_description += f'Threshold: {self.avg_threshold_exceptions[api_call_path_and_params]}'

            self._logger.debug('Processing calls to %s', api_call_label)

            # compile the results table with dummy data so we can see the table output / make sure
            # the appropriate calls are represented
            if self.dry_run:

                result_row = [
                    api_call_label,
                    api_call_description,
                    api_call_object_count,
                    'DRY RUN',
                    'N/A',
                    'N/A',
                    'N/A'
                ]
                self.results.append(result_row)
                self.table.add_row(result_row)

            # iterative execution of the API call
            else:

                result_times = []

                for x in range(0, self.num_passes):
                    result = self.session.send(api_prepared_request)

                    # if auth fails for some reason, log a warning
                    if result.status_code == requests.codes.unauthorized:
                        self._logger.warning('Got Unauthorized response for: %s',
                                             api_prepared_request.url)

                    # TODO: update this logic to leverage the acceptable responses defined by the
                    # OpenAPI schema!
                    if result.status_code in [requests.codes.ok,
                                              requests.codes.created,
                                              requests.codes.multi_status]:

                        # TODO: process multi_status in distinct fashion and look for one or more
                        # failures...
                        data = result.json()

                        if (x == 0 and api_call['method'] == 'GET' and
                                api_call['path'] in self.indexable_paths and
                                not api_call['params']):
                            result = data.get('result', None)
                            if result and isinstance(result, list) and data['count'] > 0:
                                object_uuid = data['result'][0]['uuid']
                                single_object_path = api_call['path'] + '/{uuid}'
                                self.single_object_index[single_object_path] = object_uuid
                                self._logger.debug('Cached UUID for %s: %s',
                                                   single_object_path, object_uuid)

                    elif result.status_code in [requests.codes.no_content]:
                        milliseconds = result.elapsed.total_seconds() * 1000
                        data = {
                            'count': 1,
                            'result': {},
                            'time': f'{milliseconds}mS'
                        }

                    # the webserver timed out, so we must process a synthetic / assumed result.
                    elif result.status_code == requests.codes.gateway_timeout:
                        data = {
                            'count': -1,
                            'result': 'TIMEOUT',
                            'time': '-1mS'
                        }
                    else:
                        self._logger.error('API call failed: %s %s: %s',
                                           api_call['method'], result.url, result.text)
                        data = {
                            'count': -1,
                            'result': 'FAILED',
                            'time': '-1mS'
                        }

                    # set the API call metadata by looking at the first response
                    if x == 0:
                        api_call_object_count = data.get('count', 1 if data else 0)

                    if 'time' in data:
                        api_call_response_time = float(data['time'].replace('mS', ''))
                    else:  # support "non-conforming" response structures
                        api_call_response_time = result.elapsed.total_seconds() * 1000

                    response_result = data.get('result', None)
                    if response_result == 'FAILED':
                        result_times.append('FAILED')
                    elif response_result == 'TIMEOUT':
                        result_times.append('TIMEOUT')
                    else:
                        result_times.append(api_call_response_time)

                if 'FAILED' in result_times:
                    status = 'FAILED'
                    avg_time = max_time = min_time = -1
                elif 'TIMEOUT' in result_times:
                    status = 'TIMEOUT'
                    avg_time = max_time = min_time = -1
                else:
                    avg_time = numpy.mean(result_times)
                    max_time = numpy.max(result_times)
                    min_time = numpy.min(result_times)

                    if ((api_prepared_request.url in self.avg_threshold_exceptions and
                         avg_time <=
                            self.avg_threshold_exceptions[api_prepared_request.url]) or
                        (api_call['type'] == 'object_list' and
                         avg_time <= self.avg_threshold_for_list) or
                        (api_call['type'] == 'single_object' and
                         avg_time <= self.avg_threshold_for_object)):
                        status = 'OK'
                    else:
                        status = 'SLOW'

                result_row = [
                    api_call_label,
                    api_call_description,
                    api_call_object_count,
                    status,
                    "%.2f" % avg_time,
                    "%.2f" % max_time,
                    "%.2f" % min_time
                ]
                self.results.append(result_row)
                self.table.add_row(result_row)
                self._logger.debug(result_row)

    def set_debug(self):
        self._logger.info('Setting debug level logging')
        self._logger.setLevel(logging.DEBUG)
        for handler in self._logger.handlers:
            handler.setLevel(logging.DEBUG)

    def write_results_table(self):
        self.summary_table.add_row(['SLOW threshold (object list)',
                                    self.avg_threshold_for_list])
        self.summary_table.add_row(['SLOW threshold (single object)',
                                    self.avg_threshold_for_object])

        for directory in [os.path.dirname(self.checkstyle_output_file),
                          os.path.dirname(self.html_output_file)]:
            if not os.path.exists(directory):
                os.makedirs(directory)

        html_header = """
<!DOCTYPE html>
<html>
    <head>
        <title>API Performance Test Results</title>
        <style>
            body {font-family: monospace;
                  font-size: 11pt;}
            table tr:hover {background: blue;
                            color: white;}
        </style>
    </head>
    <body>
    <div>API Performance Test Results</div>
"""

        html_footer = """
    </body>
</html>
"""

        # write checkstyle (XML) formatted output
        with open(self.checkstyle_output_file, 'w') as text_file:
            text_file.write(str(self.table))

        # write HTML formatted output
        with open(self.html_output_file, 'w') as html_file:
            html_file.write(html_header)
            html_file.write(self.summary_table.get_html_string())
            html_file.write('<br />\n')
            html_file.write(self.table.get_html_string())
            html_file.write(html_footer)
