import sys
from moat.util import NotGiven

from moat.micro.cmd.base import BaseCmd
from moat.micro.cmd.util import enc_part, get_part


class Cmd(BaseCmd):
    """
    Subsystem to handle config data.

    This app serves the config of the parent subcommand.
    """
    def __init__(self, cfg):
        super().__init__(cfg)
        self.repeats = {}

    async def cmd_r(self, p=()):
        """
        Read (part of) the configuration.

        As configuration data are frequently too large to transmit in one
        go, this code interrogates it step-by-step.

        @p is the path. An empty path is the root.

        If the accessed item is a dict, return data consists of a dict
        (simple keys and their values) and a list (keys for complex
        values).

        Same for a list.
        """
        return enc_part(get_part(self._parent.cfg, p))

    async def cmd_w(self, p=(), d=NotGiven):
        """
        Online configuration mangling.

        As configuration data are frequently too large to transmit in one
        go, this code interrogates and updates it step-by-step.

        @p is the path. It cannot be empty. Destinations are
        autogenerated. A path element of ``None``, if last,
        appends to a list.

        @d is the data replacing the destination. ``NotGiven`` (or
        omitting the parameter) deletes.

        There is no way to write the current config to the file system.
        You can use app.fs for this, or you can configure a "safe" skeleton
        setup and update it online after booting.
        """
        cur = self._parent.cfg
        if not p:
            raise ValueError("NoPath")
        for pp in p[:-1]:
            try:
                cur = cur[pp]
            except KeyError:
                cur[pp] = {}
                cur = cur[pp]
            except IndexError as exc:
                if len(cur) != pp:
                    raise exc
                cur.append({})
                cur = cur[pp]
        if d is NotGiven:
            del cur[p[-1]]
        elif isinstance(cur,list) and p[-1] is None:
            cur.append(d)
        else:
            try:
                cur[p[-1]] = d
            except IndexError as exc:
                if len(cur) != p[-1]:
                    raise exc
                cur.append(d)

    async def cmd_x(self):
        """
        Activate the new config.
        """
        await self._parent.update_config()
        return

