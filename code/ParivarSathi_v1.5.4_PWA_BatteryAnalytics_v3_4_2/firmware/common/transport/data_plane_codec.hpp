#pragma once

#include "gs/protocol.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace gs::transport {

// Normal sensor/business traffic uses this explicit data-plane envelope.
// The physically qualified FOTA protocol keeps its separate control-plane
// magic and is only classified here so it can never enter business decoding.
constexpr std::uint32_t kDataPlaneMagic = 0x47534450U;  // "GSDP"
constexpr std::uint32_t kFotaMagic = 0x4753464FU;       // existing "GSFO"
constexpr std::uint8_t kDataPlaneVersion = 1U;

constexpr std::size_t kMaxSourceIdBytes = 24U;
constexpr std::size_t kMaxLocationBytes = 24U;
constexpr std::size_t kMaxPayloadJsonBytes = 16U;
constexpr std::size_t kMaxAckReasonBytes = 48U;
constexpr std::size_t kMaxFrameBytes = 224U;

enum class FrameType : std::uint8_t {
    NodeMessage = 1U,
    NodeAck = 2U,
    NodeHealth = 3U,
    ControlFota = 0x80U
};

enum class FrameClass {
    Unknown,
    NodeMessage,
    NodeAck,
    NodeHealth,
    ControlFota
};

enum class CodecError {
    None,
    BufferTooSmall,
    FieldTooLong,
    InvalidValue,
    Truncated,
    BadMagic,
    UnsupportedVersion,
    UnknownFrameType,
    UnexpectedFrameType,
    LengthMismatch,
    TrailingData,
    MalformedFlags,
    UnsupportedSchema
};

struct EncodedFrame {
    std::array<std::uint8_t, kMaxFrameBytes> bytes{};
    std::size_t size{0};
};

struct EncodeResult {
    CodecError error{CodecError::None};
    EncodedFrame frame{};

    explicit operator bool() const { return error == CodecError::None; }
};

template <typename T>
struct DecodeResult {
    CodecError error{CodecError::None};
    std::optional<T> value;

    explicit operator bool() const {
        return error == CodecError::None && value.has_value();
    }
};

FrameClass classify_frame(const std::uint8_t* data, std::size_t size);

EncodeResult encode_node_message(const NodeMessage& message);
DecodeResult<NodeMessage> decode_node_message(const std::uint8_t* data,
                                              std::size_t size);

EncodeResult encode_node_ack(const NodeAckMessage& message);
DecodeResult<NodeAckMessage> decode_node_ack(const std::uint8_t* data,
                                            std::size_t size);

EncodeResult encode_node_health(const NodeHealthSnapshot& health);
DecodeResult<NodeHealthSnapshot> decode_node_health(const std::uint8_t* data,
                                                    std::size_t size);

}  // namespace gs::transport
