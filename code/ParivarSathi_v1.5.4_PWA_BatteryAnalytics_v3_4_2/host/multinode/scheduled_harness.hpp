#pragma once

#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/hub/components/registry/node_registry.hpp"
#include "firmware/node/runtime/node_runtime.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace gs::host::multinode {

// Host-only scheduled transport. It uses production NodeRuntime, wire codec,
// HubRuntime, journal, and ACK rules. It does not emulate RF or authentication.
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
    std::uint64_t registry_rejections{0};
    std::uint64_t maximum_ack_latency_ms{0};
};

class ScheduledHarness {
public:
    explicit ScheduledHarness(std::size_t count, std::size_t journal_capacity = 1024);
    std::optional<EventKey> record(std::size_t index, EventKind kind = EventKind::Motion);
    void set_hub_online(bool online) { hub_online_ = online; }
    void set_node_online(std::size_t index, bool online);
    void drop_next_ack(std::size_t index);
    hub::RegistryResult remove_node(std::size_t index);
    void advance(Milliseconds delta_ms);
    void run_until_quiet(Milliseconds maximum_ms = 5000);
    NodeSnapshot snapshot(std::size_t index) const;
    std::size_t node_count() const { return nodes_.size(); }
    std::size_t journal_size() { return hub_.journal().size(); }
    bool contains(const EventKey& key) { return hub_.journal().contains(key); }
    Milliseconds now_ms() const { return now_ms_; }

private:
    struct Node {
        std::string physical_id;
        std::string logical_id;
        std::string location;
        std::array<std::uint8_t, 6> radio_mac{};
        std::uint64_t session{1};
        std::unique_ptr<node::NodeRuntime> runtime;
        bool online{true};
        bool drop_ack{false};
        std::uint64_t uplink_attempts{0};
        std::uint64_t hub_admissions{0};
        std::uint64_t matching_acks{0};
        std::uint64_t ack_mismatches{0};
        std::uint64_t registry_rejections{0};
        std::uint64_t maximum_ack_latency_ms{0};
    };
    struct Frame {
        enum class Direction { Uplink, Ack } direction;
        std::size_t node_index;
        transport::EncodedFrame wire;
        Milliseconds due_ms;
        Milliseconds originated_ms;
    };

    void send_due_nodes();
    void deliver_due_frames();
    void deliver(const Frame& frame);

    hub::HubRuntime hub_;
    hub::NodeRegistry registry_;
    std::vector<Node> nodes_;
    std::vector<Frame> frames_;
    Milliseconds now_ms_{0};
    bool hub_online_{true};
};

}  // namespace gs::host::multinode
