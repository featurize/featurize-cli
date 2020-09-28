import json
from json.decoder import JSONDecodeError
import os
import sys

import click
import wcwidth as _  # noqa
from tabulate import tabulate

from .featurize_client import FeaturizeClient
from .resource import ServiceError

client = None


def _find_token():
    token_from_env = os.getenv('FEATURIZE_API_TOKEN')
    cfg_file = os.getenv('FEATURIZE_CFG_FILE', os.path.join(os.getenv('HOME'), '.featurize.json'))
    if token_from_env:
        return token_from_env

    try:
        with open(cfg_file, 'r') as f:
            cfg = json.load(f)
        return cfg.get('token')
    except FileNotFoundError:
        return None
    except JSONDecodeError:
        sys.exit(f'config file {cfg_file} parse error')


@click.group()
@click.option('-t', '--token', required=False,
              help='Your api token')
def cli(token=None):
    global client
    _token = token or _find_token()
    if _token is None:
        sys.exit('Token is missed')

    client = FeaturizeClient(token=_token)


@cli.group()
def instance():
    pass


@instance.command()
@click.option('-r', '--raw', is_flag=True, default=False,
              help='Return raw data')
def ls(raw=False):
    data = client.instance.list()
    if raw:
        return print(json.dumps(data))

    data = [(instance['id'], instance['name'], instance['gpu'].split(',')[0], instance['unit_price'], instance['status'] == 'online') for instance in data]
    print(tabulate(data, headers=['id', 'name', 'gpu', 'price', 'idle']))


@instance.command()
@click.argument('instance_id')
@click.option('-t', '--term', type=click.Choice(['daily', 'weekly', 'monthly'], case_sensitive=False))
def request(instance_id, term):
    try:
        client.instance.request(instance_id, term)
    except ServiceError as e:
        if e.code == 10015:
            sys.exit('Error: requested instance is busy.')
        elif e.code == 10001:
            sys.exit('Error: not enough balance.')
        elif e.code == 10013:
            sys.exit('Error: you can only request P106 or 1660 instances before charging')
        else:
            raise e
    print('Successfully requested instance.')


@instance.command()
@click.argument('instance_id')
def release(instance_id):
    try:
        client.instance.release(instance_id)
    except ServiceError as e:
        if e.code == 10017:
            sys.exit('Error: released instance is not busy.')
        elif e.code == 10014:
            sys.exit('Error: no need to release long term occupied instance.')
        else:
            raise e
    print('Successfully released instance.')
