#include "pch.h"
#include "webview.h"
#include <windows.h>
#include <windowsx.h>
#include <wrl.h>
#include <stdio.h>
#include <dcomp.h>
//#include <shlobj.h>
#include <vector>
#include <string>
#include <cmath>
#include <exception>
#include <WebView2.h>
//#include <dwmapi.h>
#include <nlohmann/json.hpp>

using json = nlohmann::json;

//#pragma comment(lib, "dwmapi.lib")
#pragma comment(lib, "dcomp.lib")

using namespace Microsoft::WRL;

std::wstring convert_wstring(const std::string& str);

std::string wstring_convert(const std::wstring& wstr);

LRESULT CALLBACK WndProc(HWND, UINT, WPARAM, LPARAM);

void InitWebView2(HWND hwnd);

struct WebviewParameter
{
    int width = 960;
    int height = 680;
    int x = CW_USEDEFAULT;
    int y = CW_USEDEFAULT;
    int client_x = 0;
    int client_y = 0; 
    int client_width = 100;
    int client_height = 32;
    int memory_size = 0;
    std::wstring title = L"Webview2 Viewer";
    std::wstring icon;
    std::wstring url;
};

WebviewParameter g_params;

uint8_t* r_ptr = nullptr, *w_ptr = nullptr;

static MessageListener g_listener = nullptr;

// ---------------- 全局变量 ----------------
HWND g_hwnd = nullptr;
// WebView2
ComPtr<ICoreWebView2Environment> g_env;
ComPtr<ICoreWebView2CompositionController> g_compController;
ComPtr<ICoreWebView2Controller> g_controller;
ComPtr<ICoreWebView2> g_webview;
ComPtr<ICoreWebView2SharedBuffer> g_shared4reader;
ComPtr<ICoreWebView2SharedBuffer> g_shared4writer;
// DirectComposition
ComPtr<IDCompositionDevice> g_device;
ComPtr<IDCompositionTarget> g_target;
ComPtr<IDCompositionVisual> g_visual;
bool g_tracking = false;
RECT g_webviewRect = {};

void set_title(char* title) { g_params.title = std::wstring(convert_wstring(title)); }

void set_position(int x, int y) { g_params.x = x; g_params.y = y; }

void set_size(int width, int height) { g_params.width = width; g_params.height = height; }

void set_memory(int length) { g_params.memory_size = length; }

void set_listener(MessageListener listener) { g_listener = listener; }

void set_client(int x, int y, int width, int height) { g_params.client_x = x; g_params.client_y = y; g_params.client_width = width; g_params.client_height = height; }

void set_navigation(char* url) { g_params.url = std::wstring(convert_wstring(url)); }

void set_icon(char* path) { g_params.icon = std::wstring(convert_wstring(path)); }

void* get_window() { return g_hwnd; }

int read(unsigned char* p, int size)
{
    if (w_ptr == nullptr) return 0;
    if (size > g_params.memory_size) {
        memcpy(p, w_ptr, g_params.memory_size);
        return g_params.memory_size;
    }
    memcpy(p, w_ptr, size);
    return size;
}

int write(unsigned char* p, int size)
{
    if (r_ptr == nullptr) return 0;
    if (size > g_params.memory_size) {
        memcpy(r_ptr, p, g_params.memory_size);
        return g_params.memory_size;
    }
    memcpy(r_ptr, p, size);
    return size;
}


void post(char* message)
{
    if (!g_webview) return;
    g_webview->PostWebMessageAsString(convert_wstring(message).c_str());
}

static void Trap(long status)
{
    if (FAILED(status))
        throw std::exception("webview2 interface error");
}

static POINT PointOfClient(HWND hwnd, const POINTL& p, bool s2c = true)
{
    POINT pt{ p.x, p.y };
    if (s2c)
        ScreenToClient(hwnd, &pt);
    return pt;
}

class WebView2DropTarget : public IDropTarget
{
public:
    WebView2DropTarget(HWND hwnd, ComPtr<ICoreWebView2CompositionController> controller)
        : _refCount(1), _hwnd(hwnd)
    {
        controller.As(&_controller);
        if (_hwnd) ::RegisterDragDrop(_hwnd, this);
    }

    virtual ~WebView2DropTarget()
    {
        if (_hwnd) ::RevokeDragDrop(_hwnd);
    }

    STDMETHODIMP QueryInterface(REFIID riid, void** ppv) override
    {
        if (!ppv) return E_POINTER;
        if (riid == IID_IUnknown || riid == IID_IDropTarget)
        {
            *ppv = static_cast<IDropTarget*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }

    STDMETHODIMP_(ULONG) AddRef() override { return InterlockedIncrement(&_refCount); }

    STDMETHODIMP_(ULONG) Release() override
    {
        ULONG res = InterlockedDecrement(&_refCount);
        if (res == 0) delete this;
        return res;
    }

    STDMETHODIMP DragEnter(IDataObject* pDataObj, DWORD grfKeyState, POINTL pt, DWORD* pdwEffect) override
    {
        if (!_controller || !pDataObj) return E_FAIL;
        *pdwEffect = DROPEFFECT_COPY;
        _controller->DragEnter(pDataObj, grfKeyState, PointOfClient(_hwnd, pt), pdwEffect);
        return S_OK;
    }

    STDMETHODIMP DragOver(DWORD grfKeyState, POINTL pt, DWORD* pdwEffect) override
    {
        if (!_controller) return E_FAIL;
        *pdwEffect = DROPEFFECT_COPY;
        _controller->DragOver(grfKeyState, PointOfClient(_hwnd, pt), pdwEffect);
        return S_OK;
    }

    STDMETHODIMP DragLeave() override
    {
        if (!_controller) return E_FAIL;
        _controller->DragLeave();
        return S_OK;
    }

    STDMETHODIMP Drop(IDataObject* pDataObj, DWORD grfKeyState, POINTL pt, DWORD* pdwEffect) override
    {
        if (!_controller || !pDataObj) return E_FAIL;
        *pdwEffect = DROPEFFECT_COPY;
        _controller->Drop(pDataObj, grfKeyState, PointOfClient(_hwnd, pt), pdwEffect);
        return S_OK;
    }

private:
    LONG _refCount;
    HWND _hwnd;
    ComPtr<ICoreWebView2CompositionController3> _controller;
};

static void AttachConsoleForDebug()
{
    AllocConsole();
    FILE* fp;
    freopen_s(&fp, "CONOUT$", "w", stdout);
    freopen_s(&fp, "CONOUT$", "w", stderr);
}

bool IsCaptionArea(POINT pt)
{
    return pt.x > g_params.client_x 
        && pt.x < g_params.client_x + g_params.client_width
        && pt.y > g_params.client_y
        && pt.y < g_params.client_y + g_params.client_height;
}

void NotifyEventResize()
{
    if (!g_webview) return;
    WINDOWPLACEMENT wp{};
    wp.length = sizeof(WINDOWPLACEMENT);
    GetWindowPlacement(g_hwnd, &wp);
    std::wstring windowState;
    switch (wp.showCmd)
    {
    case SW_SHOWMINIMIZED:
        windowState = L"MINIMIZED";
        break;
    case SW_SHOWMAXIMIZED:
        windowState = L"MAXIMIZED";
        break;
    case SW_SHOWNORMAL:
        windowState = L"NORMAL";
        break;
    //case SW_HIDE:
    //    windowState = L"HIDE";
    //    break;
    }
    std::wstring js = L"((()=>{window.dispatchEvent(new CustomEvent('NativeWindowResize',{detail:{WindowState:'"+windowState+L"'}}))})())";
    g_webview->ExecuteScript(js.c_str(), nullptr);
}

void SeachCaption(bool force=false)
{
    if (!g_webview) return;
    static bool executed = false;
    if (executed && !force) return;
    
    g_webview->ExecuteScript(LR"(((()=>{const allElements=document.querySelectorAll('*');for(const el of allElements){const style=window.getComputedStyle(el);if(style.webkitAppRegion==='drag'||style.appRegion==='drag'){const dpr=window.devicePixelRatio;const rect=el.getBoundingClientRect();return{x:rect.x*dpr,y:rect.y*dpr,width:rect.width*dpr,height:rect.height*dpr}}}return null})()))",
        Callback<ICoreWebView2ExecuteScriptCompletedHandler>(
            [](HRESULT errorCode, LPCWSTR result) -> HRESULT
            {
                std::wstring text = result;
                auto x = wstring_convert(text);
                json js = json::parse(x);
                
                if (!js.is_null())
                {
                    g_params.client_x      = (int)(js["x"     ].get<double>());
                    g_params.client_y      = (int)(js["y"     ].get<double>());
                    g_params.client_width  = (int)(js["width" ].get<double>());
                    g_params.client_height = (int)(js["height"].get<double>());
                    //printf("- set client area : %d, %d, %d, %d\n", g_params.client_x, g_params.client_y, g_params.client_width, g_params.client_height);
                    executed = true;
                }
                return S_OK;
            }).Get());
}

// ---------------- WebView2 初始化 ----------------
void InitWebView2(HWND hwnd)
{
    CreateCoreWebView2EnvironmentWithOptions(
        nullptr, nullptr, nullptr,
        Callback<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler>(
            [hwnd](HRESULT hr, ICoreWebView2Environment* env) -> HRESULT
            {
                //printf("- webview environment status : %d, hwnd : %p\n", FAILED(hr), hwnd);
                if (FAILED(hr)) return hr;

                g_env = env;
                ComPtr<ICoreWebView2Environment3> g_env3;
                g_env.As(&g_env3);
                //printf("- webview environment3 : %p\n", g_env3.Get());
                //HRESULT hr2 = g_env3->CreateCoreWebView2CompositionController(
                HRESULT hr2 = g_env3->CreateCoreWebView2CompositionController(
                    hwnd,
                    Callback<ICoreWebView2CreateCoreWebView2CompositionControllerCompletedHandler>(
                        [hwnd](HRESULT hr, ICoreWebView2CompositionController* controller) -> HRESULT
                        {
                            //printf("- webview status : %d\n", FAILED(hr));
                            if (FAILED(hr)) return hr;

                            ComPtr<ICoreWebView2Controller4> controller4;
                            ComPtr<ICoreWebView2Controller4> controller2;
                            ComPtr<ICoreWebView2Settings> settings;
                            
                            /*g_controller = controller;
                            g_controller.As(&g_compController);
                            g_controller.As(&controller4);*/
                            g_compController = controller;
                            g_compController.As(&g_controller);
                            g_controller.As(&controller4);
                            g_controller.As(&controller2);
                            g_controller->get_CoreWebView2(&g_webview);
                            g_webview->get_Settings(&settings);

                            WebView2DropTarget* dropTarget = new WebView2DropTarget(hwnd, g_compController);

                            controller2->put_DefaultBackgroundColor({ 0, 0, 0, 0 });
                            controller4->put_AllowExternalDrop(true);
                            g_controller->MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC);
                            g_compController->put_RootVisualTarget(g_visual.Get());
                            g_controller->put_ZoomFactor(1);
                            GetClientRect(hwnd, &g_webviewRect);
                            g_controller->put_Bounds(g_webviewRect);// WebView 区域：全窗口
                            g_controller->put_IsVisible(TRUE);      // 让 WebView 可以接收焦点
                            settings->put_IsZoomControlEnabled(FALSE);

                            g_compController->add_CursorChanged(
                                Callback<ICoreWebView2CursorChangedEventHandler>(
                                    [hwnd](ICoreWebView2CompositionController* sender, IUnknown* args) -> HRESULT
                                    {
                                        HCURSOR cursor;
                                        sender->get_Cursor(&cursor);
                                        if (cursor) SetCursor(cursor);
                                        return S_OK;
                                    }).Get(),
                                        nullptr);
                            g_webview->add_PermissionRequested(Callback<ICoreWebView2PermissionRequestedEventHandler>(
                                [](ICoreWebView2* sender, ICoreWebView2PermissionRequestedEventArgs* args) -> HRESULT {
                                    COREWEBVIEW2_PERMISSION_KIND kind;
                                    args->get_PermissionKind(&kind);
                                    if (kind == COREWEBVIEW2_PERMISSION_KIND_CLIPBOARD_READ)
                                        args->put_State(COREWEBVIEW2_PERMISSION_STATE_ALLOW);
                                    return S_OK;
                                }).Get(),
                                    nullptr);
                            g_webview->add_NavigationCompleted(Callback<ICoreWebView2NavigationCompletedEventHandler>(
                                [](ICoreWebView2* sender, ICoreWebView2NavigationCompletedEventArgs* args)
                                -> HRESULT {

                                    if (g_params.memory_size > 0)
                                    {
                                        ComPtr<ICoreWebView2Environment12> env12;
                                        ComPtr<ICoreWebView2_17> webview17;
                                        g_env.As(&env12);
                                        g_webview.As(&webview17);
                                        Trap(env12->CreateSharedBuffer(g_params.memory_size, &g_shared4reader));
                                        Trap(env12->CreateSharedBuffer(g_params.memory_size, &g_shared4writer));
                                        Trap(g_shared4reader->get_Buffer(&r_ptr));
                                        Trap(g_shared4writer->get_Buffer(&w_ptr));
                                        Trap(webview17->PostSharedBufferToScript(g_shared4reader.Get(), COREWEBVIEW2_SHARED_BUFFER_ACCESS_READ_ONLY, L"{\"type\":\"read\"}"));
                                        Trap(webview17->PostSharedBufferToScript(g_shared4writer.Get(), COREWEBVIEW2_SHARED_BUFFER_ACCESS_READ_WRITE, L"{\"type\":\"write\"}"));
                                    }
                                    
                                    return S_OK;
                                }).Get(), NULL);
                            g_webview->add_WebMessageReceived(Callback<ICoreWebView2WebMessageReceivedEventHandler>(
                                [](ICoreWebView2* sender, ICoreWebView2WebMessageReceivedEventArgs* args)
                                -> HRESULT {

                                    LPWSTR message;
                                    Trap(args->TryGetWebMessageAsString(&message));

                                    if (g_listener)
                                    {
                                        try
                                        {
                                            auto s = wstring_convert(message);
                                            //printf("- WebMessage : %s\n", s.c_str());
                                            g_listener(s.c_str());
                                        }
                                        catch (std::exception& e)
                                        {

                                        }
                                        catch (...)
                                        {

                                        }
                                    }

                                    return S_OK;
                                }).Get(), NULL);

                            //g_webview->Navigate(L"https://www.bing.com");
                            //g_webview->Navigate(L"http://172.16.1.166:8081");
                            if (!g_params.url.empty())
                            {
                                //wprintf(L"- url : %s\n", g_params.url.c_str());
                                g_webview->Navigate(g_params.url.c_str());
                            }


                            Trap(g_device->Commit());
                            return S_OK;
                        }).Get());
                //printf("- webview environment complete status : %ld\n", FAILED(hr2));
                return S_OK;
            }).Get());
}

static void print_params()
{
    /*    int width = 960;
    int height = 680;
    int x = CW_USEDEFAULT;
    int y = CW_USEDEFAULT;
    int client_x = 0;
    int client_y = 0; 
    int client_width = 100;
    int client_height = 32;
    std::wstring title = L"Webview2 Viewer";
    std::wstring icon;
    std::wstring url;*/

    printf("params:\n- x : %d\n- y : %d\n- width : %d\n- height : %d\n", g_params.x, g_params.y, g_params.width, g_params.height);
    wprintf(L"- title : %s\n- icon : %s\n- url : %s\n", g_params.title.c_str(), g_params.icon.c_str(), g_params.url.c_str());
    printf("client:\n- x : %d\n- y : %d\n- width : %d\n- height : %d\n", g_params.client_x, g_params.client_y, g_params.client_width, g_params.client_height);
}

void destroy() 
{
    if (g_controller)
    {
        g_controller->Close();
        g_controller = nullptr;
        g_compController = nullptr;
        UnregisterClass(L"WebView2Compositor", GetModuleHandle(NULL));
    }
    //OleUninitialize();
}

// ---------------- WinMain ----------------
//int WINAPI WinMain(HINSTANCE , HINSTANCE, LPSTR, int nCmdShow)
void build()
{
    //print_params();
    //OleInitialize(nullptr);
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    //AttachConsoleForDebug();
    //OleInitialize(nullptr);

    HINSTANCE hInstance = GetModuleHandle(NULL);
    
    WNDCLASS wc = {};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = L"WebView2Compositor";
    wc.hbrBackground = CreateSolidBrush(RGB(50,50,50));//(HBRUSH)(COLOR_WINDOW + 1);
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    if (!g_params.icon.empty())
    wc.hIcon = (HICON)LoadImage(nullptr, g_params.icon.c_str(), IMAGE_ICON, 32, 32, LR_LOADFROMFILE | LR_DEFAULTCOLOR);

    RegisterClass(&wc);

    g_hwnd = CreateWindow(
        wc.lpszClassName,
        g_params.title.c_str(),
        /*WS_OVERLAPPEDWINDOW & ~(WS_CAPTION | WS_THICKFRAME),*/
        WS_OVERLAPPEDWINDOW,
        g_params.x, g_params.y,
        g_params.width, g_params.height,
        nullptr,
        nullptr,
        hInstance,
        nullptr);

    SetWindowPos(g_hwnd, NULL, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE);
    
    // 1. 创建 DComp Device
    // 2. 创建 Target 绑定 HWND
    // 3. 创建根 Visual
    Trap(DCompositionCreateDevice(nullptr, IID_PPV_ARGS(&g_device)));
    Trap(g_device->CreateTargetForHwnd(g_hwnd, TRUE, &g_target));
    Trap(g_device->CreateVisual(&g_visual));
    Trap(g_target->SetRoot(g_visual.Get()));
    //Trap(g_device->Commit());

    //BOOL enable = TRUE;
    //DwmSetWindowAttribute(g_hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, &enable, sizeof(enable));

    //g_params.url = L"http://172.16.1.166:8081";

    InitWebView2(g_hwnd);

    //BOOL val = TRUE;
    //DwmSetWindowAttribute(g_hwnd, DWMWA_NCRENDERING_POLICY, &val, sizeof(val));
    //DWMNCRENDERINGPOLICY policy = DWMNCRP_DISABLED;
    //DwmSetWindowAttribute(g_hwnd, DWMWA_NCRENDERING_POLICY, &policy, sizeof(policy));
    //MARGINS margins = { -1 };
    //DwmExtendFrameIntoClientArea(g_hwnd, &margins);

    ShowWindow(g_hwnd, SW_SHOW);
    UpdateWindow(g_hwnd);

    

    //MSG msg;
    //while (GetMessage(&msg, nullptr, 0, 0))
    //{
    //    TranslateMessage(&msg);
    //    DispatchMessage(&msg);
    //}

    //OleUninitialize();
    //return 0;
}

COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS GetKeys(WPARAM wParam)
{
    COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS keys = COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_NONE;
    if (wParam & MK_LBUTTON) keys |= COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_LEFT_BUTTON;
    if (wParam & MK_RBUTTON) keys |= COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_RIGHT_BUTTON;
    if (wParam & MK_MBUTTON) keys |= COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_MIDDLE_BUTTON;
    if (wParam & MK_SHIFT) keys |= COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_SHIFT;
    if (wParam & MK_CONTROL) keys |= COREWEBVIEW2_MOUSE_EVENT_VIRTUAL_KEYS_CONTROL;
    return keys;
}

POINT GetPoint(HWND hwnd, LPARAM lParam, bool r2s = false)
{
    POINT pt = { GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam) };
    if (r2s) ScreenToClient(hwnd, &pt);
    return pt;
}

void UpdateCursor()
{
    if (!g_compController) return;
    HCURSOR hCursor = nullptr;
    g_compController->get_Cursor(&hCursor);
    if (hCursor) SetCursor(hCursor);
}

// ---------------- WndProc ----------------
LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    if (msg == WM_MOUSEMOVE)
    {
        SeachCaption();
    }
    //if (msg == WM_ERASEBKGND)
    //{
    //    HDC hdc = (HDC)wParam;
    //    RECT rc;
    //    GetClientRect(hwnd, &rc);
    //    HBRUSH hBrush = CreateSolidBrush(RGB(50,50,50));
    //    FillRect(hdc, &rc, hBrush);
    //    DeleteObject(hBrush);
    //    return 1;
    //}
    switch (msg)
    {
    case WM_RBUTTONDOWN:
    case WM_RBUTTONUP:
    case WM_RBUTTONDBLCLK:
    case WM_CONTEXTMENU:
        POINT pt = GetPoint(hwnd, lParam);
        if (msg == WM_CONTEXTMENU)
            ScreenToClient(hwnd, &pt);
        //if (pt.y < 32) return 0;
        //printf("IsCaptionArea")
        if (IsCaptionArea(pt)) return 0;
        break;
    }

    if (msg == WM_NCCALCSIZE && wParam)
    {
        auto* pParams = (NCCALCSIZE_PARAMS*)lParam;
        if (IsZoomed(hwnd))
        {
            HMONITOR hMon = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST);
            MONITORINFO mi = { sizeof(mi) };
            GetMonitorInfo(hMon, &mi);
            pParams->rgrc[0] = mi.rcWork;
        }
        else
        {
            pParams->rgrc[0].left += 7;
            //pParams->rgrc[0].top += 1;
            pParams->rgrc[0].right -= 7;
            pParams->rgrc[0].bottom -= 7;
            //SetWindowPos(g_hwnd, NULL, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE);
        }
        return 0;
    }
    if (msg == WM_NCHITTEST)
    {
        
        auto pt = GetPoint(hwnd, lParam, true);
        //printf("WM_NCHITTEST %d    %d, %d   %d, %d, %d, %d\n", IsCaptionArea(pt), pt.x, pt.y, );
        if (pt.y < 7)  return HTTOP;
        //if (pt.y < 32) return HTCAPTION;
        if (IsCaptionArea(pt)) return HTCAPTION;
    }
    else if (msg == WM_NCRBUTTONUP && wParam == HTCAPTION)
    {
        HMENU hSysMenu = GetSystemMenu(hwnd, FALSE);
        if (hSysMenu)
        {
            POINT pt = GetPoint(hwnd, lParam);
            UINT cmd = TrackPopupMenu(hSysMenu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, hwnd, NULL);
            if (cmd != 0)
                SendMessageW(hwnd, WM_SYSCOMMAND, cmd, 0);
        }
        return 0;
    }
    if (g_controller)
    {
        switch (msg)
        {
        case WM_SIZE:
            //if (wParam == SIZE_RESTORED || wParam == SIZE_MAXIMIZED)
            //{
                GetClientRect(hwnd, &g_webviewRect);
                g_controller->put_Bounds(g_webviewRect);
                SeachCaption(true);
                NotifyEventResize();
            //}
            break;
        case WM_MBUTTONDOWN:
            g_compController->SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_MIDDLE_BUTTON_DOWN, GetKeys(wParam), 0, GetPoint(hwnd, lParam));
            SetCapture(hwnd);
            UpdateCursor();
            break;
        case WM_LBUTTONDOWN:
            g_compController->SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_LEFT_BUTTON_DOWN, GetKeys(wParam), 0, GetPoint(hwnd, lParam));
            SetCapture(hwnd);
            UpdateCursor();
            break;
        case WM_RBUTTONDOWN:
            g_compController->SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_RIGHT_BUTTON_DOWN, GetKeys(wParam), 0, GetPoint(hwnd, lParam));
            SetCapture(hwnd);
            UpdateCursor();
            break;
        case WM_MBUTTONUP:
            g_compController->SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_MIDDLE_BUTTON_UP, GetKeys(wParam), 0, GetPoint(hwnd, lParam));
            ReleaseCapture();
            UpdateCursor();
            break;
        case WM_LBUTTONUP:
            g_compController->SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_LEFT_BUTTON_UP, GetKeys(wParam), 0, GetPoint(hwnd, lParam));
            ReleaseCapture();
            UpdateCursor();
            break;
        case WM_RBUTTONUP:
            g_compController->SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_RIGHT_BUTTON_UP, GetKeys(wParam), 0, GetPoint(hwnd, lParam));
            ReleaseCapture();
            UpdateCursor();
            break;
        case WM_MOUSELEAVE:
            g_tracking = false;
            g_compController->SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_MOVE, GetKeys(wParam), 0, GetPoint(hwnd, lParam));
            UpdateCursor();
            break;
        case WM_MOUSEMOVE:
            if (!g_tracking)
            {
                TRACKMOUSEEVENT tme = {};
                tme.cbSize = sizeof(TRACKMOUSEEVENT);
                tme.dwFlags = TME_HOVER | TME_LEAVE;
                tme.hwndTrack = hwnd;
                TrackMouseEvent(&tme);
                g_tracking = true;
            }
            g_compController->SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_MOVE, GetKeys(wParam), 0, GetPoint(hwnd, lParam));
            UpdateCursor();
            break;
        case WM_MOUSEWHEEL:
            g_compController->SendMouseInput(COREWEBVIEW2_MOUSE_EVENT_KIND_WHEEL, GetKeys(wParam), GET_WHEEL_DELTA_WPARAM(wParam), GetPoint(hwnd, lParam));
            UpdateCursor();
            break;
        case WM_DPICHANGED:
        case WM_WINDOWPOSCHANGED:
            g_controller->NotifyParentWindowPositionChanged();
            break;
        //case WM_SETFOCUS:
        //    g_controller->MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC);
        //    break;
        default:;
        }
    }

    if (msg == WM_DESTROY)
    {
        //destroy();
        PostQuitMessage(0);
        //exit(0);
    }
    //else if (msg == WM_CREATE || msg == WM_SIZE || msg == WM_DWMCOMPOSITIONCHANGED)
    //{
    //    MARGINS margins = { -1 };
    //    DwmExtendFrameIntoClientArea(hwnd, &margins);
    //}

    return DefWindowProc(hwnd, msg, wParam, lParam);
}

std::wstring convert_wstring(const std::string& str) {
    if (str.empty()) return {};
    const UINT code_page = CP_UTF8;
    const int len = MultiByteToWideChar(code_page, 0,
        str.c_str(), -1, nullptr, 0);
    if (len == 0) return {};
    std::wstring w_str(len - 1, L'\0');
    MultiByteToWideChar(code_page, 0,
        str.c_str(), -1, &w_str[0], len);
    return w_str;
}

std::string wstring_convert(const std::wstring& wstr) {
    if (wstr.empty()) return std::string();
    int len = WideCharToMultiByte(
        CP_UTF8, 0, wstr.data(),
        static_cast<int>(wstr.size()),
        nullptr, 0, nullptr, nullptr);
    if (len == 0) return std::string();
    std::string str(len, 0);
    WideCharToMultiByte(CP_UTF8, 0, wstr.data(),
        static_cast<int>(wstr.size()),
        &str[0], len, nullptr, nullptr);
    return str;
}