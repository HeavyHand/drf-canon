# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- RFC 9457 Problem Details for every DRF error: `exception_handler`, `ProblemDetailsMixin`, `@problem_details`.
- `errors[]` extension with `location` and JSON Pointer per failed field.
- Closed catalogue of common problem types and `Problem` for declaring your own.
- `ProblemError`, `QueryParamError`, `PathParamError`, `HeaderError`.
- `ProblemSerializer` for describing error responses in OpenAPI.
