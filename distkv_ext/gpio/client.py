# command line interface

import sys
import trio
import asyncclick as click
from functools import partial
from collections.abc import Mapping

from distkv.exceptions import ClientError
from distkv.util import yprint, attrdict, combine_dict, data_get, NotGiven, path_eval
from distkv.util import res_delete, res_get, res_update

import logging

logger = logging.getLogger(__name__)

@main.group(short_help="Manage GPIO controllers.")  # pylint: disable=undefined-variable
@click.pass_obj
async def cli(obj):
    """
    List GPIO controllers, modify device handling …
    """
    pass


@cli.command()
@click.argument("path", nargs=-1)
@click.pass_obj
async def dump(obj, path):
    """Emit the current state as a YAML file.
    """
    res = {}
    if len(path) > 4:
        raise click.UsageError("Only up to four path elements allowed")

    async for r in obj.client.get_tree(*obj.cfg.gpio.prefix, *path_eval(path, (3,4)), nchain=obj.meta, max_depth=4-len(path)):
        pl = len(path) + len(r.path)
        rr = res
        if r.path:
            for rp in r.path:
                rr = rr.setdefault(rp,{})
        rr['_'] = r if obj.meta else r.value
    yprint(res, stream=obj.stdout)


@cli.command()
@click.argument("path", nargs=-1)
@click.pass_obj
async def list(obj, path):
    """List the next stage.
    """
    res = {}
    if len(path) > 4:
        raise click.UsageError("Only up to four path elements allowed")

    res = await obj.client._request(action="enumerate", path=(*obj.cfg.gpio.prefix, *path_eval(path, (3,4))), empty=True)
    for r in res.result:
        print(r, file=obj.stdout)


@cli.command('attr')
@click.option("-a","--attr", multiple=True, help="Attribute to list or modify.")
@click.option("-v","--value",help="New value of the attribute.")
@click.option("-e", "--eval", "eval_", is_flag=True, help="The value shall be evaluated.")
@click.option("-s", "--split", is_flag=True, help="The value shall be word-split.")
@click.argument("path", nargs=-1)
@click.pass_obj
async def attr_(obj, attr, value, path, eval_, split):
    """Set/get/delete an attribute on a given GPIO element.

    `--eval` without a value deletes the attribute.
    """
    if split and eval_:
        raise click.UsageError("split and eval don't work together.")
    if value and not attr:
        raise click.UsageError("Values must have locations ('-a ATTR').")
    if split:
        value = value.split()
    await _attr(obj, attr, value, path, eval_)

@cli.command()
@click.option("-t", "--type", "typ", help="Port type. 'input' or 'output'.")
@click.option("-m", "--mode", help="Port mode. Use '-' to disable.")
@click.option("-a", "--attr", nargs=2, multiple=True, help="One attribute to set (NAME VALUE). May be used multiple times.")
@click.argument("path", nargs=-1)
@click.pass_obj
async def port(obj, path, typ, mode, attr):
    """Set/get/delete port settings. This is a shortcut for the "attr" command.

    \b
    Known attributes for types+modes:
      input:
        read: dest (path)
        count: read + interval (float), count (+-x for up/down/both)
        button: read + t_bounce (float), t_idle (float), skip (+- ignore noise?)
      output:
        write: src (path), state (path)
        oneshot: write + t_on (float), state (path)
        pulse:   oneshot + t_off (float)
      *:
        low: bool (signals are active-low if true)

    \b
    Paths elements are separated by spaces.
    "low" is the state of the wire when the input is False.
    Floats may be paths, in which case they're read from there when starting.
    """
    if len(path) != 3:
        raise click.UsageError("Path must be 3 elements: host gpioname linenr")
    res = await obj.client.get(*obj.cfg.gpio.prefix, *path_eval(path, (3,)), nchain=obj.meta or 1)
    val = res.get('value', attrdict())

    if type:
        attr = (('type', typ),) + attr
    if mode:
        attr = (('mode', mode),) + attr
    for k,v in attr:
        if k == "count":
            if v == '+':
                v = True
            elif v == '-':
                v = False
            elif v in 'xX*':
                v = None
            else:
                v = click.UsageError("'count' wants one of + - X")
        elif k in ("low","skip"):
            if v == '+':
                v = True
            elif v == '-':
                v = False
            else:
                v = click.UsageError("'low' wants one of + -")
        elif k in {"src", "dest"} or ' ' in v:
            v = v.split()
        else:
            try:
                v = int(v)
            except ValueError:
                try:
                    v = float(v)
                except ValueError:
                    pass
        if isinstance(v,click.UsageError):
            raise v
        val[k] = v

    await _attr(obj, (), val, path, False, res)

async def _attr(obj, attr, value, path, eval_, res=None):
    # Sub-attr setter.
    # Special: if eval_ is True, a value of '-' deletes. A mapping replaces instead of updating.
    if res is None:
        res = await obj.client.get(*obj.cfg.gpio.prefix, *path_eval(path, (3,4)), nchain=obj.meta or (value is not None))
    try:
        val = res.value
    except AttributeError:
        res.chain = None
    if eval_:
        if value is None:
            value = res_delete(res, *attr)
        else:
            value = eval(value)
            if isinstance(value, Mapping):
                # replace
                value = res_delete(res, *attr)
                value = value._update(*attr, value=value)
            else:
                value = res_update(res, *attr, value=value)
    else:
        if value is None:
            if not attr and obj.meta:
                val = res
            else:
                val = res_get(res, *attr)
            yprint(val, stream=obj.stdout)
            return
        value = res_update(res, *attr, value=value)
    res = await obj.client.set(*obj.cfg.gpio.prefix, *path_eval(path, (3,4)), value=value, nchain=obj.meta, chain=res.chain)
    if obj.meta:
        yprint(res, stream=obj.stdout)


@cli.command()
@click.argument("name", nargs=1)
@click.argument("controller", nargs=-1)
@click.pass_obj
async def monitor(obj, name):
    """Stand-alone task to monitor a single contoller.

    The first argument must be the local host name.
    """
    from distkv_ext.gpio.task import task
    from distkv_ext.gpio.model import GPIOroot
    server = await GPIOroot.as_handler(obj.client)
    await server.wait_loaded()
    sub = server[name]
    if controller:
        sub = (sub[x] for x in controller)
    async with trio.open_nursery() as n:
        for chip in sub:
            n.start_soon(task, obj.client, obj.cfg.gpio, chip, None)

