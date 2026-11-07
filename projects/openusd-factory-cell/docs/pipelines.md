# How I run the build

I keep one set of test and wheel-building commands so a change gets the same checks locally, on GitHub and when I connect an Azure pipeline. The repository initially contained only a README, so this change adds its first package, tests and CI rather than extending an existing suite.

## What the words mean

By a factory cell, I mean a small group of equipment working in one area. My drawing shows each piece as a box. The automatic checks make sure the saved box sizes and positions match the layout I entered, then put the tool into a file someone else can install.

A pipeline is a saved list of steps the computer runs after a change. YAML is the readable text format for those instructions. A schema is a set of rules used to check that instruction file before running it. JUnit is the test-result file format that lets the build service show which checks passed or failed. A wheel is the archive used to install this Python tool.

## Run the working parts without an Azure account

From the repository root, with Python 3.11 or 3.12:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python scripts/validate_pipeline.py
bash scripts/test.sh
bash scripts/build-wheel.sh dist
```

The shell scripts use Bash and POSIX paths, as on the Ubuntu CI agent. On Windows I run them in WSL. The package's `factory-cell` command itself is Python.

`test.sh` runs the entire suite with branch coverage, a 90% coverage floor and subprocess coverage so the real CLI tests count. `build-wheel.sh` builds the archive, installs it in a disposable environment outside the checkout, exports the example and reopens the resulting scene. An exit trap removes that disposable environment on success or failure. Neither script starts a server or browser.

## Connect Azure DevOps in about two minutes

I have not performed a hosted Azure run. The YAML is schema-checked, and GitHub CI executes its shared commands on both supported Python versions. Uploading to Azure's Tests, Coverage and Artifacts pages requires a connected organization and an agent.

1. In an Azure DevOps project, open **Pipelines → New pipeline → GitHub**.
2. Authorize access to `jackaI1/openusd-factory-cell`, select **Existing Azure Pipelines YAML file**, choose `main` and `/azure-pipelines.yml`.
3. Save and run. If Microsoft-hosted parallel jobs are not available for the organization, request the free grant or use a Linux self-hosted agent with Python 3.11/3.12 in its tool cache. Change the pool to that agent's pool if necessary.
4. Open each matrix job's **Tests** and **Code Coverage** tabs. Download `wheel-python3.11` or `wheel-python3.12` from **Artifacts**.

No token, organization ID or secret belongs in this repository. The pipeline only reads this public source, installs dependencies, tests and builds; it does not deploy or publish to a package registry.

## What the Azure jobs do

`azure-pipelines.yml` runs on changes to `main` and `skills/*`, and on pull requests targeting `main`. Each isolated matrix job selects Python with `UsePythonVersion@0`, installs `.[dev]`, checks the YAML, and calls `scripts/test.sh`.

`PublishTestResults@2` uploads `reports/junit.xml`. `PublishCodeCoverageResults@2` uploads `reports/coverage.xml`, a Cobertura-format coverage file, with the checkout as its source root. I install the .NET 8 SDK before the coverage publisher because that task requires .NET. Both publishers use `succeededOrFailed()` so a failing test does not hide the report. Missing results, failed test-result uploads and empty coverage fail their publishing tasks. A cancelled build can skip them.

The default success condition keeps wheel building and `PublishPipelineArtifact@1` behind the tests. Each job publishes to a different artifact name, preventing a collision between the Python versions. GitHub Actions uploads the same reports even after failure and retains the wheel from successful jobs. It provides public run evidence without requiring an Azure organization.

## Schema checks and their limits

`scripts/validate_pipeline.py` downloads Microsoft's full Draft 7 JSON schema from the fixed commit `e8090fd525cd6ba47d7685c698f3f51983e298c6` in [azure-pipelines-vscode](https://github.com/microsoft/azure-pipelines-vscode). It checks the SHA-256 digest before using it. A network error or digest mismatch fails the check, rather than silently skipping validation. Error output is bounded to avoid dumping the whole task catalog.

That schema lists `PublishCodeCoverageResults@2` in its task-name catalog but omits its input definition. I supplement only that task from Microsoft's [task metadata at commit 3cdc037](https://github.com/microsoft/azure-pipelines-tasks/blob/3cdc037ed3702e99641e536ed7512b3f873b9d1d/Tasks/PublishCodeCoverageResultsV2/task.json), saved in `schemas/PublishCodeCoverageResultsV2.task.json` under its accompanying Microsoft MIT license. The supplement still requires the summary path, validates input types and rejects unknown input names. It does not replace the pipeline schema with a small hand-written subset.

Regression tests validate the real YAML and reject a misspelled root field, an unknown step field, an invalid matrix, a nonexistent task version and a coverage-input typo. Schema validation checks configuration structure; it cannot prove agent availability, GitHub authorization, hosted service publication or the meaning of shell commands.

I followed Microsoft's [Python pipeline guide](https://learn.microsoft.com/azure/devops/pipelines/ecosystems/customize-python), [test publisher reference](https://learn.microsoft.com/azure/devops/pipelines/tasks/reference/publish-test-results-v2), and [coverage publisher reference](https://learn.microsoft.com/azure/devops/pipelines/tasks/reference/publish-code-coverage-results-v2).
