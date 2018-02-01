import yaml

import common

import pytest
import kubevirt


def test_create_vm_replicateset(default_kubevirt_client, request):
    client = default_kubevirt_client
    # Load testing VMReplicaSet
    with open('data/replicaset.yaml') as fh:
        body = yaml.load(fh.read())

    # Pick label
    label = "%s=%s" % tuple(
        body['spec']['selector']['matchLabels'].items())[0]
    # Pick No. replicas
    replicas_number = int(body['spec']['replicas'])

    try:
        # Create VM
        vmrs = client.create_namespaced_virtual_machine_replica_set(
            body, common.NAMESPACE
        )
        request.addfinalizer(
            lambda: client.delete_namespaced_virtual_machine_replica_set(
                kubevirt.V1DeleteOptions(), common.NAMESPACE,
                common.get_name(vmrs)
            )
        )
    except Exception as ex:
        raise AssertionError(ex)
    try:
        w = common.Watch(
            client.list_namespaced_virtual_machine,
            common.NAMESPACE, label_selector=label
        )

        runnning_vms = list()
        for e in w.watch(60):
            vm_name = common.get_name(e['object'])
            if common.get_status(e['object']) == "Running":
                if vm_name not in runnning_vms:
                    runnning_vms.append(vm_name)
            if len(runnning_vms) == replicas_number:
                break
    except common.WaitForTimeout:
        pytest.fail(
            "VMs defined in VMRS didn't scaled up"
        )
