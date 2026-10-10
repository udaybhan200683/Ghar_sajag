#pragma once
#include "cloud/http_backend_transport.hpp"

namespace gs::hub::target {
// Deployment supplies the existing endpoint's trust anchor and opaque HTTP
// Authorization value. This does not define or provision a credential scheme.
// No secrets/configuration are compiled into the firmware. Missing configuration
// refuses all requests. Production Hub middleware/provisioning remains a gate.
class HttpsBackendChannel final : public BackendHttpChannel {
public:
    HttpsBackendChannel(std::string origin, std::string trusted_ca,
                        std::string authorization);
    ~HttpsBackendChannel() override;
    BackendHttpResponse post(const std::string& path, const std::string& body) override;
private:
    std::string origin_, trusted_ca_, authorization_;
};
}
