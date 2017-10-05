import yaml

import pytest

from common import (
    KVOW,
)
from kubevirt.errors import (
    WaitForTimeout,
)


def test_migrate_non_existing_vm(default_kubevirt_client, request):
    mig_c = default_kubevirt_client.get_resource('migrations')

    # Clean all migrations
    for m in mig_c.list()['items']:
        mig_c.delete(m['metadata']['name'])

    # Load testing migration
    with open('data/migration.yaml') as fh:
        body = yaml.load(fh.read())

    # Create Migration
    try:
        m = mig_c.create(body)
        request.addfinalizer(lambda: mig_c.delete(m['metadata']['name']))
    except Exception as ex:
        raise AssertionError(ex)

    # Wait for migration to fail
    try:
        for event in mig_c.watch(20):
            if event['type'] == 'MODIFIED':
                if KVOW(event['object']).status == "Failed":
                    break
    except WaitForTimeout:
        pytest.fail("Migration didn't fail.")


def test_migrate_vm(default_kubevirt_client, default_test_vm, request):
    mig_c = default_kubevirt_client.get_resource('migrations')

    # Clean all migrations
    for m in mig_c.list()['items']:
        mig_c.delete(m['metadata']['name'])

    # Load testing migration
    with open('data/migration.yaml') as fh:
        body = yaml.load(fh.read())

    vm_node = default_test_vm['status']['nodeName']

    # Create Migration
    try:
        m = mig_c.create(body)
        request.addfinalizer(lambda: mig_c.delete(m['metadata']['name']))
    except Exception as ex:
        raise AssertionError(ex)

    # Wait for migration to complete
    def desired_state(event):
        if event['type'] == 'MODIFIED':
            if KVOW(event['object']).status == "Succeeded":
                return True
        return False
    try:
        m = mig_c.wait_for_item(
            name=m['metadata']['name'], timeout=120,
            success_condition=desired_state,
        )
    except WaitForTimeout:
        pytest.fail("Migration didn't complete.")

    # Verify that VM is running on second different
    vm_c = default_kubevirt_client.get_resource('virtualmachines')
    vm = vm_c.get(default_test_vm['metadata']['name'])
    assert vm_node != vm['status']['nodeName']
