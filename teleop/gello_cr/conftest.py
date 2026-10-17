"""All automated tests are offline: block hardware SDKs and device opens."""
import os
import importlib.abc
import socket
import sys

import pytest

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"


class HardwareImportBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if (fullname.rsplit('.', 1)[-1] == '_nrc_host'
                or fullname.split('.')[0] in {'pyrealsense2', 'dynamixel_sdk'}):
            raise AssertionError(f'Hardware import prohibited in tests: {fullname}')


@pytest.fixture(autouse=True)
def no_hardware(monkeypatch, request):
    if request.node.get_closest_marker("hardware"):
        yield
        return
    def forbidden(*args, **kwargs):
        raise AssertionError('Hardware/network access prohibited in offline tests')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    import serial
    monkeypatch.setattr(serial.Serial, 'open', forbidden)
    blocker = HardwareImportBlocker()
    sys.meta_path.insert(0, blocker)
    yield
    sys.meta_path.remove(blocker)
