# OpenAPI Performance Testing

This utility is a combination of a CLI and python module intended to introspect a running API based on its
OpenAPI specification and empirically measure average response time (calculated server-side) of those calls.

The following items are required for this utility to be of immediate value:

* Your API is documented using the OpenAPI schema version 2.0
* Your endpoints use token-based auth with `Authorization` header
* Your API supports JSON request and response bodies
* Response body JSON object includes the `time` property which specifies the server-side calculated
amount of time it took to compose the response (in units of milliseconds) with or without the `mS`
unit of measure notation (suffix).


# Automation

Currently, only the `GET` method of any API endpoint is automatically tested and measured.
See the `Extending API call scope` for strategies on other HTTP methods and more complex API calls
which may not be automatically tested. 

The utility has some basic methodologies of automatically constructing API calls with certain types of
query and path parameters.

Query parameters:
 * `boolean` type parameters - will test both `true` and `false`
 * `string` type parameters with `enum` defined - will test all values of the `enum`
 * Parameters with the `x-param-conflicts-with` property in their schema (which contains a list of
 mutually exclusive parameter names) will be processed to ensure that no such parameter combinations
 shall be tested for a given endpoint

Path parameters:
 * `{uuid}` - will attempt to make a call to the "listing" endpoint (simply removes `/{uuid}` from
 the given path) and use the value of the `uuid` property of the first object returned in order to
 populate this value.

Any API call definition (e.g. `GET /v1/users`) with the `x-skip-perf-test` property present and set to
a value which evaluates in python to be "non-Falsy" will be skipped.

# Installation

Python script dependencies are provided via pipenv.

```
git clone git@github.com:mxmader/openapi-perf-testing
cd openapi-perf-testing
pipenv install --deploy
```

# Configuration

See `perf_config.json.example` for the "kitchen sink" of supported configuration variables and examples.
Their semantics are documented here:

* `Average_Threshold_Exceptions` - object whose keys are API endpoint paths and query strings with values
of performance threshold (typically higher than the value of `Average_Threshold_For_*` depending on the
response structure - `List` or `Object`) to use specifically for those endpoints/query strings
* `Average_Threshold_For_List` - integer value used to determine whether an API call for a list is "slow"
* `Average_Threshold_For_Object` - integer value used to determine whether an API call for an object is "slow"
* `Headers` - key/value pairs representing HTTP request headers to be used for every API call
* `Number_Of_Passes` - number of times each API call is to be made for the purposes of computing average
response time.
* `Path_Blacklist` - list of paths for which API calls shall not be made / no measurements will be taken
* `Path_Whitelist` - list of paths for which API calls shall be made; no other paths will be used when
this list is present.

# Script usage

```
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
```

Since we're using pipenv and provided an entry in the `[scripts]` section of `Pipfile`, you may invoke
this script like so:

```
pipenv run measure-api-response-time [options]
```

# Defaults

For development purposes, the utility will attempt to retrieve the OpenAPI spec from
`http://localhost:8080/api/v1/openapi` if the `--api-spec-url` argument is not specified.

# Extending API call scope

Sometimes you may need additional "pre-processing" logic in order to determine proper values for
query or path parameters; or, you may want to performance-test API calls with support for POST, PUT, or
DELETE methods.

To facilitate this, you may create a python module in the root of this project named `api_call_generators`.
When present, the performance testing logic will import the module and execute every function found therein.

Be sure to `return` a data structure as follows for `GET` requests:
```python3
return {
    'description': '',  # output with `--print` argument to the measurement script
    'path': '/v1/widgets',
    'method': 'GET',
    'params': {'broken': True}
}
```

And use the following for `POST` or `PUT` (simply adds the `data` property; you can retain `params` if
applicable to your use case):

```python3
return {
    'description': '',
    'path': '/v1/widgets',
    'method': 'POST',  # or 'PUT'
    'data': {'name': 'foo', 'broken': True}
}
```

See `api_call_generators.py.example` for a practical example.
