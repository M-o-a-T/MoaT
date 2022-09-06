# command line interface

import os
import sys

import anyio
import json
import socket

from moat.util import yload
from .client import open_mqttclient, ConnectException, _codecs
from .version import get_version

import asyncclick as click

import logging
logger = logging.getLogger(__name__)


@click.group(short_help="MQTT client and broker")
@click.pass_obj
async def cli(obj):
	"""
	Run MQTT commands
	"""
	pass


import logging
import anyio
import os
from contextlib import AsyncExitStack
import asyncclick as click
from .broker import create_broker
from .utils import read_yaml_config
from asyncscope import main_scope


logger = logging.getLogger(__name__)


@cli.command()
@click.pass_obj
async def broker(obj):
	"""
	A basic MQTT broker that supports plug-ins and can use distkv as backend.
	"""
	try:
		from moat.util import as_service
	except ImportError:
		as_service = None

	async with AsyncExitStack() as stack:
		await stack.enter_async_context(main_scope())
		await stack.enter_async_context(create_broker(obj.cfg.mqtt.broker))
		if as_service is not None:
			evt = await stack.enter_async_context(as_service())
			evt.set()
		while True:
			await anyio.sleep(99999)



def _gen_client_id():
	pid = os.getpid()
	hostname = socket.gethostname()
	return "moat_mqtt_pub/%d-%s" % (pid, hostname)


def _get_qos(args, cfg):
	res = args["qos"]
	if res is None:
		return cfg.default_qos


def _get_extra_headers(args, cfg):
	if args["extra_headers"]:
		hdrs = yload(args["extra_headers"])
		return combine_dict(hdrs, cfg.extra_headers)
	else:
		return cfg.extra_headers


def _get_message(args):
	codec = args["codec"] or "utf8"
	codec = _codecs[codec]()

	for m in args["msg"]:
		yield m.encode(encoding="utf-8")
	for m in args["msg_eval"]:
		yield codec.encode(eval(m))  # pylint: disable=eval-used
	if args["msg_lines"]:
		with open(args["msg_lines"], "r") as f:
			for line in f:
				yield line.encode(encoding="utf-8")
	if args["msg_stdin_lines"]:
		for line in sys.stdin:
			if line:
				yield line.encode(encoding="utf-8")
	if args["msg_stdin"]:
		yield sys.stdin.buffer.read()
	if args["msg_stdin_eval"]:
		message = sys.stdin.read()
		yield codec.encode(eval(message))  # pylint: disable=eval-used


async def do_pub(client, args, cfg):
	logger.info("%s Connecting to broker", client.client_id)

	await client.connect(
		uri=args["url"] or cfg.url,
		cleansession=args["clean_session"],
		cafile=args["ca_file"] or cfg.ca.file,
		capath=args["ca_path"] or cfg.ca.path,
		cadata=args["ca_data"] or cfg.ca.data,
		extra_headers=_get_extra_headers(args, cfg),
	)
	try:
		qos = _get_qos(args, cfg)
		topic = args["topic"]
		retain = args["retain"]
		async with anyio.create_task_group() as tg:
			for message in _get_message(args):
				logger.info("%s Publishing to '%s'", client.client_id, topic)
				tg.start_soon(client.publish, topic, message, qos, retain)
		logger.info("%s Disconnected from broker", client.client_id)
	except KeyboardInterrupt:
		logger.info("%s Disconnected from broker", client.client_id)
	except ConnectException as ce:
		logger.fatal("connection to '%s' failed: %r", url, ce)
	finally:
		with anyio.fail_after(2, shield=True):
			await client.disconnect()

def fix_will(args, cfg):
	if args["will_topic"] and args["will_message"]:
		will = attrdict()
		will.topic = arguments["will_topic"]
		will.message = args["will_message"]
		will.qos = args["will_qos"]
		if will.qos is None:
			will.qos = cfg.will.qos
		will.retain = args["will_retain"]
		cfg.will = will
	if isinstance(cfg.will.message, str):
		cfg.will.message = cfg.will.message.encode("utf-8")

@cli.command()
@click.option("--url", help="Broker connection URL (musr conform to MQTT URI scheme")
@click.option("-i", "--client_id", help="string to use as client ID")
@click.option("-q","--qos", type=click.IntRange(0,2), help="Quality of service to use (0-2)")
@click.option("-r","--retain", is_flag=True, help="Set the Retain flag")
@click.option("-t","--topic", required=True, help="Message topic, '/'-separated")
@click.option("-m","--msg", multiple=True, help="Message data (may be repeated)")
@click.option("-M","--msg-eval", multiple=True, help="Message data (Python, evaluated, may be repeated)")
@click.option("-f","--msg-lines", type=click.File("r"), help="File with messages (each line sent separately")
@click.option("-R","--msg-stdin", is_flag=True, help="Single message from stdin")
@click.option("-s","--msg-stdin-lines", is_flag=True, help="Messages from stdin (each line sent separately")
@click.option("-S","--msg-stdin-eval", is_flag=True, help="Python code that evaluates to the message on stdin")
@click.option("-C","--codec", help="Message codec (default UTF-8)")
@click.option("-k","--keep-alive", type=float, help="Keep-alive timeout (seconds)")
@click.option("--clean-session", is_flag=True, help="Clean session on connect?")
@click.option("--ca-file", help="CA file")
@click.option("--ca-path", help="CA path")
@click.option("--ca-data", help="CA data")
@click.option("--will-topic", help="Topic to send to, when client exits")
@click.option("--will-message", help="Message to send, when client exits")
@click.option("--will-qos", type=int, help="QOS for Will message")
@click.option("--will-retain", is_flag=True, help="Retain Will message?")
@click.option("--extra-headers", type=click.File("r"), help="File to read extra MQTT headers from")
@click.pass_obj
async def pub(obj, **args):
	"""Publish one or more MQTT messages"""
	if args["msg_stdin"]+args["msg_stdin_lines"]+args["msg_stdin_eval"] > 1:
		raise click.UsageError("You can only read from stdin once")
	cfg = obj.cfg.mqtt.client
	client_id = args.get("client_id", cfg.get("id",None))
	if not client_id:
		client_id = _gen_client_id()

	if args["keep_alive"]:
		config["keep_alive"] = args["keep_alive"]

	fix_will(args, cfg)
	cfg.codec = "noop"

	async with open_mqttclient(client_id=client_id, config=cfg) as C:
		await do_pub(C, args, cfg)


async def do_sub(client, args, cfg):

	try:
		await client.connect(
			uri=args.get("url",None) or cfg.url,
			cleansession=args("clean_session"),
			cafile=args("ca_file", None) or cfg.ca.file,
			capath=args("ca_path", None) or cfg.ca.path,
			cadata=args("ca_data", None) or cfg.ca.data,
			extra_headers=_get_extra_headers(args, cfg),
		)
		async with anyio.create_task_group() as tg:
			for topic in args["topic"]:
				tg.start_soon(run_sub, client, topic, arguments)

	except KeyboardInterrupt:
		pass
	except ConnectException as ce:
		logger.fatal("connection to '%s' failed: %r", args["url"], ce)
	finally:
		with anyio.fail_after(2, shield=True):
			await client.disconnect()


async def run_sub(client, topic, args, cfg):
	qos = _get_qos(args, cfg)
	max_count = args["n_msg"]
	count = 0

	async with client.subscription(topic, qos) as sub:
		async for message in sub:
			count += 1
			print(message.topic, message.data, sep="\t")
			if max_count and count >= max_count:
				break


@cli.command()
@click.option("--url", help="Broker connection URL (musr conform to MQTT URI scheme")
@click.option("-i", "--client_id", help="string to use as client ID")
@click.option("-q","--qos", type=click.IntRange(0,2), help="Quality of service to use (0-2)")
@click.option("-r","--retain", is_flag=True, help="Set the Retain flag")
@click.option("-t","--topic", multiple=True, help="Message topic, '/'-separated (can be used more than once)")
@click.option("-n","--n_msg", type=int, default=0, help="Number of messages to read (per topic)")
@click.option("-C","--codec", help="Message codec (default UTF-8)")
@click.option("-k","--keep-alive", type=float, help="Keep-alive timeout (seconds)")
@click.option("--clean-session", is_flag=True, help="Clean session on connect?")
@click.option("--ca-file", help="CA file")
@click.option("--ca-path", help="CA path")
@click.option("--ca-data", help="CA data")
@click.option("--will-topic", help="Topic to send to, when client exits")
@click.option("--will-message", help="Message to send, when client exits")
@click.option("--will-qos", type=int, help="QOS for Will message")
@click.option("--will-retain", is_flag=True, help="Retain Will message?")
@click.pass_obj
async def sub(obj, args):
	"""Subscribe to one or more MQTT topics"""
	cfg = obj.cfg.mqtt.client

	client_id = args["client_id"]
	if not client_id:
		client_id = _gen_client_id()

	if args["keep_alive"]:
		cfg["keep_alive"] = args["keep_alive"]

	fix_will(args, cfg)

	async with open_mqttclient(client_id=client_id, config=config, codec=args["codec"]) as C:
		await do_sub(C, arguments)

