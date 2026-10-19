#pragma once
#include "cloud_sync/cloud_sync.hpp"

namespace gs::hub {

// One synchronous HTTP request/response on the configured authenticated channel.
// The channel owns credentials, TLS trust/hostname checks, framing and timeouts.
// It must not set server_authenticated for plaintext or unverified TLS.
struct BackendHttpResponse {
    unsigned status{0};
    bool server_authenticated{false};
    bool message_complete{false};
    std::string body;
    // True once the channel starts opening the remote request. Diagnostics use
    // this to distinguish a local fail-closed preflight from a network failure.
    bool network_attempted{false};
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
    NodeHealthReply submit_node_health(const CloudAuthorityBinding& binding,
                                       const NodeHealthPublication& publication) override;
    HubRuleDecisionReply submit_hub_rule_decision(const CloudAuthorityBinding& binding,
                                                  const HubRuleDecisionRequest& request) override;
    // Retry the exact bytes recovered from the authenticated Hub-owned outbox.
    HubRuleDecisionReply submit_hub_rule_decision_body(const CloudAuthorityBinding& binding,
                                                       const std::string& decision_id,
                                                       const std::string& body);
    // Decode only the established EventKey/COMMITTED/duplicate response grammar.
    // No transport success, 202, simulator DURABLE_MODEL or truncated JSON is a receipt.
    static BackendCommitReply decode(const BackendCommitRequest& request,
                                     const BackendHttpResponse& response);
private:
    BackendHttpChannel& channel_;
};
} // namespace gs::hub
