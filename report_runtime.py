"""External LimeReport process boundary."""

import os
import subprocess
from pathlib import Path


class ReportProcessError(RuntimeError):
    pass


class LimeReportProcess:
    def __init__(self, executable_directory, popen=subprocess.Popen, opener=os.startfile):
        self.executable = str(Path(executable_directory) / "limereport")
        self.popen = popen
        self.opener = opener

    def command(self, template, output, parameters=None):
        command = [self.executable, "-s{}".format(template), "-d{}".format(output)]
        for name, value in (parameters or {}).items():
            command.append("-p{}={}".format(name, value))
        return command

    def generate(self, template, output, parameters=None):
        process = self.popen(self.command(template, output, parameters))
        return_code = process.wait()
        if return_code not in (None, 0):
            raise ReportProcessError(
                "LimeReport exited with status {}.".format(return_code)
            )
        return Path(output)

    def open_output(self, output):
        self.opener(str(output))

