from .resource import Instance, Dataset, OssCredentials, Notebook


class FeaturizeClient:

    def __init__(self, token):
        self.token = token

    @property
    def instance(self) -> Instance:
        if not hasattr(self, '_instance'):
            self._instance = Instance(self.token)
        return self._instance

    @property
    def dataset(self) -> Dataset:
        if not hasattr(self, '_dataset'):
            self._dataset = Dataset(self.token)
        return self._dataset

    @property
    def oss_credential(self) -> OssCredentials:
        if not hasattr(self, '_oss_credential'):
            self._oss_credential = OssCredentials(self.token)
        return self._oss_credential

    @property
    def notebook(self) -> Notebook:
        if not hasattr(self, '_notebook'):
            self._notebook = Notebook(self.token)
        return self._notebook
