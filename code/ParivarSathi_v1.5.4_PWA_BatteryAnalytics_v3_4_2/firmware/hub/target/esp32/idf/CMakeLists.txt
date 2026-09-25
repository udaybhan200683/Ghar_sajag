cmake_minimum_required(VERSION 3.16)

option(GS_HIL_BUILD "Enable the USB HIL control plane (never for release images)" OFF)
option(GS_HIL_CONTROL "Enable test-only UART controls while retaining product security/runtime paths" OFF)
if(GS_HIL_BUILD)
    set(GS_HIL_CONTROL ON)
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(gs_hw_m1_hub)
