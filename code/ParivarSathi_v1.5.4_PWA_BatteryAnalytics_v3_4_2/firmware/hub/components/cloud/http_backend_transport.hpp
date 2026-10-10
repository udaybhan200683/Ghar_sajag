#pragma once
#include "cloud/cloud_sync.hpp"

namespace gs::hub {

// One synchronous HTTP request/response on the configured authenticated channel.
// The channel owns credentials, TLS trust/hostname checks, framing and timeouts.
// It must not set server_authenticated for plaintext or unverified TLS.
struct BackendHttpResponse {
    unsigned status{0};
    bool server_authenticated{false};
    bool message_complete{false};
    std::string body;
};
class BackendHttpChannel {
public:
    virtual ~BackendHttpChannel() = default;
    virtual BackendHttpResponse post(const std::string& path, const std::string& body) = 0;
};

class HttpBackendTransport final : public CloudBackendTransport {
public:
    static constexpr std::size_t kMaximumRequestBytes = 2048;
    static constexpr std::size_t kMaximumResponseBytes = 1024;
    explicit HttpBackendTransport(BackendHttpChannel& channel) : channel_(channel) {}
    BackendCommitReply submit(const BackendCommitRequest& request) override;
    // Decode only the established EventKey/COMMITTED/duplicate response grammar.
    // No transport success, 202, simulator DURABLE_MODEL or truncated JSON is a receipt.
    static BackendCommitReply decode(const BackendCommitRequest& request,
                                     const BackendHttpResponse& response);
private:
    BackendHttpChannel& channel_;
};
} // namespace gs::hub
