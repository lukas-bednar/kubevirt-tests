import yaml

import pytest
import kubevirt

import common


def test_getting_non_existing_vm(default_kubevirt_client):
    with pytest.raises(kubevirt.rest.ApiException) as exi:
        default_kubevirt_client.read_namespaced_virtual_machine(
            "non-existing", common.NAMESPACE
        )
    assert exi.value.status == 404


def test_create_vm(default_kubevirt_client, request):
    # Load testing VM
    with open('data/vm.yaml') as fh:
        body = yaml.load(fh.read())

    try:
        # Create VM
        vm = default_kubevirt_client.create_namespaced_virtual_machine(
            body, common.NAMESPACE
        )
        request.addfinalizer(
            lambda: default_kubevirt_client.delete_namespaced_virtual_machine(
                common.NAMESPACE, common.get_name(vm)
            )
        )
    except Exception as ex:
        raise AssertionError(ex)

    # Wait until it is running
    try:
        w = common.Watch(
            default_kubevirt_client.list_namespaced_virtual_machine,
            common.NAMESPACE
        )
        vm = w.wait_for_item(
            common.get_name(vm), timeout=60,
            success_condition=lambda e:
                common.get_status(e['object']) == "Running"
        )
    except common.WaitForTimeout:
        vm = default_kubevirt_client.read_namespaced_virtual_machine(
            common.get_name(vm)
        )
        pytest.fail(
            "VM is not in expected state: %s != %s" % (
                common.get_status(vm), "Running"
            )
        )
