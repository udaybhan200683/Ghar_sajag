#pragma once

namespace gs::hub::target {

// The authenticated fixture envelope and initialized Wi-Fi radio are local
// Hub prerequisites. A working station route and authenticated signed time
// are separate CloudSync prerequisites and must not disable local Node service.
constexpr bool gs40_test_only_local_hub_start_allowed(
    bool authenticated_config_ready, bool wifi_driver_ready) {
    return authenticated_config_ready && wifi_driver_ready;
}

constexpr bool gs40_test_only_cloud_bootstrap_ready(
    bool authenticated_config_ready, bool station_connected,
    bool authenticated_time_ready) {
    return authenticated_config_ready && station_connected && authenticated_time_ready;
}

}  // namespace gs::hub::target
