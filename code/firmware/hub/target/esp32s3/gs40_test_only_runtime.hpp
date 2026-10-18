#pragma once

#if !defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD
#error "TEST_ONLY runtime entry points are forbidden in commercial builds"
#endif

#include "gs40_test_only_bootstrap.hpp"
#include "esp_err.h"

namespace gs::hub::target {

// Bounded USB Serial/JTAG one-session config receive. The root is the
// TEST_ONLY public config-signing key embedded by the isolated build profile.
esp_err_t gs40_test_only_receive_config(Gs40TestOnlyRuntimeConfig& config);
esp_err_t gs40_test_only_connect_wifi(Gs40TestOnlyRuntimeConfig& config);
esp_err_t gs40_test_only_bootstrap_time(
    const Gs40TestOnlyRuntimeConfig& config,
    AuthenticatedTimeFloorStore& floor_store,
    AuthenticatedHubTimeProvider& time_provider);

}  // namespace gs::hub::target
