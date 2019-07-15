# command line interface

import os
import sys
import trio_click as click
import time
import anyio
from pprint import pprint
import yaml

from distkv.util import (
    attrdict,
    PathLongener,
    MsgReader,
    PathShortener,
    split_one,
    NotGiven,
)
from distkv.client import open_client, StreamedRequest
from distkv.command import Loader
from distkv.default import CFG
from distkv.server import Server
from distkv.auth import loader, gen_auth
from distkv.exceptions import ClientError, ServerError
from distkv.code import CodeRoot
from distkv.runner import AnyRunnerRoot, SingleRunnerRoot

import logging

logger = logging.getLogger(__name__)


@main.group()
@click.option(
    "-n", "--node", help="node to run this code on. Empty: any one node"
)
@click.pass_obj
async def cli(obj, node):
    """Run code stored in DistKV."""
    obj.node = node


@cli.command()
@click.pass_obj
async def all(obj):
    """
    Run code that needs to run.

    This does not return.
    """
    c = obj.client
    cr = await CodeRoot.as_handler(c)
    if obj.node is None:
        r = await AnyRunnerRoot.as_handler(c, code=cr)
    else:
        r = await SingleRunnerRoot.as_handler(c, code=cr)
    while True:
        await anyio.sleep(99999)

@cli.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print complete results. Default: just the value",
)
@click.option("-s", "--state", is_flag=True, help="Add state data")
@click.option("-S", "--state-only", is_flag=True, help="Show only state data")
@click.option(
    "-d",
    "--as-dict", 
    default=None,
    help="YAML: structure as dictionary. The argument is the key to use "
    "for values. Default: return as list",
)
@click.argument("path", nargs=-1)
@click.pass_obj
async def list(obj, state, state_only, as_dict, verbose, path):
    """List runners.
    """
    if not path:
        path = ()
    if obj.node is None:
        path = obj.cfg['anyrunner'].prefix+path
        if state or state_only:
            state = obj.cfg['anyrunner'].state+path
    else:
        path = obj.cfg['singlerunner'].prefix+(obj.node,)+path
        if state or state_only:
            state = obj.cfg['singlerunner'].state+(obj.node,)+path
    if state_only:
        path = state
        state = None
    res = await obj.client._request(
        action="get_tree",
        path=path,
        iter=True,
        nchain=3 if verbose else 0,
    )

    y = {}
    async for r in res:
        if as_dict is not None:
            yy = y
            for p in r.pop("path"):
                yy = yy.setdefault(p, {})
            yy[as_dict] = r if verbose else r.pop("value")
        else:
            yy = {}
            if verbose:
                yy[r.pop('path')] = r
            else:
                yy[r.path] = r.value
                
        if state:
            rs = await obj.client._request(
                action="get_value",
                path=state,
                iter=False,
                nchain=3 if verbose else 0,
            )
            if 'value' in rs:
                if not verbose:
                    rs = rs.value
                yy['state'] = rs
            else:
                yy['state'] = None
        if as_dict is None:
            print(yaml.safe_dump([yy], default_flow_style=False), file=sys.stdout)

    if as_dict is not None:
        print(yaml.safe_dump(y, default_flow_style=False), file=sys.stdout)


@cli.command()
@click.option("-r", "--result", is_flag=True, help="Just print the actual result.")
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print the complete result. Default: just the value",
)
@click.argument("path", nargs=-1)
@click.pass_obj
async def state(obj, path, verbose, result):
    """Get the status of a runner entry.
    """
    if result and verbose:
        raise click.UsageError("You can't use '-v' and '-r' at the same time.")
    if not path:
        raise click.UsageError("You need a non-empty path.")
    if obj.node is None:
        path = obj.cfg['anyrunner'].state+path
    else:
        path = obj.cfg['singlerunner'].state+(obj.node,)+path

    res = await obj.client._request(
        action="get_value",
        path=path,
        iter=False,
        nchain=3 if verbose else 0,
    )
    if 'value' not in res:
        if obj.debug:
            print("Not found (yet?)", file=sys.stderr)
        sys.exit(1)
    if not verbose:
        res = res.value

    print(yaml.safe_dump(res, default_flow_style=False))


@cli.command()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Print the complete result. Default: just the value",
)
@click.argument("path", nargs=-1)
@click.pass_obj
async def get(obj, path, verbose):
    """Read a runner entry"""
    if not path:
        raise click.UsageError("You need a non-empty path.")
    if obj.node is None:
        path = obj.cfg['anyrunner'].prefix+path
    else:
        path = obj.cfg['singlerunner'].prefix+(obj.node,)+path

    res = await obj.client._request(
        action="get_value",
        path=path,
        iter=False,
        nchain=3 if verbose else 0,
    )
    if not verbose:
        res = res.value

    print(yaml.safe_dump(res, default_flow_style=False))


@cli.command()
@click.option("-c", "--code", help="Path to the code that should run. Space separated path.")
@click.option("-t", "--time", "tm", type=float, help="time the code should next run at")
@click.option("-r", "--repeat", type=int, help="Seconds the code should re-run after")
@click.option("-b", "--backoff", type=float, help="Back-off factor. Default: 1.4")
@click.option("-d", "--delay", type=int, help="Seconds the code should retry after (w/ backoff)")
@click.option(
    "-i", "--info", help="Short human-readable information"
)
@click.option(
    "-e", "--eval", "eval_", help="'code' is a Python expression (must eval to a list)"
)
@click.argument("path", nargs=-1)
@click.pass_obj
async def set(obj, path, code, eval_, tm, info, repeat, delay, backoff):
    """Save / modify a run entry."""
    if not path:
        raise click.UsageError("You need a non-empty path.")
    if eval_:
        code = eval(code)
        if not isinstance(code, (list,tuple)):
            raise click.UsageError("'code' must be a list")
    elif code is not None:
        code = code.split(' ')

    if obj.node is None:
        path = obj.cfg['anyrunner'].prefix+path
    else:
        path = obj.cfg['singlerunner'].prefix+(obj.node,)+path

    try:
        res = await obj.client._request(
            action="get_value",
            path=path,
            iter=False,
            nchain=3,
        )
        if 'value' not in res:
            raise ServerError
    except ServerError:
        if code is None:
            raise click.UsageError("New entry, need code")
        res = {}
        chain = None
    else:
        chain = res['chain']
        res = res['value']

    if code is not None:
        res['code'] = code
    if info is not None:
        res['info'] = info
    if backoff is not None:
        res['backoff'] = backoff
    if delay is not None:
        res['delay'] = delay
    if repeat is not None:
        res['repeat'] = repeat
    if tm is not None:
        res['target'] = time.time() + tm
        
    res = await obj.client._request(
        action="set_value",
        value=res,
        path=path,
        iter=False,
        nchain=3,
        **({"chain":chain} if chain else {})
    )
    print(yaml.safe_dump(res, default_flow_style=False))


