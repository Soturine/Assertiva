"""TCC-A04 / A07 / A13: native host tests, firmware builds and on-device tests are different evidence, and services
or containers named in CI are classified, never run without consent."""

import sys

import pytest

from assertiva.adapters.ci_common import command_check
from assertiva.adapters.commands import classify_command, reproduction_plan
from assertiva.verification import GateMode, VerificationKind as K


@pytest.mark.parametrize("command,kind,modality", [
    ("pio test -e native", K.TEST, "NATIVE_HOST"),
    ("platformio test -e native_coverage", K.TEST, "NATIVE_HOST"),
    ("pio test -e esp32dev", K.TEST, "TARGET_DEVICE"),
    ("pio test -e esp32dev --without-testing", K.BUILD, "FIRMWARE_BUILD"),
    ("pio test", K.TEST, "UNKNOWN"),
    ("pio run -e esp32dev", K.BUILD, "FIRMWARE_BUILD"),
    ("pio run -e esp32dev -t upload", K.DEPLOY, "FIRMWARE_UPLOAD"),
])
def test_platformio_commands_carry_their_modality(command, kind, modality):
    cls = classify_command(command)
    assert cls.kind is kind and cls.metadata["modality"] == modality


def plan(command):
    return reproduction_plan(command_check("gha", "c", command, "ci.yml", GateMode.UNKNOWN, {}), sys.executable)


def test_on_device_or_unnamed_targets_are_never_run():
    for command in ("pio test -e esp32dev", "pio test"):
        assert plan(command).argv is None and "device" in plan(command).reason


def test_a_native_host_test_may_run_and_a_firmware_build_is_not_a_test():
    assert plan("pio test -e native").argv is not None
    assert classify_command("pio run -e esp32dev").kind is not K.TEST


@pytest.mark.parametrize("command,kind", [
    ("docker compose up -d mysql", K.CONTAINER), ("docker run --rm eclipse-mosquitto", K.CONTAINER),
    ("docker-compose up -d", K.CONTAINER), ("mosquitto_pub -t alerts -m x", K.CUSTOM), ("mysql -e 'select 1'", K.CUSTOM),
])
def test_services_and_containers_are_classified_and_need_consent(command, kind):
    assert classify_command(command).kind is kind
    assert plan(command).needs_authorization  # containers and custom commands run only when authorized
