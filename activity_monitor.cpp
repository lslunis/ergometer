#include <Windows.h>

extern "C" { // Necessary for MinGW; shouldn't be necessary for real WinSDK?
#include <Hidsdi.h>
}

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

        string str(1000, '?'); // FIXME, lazy

        UINT character_count = str.size() + 1; // include null terminator in std::string

        const UINT ret = GetRawInputDeviceInfoA(ridl.hDevice, RIDI_DEVICENAME, str.data(), &character_count);

        if (ret == 0 || ret == static_cast<UINT>(-1)) {
            cerr << "Can't handle these GetRawInputDeviceInfoA cases yet" << endl;
            exit(EXIT_FAILURE);
        }

        const UINT new_size = ret - 1; // exclude null terminator from WinAPI

        if (new_size > str.size()) {
            cerr << "Can't happen, how did we get more characters than we had room for?" << endl;
            exit(EXIT_FAILURE);
        }

        str.erase(new_size);

        cout << "Name: \"" << str << "\"" << endl;


        HANDLE hand = CreateFileA(str.c_str(), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0, nullptr);

        if (hand == INVALID_HANDLE_VALUE) {
            cerr << "CreateFileA failed" << endl;
            // exit(EXIT_FAILURE);
        } else {
            wstring device_name(126, L'?');

            const BOOLEAN get_product_string_ret = HidD_GetProductString(hand, device_name.data(), (device_name.size() + 1 /* wstring null terminator */) * sizeof(wchar_t));

            if (!get_product_string_ret) {
                cerr << "HidD_GetProductString failed" << endl;
                exit(EXIT_FAILURE);
            }

            CloseHandle(hand); // should be RAII

            cout << "success" << endl;
        }

        cout << endl;
    }
}
