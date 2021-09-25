import json
from json.decoder import JSONDecodeError
import os
import sys
import uuid

import click
from click.types import Choice
import wcwidth as _  # noqa
from tabulate import tabulate
from pathlib import Path
import hashlib
import oss2
from tqdm import tqdm
import shutil

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
        sys.exit('Token is missed, please see doc: https://docs.featurize.cn/命令行工具')

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

    data = [(instance['id'], instance['name'], instance['gpu'].split(',')[0], instance['unit_price'], instance['status'] == 'online') for instance in data['records']]
    print(tabulate(data, headers=['id', 'name', 'gpu', 'price', 'idle']))


@instance.command()
@click.argument('instance_id')
def request(instance_id):
    try:
        client.instance.request(instance_id)
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


@cli.group()
def notebook():
    pass

@notebook.command()
@click.argument('file')
@click.option('-n', '--name', required=True)
def create(file: str, name: str):
    try:
        response = client.notebook.create(file, name)
    except Exception as e:
        sys.exit(f'Uncaught error {e}')
    print(f'Successfully created public notebook, visit https://featurize.cn/notebooks/{response["digest"]}')


@cli.group()
def dataset():
    pass


@dataset.command()
@click.argument('file')
@click.option('-n', '--name', default='')
@click.option('-r', '--range', type=Choice(['public', 'personal']), default='personal')
@click.option('-d', '--description', default='')
@click.option('-d', '--proxy', is_flag=True, default=False)
def upload(file, name, range, description, proxy):
    if not proxy:
        os.environ['HTTP_PROXY'] = ''
        os.environ['HTTPS_PROXY'] = ''
        os.environ['http_proxy'] = ''
        os.environ['https_proxy'] = ''
    if not (file.endswith(".zip") or file.endswith(".tar.gz")):
        sys.exit('Error: uploading file should be one of .zip or .tar.gz type')
    filepath = Path(file)
    total_size = filepath.stat().st_size
    if not filepath.exists():
        sys.exit('Error: file not exists')
    name = name or filepath.name
    sha1 = hashlib.sha1()
    sha1.update((f"{filepath.name}-{total_size}").encode())
    digest = sha1.hexdigest()
    dataset_file = Path.home() / '.featurize' / f"file_upload_checkpoint_{digest}" / "dataset.json"
    dataset_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        dataset = json.loads(dataset_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        # init dataset
        res = client.dataset.create(name, range, description)
        dataset = {
            'id': res['id'],
            'dataset_center': res['dataset_center'],
            'uploader_id': res['uploader_id'],
            'consumed_bytes': 0
        }
        dataset_file.write_text(json.dumps(dataset))
    credential = client.oss_credential.get()
    auth = oss2.StsAuth(
        credential['AccessKeyId'],
        credential['AccessKeySecret'],
        credential['SecurityToken']
    )
    bucket = oss2.Bucket(auth, 'http://oss-cn-beijing.aliyuncs.com', dataset['dataset_center']['bucket'])

    def progress_callback(consumed_bytes, total_bytes):
        pbar.update(consumed_bytes - pbar.n)
        dataset['consumed_bytes'] = consumed_bytes
        dataset_file.write_text(json.dumps(dataset))

    pbar = tqdm(total=total_size, unit='B', unit_scale=True)
    path = f"{dataset['uploader_id']}_{dataset['id']}/{filepath.name}"
    result = oss2.resumable_upload(
        bucket,
        path,
        filepath.resolve().as_posix(),
        store=oss2.ResumableStore(root='/tmp'),
        multipart_threshold=8 * 1024 * 1024,
        part_size=1024 * 1024 * 1,
        num_threads=1,
        progress_callback=progress_callback
    )

    if result.status != 200:
        sys.exit(f"Error: upload respond with code {result.status}")

    client.dataset.update(
        dataset_id=dataset['id'],
        uploaded=True,
        domain=f"{dataset['dataset_center']['bucket']}.oss-cn-beijing.aliyuncs.com",
        path=path,
        size=total_size,
        filename=filepath.name
    )

    shutil.rmtree(dataset_file.parent)

@dataset.command()
@click.argument('id')
def download(id):
    try:
        id = uuid.UUID(hex=id)
        client.dataset.download(dataset_id=str(id))
    except ValueError:
        sys.exit("Error: id is not valid")
