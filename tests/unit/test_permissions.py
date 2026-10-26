import pytest

from voiceroute import ALL_PERMISSIONS, Permission, Permissions


def test_administrator_expands_to_every_permission() -> None:
    permissions = Permissions([Permission.ADMINISTRATOR])

    assert len(permissions) == len(ALL_PERMISSIONS)
    assert permissions.has(Permission.BAN_MEMBERS)
    assert permissions.has_all([Permission.MANAGE_ROLES, Permission.MANAGE_CHANNELS])


def test_permissions_report_missing_values_in_registry_order() -> None:
    permissions = Permissions([Permission.VIEW_CHANNEL])

    assert permissions.missing(
        [Permission.VIEW_CHANNEL, Permission.SEND_MESSAGES, Permission.ATTACH_FILES]
    ) == (Permission.SEND_MESSAGES, Permission.ATTACH_FILES)


def test_unknown_permission_is_rejected() -> None:
    with pytest.raises(ValueError):
        Permissions(["futurePermission"])
