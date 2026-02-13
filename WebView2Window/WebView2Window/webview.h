#pragma once

#ifdef WV2_API__
#define WV2_API __declspec(dllexport)
#else
#define WV2_API __declspec(dllimport)
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*MessageListener)(const char*);

WV2_API void set_title(char* title);

WV2_API void set_position(int x, int y);

WV2_API void set_listener(MessageListener listener);

WV2_API void set_client(int x, int y, int width, int height);

WV2_API void set_navigation(char* url);

WV2_API void set_icon(char* path);

WV2_API void set_size(int width, int height);

WV2_API void set_memory(int length);

WV2_API void* get_window();

WV2_API void build();

WV2_API void destroy();

WV2_API int read(unsigned char* p, int size);

WV2_API int write(unsigned char* p, int size);

WV2_API void post(char* message);

WV2_API void preload(char* script);

WV2_API void evaluate(char* script, MessageListener callback);

#ifdef __cplusplus
}
#endif