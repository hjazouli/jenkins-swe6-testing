import pytest
import ctypes
import os
import sys

# Add the root directory to path so we can import bridges
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.bridge.hardware_bridge import HardwareBridge
from tests.bridge.sim_bridge import SimBridge

def pytest_addoption(parser):
    parser.addoption(
        "--target", action="store", default="hardware", help="Target: sim or hardware"
    )

@pytest.fixture
def bcm_target(request):
    target_type = request.config.getoption("--target")

    if target_type == "hardware":
        bridge = HardwareBridge()
        yield bridge
        bridge.close()
    else:
        # For simulation, we would load the DLL here
        # bcm_lib = ctypes.CDLL("./bcm.so")
        yield SimBridge(None)
