import hashlib
from json.decoder import JSONDecodeError
import requests
import logging
from pathlib import Path
import json
import os
from tqdm import tqdm

logger = logging.getLogger(__file__)


def to_camel_case(snake_str: str) -> str:
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def extract(source, dest):
    out = os.system(f'unzip -o "{source}" -d {dest} >> ~/.server.log 2>&1 ')
    if out == 0:
        return 0

    out = os.system(f'tar -zxf "{source}" -C {dest} >> ~/.server.log 2>&1')
    if out == 0:
        return 0

    out = os.system(f'tar -xf "{source}" -C {dest} >> ~/.server.log 2>&1')
    return out


class HTTPCodeError(Exception):

    def __init__(self, code: str, response: requests.Response):
        super().__init__(f'HTTP request failed with code: {code}, body: {response}')


class ServiceError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f'Error {code}: {message}')


class Resource:

    base = 'https://featurize.cn/bus/api/v1'
    # base = 'http://dev.featurize.ai:7777/bus/api/v1'

    def __init__(self, token: str):
        self.token = token

    def _http(self, url: str, method: str = 'get', data: dict = None, headers: dict = {}, **kwargs) -> requests.Response:
        url = f'{self.base}{url}'
        if method in ['get', 'delete', 'head']:
            kwargs = {
                'params': data,
                **kwargs
            }
        else:
            kwargs = {
                'json': data,
                **kwargs
            }
        req = requests.request(
            method,
            url,
            headers={'Token': self.token, **headers},
            timeout=30,
            **kwargs)

        if req.status_code != 200:
            raise HTTPCodeError(req.status_code, req.json())

        res = req.json()
        if res['status'] != 0:
            raise ServiceError(res['status'], res['message'])

        return res['data']

    @property
    def cache_dir(self) -> Path:
        from_env = os.getenv('FEATURIZE_CACHE_DIR')
        path = Path(from_env) if from_env else (Path.home() / '.featurize')
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        return path

    def cache_file(self, name: str) -> Path:
        file_path = self.cache_dir / name
        return file_path


class Instance(Resource):

    def list(self) -> dict:
        return self._http('/available_instances')

    def request(self, instance_id: str) -> dict:
        return self._http(f'/instances/{instance_id}/request', 'post')

    def release(self, instance_id: str) -> dict:
        return self._http(f'/instances/{instance_id}/request', 'delete')


class Notebook(Resource):

    def create(self, file: str, name: str):
        # check cache file, if exists create version instead of notebook
        s = hashlib.sha1()
        s.update(file.encode())
        cache_file_name = f"notebook.{s.hexdigest()}.json"
        cache_file = self.cache_file(cache_file_name)
        upload_files = {'file': open(file, 'rb')}
        try:
            notebook_id = json.loads(cache_file.read_text())["id"]
            response = self._http(f'/notebooks/{notebook_id}/version', 'POST', params={'name': name}, files=upload_files)
        except (JSONDecodeError, FileNotFoundError, KeyError):
            response = self._http('/notebooks', 'POST', params={'name': name}, files=upload_files)
        self.cache_file(cache_file_name).write_text(json.dumps(response))
        return response


class Dataset(Resource):

    def create(self, name: str, range: str = 'private', description: str = '') -> dict:
        return self._http(f'/datasets/', 'post', {
            'name': name,
            'description': description,
            'range': range
        })

    def update(self, dataset_id: str, **kwargs) -> dict:
        return self._http(f'/datasets/{dataset_id}', 'patch', kwargs)

    def download(self, dataset_id: str):
        dataset = self._http(f'/datasets/{dataset_id}')
        if not dataset['uploaded']:
            raise RuntimeError('Dataset uploaded')
        if dataset['cache_progress'] != 100:
            raise RuntimeError('Dataset is not synced yet, please try later')

        path = dataset['path']
        chunk_size = 1024 * 1024 * 4
        dataset_dir = Path.home() / 'data'
        dataset_dir.mkdir(parents=True, exist_ok=True)
        dataset_file = dataset_dir / dataset['path'].split('/')[-1]
        url = f'http://{dataset["cache"][os.getenv("INSTANCE_REGION")]}/{dataset["path"]}'

        with requests.get(url, stream=True, proxies={"http": "", "https": ""}) as resp:
            resp.raise_for_status()
            file_size = int(resp.headers['content-length'])
            progress_bar = tqdm(total=file_size, unit='iB', unit_scale=True)
            with open(dataset_file, 'wb') as data_fd:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    progress_bar.update(len(chunk))
                    data_fd.write(chunk)
            progress_bar.close()
        print("🍬  下载完成，正在解压...")
        result = extract(dataset_file.resolve().as_posix(), dataset_dir.resolve().as_posix())
        if result != 0:
            print("🐛  解压失败，请尝试手动解压或查看文件完整性")
        else:
            print("🏁  数据集已经成功添加")


class OssCredentials(Resource):

    def get(self) -> dict:
        return self._http(f'/oss_credentials')
