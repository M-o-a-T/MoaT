"""
App and command base classes
"""
from moat.micro.cmd.base import BaseCmd


class ConfigError(RuntimeError):
    "generic config error exception"
    pass  # pylint:disable=unnecessary-pass


class BaseAppCmd(BaseCmd):
    "App-specific command"

    def __init__(self, parent, name, cfg, gcfg):
        super().__init__(parent)
        self.name = name
        self.cfg = cfg
        self.gcfg = gcfg
