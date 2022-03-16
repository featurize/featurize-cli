import json
from json.decoder import JSONDecodeError
import os
import sys
import uuid

import click
from click.types import Choice
from featurize import create_client_from_env
import wcwidth as _  # noqa
from tabulate import tabulate
from pathlib import Path
import hashlib
import oss2
from tqdm import tqdm
import shutil

from .featurize_client import FeaturizeClient
from .resource import ServiceError

client : FeaturizeClient = None


@click.group()
@click.option('-t', '--token', required=False,
              help='Your api token')
def cli(token=None):
    global client
    client = create_client_from_env()


@cli.group()
def event():
    pass


@event.command()
@click.option("-t", "--title", required=True)
@click.option("-c", "--content", required=True)
def create(title, content):
    client.event.create(title, content)


@cli.group()
def instance():
    pass


@instance.command()
def release():
    client.instance.release()


@cli.group()
def port():
    pass


@port.command()
@click.option("-f", "--format", default="tabulate")
def list(format):
    ports = client.port.list()
    if format == "tabulate":
        print(tabulate(ports, headers=("本地端口", "外部端口"), tablefmt='grid'))
    elif format == "json":
        print(json.dumps(ports))


@port.command()
@click.argument("local_port")
@click.option("-r", "--raw", is_flag=True, default=False)
def export(local_port, raw):
    new_port = client.port.create(local_port)
    if raw:
        print(new_port, end="")
    else:
        print(f"Local port {local_port} has been exported to {new_port}")
        print(f"You can visit http://workspace.featurize.cn:{new_port} if it's a http server")


@port.command()
@click.argument("local_port")
def unexport(local_port):
    client.port.destroy(local_port)
    print("done")


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
        os.environ['ALL_PROXY'] = ''
        os.environ['https_proxy'] = ''
        os.environ['http_proxy'] = ''
        os.environ['all_proxy'] = ''
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
