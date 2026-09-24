#pragma once

#include "esp_err.h"

namespace gs::hub::target {

esp_err_t start_fota_sender();
#if GS_HIL_BUILD
// Test-only UART control hook. Returns false when a transfer is already queued.
bool hil_request_fota();
#endif

}  // namespace gs::hub::target
