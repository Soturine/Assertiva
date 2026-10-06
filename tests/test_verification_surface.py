import pytest

from assertiva.verification import (
    GateMode,
    VerificationCheck,
    VerificationKind,
    VerificationOrigin,
    VerificationSurface,
)


def check(check_id, kind=VerificationKind.CUSTOM, origin=VerificationOrigin.UNKNOWN, gate=GateMode.UNKNOWN):
    return VerificationCheck(check_id=check_id, kind=kind, origin=origin, gate=gate)


def test_verification_surface_is_not_test_framework_specific():
    surface = VerificationSurface()
    surface.add(check("tests", VerificationKind.TEST, VerificationOrigin.CI, GateMode.BLOCKING))
    surface.add(check("types", VerificationKind.TYPECHECK, VerificationOrigin.CI, GateMode.BLOCKING))
    surface.add(check("translations", VerificationKind.LOCALIZATION, VerificationOrigin.HOOK, GateMode.BLOCKING))
    surface.add(check("package", VerificationKind.PACKAGE, VerificationOrigin.BUILD, GateMode.BLOCKING))
    surface.add(check("deploy", VerificationKind.DEPLOY, VerificationOrigin.DEPLOY, GateMode.BLOCKING))

    assert {item.kind for item in surface.checks} == {
        VerificationKind.TEST,
        VerificationKind.TYPECHECK,
        VerificationKind.LOCALIZATION,
        VerificationKind.PACKAGE,
        VerificationKind.DEPLOY,
    }


def test_unknown_custom_check_is_preserved_not_guessed():
    item = VerificationCheck(
        check_id="custom:verify",
        kind=VerificationKind.UNKNOWN,
        origin=VerificationOrigin.LOCAL,
        command="./project-verify",
        limitations=("No semantic adapter is installed.",),
    )
    assert item.command == "./project-verify"
    assert item.kind is VerificationKind.UNKNOWN
    assert item.gate is GateMode.UNKNOWN


def test_duplicate_check_identity_is_rejected():
    surface = VerificationSurface([check("same")])
    with pytest.raises(ValueError):
        surface.add(check("same"))
