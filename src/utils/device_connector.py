from ppadb.client import Client as AdbClient

class DeviceConnector:
    @staticmethod
    def connect_device(host="127.0.0.1", port=5037):
        adb = AdbClient(host=host, port=port)
        devices = adb.devices()
        if not devices:
            raise Exception("No devices found. Make sure your emulator is running.")
        return devices[0]