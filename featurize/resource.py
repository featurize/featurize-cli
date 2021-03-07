import requests


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

    def __init__(self, token: str):
        self.token = token

    def _http(self, url: str, method: str = 'get', data: dict = None) -> requests.Response:
        url = f'{self.base}{url}'
        if method in ['get', 'delete', 'head']:
            kwargs = {'params': data}
        else:
            kwargs = {'json': data}
        req = requests.request(
            method,
            url,
            headers={'Token': self.token},
            timeout=30,
            **kwargs)

        if req.status_code != 200:
            raise HTTPCodeError(req.status_code, req.json())

        res = req.json()
        if res['status'] != 0:
            raise ServiceError(res['status'], res['message'])

        return res['data']


class Instance(Resource):

    def list(self) -> dict:
        return self._http('/available_instances')

    def request(self, instance_id: str) -> dict:
        return self._http(f'/instances/{instance_id}/request', 'post')

    def release(self, instance_id: str) -> dict:
        return self._http(f'/instances/{instance_id}/request', 'delete')


class Dataset(Resource):

    def create(self, name: str, range: str = 'private', description: str = '') -> dict:
        return self._http(f'/datasets/', 'post', {
            'name': name,
            'description': description,
            'range': range
        })

    def update(self, dataset_id: str, **kwargs) -> dict:
        return self._http(f'/datasets/{dataset_id}', 'patch', kwargs)


class OssCredentials(Resource):

    def get(self) -> dict:
        return self._http(f'/oss_credentials')
