from .resource import Instance, Dataset, OssCredentials, Notebook, Port, Event


class FeaturizeClient:

    def __init__(self, token, instance_id=None):
        self.token = token
        self.instance_id = instance_id

    @property
    def instance(self) -> Instance:
        return self._get_resource(Instance)

    @property
    def event(self) -> Event:
        return self._get_resource(Event)

    @property
    def port(self) -> Port:
        return self._get_resource(Port)

    @property
    def dataset(self) -> Dataset:
        return self._get_resource(Dataset)

    @property
    def oss_credential(self) -> OssCredentials:
        return self._get_resource(OssCredentials)

    @property
    def notebook(self) -> Notebook:
        return self._get_resource(Notebook)

    def _get_resource(self, resource_type):
        resource_name = resource_type.__name__
        if not hasattr(self, resource_name):
            setattr(self, resource_name, resource_type(self.token, self.instance_id))
        return getattr(self, resource_name)
