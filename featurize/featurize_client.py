from .resource import Instance


class FeaturizeClient:

    def __init__(self, token):
        self.token = token

    @property
    def instance(self):
        if not hasattr(self, '_instance'):
            self._instance = Instance(self.token)
        return self._instance
