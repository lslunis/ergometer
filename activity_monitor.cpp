// g++ -Wall -Wextra -std=c++17 -mwindows activity_monitor.cpp -lcomctl32
// -lole32 -o activity_monitor.exe

// cl /EHsc /nologo /W4 /std:c++17 activity_monitor.cpp comctl32.lib ole32.lib
// user32.lib

#define STRICT
#include <Windows.h>

#include <algorithm>
#include <array>
#include <assert.h>
#include <chrono>
#include <commctrl.h>
#include <memory>
#include <ole2.h>
#include <shlwapi.h>
#include <strsafe.h>
#include <windowsx.h>
using namespace std;

constexpr UINT_PTR IDT_TIMER1 = 1;

HINSTANCE g_hinst; /* This application's HINSTANCE */
HWND g_hwndChild;  /* Optional child window */

bool g_wasActive = false;

constexpr array g_buttonCountDenyList = {110u}; // both keyboards and mice

/*
 *  OnSize
 *      If we have an inner child, resize it to fit.
 */
void OnSize([[maybe_unused]] HWND hwnd, [[maybe_unused]] UINT state, int cx, int cy) {
    if (g_hwndChild) {
        MoveWindow(g_hwndChild, 0, 0, cx, cy, TRUE);
    }
}

/*
 *  OnCreate
 *      Applications will typically override this and maybe even
 *      create a child window.
 */
BOOL OnCreate(HWND hwnd, [[maybe_unused]] LPCREATESTRUCT lpcs) {
    g_hwndChild = CreateWindow(TEXT("listbox"), NULL,
                               LBS_HASSTRINGS | WS_CHILD | WS_VISIBLE | WS_VSCROLL, 0,
                               0, 0, 0, hwnd, NULL, g_hinst, 0);

    RAWINPUTDEVICE dev[2];
    dev[0].usUsagePage = 1;
    dev[0].usUsage = 6;
    dev[0].dwFlags = RIDEV_INPUTSINK;
    dev[0].hwndTarget = hwnd;

    dev[1].usUsagePage = 1;
    dev[1].usUsage = 2;
    dev[1].dwFlags = RIDEV_INPUTSINK;
    dev[1].hwndTarget = hwnd;

    RegisterRawInputDevices(dev, sizeof(dev) / sizeof(dev[0]), sizeof(dev[0]));

    SetTimer(hwnd, IDT_TIMER1, 1000, nullptr);

    return TRUE;
}

/*
 *  OnDestroy
 *      Post a quit message because our application is over when the
 *      user closes this window.
 */
void OnDestroy(HWND hwnd) {
    RAWINPUTDEVICE dev[2];
    dev[0].usUsagePage = 1;
    dev[0].usUsage = 6;
    dev[0].dwFlags = RIDEV_REMOVE;
    dev[0].hwndTarget = hwnd;

    dev[1].usUsagePage = 1;
    dev[1].usUsage = 2;
    dev[1].dwFlags = RIDEV_REMOVE;
    dev[1].hwndTarget = hwnd;

    RegisterRawInputDevices(dev, sizeof(dev) / sizeof(dev[0]), sizeof(dev[0]));

    KillTimer(hwnd, IDT_TIMER1);

    PostQuitMessage(0);
}

#define HANDLE_WM_INPUT(hwnd, wParam, lParam, fn)                                      \
    ((fn)((hwnd), GET_RAWINPUT_CODE_WPARAM(wParam), (HRAWINPUT)(lParam)), 0)

struct Guard_DefRawInputProc {
    RAWINPUT* input;

    ~Guard_DefRawInputProc() { DefRawInputProc(&input, 1, sizeof(RAWINPUTHEADER)); }
};

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

    if (ret != sizeof(device_info) || device_info.cbSize != sizeof(device_info)
        || device_info.dwType != input->header.dwType) {
        assert(false);
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
 *  PaintContent
 *      Interesting things will be painted here eventually.
 */
void PaintContent([[maybe_unused]] HWND hwnd, [[maybe_unused]] PAINTSTRUCT* pps) {}

/*
 *  OnPaint
 *      Paint the content as part of the paint cycle.
 */
void OnPaint(HWND hwnd) {
    PAINTSTRUCT ps;
    BeginPaint(hwnd, &ps);
    PaintContent(hwnd, &ps);
    EndPaint(hwnd, &ps);
}

/*
 *  OnPrintClient
 *      Paint the content as requested by USER.
 */
void OnPrintClient(HWND hwnd, HDC hdc) {
    PAINTSTRUCT ps;
    ps.hdc = hdc;
    GetClientRect(hwnd, &ps.rcPaint);
    PaintContent(hwnd, &ps);
}

/*
 *  Window procedure
 */
LRESULT CALLBACK WndProc(HWND hwnd, UINT uiMsg, WPARAM wParam, LPARAM lParam) {
    switch (uiMsg) {
        HANDLE_MSG(hwnd, WM_CREATE, OnCreate);
        HANDLE_MSG(hwnd, WM_SIZE, OnSize);
        HANDLE_MSG(hwnd, WM_DESTROY, OnDestroy);
        HANDLE_MSG(hwnd, WM_PAINT, OnPaint);
        HANDLE_MSG(hwnd, WM_INPUT, OnInput);
    case WM_PRINTCLIENT:
        OnPrintClient(hwnd, (HDC)wParam);
        return 0;

    case WM_TIMER: {
        using sc = chrono::system_clock;
        const auto timestamp = sc::to_time_t(sc::now());

        TCHAR buffer[256];
        StringCchPrintf(buffer, ARRAYSIZE(buffer), TEXT("%s TIMESTAMP %lld"),
                        g_wasActive ? "ACTIVE!" : "Zzzzzz.",
                        static_cast<long long>(timestamp));
        ListBox_AddString(g_hwndChild, buffer);
        g_wasActive = false;

        return 0;
    }
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
                   [[maybe_unused]] LPSTR lpCmdLine, int nShowCmd) {
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
