cmake_minimum_required(VERSION 3.16)

option(GS_HIL_BUILD "Enable the USB HIL control plane (never for release images)" OFF)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(gs_hw_m1_node)
