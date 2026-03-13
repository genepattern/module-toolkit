"""Unit tests for agents.error_classifier."""

import unittest
from agents.error_classifier import classify_error, should_escalate, RootCause


class TestClassifyError(unittest.TestCase):
    """Verify that each error pattern maps to the correct target artifact."""

    # =====================================================================
    # WRAPPER ESCALATION — structural / logic errors in the wrapper
    # These SHOULD escalate when the failing artifact is 'dockerfile'.
    # =====================================================================

    def test_python_syntax_error(self):
        error = "SyntaxError: invalid syntax (wrapper.py, line 42)"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "wrapper")
        self.assertTrue(should_escalate(rc))

    def test_arguments_required(self):
        error = "error: the following arguments are required: --input-file, --output-dir"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "wrapper")
        self.assertIn("--input-file", rc.reason)
        self.assertTrue(should_escalate(rc))

    def test_unrecognized_arguments(self):
        error = "error: unrecognized arguments: --foo --bar"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "wrapper")
        self.assertIn("--foo", rc.reason)
        self.assertTrue(should_escalate(rc))

    def test_argument_error(self):
        error = "error: argument --threads: invalid int value: 'abc'"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "wrapper")
        self.assertTrue(should_escalate(rc))

    # -- R wrapper structural / logic errors ---------------------------------

    def test_r_object_not_found(self):
        error = "Error in eval(expr): object 'my_data' not found"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "wrapper")
        self.assertIn("my_data", rc.reason)
        self.assertTrue(should_escalate(rc))

    def test_r_unexpected_symbol(self):
        error = "Error: unexpected symbol in \"some_function(x y\""
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "wrapper")
        self.assertTrue(should_escalate(rc))

    def test_r_unexpected_string_constant(self):
        error = 'Error: unexpected string constant in "x \"hello\""'
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "wrapper")

    def test_r_unexpected_bracket(self):
        error = "Error: unexpected ')' in \"func(x, y))\""
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "wrapper")

    def test_r_could_not_find_function(self):
        error = "Error in some_call() : could not find function \"process_data\""
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "wrapper")
        self.assertIn("process_data", rc.reason)

    def test_r_optparse_unknown_flag(self):
        error = "Error in getopt(spec = spec, opt = args) : unknown flag '--bad-flag'"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "wrapper")
        self.assertTrue(should_escalate(rc))

    # =====================================================================
    # DOCKERFILE — missing packages / build errors (NO escalation)
    # These should NOT escalate; the Dockerfile itself needs fixing.
    # =====================================================================

    # -- Python missing-package errors (fix with pip install) ----------------

    def test_module_not_found_error(self):
        """ModuleNotFoundError means the Dockerfile needs pip install, NOT
        that the wrapper should stop importing the module."""
        error = "ModuleNotFoundError: No module named 'pandas'"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")
        self.assertIn("pandas", rc.reason)
        self.assertFalse(should_escalate(rc))

    def test_import_error_cannot_import_name(self):
        error = "ImportError: cannot import name 'foo' from 'bar'"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")
        self.assertFalse(should_escalate(rc))

    def test_import_error_shared_library(self):
        """Missing .so file is a system-library issue, fix with apt-get."""
        error = "ImportError: libsomething.so not found"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")
        self.assertFalse(should_escalate(rc))

    # -- R missing-package errors (fix with install.packages) ----------------

    def test_r_no_package_called(self):
        """Missing R package → fix in Dockerfile, not wrapper."""
        error = "Error: there is no package called 'DESeq2'"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")
        self.assertIn("DESeq2", rc.reason)
        self.assertFalse(should_escalate(rc))

    def test_r_error_in_library(self):
        """library() failure → install the package in the Dockerfile."""
        error = "Error in library(ggplot2) : there is no package called 'ggplot2'"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")
        self.assertFalse(should_escalate(rc))

    def test_r_load_namespace_error(self):
        error = "Error in loadNamespace(name) : there is no package called 'Seurat'"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")
        self.assertIn("Seurat", rc.reason)

    def test_r_package_install_failed(self):
        error = "Installation of package 'GenomicRanges' had non-zero exit status"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")
        self.assertIn("GenomicRanges", rc.reason)

    def test_r_source_file_not_found(self):
        error = "Error in source('helper.R') : file 'helper.R' not found"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")

    def test_r_cannot_open_connection(self):
        error = "Error in file(filename, 'r') : cannot open connection\nIn addition: Warning message:\ncannot open file '/data/input.csv': No such file or directory"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")

    # -- apt / system package errors -----------------------------------------

    def test_apt_unable_to_locate(self):
        error = "E: Unable to locate package libfoo-dev"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")
        self.assertFalse(should_escalate(rc))

    def test_apt_no_installation_candidate(self):
        error = "E: Package 'libbar' has no installation candidate"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")

    def test_pip_no_matching_distribution(self):
        error = "pip: No matching distribution found for nonexistent-pkg"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")

    def test_shared_library_loading_error(self):
        error = "error while loading shared libraries: libhdf5.so.10: cannot open shared object file"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")
        self.assertIn("libhdf5.so.10", rc.reason)

    def test_cannot_open_shared_object(self):
        error = "libcurl.so: cannot open shared object file: No such file"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")

    # -- Dockerfile build / syntax errors ------------------------------------

    def test_unexpected_end_of_statement(self):
        error = 'failed to solve: unexpected end of statement'
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")

    def test_command_not_found(self):
        error = "bash: samtools: command not found"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")

    def test_executor_failed(self):
        error = "executor failed running [/bin/sh -c make install]"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")

    def test_wrapper_file_not_found(self):
        error = "python: can't open file '/module/wrapper.py': No such file or directory"
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")

    # =====================================================================
    # Edge cases
    # =====================================================================

    def test_empty_error_returns_none(self):
        rc = classify_error("", "dockerfile")
        self.assertIsNone(rc)

    def test_unrecognised_error_returns_none(self):
        rc = classify_error("Something completely random happened", "dockerfile")
        self.assertIsNone(rc)

    def test_should_escalate_none(self):
        self.assertFalse(should_escalate(None))

    def test_should_escalate_same_artifact(self):
        rc = RootCause(
            target_artifact="dockerfile",
            reason="some reason",
            original_artifact="dockerfile",
        )
        self.assertFalse(should_escalate(rc))

    def test_should_escalate_different_artifact(self):
        rc = RootCause(
            target_artifact="wrapper",
            reason="some reason",
            original_artifact="dockerfile",
        )
        self.assertTrue(should_escalate(rc))

    def test_multiline_error_wrapper_escalation(self):
        """When multiple errors are present, the first matching rule wins."""
        error = (
            "Some irrelevant log line\n"
            "Another log line\n"
            "error: the following arguments are required: --input\n"
            "ModuleNotFoundError: No module named 'scipy'\n"
        )
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        # argparse error comes first in rules → wrapper
        self.assertEqual(rc.target_artifact, "wrapper")
        self.assertIn("--input", rc.reason)

    def test_multiline_error_dockerfile_only(self):
        """When all errors are Dockerfile-level, no escalation."""
        error = (
            "ModuleNotFoundError: No module named 'scipy'\n"
            "E: Unable to locate package libx11\n"
        )
        rc = classify_error(error, "dockerfile")
        self.assertIsNotNone(rc)
        self.assertEqual(rc.target_artifact, "dockerfile")
        self.assertFalse(should_escalate(rc))


if __name__ == "__main__":
    unittest.main()

