from kubevirt import KubeVirtClient


class KubeVirtObjectWrapper(object):
    def __init__(self, obj):
        self.o = obj

    @property
    def name(self):
        return self.o.get('manifest', dict()).get('name')

    @property
    def status(self):
        return self.o.get('status', dict()).get('phase')


KVOW = KubeVirtObjectWrapper


class KubeVirtClientWrapper(object):

    def __init__(self, c=None):
        if c is None:
            c = KubeVirtClient()
        self._c = c

    def get_resource(self, name, namespace=None):
        return self._c._get_resource(name, namespace)
