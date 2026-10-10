# Shared C3/S3 packaging. No persistent configuration partition or runtime writes.
set(GS_NODE_HEALTH_CONFIG "${GS_ROOT}/config/node_health.json" CACHE FILEPATH "GS-40 JSON firmware input")
set(GS_NODE_HEALTH_GENERATED "${CMAKE_BINARY_DIR}/gs40_generated")
execute_process(COMMAND "${PYTHON}" "${GS_ROOT}/scripts/generate_node_health_config.py"
    --config "${GS_NODE_HEALTH_CONFIG}"
    --output "${GS_NODE_HEALTH_GENERATED}/gs/node_health_config.hpp"
    RESULT_VARIABLE GS_CONFIG_RESULT OUTPUT_VARIABLE GS_CONFIG_DIGEST ERROR_VARIABLE GS_CONFIG_ERROR)
if(NOT GS_CONFIG_RESULT EQUAL 0)
    message(FATAL_ERROR "GS-40 configuration validation failed: ${GS_CONFIG_ERROR}")
endif()
message(STATUS "${GS_CONFIG_DIGEST}")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${GS_NODE_HEALTH_CONFIG}"
    "${GS_ROOT}/scripts/generate_node_health_config.py"
    "${GS_ROOT}/backend/ghar_sajag/node_health_policy.py")
