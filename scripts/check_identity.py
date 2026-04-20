from tests.bridge.hardware_bridge import HardwareBridge


def check_bcm_identity():
    bridge = HardwareBridge()
    print("\n QUERYING BCM SW VERSION...")
    version = bridge.get_sw_version()
    print(f" DETECTED VERSION: {version}")

    print("\n CHECKING CURRENT TELEMETRY...")
    status = bridge.get_status()
    print(f" TELEMETRY FRAME:  {status}")

    bridge.close()


if __name__ == "__main__":
    check_bcm_identity()
