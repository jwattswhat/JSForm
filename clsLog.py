"""Provide the legacy-compatible JSForm diagnostic logger."""

import sys
import pprint
import datetime
import os
from pathlib import Path

import JSForm


def default_log_path(application_name=None, environment=None, executable=None):
    """Return a user-writable path for the legacy diagnostic log."""

    environment = os.environ if environment is None else environment
    if application_name is None:
        executable = Path(sys.executable if executable is None else executable)
        application_name = executable.stem if getattr(sys, "frozen", False) else "JSForm"
    safe_name = "".join(
        character for character in str(application_name) if character.isalnum() or character in "-_ "
    ).strip() or "JSForm"
    local_app_data = environment.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / safe_name / "Logs" / "Log.txt"

class clsLog:
    def __init__(self, logfile=None) -> None:
        self.logfile = Path(logfile) if logfile is not None else default_log_path()
        self.lf = None

    def _open(self):
        """Open the diagnostic file lazily without breaking application startup."""

        if self.lf is not None:
            return True
        try:
            self.logfile.parent.mkdir(parents=True, exist_ok=True)
            self.lf = self.logfile.open("w", encoding="utf-8")
        except OSError:
            return False
        now = datetime.datetime.now()
        self.lf.write(now.strftime(("%Y-%m-%d %H:%M:%S")))
        self.lf.write("\n\n")
        return True

    def log(self, **param):
        if cmLOG == True and self._open():
            caller = sys._getframe(2).f_code.co_name
            if caller == "<module>":
                caller = "__main__"
            funcname = sys._getframe(1).f_code.co_name
            self.lf.write("\n")
            self.lf.write(
                "Caller <{caller}>: Module <{funcname}>\n".format(
                    caller=caller, funcname=funcname
                )
            )
            if cmLOGPARAM == True:
                if len(param) != 0:
                    self.lf.write("Parameters\n")
                    for p in param:
                        self.lf.write("\t{p}\t{ty}\t".format(p=p, ty=type(param[p])))
                        pprint.pprint(param[p], stream=self.lf)

    def close(self):
        if self.lf is not None:
            self.lf.close()
            self.lf = None


cmLOG = False
cmLOGPARAM = False
LG = clsLog()
