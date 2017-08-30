import time
from functools import wraps

from urllib3.exceptions import ReadTimeoutError
from kubernetes import client, watch


DEFAULT_GROUP = "kubevirt.io"
DEFAULT_VERSION = "v1alpha1"
DEFAULT_NAMESPACE = "default"


def entity_common_error_wrapper(f):
    @wraps(f)
    def wrapper(self, name, *args, **kwargs):
        try:
            return f(self, name, *args, **kwargs)
        except client.rest.ApiException as ex:
            if ex.status == 404:
                raise EntityNotFound(
                    "%s/%s/%s" % (self._ns, self._plural, name), ex)
            if ex.status == 409:
                raise ConflictingEntities(
                    "%s/%s/%s" % (self._ns, self._plural, name), ex)
            else:
                raise
    return wrapper


class KubeVirtException(Exception):
    pass


class WaitForException(KubeVirtException):
    pass


class WaitForFailureMatch(WaitForException):
    def __init__(self, event):
        self.event = event

    def __str__(self):
        return "Failure condition satisfied with item: %s" % self.event


class WaitForTimeout(WaitForException):
    def __init__(self, name, timeout):
        self.name = name
        self.timeout = timeout

    def __str__(self):
        return "Waiting for events on %s reached timeout: %ss" % (
            self.name, self.timeout
        )


class EntityNotFound(KubeVirtException):
    def __init__(self, entity, origexc):
        self.entiy = entity
        self.exc = origexc

    def __str__(self):
        return "Entity %s not found.\n%s %s" % (
            self.entiy, self.exc.__class__.__name__, self.exc
        )


class ConflictingEntities(KubeVirtException):
    def __init__(self, entity, origexc):
        self.entiy = entity
        self.exc = origexc

    def __str__(self):
        return "Entity %s has conflict found.\n%s %s" % (
            self.entiy, self.exc.__class__.__name__, self.exc
        )


class KubeVirtNamespace(object):
    def __init__(self, group, version, namespace):
        self.group = group
        self.version = version
        self.ns = namespace

    def __str__(self):
        return "ns:%s/%s/%s" % (self.group, self.version, self.ns)


class KubeVirtNamespacedObject(object):

    def __init__(self, client, namespace, plular):
        self._c = client
        self._ns = namespace
        self._plural = plular

    @entity_common_error_wrapper
    def get(self, name, **kwargs):
        return self._c.get_namespaced_custom_object(
            self._ns.group, self._ns.version, self._ns.ns, self._plural, name,
            **kwargs
        )

    @entity_common_error_wrapper
    def delete(self, name, **kwargs):
        k = kwargs.copy()
        if 'body' not in k:
            k['body'] = client.V1DeleteOptions()
        return self._c.delete_namespaced_custom_object(
            self._ns.group, self._ns.version, self._ns.ns, self._plural, name,
            **k
        )

    def create(self, obj, **kwargs):
        return self._c.create_namespaced_custom_object(
            self._ns.group, self._ns.version, self._ns.ns, self._plural, obj,
            **kwargs
        )

    def list(self, **kwargs):
        result = self._c.list_namespaced_custom_object(
            self._ns.group, self._ns.version, self._ns.ns, self._plural,
            **kwargs
        )
        if isinstance(result, dict):  # it might return future object
            return result.get('items')
        return result

    def _watch(self, event_source, request_timeout=None):
        kw = dict()
        if request_timeout:
            kw['_request_timeout'] = request_timeout
        w = watch.Watch()
        try:
            for e in w.stream(event_source, **kw):
                yield e
        except GeneratorExit:
            w.stop()
            raise

    def watch(self, request_timeout=None):
        return self._watch(self.list, request_timeout)

    def _wait_for_x(
        self, timeout, filter_condition, success_condition, failure_condition
    ):
        step = 5  # 5s
        endtime = timeout + time.time()
        while timeout < endtime:
            try:
                for e in self._watch(self.list, request_timeout=step):
                    if not filter_condition(e):
                        continue
                    if success_condition(e):
                        return e['object']
                    if failure_condition(e):
                        raise WaitForFailureMatch(e)
            except ReadTimeoutError:
                continue
        raise WaitForTimeout(str(self._ns), self.timeout)

    def wait_for_item(
        self, name, timeout, success_condition,
        failure_condition=lambda e: False
    ):
        return self._wait_for_x(
            timeout,
            lambda e: e['object'].get('metadata', dict()).get('name') == name,
            success_condition, failure_condition
        )

    def wait_for(
        self, timeout, success_condition, failure_condition=lambda e: False
    ):
        return self._wait_for_x(
            self.list, timeout, lambda e: True, success_condition,
            failure_condition
        )


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

    def __init__(self, c=None, group=DEFAULT_GROUP, version=DEFAULT_VERSION):
        if c is None:
            c = client.CustomObjectsApi()
        self._c = c
        self._group = group
        self._version = version

    def get_namespace(self, name):
        return KubeVirtNamespace(self._group, self._version, name)

    def get_resource(self, name, namespace=None):
        if namespace is None:
            namespace = self.get_namespace(DEFAULT_NAMESPACE)
        return KubeVirtNamespacedObject(self._c, namespace, name)
