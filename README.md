# OpenAPI Performance Testing

This utility is a combination of a CLI and python module intended to introspect a running API based on its
OpenAPI specification and execute requests against the API.

The following items are required for this utility to be of immediate value:

* OpenAPI schema version 2.0
* Token-based auth with `Authorization` header
* JSON request and response bodies
* Response body JSON object includes the `time` property which specifies the server-side calculated
amount of time it took to compose the response (in units of milliseconds) with or without the `mS`
unit of measure notation.

Performance is only measured for `GET` requests.

# Configuration

See `perf_config.json.example` for the "kitchen sink" of supported configuration variables and examples.
Their semantics are documented here:

* `Average_Threshold_Exceptions` - object whose keys are API endpoint paths and query strings with values
of performance threshold (typically higher than the value of `Average_Threshold_For_*` depending on the
response structure - list or object) to use specifically for those endpoints/query strings
* `Average_Threshold_For_List` - integer value used to determine whether an API call for a list is "slow"
* `Average_Threshold_For_Object` - integer value used to determine whether an API call for an object is "slow"
* `Headers` - key/value pairs representing HTTP request headers to be used for every API call
* `Number_Of_Passes` - number of times each API call is to be made for the purposes of computing average
response time.
* `Path_Blacklist` - list of paths for which API calls shall not be made / no measurements will be taken
* `Path_Whitelist` - list of paths for which API calls shall be made; no nother paths will be used when
this list is present.

# CLI usage

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

# Defaults

For development purposes, the utility will attempt to retrieve the OpenAPI spec from
`http://localhost:8080/api/v1/openapi` if the `--api-spec-url` argument is not specified.