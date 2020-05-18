// cl /EHsc /nologo /W4 /std:c++17 activity_monitor.cpp comctl32.lib ole32.lib
// user32.lib

#define STRICT
#include <Windows.h>

#include <algorithm>
#include <chrono>
#include <commctrl.h>
#include <memory>
#include <ole2.h>
#include <regex>
#include <shlwapi.h>
#include <stdexcept>
#include <stdio.h>
#include <string>
#include <vector>
#include <windowsx.h>
using namespace std;

constexpr UINT_PTR IDT_TIMER1 = 1;

HINSTANCE g_hinst;

bool g_wasActive = false;

vector<DWORD> g_buttonCountDenyList; // both keyboards and mice

void register_for_raw_input(const HWND hwnd, const DWORD dwFlags) {
    const RAWINPUTDEVICE dev[]{{1, 6, dwFlags, hwnd}, {1, 2, dwFlags, hwnd}};
    RegisterRawInputDevices(dev, static_cast<UINT>(size(dev)), sizeof(dev[0]));
}

BOOL OnCreate(HWND hwnd, LPCREATESTRUCT) {
    register_for_raw_input(hwnd, RIDEV_INPUTSINK);
    SetTimer(hwnd, IDT_TIMER1, 1000, nullptr);
    return TRUE;
}

void OnDestroy(HWND hwnd) {
    register_for_raw_input(hwnd, RIDEV_REMOVE);
    KillTimer(hwnd, IDT_TIMER1);
    PostQuitMessage(0);
}

#define HANDLE_WM_INPUT(hwnd, wParam, lParam, fn)                                      \
    ((fn)((hwnd), GET_RAWINPUT_CODE_WPARAM(wParam), (HRAWINPUT)(lParam)), 0)

struct Guard_DefRawInputProc {
    RAWINPUT* input;

    ~Guard_DefRawInputProc() { DefRawInputProc(&input, 1, sizeof(RAWINPUTHEADER)); }
};

bool check_equal_values(const char* const name1, const DWORD value1,
                        const char* const name2, const DWORD value2) {
    const bool eq = value1 == value2;

    if (!eq) {
        fprintf(stderr, "%s (%u) != %s (%u)\n", name1, value1, name2, value2);
    }

    return eq;
}

void OnInput([[maybe_unused]] HWND hwnd, [[maybe_unused]] WPARAM code,
             HRAWINPUT hRawInput) {
    UINT dwSize;
    GetRawInputData(hRawInput, RID_INPUT, nullptr, &dwSize, sizeof(RAWINPUTHEADER));
    auto storage = std::make_unique<unsigned char[]>(dwSize);
    RAWINPUT* input = reinterpret_cast<RAWINPUT*>(storage.get());
    Guard_DefRawInputProc guard{input};

    GetRawInputData(hRawInput, RID_INPUT, input, &dwSize, sizeof(RAWINPUTHEADER));

    if (!(input->header.dwType == RIM_TYPEKEYBOARD
          || (input->header.dwType == RIM_TYPEMOUSE
              && input->data.mouse.usButtonFlags != 0))) {
        return; // process only keyboard and mouse button events (not mouse
                // movement or other devices)
    }

    if (!input->header.hDevice) {
        return; // skip null handles (representing synthetic keyboards/mice?)
    }

    RID_DEVICE_INFO device_info{};
    device_info.cbSize = sizeof(device_info);
    UINT cbSize = sizeof(device_info);
    const UINT ret = GetRawInputDeviceInfoA(input->header.hDevice, RIDI_DEVICEINFO,
                                            &device_info, &cbSize);

    const bool eq1 = check_equal_values("ret", ret, "sizeof(device_info)",
                                        static_cast<DWORD>(sizeof(device_info)));
    const bool eq2 = check_equal_values("device_info.cbSize", device_info.cbSize,
                                        "sizeof(device_info)",
                                        static_cast<DWORD>(sizeof(device_info)));
    const bool eq3 = check_equal_values("device_info.dwType", device_info.dwType,
                                        "input->header.dwType", input->header.dwType);

    if (!eq1 || !eq2 || !eq3) {
        return; // avoid short-circuiting so that all warnings are printed
    }

    const DWORD button_count = input->header.dwType == RIM_TYPEKEYBOARD
                                   ? device_info.keyboard.dwNumberOfKeysTotal
                                   : device_info.mouse.dwNumberOfButtons;

    if (find(g_buttonCountDenyList.begin(), g_buttonCountDenyList.end(), button_count)
        != g_buttonCountDenyList.end()) {
        return; // skip keyboards/mice with denied button counts
    }

    g_wasActive = true;
}

/*
 *  Window procedure
 */
LRESULT CALLBACK WndProc(HWND hwnd, UINT uiMsg, WPARAM wParam, LPARAM lParam) {
    switch (uiMsg) {
        HANDLE_MSG(hwnd, WM_CREATE, OnCreate);
        HANDLE_MSG(hwnd, WM_DESTROY, OnDestroy);
        HANDLE_MSG(hwnd, WM_INPUT, OnInput);

    case WM_TIMER:
        if (g_wasActive) {
            using sc = chrono::system_clock;
            const auto timestamp = sc::to_time_t(sc::now());
            printf("%lld\n", static_cast<long long>(timestamp));
            fflush(stdout);
            g_wasActive = false;
        }

        return 0;
    }
    return DefWindowProc(hwnd, uiMsg, wParam, lParam);
}

BOOL InitApp(void) {
    WNDCLASS wc;
    wc.style = 0;
    wc.lpfnWndProc = WndProc;
    wc.cbClsExtra = 0;
    wc.cbWndExtra = 0;
    wc.hInstance = g_hinst;
    wc.hIcon = NULL;
    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    wc.lpszMenuName = NULL;
    wc.lpszClassName = TEXT("Scratch");
    if (!RegisterClass(&wc))
        return FALSE;
    InitCommonControls(); /* In case we use a common control */
    return TRUE;
}

int WINAPI WinMain(HINSTANCE hinst, [[maybe_unused]] HINSTANCE hinstPrev,
                   LPSTR lpCmdLine, int nShowCmd) {

    const regex digits{R"(\d+)"};
    const string strCmdLine{lpCmdLine};
    for (sregex_token_iterator it(strCmdLine.begin(), strCmdLine.end(), digits), end;
         it != end; ++it) {
        const ssub_match sm = *it;
        try {
            g_buttonCountDenyList.push_back(static_cast<DWORD>(stoi(sm)));
        } catch (const out_of_range&) {
            fprintf(stderr, "Ignoring out-of-range command-line argument '%s'.\n",
                    sm.str().c_str());
        }
    }

    MSG msg;
    HWND hwnd;
    g_hinst = hinst;
    if (!InitApp())
        return 0;
    if (SUCCEEDED(CoInitialize(NULL))) {                  /* In case we use COM */
        hwnd = CreateWindow(TEXT("Scratch"),              /* Class Name */
                            TEXT("Scratch"),              /* Title */
                            WS_OVERLAPPEDWINDOW,          /* Style */
                            CW_USEDEFAULT, CW_USEDEFAULT, /* Position */
                            CW_USEDEFAULT, CW_USEDEFAULT, /* Size */
                            NULL,                         /* Parent */
                            NULL,                         /* No menu */
                            hinst,                        /* Instance */
                            0);                           /* No special parameters */
        ShowWindow(hwnd, nShowCmd);
        while (GetMessage(&msg, NULL, 0, 0)) {
            TranslateMessage(&msg);
            DispatchMessage(&msg);
        }
        CoUninitialize();
    }
    return 0;
}
