#include <Windows.h>
#include <vector>
#include <iostream>
#include <stdlib.h>
#include <string>
using namespace std;

int main() {
    vector<RAWINPUTDEVICELIST> devices;

    devices.resize(1); // vector must be non-empty
    for (;;) {
        UINT num_devices = static_cast<UINT>(devices.size());

        const UINT ret = GetRawInputDeviceList(devices.data(), &num_devices, sizeof(RAWINPUTDEVICELIST));

        if (ret != static_cast<UINT>(-1)) {
            if (ret > devices.size()) {
                cerr << "This shouldn't happen (how did we get more devices than we had room for)!" << endl;
                exit(EXIT_FAILURE);
            }

            devices.erase(devices.begin() + ret, devices.end());
            break;
        }

        const DWORD last_error = GetLastError();

        if (last_error != ERROR_INSUFFICIENT_BUFFER) {
            cerr << "GetRawInputDeviceList failed with " << last_error << endl;
            exit(EXIT_FAILURE);
        }

        if (num_devices <= devices.size()) {
            cerr << "This shouldn't happen (how did we have insufficient space when we had enough)!" << endl;
            exit(EXIT_FAILURE);
        }

        devices.resize(num_devices);
    }

    cout << "Actually got " << devices.size() << " elements." << endl << endl;

    for (const auto& ridl : devices) {
        switch (ridl.dwType) {
        case RIM_TYPEHID:
            cout << "The device is an HID that is not a keyboard and not a mouse." << endl;
            break;
        case RIM_TYPEKEYBOARD:
            cout << "The device is a keyboard." << endl;
            break;
        case RIM_TYPEMOUSE:
            cout << "The device is a mouse." << endl;
            break;
        default:
            cout << "Unknown dwType " << ridl.dwType << endl;
            break;
        }

        if (ridl.dwType == RIM_TYPEKEYBOARD || ridl.dwType == RIM_TYPEMOUSE) {
            RID_DEVICE_INFO device_info{};

            UINT cbSize = sizeof(device_info);

            const UINT ret = GetRawInputDeviceInfoA(ridl.hDevice, RIDI_DEVICEINFO, &device_info, &cbSize);

            if (ret == 0 || ret == static_cast<UINT>(-1)) {
                cerr << "GetRawInputDeviceInfoA failed" << endl;
                exit(EXIT_FAILURE);
            }

            if (ret != sizeof(device_info)) {
                cerr << "GetRawInputDeviceInfoA copied an unexpected number of bytes" << endl;
                exit(EXIT_FAILURE);
            }

            // GetRawInputDeviceInfoA reported success

            if (device_info.cbSize != sizeof(device_info) || device_info.dwType != ridl.dwType) {
                cerr << "Inconsistent info in device_info" << endl;
                exit(EXIT_FAILURE);
            }

            if (ridl.dwType == RIM_TYPEKEYBOARD) {
                cout << "dwType: " << device_info.keyboard.dwType << endl;
                cout << "dwSubType: " << device_info.keyboard.dwSubType << endl;
                cout << "dwKeyboardMode: " << device_info.keyboard.dwKeyboardMode << endl;
                cout << "dwNumberOfFunctionKeys: " << device_info.keyboard.dwNumberOfFunctionKeys << endl;
                cout << "dwNumberOfIndicators: " << device_info.keyboard.dwNumberOfIndicators << endl;
                cout << "dwNumberOfKeysTotal: " << device_info.keyboard.dwNumberOfKeysTotal << endl;
            } else if (ridl.dwType == RIM_TYPEMOUSE) {
                cout << "dwId: " << device_info.mouse.dwId << endl;
                cout << "dwNumberOfButtons: " << device_info.mouse.dwNumberOfButtons << endl;
                cout << "dwSampleRate: " << device_info.mouse.dwSampleRate << endl;
                cout << "fHasHorizontalWheel: " << device_info.mouse.fHasHorizontalWheel << endl;
            } else {
                cerr << "LOGIC ERROR" << endl;
                exit(EXIT_FAILURE);
            }
        }

        cout << endl;
    }
}
