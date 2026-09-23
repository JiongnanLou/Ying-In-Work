cmake_minimum_required(VERSION 3.16)
project(link_camera_bridge LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(LINK_SDK_DIR "" CACHE PATH "Insta360 Windows x64 SDK directory")
if(NOT EXISTS "${LINK_SDK_DIR}/include/uvc_camera.h")
    message(FATAL_ERROR "Set -DLINK_SDK_DIR to the official Windows x64 SDK directory")
endif()
add_executable(link_camera_bridge link_camera_bridge.cc)
if(MSVC)
    target_compile_options(link_camera_bridge PRIVATE /utf-8)
endif()
target_include_directories(link_camera_bridge PRIVATE "${LINK_SDK_DIR}/include")
target_link_directories(link_camera_bridge PRIVATE "${LINK_SDK_DIR}/lib")
target_link_libraries(link_camera_bridge PRIVATE UVCCamera llog)

add_custom_command(TARGET link_camera_bridge POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${LINK_SDK_DIR}/bin/UVCCamera.dll"
        "$<TARGET_FILE_DIR:link_camera_bridge>/UVCCamera.dll")
