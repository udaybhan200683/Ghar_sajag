cmake_minimum_required(VERSION 3.16)

option(GS_HIL_BUILD "Enable the USB HIL control plane (never for release images)" OFF)
option(GS_HIL_CONTROL "Enable test-only UART controls while retaining product security/runtime paths" OFF)
option(GS_BAT_C8_PHYSICAL_WAKE "Allow real GPIO4/timer light sleep in the HIL-control qualification image" OFF)
if(GS_HIL_BUILD)
    set(GS_HIL_CONTROL ON)
endif()
if(GS_BAT_C8_PHYSICAL_WAKE AND (NOT GS_HIL_CONTROL OR GS_HIL_BUILD))
    message(FATAL_ERROR "GS_BAT_C8_PHYSICAL_WAKE requires GS_HIL_CONTROL=ON and GS_HIL_BUILD=OFF")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(gs_hw_m1_node)
