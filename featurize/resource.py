import requests


class HTTPCodeError(Exception):

    def __init__(self, code, response):
        super().__init__(f'HTTP request failed with code: {code}, body: {response}')


class ServiceError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f'Error {code}: {message}')


class Resource:

    base = 'https://featurize.cn/bus/api/v1'

    def __init__(self, token):
        self.token = token

    def _http(self, url, method='get', data=None):
        url = f'{self.base}{url}'
        if method in ['get', 'delete', 'head']:
            kwargs = {'params': data}
        else:
            kwargs = {'json': data}
        req = requests.request(
            method,
            url,
            headers={'Token': self.token},
            timeout=10,
            **kwargs)

        if req.status_code != 200:
            raise HTTPCodeError(req.status_code, req.json())

        res = req.json()
        if res['status'] != 0:
            raise ServiceError(res['status'], res['message'])

        return res['data']


class Instance(Resource):

    def __init__(self, token):
        super().__init__(token)

    def list(self):
        return self._http('/available_instances')

    def request(self, instance_id, term=None):
        return self._http(f'/instances/{instance_id}/request', 'post')

    def release(self, instance_id):
        return self._http(f'/instances/{instance_id}/request', 'delete')
