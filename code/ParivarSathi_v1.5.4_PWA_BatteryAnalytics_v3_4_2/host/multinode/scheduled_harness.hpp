#pragma once

#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/hub/components/registry/node_registry.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "firmware/node/components/storage/node_recovery_persistence.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"
#include "firmware/common/security/runtime_frame_security.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <limits>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace gs::host::multinode {

// Host-only scheduled transport. It uses production NodeRuntime, commissioning
// protocol, registry, wire codec, HubRuntime, journal, and ACK rules. It does
// not emulate RF or target credential storage.
struct NodeSnapshot {
    std::string physical_id;
    std::string logical_id;
    std::string location;
    std::uint64_t session{0};
    std::uint64_t next_sequence{0};
    std::size_t retained{0};
    std::size_t pending{0};
    std::uint64_t uplink_attempts{0};
    std::uint64_t hub_admissions{0};
    std::uint64_t matching_acks{0};
    std::uint64_t ack_mismatches{0};
    std::uint64_t stale_acks{0};
    std::uint64_t registry_rejections{0};
    std::uint64_t ingress_rejections{0};
    std::uint64_t application_rejections{0};
    std::uint64_t volatile_receipts{0};
    std::uint64_t maximum_ack_latency_ms{0};
    bool commissioned{false};
};

class ScheduledHarness {
public:
    explicit ScheduledHarness(std::size_t count, std::size_t journal_capacity = 1024);
    ~ScheduledHarness();
    std::optional<EventKey> record(std::size_t index, EventKind kind = EventKind::Motion);
    void set_hub_online(bool online) { hub_online_ = online; }
    void set_hub_processing_budget(std::size_t per_tick) { hub_processing_budget_ = per_tick; }
    void set_node_online(std::size_t index, bool online);
    void drop_next_ack(std::size_t index);
    void redirect_next_ack(std::size_t from_index, std::size_t to_index);
    hub::RegistryResult remove_node(std::size_t index);
    bool restart_node(std::size_t index);
    void advance(Milliseconds delta_ms);
    void run_until_quiet(Milliseconds maximum_ms = 5000);
    NodeSnapshot snapshot(std::size_t index) const;
    std::size_t node_count() const { return nodes_.size(); }
    std::size_t journal_size() { return hub_.journal().size(); }
    std::size_t ingest_depth() const { return hub_.ingest_depth(); }
    std::size_t ingest_high_water() const { return hub_.ingest_high_water(); }
    std::size_t ingest_rejected() const { return hub_.ingest_rejected(); }
    bool contains(const EventKey& key);
    Milliseconds now_ms() const { return now_ms_; }

private:
    struct MemoryRecoveryBlob final : gs::security::SecurityBlobStore {
        bool read(gs::security::Bytes& out, bool& found) override {
            out = bytes;
            found = present;
            return true;
        }
        bool write(const gs::security::Bytes& blob) override {
            bytes = blob;
            present = true;
            return true;
        }
        gs::security::Bytes bytes;
        bool present{false};
    };
    struct Node {
        std::string physical_id;
        std::string logical_id;
        std::string location;
        std::array<std::uint8_t, 6> radio_mac{};
        std::uint64_t session{1};
        std::unique_ptr<node::NodeRuntime> runtime;
        std::unique_ptr<gs::security::CommissioningBinding> node_binding;
        std::unique_ptr<gs::security::CommissioningBinding> hub_binding;
        gs::security::Key32 recovery_key{};
        std::unique_ptr<MemoryRecoveryBlob> recovery_blob;
        std::unique_ptr<node::NodeRecoveryRepository> recovery_repository;
        bool online{true};
        bool drop_ack{false};
        std::optional<std::size_t> redirect_ack_to;
        std::uint64_t uplink_attempts{0};
        std::uint64_t hub_admissions{0};
        std::uint64_t matching_acks{0};
        std::uint64_t ack_mismatches{0};
        std::uint64_t stale_acks{0};
        std::uint64_t registry_rejections{0};
        std::uint64_t ingress_rejections{0};
        std::uint64_t application_rejections{0};
        std::uint64_t volatile_receipts{0};
        std::uint64_t maximum_ack_latency_ms{0};
        std::unique_ptr<gs::security::RuntimeFrameSecurity> node_security;
        std::unique_ptr<gs::security::RuntimeFrameSecurity> hub_security;
        bool commissioned{false};
    };
    struct Frame {
        enum class Direction { Uplink, Ack } direction;
        std::size_t node_index;
        gs::security::SecureFrame wire;
        Milliseconds due_ms;
        Milliseconds originated_ms;
    };
    struct Admitted {
        std::size_t node_index;
        Milliseconds originated_ms;
    };

    void send_due_nodes();
    void deliver_due_frames();
    void deliver(const Frame& frame);
    void process_hub_events();
    bool establish_session(Node& node, std::uint64_t last_session);
    void commit_recovery(Node& node);

    hub::HubRuntime hub_;
    hub::NodeRegistry registry_;
    host::security::OpenSslCommissioningCrypto crypto_;
    std::vector<Node> nodes_;
    std::vector<Frame> frames_;
    std::deque<Admitted> admitted_;
    Milliseconds now_ms_{0};
    bool hub_online_{true};
    std::size_t hub_processing_budget_{std::numeric_limits<std::size_t>::max()};
};

}  // namespace gs::host::multinode
