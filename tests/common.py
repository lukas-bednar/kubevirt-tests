import time
from urllib3.exceptions import ReadTimeoutError
from kubernetes import watch


NAMESPACE = "default"


def get_name(obj):
    if isinstance(obj, dict):
        return obj.get('metadata', dict()).get('name')
    return obj.metadata.name


def get_status(obj):
    if isinstance(obj, dict):
        return obj.get('status', dict()).get('phase')
    return obj.status.phase


def get_node_name_vm_running(obj):
    if isinstance(obj, dict):
        return obj.get('status', dict()).get('nodeName')
    return obj.status.node_name


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


class Watch(object):

    def __init__(self, event_source, *args, **kwargs):
        self._es = event_source
        self._args = args
        self._kw = kwargs

    def _event_source(self, **kwargs):
        kw = self._kw.copy()
        kw.update(kwargs)
        with open('/tmp/a', 'w') as fh:
            fh.write("%s" % kw)
        return self._es(*self._args, **kw)

    def watch(self, request_timeout=None):
        kw = dict()
        if request_timeout:
            kw['_request_timeout'] = request_timeout
        w = watch.Watch()
        try:
            for e in w.stream(self._event_source, **kw):
                yield e
        except GeneratorExit:
            w.stop()
            raise

    def _wait_for_x(
        self, timeout, filter_condition, success_condition,
        failure_condition
    ):
        step = 5  # 5s
        endtime = timeout + time.time()
        while timeout < endtime:
            try:
                for e in self.watch(request_timeout=step):
                    if not filter_condition(e):
                        continue
                    if success_condition(e):
                        return e['object']
                    if failure_condition(e):
                        raise WaitForFailureMatch(e)
            except ReadTimeoutError:
                continue
#        raise WaitForTimeout(str(self._ns), self.timeout)
        raise WaitForTimeout("TODO: somehow address name", self.timeout)

    def wait_for_item(
        self, name, timeout, success_condition,
        failure_condition=lambda e: False
    ):
        return self._wait_for_x(
            timeout,
            lambda e: get_name(e['object']) == name,
            success_condition, failure_condition
        )

    def wait_for(
        self, timeout, success_condition,
        failure_condition=lambda e: False
    ):
        return self._wait_for_x(
            timeout, lambda e: True, success_condition,
            failure_condition
        )
