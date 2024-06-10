# -*- coding: utf-8 -*-
import os
import subprocess
import sys

from setuptools import setup, Command

###################################################################################
#  Legacy package configuration, prefer pyproject.toml over setup.cfg or setup.py #
###################################################################################

here = os.path.abspath(os.path.dirname(__file__))


class BaseCommand(Command):
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print("\033[1m{0}\033[0m".format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def _run(self, s, command):
        try:
            self.status(s + "\n" + " ".join(command))
            subprocess.check_call(command)
        except subprocess.CalledProcessError as error:
            sys.exit(error.returncode)


class CodegenCommand(BaseCommand):
    def run(self):
        header = (
            "# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "#\n"
            "#  *** DO NOT EDIT THIS FILE ***\n"
            "#\n"
            "#  1) Modify slack_sdk/web/client.py\n"
            "#  2) Run `python setup.py codegen`\n"
            "#\n"
            "# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "\n"
        )
        with open(f"{here}/slack_sdk/web/client.py", "r") as original:
            source = original.read()
            import re

            async_source = header + source
            async_source = re.sub("    def ", "    async def ", async_source)
            async_source = re.sub("from asyncio import Future\n", "", async_source)
            async_source = re.sub(r"return self.api_call\(", "return await self.api_call(", async_source)
            async_source = re.sub("-> SlackResponse", "-> AsyncSlackResponse", async_source)
            async_source = re.sub(
                "from .base_client import BaseClient, SlackResponse",
                "from .async_base_client import AsyncBaseClient, AsyncSlackResponse",
                async_source,
            )
            # from slack_sdk import WebClient
            async_source = re.sub(
                r"class WebClient\(BaseClient\):",
                "class AsyncWebClient(AsyncBaseClient):",
                async_source,
            )
            async_source = re.sub(
                "from slack_sdk import WebClient",
                "from slack_sdk.web.async_client import AsyncWebClient",
                async_source,
            )
            async_source = re.sub(r"= WebClient\(", "= AsyncWebClient(", async_source)
            async_source = re.sub(
                r" self.files_getUploadURLExternal\(",
                " await self.files_getUploadURLExternal(",
                async_source,
            )
            async_source = re.sub(
                r" self._upload_file\(",
                " await self._upload_file(",
                async_source,
            )
            async_source = re.sub(
                r" self.files_completeUploadExternal\(",
                " await self.files_completeUploadExternal(",
                async_source,
            )
            async_source = re.sub(
                r" self.files_info\(",
                " await self.files_info(",
                async_source,
            )
            async_source = re.sub(
                "_attach_full_file_metadata",
                "_attach_full_file_metadata_async",
                async_source,
            )
            async_source = re.sub(
                r" _attach_full_file_metadata_async\(",
                " await _attach_full_file_metadata_async(",
                async_source,
            )
            with open(f"{here}/slack_sdk/web/async_client.py", "w") as output:
                output.write(async_source)

            legacy_source = header + "from asyncio import Future\n" + source
            legacy_source = re.sub("-> SlackResponse", "-> Union[Future, SlackResponse]", legacy_source)
            legacy_source = re.sub(
                "from .base_client import BaseClient, SlackResponse",
                "from .legacy_base_client import LegacyBaseClient, SlackResponse",
                legacy_source,
            )
            legacy_source = re.sub(
                r"class WebClient\(BaseClient\):",
                "class LegacyWebClient(LegacyBaseClient):",
                legacy_source,
            )
            legacy_source = re.sub(
                "from slack_sdk import WebClient",
                "from slack_sdk.web.legacy_client import LegacyWebClient",
                legacy_source,
            )
            legacy_source = re.sub(r"= WebClient\(", "= LegacyWebClient(", legacy_source)
            with open(f"{here}/slack_sdk/web/legacy_client.py", "w") as output:
                output.write(legacy_source)

            self._run(
                "Running black (code formatter) ... ",
                [sys.executable, "-m", "black", f"{here}/slack_sdk"],
            )


class ValidateCommand(BaseCommand):
    """Support setup.py validate."""

    description = "Run Python static code analyzer (flake8), formatter (black) and unit tests (pytest)."

    user_options = [("test-target=", "i", "tests/{test-target}")]

    def initialize_options(self):
        self.test_target = ""

    def run(self):
        def run_black(target, target_name=None):
            self._run(
                f"Running black for {target_name or target} ...",
                [sys.executable, "-m", "black", "--check", f"{here}/{target}"],
            )

        run_black("slack", "legacy packages")
        run_black("slack_sdk", "slack_sdk package")
        run_black("tests")
        run_black("integration_tests")

        def run_flake8(target, target_name=None):
            self._run(
                f"Running flake8 for {target_name or target} ...",
                [sys.executable, "-m", "flake8", f"{here}/{target}"],
            )

        run_flake8("slack", "legacy packages")
        run_flake8("slack_sdk", "slack_sdk package")
        # TODO: resolve linting errors for tests
        # run_flake8("tests")
        # run_flake8("integration_tests")

        target = self.test_target.replace("tests/", "", 1)
        self._run(
            "Running unit tests ...",
            [
                sys.executable,
                "-m",
                "pytest",
                "--cov-report=xml",
                f"--cov={here}/slack_sdk",
                f"tests/{target}",
            ],
        )


class UnitTestsCommand(BaseCommand):
    """Support setup.py unit_tests."""

    description = "Run unit tests (pytest)."
    user_options = [("test-target=", "i", "tests/{test-target}")]

    def initialize_options(self):
        self.test_target = ""

    def run(self):
        target = self.test_target.replace("tests/", "", 1)
        self._run(
            "Running unit tests ...",
            [
                sys.executable,
                "-m",
                "pytest",
                f"tests/{target}",
            ],
        )


class IntegrationTestsCommand(BaseCommand):
    """Support setup.py run_integration_tests"""

    description = "Run integration tests (pytest)."

    user_options = [
        ("test-target=", "i", "integration_tests/{test-target}"),
    ]

    def initialize_options(self):
        self.test_target = ""
        self.legacy = ""

    def run(self):
        target = self.test_target.replace("integration_tests/", "", 1)
        path = f"integration_tests/{target}"
        self._run(
            "Running integration tests ...",
            [
                sys.executable,
                "-m",
                "pytest",
                path,
            ],
        )


setup(
    cmdclass={
        "codegen": CodegenCommand,
        "validate": ValidateCommand,
        "unit_tests": UnitTestsCommand,
        "integration_tests": IntegrationTestsCommand,
    },
)
