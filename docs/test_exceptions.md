# test_exceptions.md
# No skipped/xfail test without an owner-approved entry here (§C6, P25 G25.4).

## Test Exceptions

### Nested regression guards
- `tests/enterprise/test_regression_p8.py::TestRegression::test_p1_through_p7_suite_passes`
  - Reason: AMINOPS_REGRESSION_NESTED guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28 (removes nested-regression tests entirely).
- `tests/integration/test_regression_p9.py::TestRegression::test_p1_through_p8_suite_passes`
  - Reason: AMINOPS_REGRESSION_NESTED guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.
- `tests/governance/test_regression_p14.py::TestFullRegression::test_full_regression_passes`
  - Reason: AMINOPS_REGRESSION_NESTED_P14 guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.
- `tests/governance/test_regression_p15.py::TestFullRegression::test_full_regression_passes`
  - Reason: AMINOPS_REGRESSION_NESTED_P15 guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.
- `tests/governance/test_regression_p17.py::TestFullRegression::test_full_regression_passes`
  - Reason: AMINOPS_REGRESSION_NESTED_P17 guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.
- `tests/governance/test_regression_p18.py::TestFullRegression::test_full_regression_passes`
  - Reason: AMINOPS_REGRESSION_NESTED_P18 guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.
- `tests/governance/test_regression_p19.py::TestFullRegression::test_full_regression_passes`
  - Reason: AMINOPS_REGRESSION_NESTED_P19 guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.
- `tests/governance/test_regression_p20.py::TestFullRegression::test_full_regression_passes`
  - Reason: AMINOPS_REGRESSION_NESTED_P20 guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.
- `tests/governance/test_regression_p21.py::TestFullRegression::test_full_regression_passes`
  - Reason: AMINOPS_REGRESSION_NESTED_P21 guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.
- `tests/governance/test_regression_p22.py::TestFullRegression::test_full_regression_passes`
  - Reason: AMINOPS_REGRESSION_NESTED_P22 guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.
- `tests/governance/test_regression_p23.py::TestFullRegression::test_full_regression_passes`
  - Reason: AMINOPS_REGRESSION_NESTED_P23 guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.
- `tests/governance/test_regression_p24.py::TestFullRegression::test_full_regression_passes`
  - Reason: AMINOPS_REGRESSION_NESTED_P24 guard skips the subprocess
    when run inside a parent regression suite.
  - Expiry: P28.

### CI-file-dependent skips
- `tests/twin/test_cross_platform.py` (ci.yml skip)
  - Reason: skips when `.github/workflows/ci.yml` is not found
    (e.g. when running outside the repo root).
  - Expiry: P28 (removes CI-file-dependent tests).

### Regulatory file skips
- `tests/governance/test_regulatory.py` (applicability_matrix skips)
  - Reason: `docs/regulatory_scope/applicability_matrix.yaml` was not
    created in P4; the test skips when the file is absent.
  - Expiry: P28 (consolidates regulatory scope tests).

### Architecture canary skip
- `tests/arch/test_arch_canary.py` (import-linter skip)
  - Reason: skips when import-linter is not installed or when
    running outside the configured environment.
  - Expiry: P28 (removes redundant arch canary).
