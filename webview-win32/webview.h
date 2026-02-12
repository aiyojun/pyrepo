#pragma once

#ifdef WPL_API__
#define WPL_API __declspec(dllexport)
#else
#define WPL_API __declspec(dllimport)
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*MessageListener)(const char*);

WPL_API void set_title(char* title);

WPL_API void set_position(int x, int y);

WPL_API void set_listener(MessageListener listener);

WPL_API void set_client(int x, int y, int width, int height);

WPL_API void set_navigation(char* url);

WPL_API void set_icon(char* path);

WPL_API void set_size(int width, int height);

WPL_API void set_memory(int length);

WPL_API void* get_window();

WPL_API int read(unsigned char* p, int size);

WPL_API int write(unsigned char* p, int size);

WPL_API void post(char* message);

WPL_API void build();

WPL_API void destroy();

#ifdef __cplusplus
}
#endif