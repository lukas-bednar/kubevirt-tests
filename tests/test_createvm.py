import yaml

import pytest

from kubevirt.errors import (
    EntityNotFound,
    WaitForTimeout,
)


def test_getting_non_existing_vm(default_kubevirt_client):
    vms_c = default_kubevirt_client.get_resource('vms')

    with pytest.raises(EntityNotFound):
        vms_c.get("non-existing")


def test_create_vm(default_kubevirt_client, request):
    vms_c = default_kubevirt_client.get_resource('vms')

    # Load testing VM
    with open('data/vm.yaml') as fh:
        body = yaml.load(fh.read())

    try:
        # Create VM
        vm = vms_c.create(body)
        request.addfinalizer(lambda: vms_c.delete(vm['metadata']['name']))
    except Exception as ex:
        raise AssertionError(ex)

    # Wait until it is running
    try:
        vm = vms_c.wait_for_item(
            vm['metadata']['name'], timeout=60,
            success_condition=lambda e:
                e['object'].get('status', dict()).get('phase') == "Running"
        )
    except WaitForTimeout:
        vm = vms_c.get(vm['metadata']['name'])
        pytest.fail(
            "VM is not in expected state: %s != %s" % (
                vm.get('status', dict()).get('phase'), "Running"
            )
        )
