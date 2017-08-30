import yaml

import pytest
from kubernetes import config

from common import KubeVirtClientWrapper


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
    config.load_kube_config(kubeconfig)

    return KubeVirtClientWrapper()


@pytest.fixture
def default_test_vm(default_kubevirt_client, request):
    vms_c = default_kubevirt_client.get_resource('vms')
    # Load testing vm
    with open('data/vm.yaml') as fh:
        body = yaml.load(fh.read())
    vm = vms_c.create(body)
    request.addfinalizer(lambda: vms_c.delete(vm['metadata']['name']))

    return vms_c.wait_for_item(
        vm['metadata']['name'], timeout=30,
        success_condition=lambda e:
            e['object'].get('status', dict()).get('phase') == "Running"
    )
