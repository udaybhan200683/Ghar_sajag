#pragma once

#if !defined(GS40_TEST_ONLY_CLOUDSYNC_BUILD) || !GS40_TEST_ONLY_CLOUDSYNC_BUILD
#error "TEST_ONLY runtime entry points are forbidden in commercial builds"
#endif

#include "gs40_test_only_bootstrap.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "esp_err.h"

namespace gs::hub { class BackendHttpChannel; }

namespace gs::hub::target {

// Bounded USB Serial/JTAG one-session config receive. The root is the
// TEST_ONLY public config-signing key embedded by the isolated build profile.
esp_err_t gs40_test_only_receive_config(Gs40TestOnlyRuntimeConfig& config);
esp_err_t gs40_test_only_connect_wifi(Gs40TestOnlyRuntimeConfig& config);
bool gs40_test_only_apply_activity_home(
    const Gs40TestOnlyRuntimeConfig& config,
    const CloudAuthorityBinding& current_authority,
    HubRuntime& runtime);
enum class Gs40TestOnlyConfigSyncResult {
    Unavailable,
    NoDesired,
    PolicyReady,
    Applied,
    AppliedAckPending,
    Rejected,
};
struct Gs40TestOnlyHouseholdPolicy {
    gs::HomeConfig home;
    CloudAuthorityBinding authority;
};
Gs40TestOnlyConfigSyncResult gs40_test_only_fetch_household_config(
    const Gs40TestOnlyRuntimeConfig& config,
    const CloudAuthorityBinding& current_authority,
    gs::hub::BackendHttpChannel& channel,
    Gs40TestOnlyHouseholdPolicy& policy);
bool gs40_test_only_apply_household_config(
    const Gs40TestOnlyRuntimeConfig& config,
    const Gs40TestOnlyHouseholdPolicy& policy,
    HubRuntime& runtime);
bool gs40_test_only_ack_household_config(
    const Gs40TestOnlyRuntimeConfig& config,
    const CloudAuthorityBinding& authority,
    std::uint32_t version,
    gs::hub::BackendHttpChannel& channel);
Gs40TestOnlyConfigSyncResult gs40_test_only_sync_household_config(
    const Gs40TestOnlyRuntimeConfig& config,
    const CloudAuthorityBinding& current_authority,
    HubRuntime& runtime,
    gs::hub::BackendHttpChannel& channel);
bool gs40_test_only_local_minute(const Gs40TestOnlyRuntimeConfig& config,
                                 EpochSeconds trusted_utc,
                                 std::uint16_t& local_minute);
bool gs40_test_only_local_minute(const Gs40TestOnlyRuntimeConfig& config,
                                 const HubRuntime& runtime,
                                 EpochSeconds trusted_utc,
                                 std::uint16_t& local_minute);
esp_err_t gs40_test_only_refresh_time(
    const Gs40TestOnlyRuntimeConfig& config,
    AuthenticatedHubTimeProvider& time_provider);
esp_err_t gs40_test_only_bootstrap_time(
    const Gs40TestOnlyRuntimeConfig& config,
    AuthenticatedTimeFloorStore& floor_store,
    AuthenticatedHubTimeProvider& time_provider);

}  // namespace gs::hub::target
