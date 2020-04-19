#include <Windows.h>
#include <vector>
#include <iostream>
#include <stdlib.h>
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

    cout << "Actually got " << devices.size() << " elements" << endl;
}
