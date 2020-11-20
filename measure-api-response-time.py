#!/usr/bin/env python3
"""
Usage:
  measure-api-response-time.py [options]
  measure-api-response-time.py --help

Options:
  -h --help                        Show this help screen
  --api-spec-url=url               URL of the API spec
  --config-file                    Config file path, if not 'perf_config.json'
  --checkstyle                     Write checkstyle and HTML output files
  --debug                          Debugging mode (outputs details regarding API call list
                                        construction)
  --dry-run                        Build the list of API calls, but don't execute them. Most useful
                                       when used with '--debug'. Renders --checkstyle and --html
                                       inert.
  --html                           Write HTML output file
  --print                          Print results table to stdout
"""

from docopt import docopt
import perf

import json
import os
import sys

arguments = docopt(__doc__, help=True)
api_spec_url = arguments.get('--api-spec-url')
if not api_spec_url:
    api_spec_url = 'http://localhost:8080/api/v1/openapi'

config_file_path = arguments.get('--config-file')
if not config_file_path:
    config_file_path = 'perf_config.json'

try:
    with open('perf_config.json', 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    print(f'Could not find config file: {config_file_path} - exiting')
    sys.exit(1)

script_dir = os.path.dirname(os.path.realpath(__file__))

api_perf_tester = perf.ApiPerformance(script_dir, api_spec_url, config)

if arguments['--dry-run']:
    api_perf_tester.dry_run = True

if arguments['--debug']:
    api_perf_tester.set_debug()

api_perf_tester.init_summary_table()
api_perf_tester.build_api_calls()
api_perf_tester.run()

if arguments['--print']:
    api_perf_tester.print_results_table()

# write filesystem artifacts if requested / applicable
if not arguments['--dry-run']:
    if arguments['--checkstyle']:
        api_perf_tester.analyze_results()

    if arguments['--html'] or arguments['--checkstyle']:
        api_perf_tester.write_results_table()
