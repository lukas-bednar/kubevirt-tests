import yaml

import pytest
from kubernetes import config
import kubevirt

import common


def pytest_addoption(parser):
    group = parser.getgroup('KubeVirt')
    group.addoption(
        '--kubeconfig',
        action='store',
        dest='kubeconfig',
        default='data/.kubeconfig',
        help='Path to kubeconfig'
    )


@pytest.fixture
def default_kubevirt_client():
    kubeconfig = pytest.config.getoption("kubeconfig")
    cl = config.kube_config._get_kube_config_loader_for_yaml_file(kubeconfig)
    cl.load_and_set(kubevirt.configuration)

    # FIXME: WorkAround because KubeVirt API is served on differently
    api = kubevirt.DefaultApi()
    # with open('/tmp/i', 'a') as fh:
    #     fh.write("%s\n" % api.api_client.host)
    # api.api_client.host = "http://192.168.200.2:8184"

    return api


@pytest.fixture
def default_test_vm(default_kubevirt_client, request):
    # Load testing vm
    with open('data/vm.yaml') as fh:
        body = yaml.load(fh.read())
    vm = default_kubevirt_client.create_namespaced_virtual_machine(
        body, common.NAMESPACE
    )
    request.addfinalizer(
        lambda: default_kubevirt_client.delete_namespaced_virtual_machine(
            kubevirt.V1DeleteOptions(), common.NAMESPACE, common.get_name(vm)
        )
    )

    w = common.Watch(
        default_kubevirt_client.list_namespaced_virtual_machine,
        common.NAMESPACE
    )
    return w.wait_for_item(
        common.get_name(vm), timeout=30,
        success_condition=lambda e:
            common.get_status(e['object']) == "Running"
    )
