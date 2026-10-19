#pragma once

namespace gs::hub::connectivity {

// Notify the S3 station owner only after a credential generation has been
// loaded from or committed to the approved encrypted credential store.
// This call never persists credentials or grants installer/Home authority.
void notify_s3_wifi_credentials_ready();

}  // namespace gs::hub::connectivity
