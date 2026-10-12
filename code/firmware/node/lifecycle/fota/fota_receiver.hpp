#pragma once

#include "firmware/common/transport/fota_protocol.hpp"

#include <cstddef>
#include <cstdint>

namespace gs::node::fota_receiver {

// Hardware boundary for the production receiver. Implementations own any
// platform handles/partitions; the receiver owns all protocol and policy.
class IOtaWriter {
public:
    virtual ~IOtaWriter() = default;
    virtual std::size_t capacity() = 0;
    virtual bool begin(std::size_t image_size) = 0;
    virtual bool write(const std::uint8_t* data, std::size_t size) = 0;
    virtual bool finalize() = 0;
    virtual bool commit_boot() = 0;
    virtual void abort() = 0;
};

class IReceiverCallbacks {
public:
    virtual ~IReceiverCallbacks() = default;
    virtual void send_ack(const gs::fota::Ack& ack) = 0;
    virtual void set_maintenance(bool active) = 0;
    virtual void report_timeout() = 0;
    virtual void request_restart() = 0;
};

struct Snapshot {
    bool active{false};
    bool completion_requested{false};
    std::uint32_t session_id{0};
    std::uint32_t expected_sequence{0};
    std::uint32_t expected_size{0};
    std::uint32_t bytes_written{0};
};

class Receiver {
public:
    static constexpr std::uint64_t kInactivityTimeoutMs = 30000U;

    Receiver(IOtaWriter& writer, IReceiverCallbacks& callbacks)
        : writer_(writer), callbacks_(callbacks) {}

    // Returns false only for a frame outside the FOTA wire protocol. Such
    // frames are deliberately ignored, matching the target receiver.
    bool process(const gs::fota::Packet& packet, std::uint64_t now_ms);
    void poll(std::uint64_t now_ms);
    Snapshot snapshot() const;

private:
    void handle_begin(const gs::fota::Packet& packet, std::uint64_t now_ms);
    void handle_data(const gs::fota::Packet& packet, std::uint64_t now_ms);
    void handle_end(const gs::fota::Packet& packet);
    void send_ack(std::uint32_t session_id, gs::fota::Status status,
                  std::uint32_t sequence);
    void reset(bool abort_writer);

    IOtaWriter& writer_;
    IReceiverCallbacks& callbacks_;
    bool active_{false};
    bool completion_requested_{false};
    std::uint32_t session_id_{0};
    std::uint32_t expected_sequence_{0};
    std::uint32_t expected_size_{0};
    std::uint32_t expected_crc_{0};
    std::uint32_t bytes_written_{0};
    std::uint32_t running_crc_{0};
    std::uint64_t last_activity_ms_{0};
};

}  // namespace gs::node::fota_receiver
