#include "firmware/common/transport/data_plane_codec.hpp"

#include <limits>
#include <string>
#include <utility>

namespace gs::transport {
namespace {

constexpr std::size_t kHeaderBytes = 8U;
constexpr std::uint8_t kOccurredAtPresent = 1U << 0U;
constexpr std::uint8_t kPowerPresent = 1U << 1U;
constexpr std::uint8_t kIsTest = 1U << 2U;
constexpr std::uint8_t kKnownFlags = kOccurredAtPresent | kPowerPresent | kIsTest;

class Writer {
public:
    explicit Writer(EncodedFrame& frame) : frame_(frame) {}

    bool u8(std::uint8_t value) {
        if (!space(1U)) return false;
        frame_.bytes[position_++] = value;
        return true;
    }

    bool u16(std::uint16_t value) {
        return u8(static_cast<std::uint8_t>((value >> 8U) & 0xFFU)) &&
               u8(static_cast<std::uint8_t>(value & 0xFFU));
    }

    bool i16(std::int16_t value) {
        const auto encoded = value >= 0
            ? static_cast<std::uint16_t>(value)
            : static_cast<std::uint16_t>(
                  std::numeric_limits<std::uint16_t>::max() -
                  static_cast<std::uint16_t>(-(static_cast<std::int32_t>(value) + 1)));
        return u16(encoded);
    }

    bool u32(std::uint32_t value) {
        return u8(static_cast<std::uint8_t>((value >> 24U) & 0xFFU)) &&
               u8(static_cast<std::uint8_t>((value >> 16U) & 0xFFU)) &&
               u8(static_cast<std::uint8_t>((value >> 8U) & 0xFFU)) &&
               u8(static_cast<std::uint8_t>(value & 0xFFU));
    }

    bool u64(std::uint64_t value) {
        for (int shift = 56; shift >= 0; shift -= 8) {
            if (!u8(static_cast<std::uint8_t>((value >> shift) & 0xFFU))) return false;
        }
        return true;
    }

    bool i64(std::int64_t value) {
        const auto encoded = value >= 0
            ? static_cast<std::uint64_t>(value)
            : std::numeric_limits<std::uint64_t>::max() -
                  static_cast<std::uint64_t>(-(value + 1));
        return u64(encoded);
    }

    bool string8(const std::string& value, std::size_t maximum) {
        if (value.size() > maximum || value.size() > 0xFFU) return false;
        if (!u8(static_cast<std::uint8_t>(value.size())) || !space(value.size())) return false;
        for (const char byte : value) frame_.bytes[position_++] = static_cast<std::uint8_t>(byte);
        return true;
    }

    bool finish(FrameType type) {
        if (position_ < kHeaderBytes) return false;
        const auto payload_size = position_ - kHeaderBytes;
        if (payload_size > std::numeric_limits<std::uint16_t>::max()) return false;
        frame_.bytes[0] = static_cast<std::uint8_t>((kDataPlaneMagic >> 24U) & 0xFFU);
        frame_.bytes[1] = static_cast<std::uint8_t>((kDataPlaneMagic >> 16U) & 0xFFU);
        frame_.bytes[2] = static_cast<std::uint8_t>((kDataPlaneMagic >> 8U) & 0xFFU);
        frame_.bytes[3] = static_cast<std::uint8_t>(kDataPlaneMagic & 0xFFU);
        frame_.bytes[4] = kDataPlaneVersion;
        frame_.bytes[5] = static_cast<std::uint8_t>(type);
        frame_.bytes[6] = static_cast<std::uint8_t>((payload_size >> 8U) & 0xFFU);
        frame_.bytes[7] = static_cast<std::uint8_t>(payload_size & 0xFFU);
        frame_.size = position_;
        return true;
    }

    bool reserve_header() {
        if (!space(kHeaderBytes)) return false;
        position_ = kHeaderBytes;
        return true;
    }

private:
    bool space(std::size_t count) const {
        return count <= frame_.bytes.size() - position_;
    }

    EncodedFrame& frame_;
    std::size_t position_{0};
};

class Reader {
public:
    Reader(const std::uint8_t* data, std::size_t size) : data_(data), size_(size) {}

    bool u8(std::uint8_t& value) {
        if (!available(1U)) return false;
        value = data_[position_++];
        return true;
    }

    bool u16(std::uint16_t& value) {
        std::uint8_t high = 0;
        std::uint8_t low = 0;
        if (!u8(high) || !u8(low)) return false;
        value = static_cast<std::uint16_t>((static_cast<std::uint16_t>(high) << 8U) | low);
        return true;
    }

    bool i16(std::int16_t& value) {
        std::uint16_t encoded = 0;
        if (!u16(encoded)) return false;
        if (encoded <= static_cast<std::uint16_t>(std::numeric_limits<std::int16_t>::max())) {
            value = static_cast<std::int16_t>(encoded);
        } else {
            value = static_cast<std::int16_t>(
                -1 - static_cast<std::int32_t>(std::numeric_limits<std::uint16_t>::max() - encoded));
        }
        return true;
    }

    bool u32(std::uint32_t& value) {
        value = 0;
        for (int index = 0; index < 4; ++index) {
            std::uint8_t byte = 0;
            if (!u8(byte)) return false;
            value = (value << 8U) | byte;
        }
        return true;
    }

    bool u64(std::uint64_t& value) {
        value = 0;
        for (int index = 0; index < 8; ++index) {
            std::uint8_t byte = 0;
            if (!u8(byte)) return false;
            value = (value << 8U) | byte;
        }
        return true;
    }

    bool i64(std::int64_t& value) {
        std::uint64_t encoded = 0;
        if (!u64(encoded)) return false;
        if (encoded <= static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
            value = static_cast<std::int64_t>(encoded);
        } else {
            value = -1 - static_cast<std::int64_t>(
                std::numeric_limits<std::uint64_t>::max() - encoded);
        }
        return true;
    }

    bool string8(std::string& value, std::size_t maximum) {
        std::uint8_t length = 0;
        if (!u8(length) || length > maximum || !available(length)) return false;
        value.assign(reinterpret_cast<const char*>(data_ + position_), length);
        position_ += length;
        return true;
    }

    bool at_end() const { return position_ == size_; }

private:
    bool available(std::size_t count) const {
        return count <= size_ - position_;
    }

    const std::uint8_t* data_;
    std::size_t size_;
    std::size_t position_{kHeaderBytes};
};

CodecError validate_header(const std::uint8_t* data, std::size_t size,
                           FrameType expected) {
    if (data == nullptr || size < kHeaderBytes) return CodecError::Truncated;
    const std::uint32_t magic =
        (static_cast<std::uint32_t>(data[0]) << 24U) |
        (static_cast<std::uint32_t>(data[1]) << 16U) |
        (static_cast<std::uint32_t>(data[2]) << 8U) |
        static_cast<std::uint32_t>(data[3]);
    if (magic != kDataPlaneMagic) return CodecError::BadMagic;
    if (data[4] != kDataPlaneVersion) return CodecError::UnsupportedVersion;

    const auto type = data[5];
    if (type != static_cast<std::uint8_t>(FrameType::NodeMessage) &&
        type != static_cast<std::uint8_t>(FrameType::NodeAck) &&
        type != static_cast<std::uint8_t>(FrameType::NodeHealth) &&
        type != static_cast<std::uint8_t>(FrameType::ControlFota)) {
        return CodecError::UnknownFrameType;
    }
    if (type != static_cast<std::uint8_t>(expected)) return CodecError::UnexpectedFrameType;

    const auto payload_size = static_cast<std::size_t>(
        (static_cast<std::uint16_t>(data[6]) << 8U) | data[7]);
    const auto expected_size = kHeaderBytes + payload_size;
    if (size < expected_size) return CodecError::Truncated;
    if (size > expected_size) return CodecError::TrailingData;
    return CodecError::None;
}

std::optional<std::uint8_t> encode_event_kind(EventKind kind) {
    switch (kind) {
        case EventKind::Motion: return 1U;
        case EventKind::DoorOpen: return 2U;
        case EventKind::DoorClosed: return 3U;
        case EventKind::OkPressed: return 4U;
        case EventKind::CallFamily: return 5U;
        case EventKind::Heartbeat: return 6U;
        case EventKind::PrivacyOn: return 7U;
        case EventKind::PrivacyOff: return 8U;
        case EventKind::Gap: return 9U;
    }
    return std::nullopt;
}

std::optional<EventKind> decode_event_kind(std::uint8_t value) {
    switch (value) {
        case 1U: return EventKind::Motion;
        case 2U: return EventKind::DoorOpen;
        case 3U: return EventKind::DoorClosed;
        case 4U: return EventKind::OkPressed;
        case 5U: return EventKind::CallFamily;
        case 6U: return EventKind::Heartbeat;
        case 7U: return EventKind::PrivacyOn;
        case 8U: return EventKind::PrivacyOff;
        case 9U: return EventKind::Gap;
        default: return std::nullopt;
    }
}

std::optional<std::uint8_t> encode_sensor_type(SensorType type) {
    switch (type) {
        case SensorType::Unknown: return 0U;
        case SensorType::Pir: return 1U;
        case SensorType::Reed: return 2U;
        case SensorType::Button: return 3U;
        case SensorType::Heartbeat: return 4U;
        case SensorType::System: return 5U;
    }
    return std::nullopt;
}

std::optional<SensorType> decode_sensor_type(std::uint8_t value) {
    switch (value) {
        case 0U: return SensorType::Unknown;
        case 1U: return SensorType::Pir;
        case 2U: return SensorType::Reed;
        case 3U: return SensorType::Button;
        case 4U: return SensorType::Heartbeat;
        case 5U: return SensorType::System;
        default: return std::nullopt;
    }
}

std::optional<std::uint8_t> encode_ack_class(AckClass ack) {
    switch (ack) {
        case AckClass::Durable: return 1U;
        case AckClass::ReceivedVolatile: return 2U;
        case AckClass::DiscardedPolicy: return 3U;
        case AckClass::Rejected: return 4U;
    }
    return std::nullopt;
}

std::optional<AckClass> decode_ack_class(std::uint8_t value) {
    switch (value) {
        case 1U: return AckClass::Durable;
        case 2U: return AckClass::ReceivedVolatile;
        case 3U: return AckClass::DiscardedPolicy;
        case 4U: return AckClass::Rejected;
        default: return std::nullopt;
    }
}

bool write_power(Writer& writer, const NodePowerTelemetry& power) {
    return writer.u64(power.deep_sleep_ms) && writer.u64(power.awake_ms) &&
           writer.u64(power.sensor_active_ms) && writer.u64(power.radio_tx_ms) &&
           writer.u64(power.radio_rx_ms) && writer.u64(power.radio_tx_packets) &&
           writer.u64(power.radio_retries) && writer.u64(power.wake_count) &&
           writer.u64(power.heartbeat_count) && writer.u64(power.boot_count) &&
           writer.u64(power.brownout_count);
}

bool read_power(Reader& reader, NodePowerTelemetry& power) {
    return reader.u64(power.deep_sleep_ms) && reader.u64(power.awake_ms) &&
           reader.u64(power.sensor_active_ms) && reader.u64(power.radio_tx_ms) &&
           reader.u64(power.radio_rx_ms) && reader.u64(power.radio_tx_packets) &&
           reader.u64(power.radio_retries) && reader.u64(power.wake_count) &&
           reader.u64(power.heartbeat_count) && reader.u64(power.boot_count) &&
           reader.u64(power.brownout_count);
}

}  // namespace

FrameClass classify_frame(const std::uint8_t* data, std::size_t size) {
    if (data == nullptr || size < 4U) return FrameClass::Unknown;
    const bool fota_big_endian = data[0] == 0x47U && data[1] == 0x53U &&
                                 data[2] == 0x46U && data[3] == 0x4FU;
    const bool fota_esp_little_endian = data[0] == 0x4FU && data[1] == 0x46U &&
                                        data[2] == 0x53U && data[3] == 0x47U;
    if (fota_big_endian || fota_esp_little_endian) return FrameClass::ControlFota;
    if (size < kHeaderBytes || data[0] != 0x47U || data[1] != 0x53U ||
        data[2] != 0x44U || data[3] != 0x50U || data[4] != kDataPlaneVersion) {
        return FrameClass::Unknown;
    }
    if (data[5] == static_cast<std::uint8_t>(FrameType::NodeMessage)) {
        return FrameClass::NodeMessage;
    }
    if (data[5] == static_cast<std::uint8_t>(FrameType::NodeAck)) {
        return FrameClass::NodeAck;
    }
    if (data[5] == static_cast<std::uint8_t>(FrameType::NodeHealth)) {
        return FrameClass::NodeHealth;
    }
    if (data[5] == static_cast<std::uint8_t>(FrameType::ControlFota)) {
        return FrameClass::ControlFota;
    }
    return FrameClass::Unknown;
}

EncodeResult encode_node_message(const NodeMessage& message) {
    EncodeResult result;
    if (!valid_node_message(message)) {
        result.error = message.schema == NodeProtocolPolicy::wire_schema
            ? CodecError::InvalidValue : CodecError::UnsupportedSchema;
        return result;
    }
    if (message.node_id.size() > kMaxSourceIdBytes ||
        message.location.size() > kMaxLocationBytes ||
        message.payload_json.size() > kMaxPayloadJsonBytes) {
        result.error = CodecError::FieldTooLong;
        return result;
    }
    const auto sensor = encode_sensor_type(message.sensor_type);
    const auto event = encode_event_kind(message.event_type);
    if (!sensor || !event) {
        result.error = CodecError::InvalidValue;
        return result;
    }

    Writer writer(result.frame);
    std::uint8_t flags = message.is_test ? kIsTest : 0U;
    if (message.occurred_at) flags |= kOccurredAtPresent;
    if (message.power) flags |= kPowerPresent;
    const bool ok = writer.reserve_header() && writer.u32(message.schema) &&
        writer.string8(message.node_id, kMaxSourceIdBytes) &&
        writer.u64(message.session_id) && writer.u64(message.sequence_number) &&
        writer.u8(*sensor) && writer.u8(*event) &&
        writer.string8(message.location, kMaxLocationBytes) &&
        writer.i64(message.monotonic_ms) && writer.u8(flags) &&
        (!message.occurred_at || writer.i64(*message.occurred_at)) &&
        writer.u32(message.time_uncertainty_ms) && writer.u16(message.battery_mv) &&
        writer.i16(message.rssi_dbm) &&
        (!message.power || write_power(writer, *message.power)) &&
        writer.string8(message.payload_json, kMaxPayloadJsonBytes) &&
        writer.finish(FrameType::NodeMessage);
    if (!ok) result.error = CodecError::BufferTooSmall;
    return result;
}

DecodeResult<NodeMessage> decode_node_message(const std::uint8_t* data,
                                              std::size_t size) {
    DecodeResult<NodeMessage> result;
    result.error = validate_header(data, size, FrameType::NodeMessage);
    if (result.error != CodecError::None) return result;

    Reader reader(data, size);
    NodeMessage message;
    std::uint8_t sensor_value = 0;
    std::uint8_t event_value = 0;
    std::uint8_t flags = 0;
    if (!reader.u32(message.schema) ||
        !reader.string8(message.node_id, kMaxSourceIdBytes) ||
        !reader.u64(message.session_id) || !reader.u64(message.sequence_number) ||
        !reader.u8(sensor_value) || !reader.u8(event_value) ||
        !reader.string8(message.location, kMaxLocationBytes) ||
        !reader.i64(message.monotonic_ms) || !reader.u8(flags)) {
        result.error = CodecError::Truncated;
        return result;
    }
    if (message.schema != NodeProtocolPolicy::wire_schema) {
        result.error = CodecError::UnsupportedSchema;
        return result;
    }
    if ((flags & static_cast<std::uint8_t>(~kKnownFlags)) != 0U) {
        result.error = CodecError::MalformedFlags;
        return result;
    }
    const auto sensor = decode_sensor_type(sensor_value);
    const auto event = decode_event_kind(event_value);
    if (!sensor || !event) {
        result.error = CodecError::InvalidValue;
        return result;
    }
    message.sensor_type = *sensor;
    message.event_type = *event;
    message.is_test = (flags & kIsTest) != 0U;
    if ((flags & kOccurredAtPresent) != 0U) {
        EpochSeconds occurred_at = 0;
        if (!reader.i64(occurred_at)) {
            result.error = CodecError::Truncated;
            return result;
        }
        message.occurred_at = occurred_at;
    }
    if (!reader.u32(message.time_uncertainty_ms) ||
        !reader.u16(message.battery_mv) || !reader.i16(message.rssi_dbm)) {
        result.error = CodecError::Truncated;
        return result;
    }
    if ((flags & kPowerPresent) != 0U) {
        NodePowerTelemetry power;
        if (!read_power(reader, power)) {
            result.error = CodecError::Truncated;
            return result;
        }
        message.power = power;
    }
    if (!reader.string8(message.payload_json, kMaxPayloadJsonBytes)) {
        result.error = CodecError::Truncated;
        return result;
    }
    if (!reader.at_end()) {
        result.error = CodecError::LengthMismatch;
        return result;
    }
    if (!valid_node_message(message)) {
        result.error = CodecError::InvalidValue;
        return result;
    }
    result.value = std::move(message);
    return result;
}

EncodeResult encode_node_ack(const NodeAckMessage& message) {
    EncodeResult result;
    if (message.schema != NodeProtocolPolicy::ack_schema) {
        result.error = CodecError::UnsupportedSchema;
        return result;
    }
    if (message.node_id.empty() || message.session_id == 0U ||
        message.sequence_number == 0U || message.hub_received_at < 0) {
        result.error = CodecError::InvalidValue;
        return result;
    }
    if (message.node_id.size() > kMaxSourceIdBytes ||
        message.reason.size() > kMaxAckReasonBytes) {
        result.error = CodecError::FieldTooLong;
        return result;
    }
    const auto ack = encode_ack_class(message.ack_type);
    if (!ack) {
        result.error = CodecError::InvalidValue;
        return result;
    }
    Writer writer(result.frame);
    const bool ok = writer.reserve_header() && writer.u32(message.schema) &&
        writer.string8(message.node_id, kMaxSourceIdBytes) &&
        writer.u64(message.session_id) && writer.u64(message.sequence_number) &&
        writer.u8(*ack) && writer.i64(message.hub_received_at) &&
        writer.string8(message.reason, kMaxAckReasonBytes) &&
        writer.finish(FrameType::NodeAck);
    if (!ok) result.error = CodecError::BufferTooSmall;
    return result;
}

DecodeResult<NodeAckMessage> decode_node_ack(const std::uint8_t* data,
                                            std::size_t size) {
    DecodeResult<NodeAckMessage> result;
    result.error = validate_header(data, size, FrameType::NodeAck);
    if (result.error != CodecError::None) return result;

    Reader reader(data, size);
    NodeAckMessage message;
    std::uint8_t ack_value = 0;
    if (!reader.u32(message.schema) ||
        !reader.string8(message.node_id, kMaxSourceIdBytes) ||
        !reader.u64(message.session_id) || !reader.u64(message.sequence_number) ||
        !reader.u8(ack_value) || !reader.i64(message.hub_received_at) ||
        !reader.string8(message.reason, kMaxAckReasonBytes)) {
        result.error = CodecError::Truncated;
        return result;
    }
    if (message.schema != NodeProtocolPolicy::ack_schema) {
        result.error = CodecError::UnsupportedSchema;
        return result;
    }
    const auto ack = decode_ack_class(ack_value);
    if (!ack || message.node_id.empty() || message.session_id == 0U ||
        message.sequence_number == 0U || message.hub_received_at < 0) {
        result.error = CodecError::InvalidValue;
        return result;
    }
    if (!reader.at_end()) {
        result.error = CodecError::LengthMismatch;
        return result;
    }
    message.ack_type = *ack;
    result.value = std::move(message);
    return result;
}

EncodeResult encode_node_health(const NodeHealthSnapshot& health) {
    EncodeResult result;
    if (!valid_node_health(health)) {
        result.error = health.schema == NodeHealthSnapshot::schema_version
            ? CodecError::InvalidValue : CodecError::UnsupportedSchema;
        return result;
    }
    if (health.node_id.size() > kMaxSourceIdBytes) {
        result.error = CodecError::FieldTooLong;
        return result;
    }

    Writer writer(result.frame);
    const bool ok = writer.reserve_header() && writer.u32(health.schema) &&
        writer.string8(health.node_id, kMaxSourceIdBytes) &&
        writer.u64(health.session_id) && writer.u64(health.health_sequence) &&
        writer.u64(health.uptime_ms) && writer.u32(health.reset_reason) &&
        writer.u8(health.raw_pir_level ? 1U : 0U) &&
        writer.u32(health.raw_pir_edges) && writer.u32(health.accepted_pir) &&
        writer.u32(health.rejected_pir) && writer.u32(health.store_full) &&
        writer.u32(health.dropped_motion) && writer.u32(health.priority_rejected) &&
        writer.u32(health.sensing_liveness) && writer.u32(health.runtime_liveness) &&
        writer.u8(static_cast<std::uint8_t>(health.last_breadcrumb)) &&
        writer.u16(health.retained_count) && writer.u64(health.oldest_sequence) &&
        writer.u8(health.radio_in_flight ? 1U : 0U) &&
        writer.u32(health.tx_attempts) && writer.u32(health.mac_success) &&
        writer.u32(health.mac_failure) && writer.u32(health.durable_acks) &&
        writer.u32(health.volatile_acks) && writer.u32(health.retries) &&
        writer.u32(health.periodic_backoff_entries) &&
        writer.u16(static_cast<std::uint16_t>(health.last_error)) &&
        writer.u32(health.free_heap) && writer.u32(health.minimum_free_heap) &&
        writer.u8(health.maintenance_active ? 1U : 0U) &&
        writer.finish(FrameType::NodeHealth);
    if (!ok) result.error = CodecError::BufferTooSmall;
    return result;
}

DecodeResult<NodeHealthSnapshot> decode_node_health(const std::uint8_t* data,
                                                    std::size_t size) {
    DecodeResult<NodeHealthSnapshot> result;
    result.error = validate_header(data, size, FrameType::NodeHealth);
    if (result.error != CodecError::None) return result;

    Reader reader(data, size);
    NodeHealthSnapshot health;
    std::uint8_t raw_pir = 0;
    std::uint8_t breadcrumb = 0;
    std::uint8_t in_flight = 0;
    std::uint16_t last_error = 0;
    std::uint8_t maintenance = 0;
    if (!reader.u32(health.schema) ||
        !reader.string8(health.node_id, kMaxSourceIdBytes) ||
        !reader.u64(health.session_id) || !reader.u64(health.health_sequence) ||
        !reader.u64(health.uptime_ms) || !reader.u32(health.reset_reason) ||
        !reader.u8(raw_pir) || !reader.u32(health.raw_pir_edges) ||
        !reader.u32(health.accepted_pir) || !reader.u32(health.rejected_pir) ||
        !reader.u32(health.store_full) || !reader.u32(health.dropped_motion) ||
        !reader.u32(health.priority_rejected) || !reader.u32(health.sensing_liveness) ||
        !reader.u32(health.runtime_liveness) || !reader.u8(breadcrumb) ||
        !reader.u16(health.retained_count) || !reader.u64(health.oldest_sequence) ||
        !reader.u8(in_flight) || !reader.u32(health.tx_attempts) ||
        !reader.u32(health.mac_success) || !reader.u32(health.mac_failure) ||
        !reader.u32(health.durable_acks) || !reader.u32(health.volatile_acks) ||
        !reader.u32(health.retries) || !reader.u32(health.periodic_backoff_entries) ||
        !reader.u16(last_error) || !reader.u32(health.free_heap) ||
        !reader.u32(health.minimum_free_heap) || !reader.u8(maintenance)) {
        result.error = CodecError::Truncated;
        return result;
    }
    if (!reader.at_end()) {
        result.error = CodecError::LengthMismatch;
        return result;
    }
    if (health.schema != NodeHealthSnapshot::schema_version) {
        result.error = CodecError::UnsupportedSchema;
        return result;
    }
    if (raw_pir > 1U || in_flight > 1U || maintenance > 1U ||
        breadcrumb < static_cast<std::uint8_t>(NodeBreadcrumb::Boot) ||
        breadcrumb > static_cast<std::uint8_t>(NodeBreadcrumb::FotaResume) ||
        last_error > static_cast<std::uint16_t>(NodeHealthError::FotaTimeout)) {
        result.error = CodecError::InvalidValue;
        return result;
    }
    health.raw_pir_level = raw_pir != 0U;
    health.radio_in_flight = in_flight != 0U;
    health.maintenance_active = maintenance != 0U;
    health.last_breadcrumb = static_cast<NodeBreadcrumb>(breadcrumb);
    health.last_error = static_cast<NodeHealthError>(last_error);
    if (!valid_node_health(health)) {
        result.error = CodecError::InvalidValue;
        return result;
    }
    result.value = std::move(health);
    return result;
}

}  // namespace gs::transport
