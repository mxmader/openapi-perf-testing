# OpenAPI Performance Testing

This utility is a combination of a CLI and python module intended to introspect a running API based on its
OpenAPI specification and execute requests against the API.

The following items are required for this utility to be of immediate value:

* OpenAPI schema version 2.0
* Token-based auth with `Authorization` header
* JSON request and response bodies

# Configuration

See `perf_config.json.example`

TODO: add details of the various object keys here.

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