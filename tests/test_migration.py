import yaml

import pytest

import common


def delete_migrations(client):
    for m in client.list_namespaced_migration(
        common.NAMESPACE
    ).items:
        client.delete_namespaced_migration(
            common.NAMESPACE, common.get_name(m)
        )


def test_migrate_non_existing_vm(default_kubevirt_client, request):
    # Clean all migrations
    delete_migrations(default_kubevirt_client)

    # Load testing migration
    with open('data/migration.yaml') as fh:
        body = yaml.load(fh.read())

    # Create Migration
    try:
        m = default_kubevirt_client.create_namespaced_migration(
            body, common.NAMESPACE
        )
        request.addfinalizer(
            lambda: default_kubevirt_client.delete_namespaced_migration(
                common.NAMESPACE, common.get_name(m)
            )
        )
    except Exception as ex:
        raise AssertionError(ex)

    # Wait for migration to fail
    try:
        w = common.Watch(
            default_kubevirt_client.list_namespaced_migration,
            common.NAMESPACE
        )
        for event in w.watch(20):
            if event['type'] in ('ADDED', 'MODIFIED'):
                if common.get_status(event['object']) == "Failed":
                    break
    except common.WaitForTimeout:
        pytest.fail("Migration didn't fail.")


def test_migrate_vm(default_kubevirt_client, default_test_vm, request):
    # Clean all migrations
    delete_migrations(default_kubevirt_client)

    # Load testing migration
    with open('data/migration.yaml') as fh:
        body = yaml.load(fh.read())

    vm_node = common.get_node_name_vm_running(default_test_vm)

    # Create Migration
    try:
        m = default_kubevirt_client.create_namespaced_migration(
            body, common.NAMESPACE
        )
        request.addfinalizer(
            lambda: default_kubevirt_client.delete_namespaced_migration(
                common.NAMESPACE, common.get_name(m)
            )
        )
    except Exception as ex:
        raise AssertionError(ex)

    # Wait for migration to complete
    def desired_state(event):
        if event['type'] in ('ADDED', 'MODIFIED'):
            if common.get_status(event['object']) == "Succeeded":
                return True
        return False
    try:
        w = common.Watch(
            default_kubevirt_client.list_namespaced_migration,
            common.NAMESPACE
        )
        m = w.wait_for_item(
            name=common.get_name(m), timeout=120,
            success_condition=desired_state,
        )
    except common.WaitForTimeout:
        pytest.fail("Migration didn't complete.")

    # Verify that VM is running on second different
    vm = default_kubevirt_client.read_namespaced_virtual_machine(
        common.get_name(default_test_vm), common.NAMESPACE
    )
    assert vm_node != common.get_node_name_vm_running(vm)
