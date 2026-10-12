#pragma once

#include "esp_err.h"

#include <string>

namespace gs::hub::target {

esp_err_t start_fota_sender();
#if !GS_HIL_BUILD
struct FotaStartRequest {
    std::string physical_device_id;
    std::string board;
    std::string version;
};
// Internal product request boundary; there is no external authorized caller.
// Queue acceptance is not transfer success or image authenticity.
bool request_authenticated_fota(FotaStartRequest request);
#endif
#if GS_HIL_BUILD
// Test-only UART control hook. Returns false when a transfer is already queued.
bool hil_request_fota();
#endif
#if GS_HIL_CONTROL && !GS_HIL_BUILD
// Test-only entry to the authenticated production sender. The owner still
// resolves enrollment and session state; the UART control owns no keys.
bool hil_request_authenticated_fota(FotaStartRequest request);
#endif

}  // namespace gs::hub::target
