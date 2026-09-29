#pragma once

#include "firmware/common/security/commissioning_crypto.hpp"
#include "firmware/common/transport/data_plane_codec.hpp"
#include "firmware/node/runtime/node_runtime.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace gs::transport {

constexpr std::size_t kMaxRetirementKeys = 32;
constexpr std::size_t kRetirementReportHeaderBytes = 30;
constexpr std::size_t kMaxRetirementReportBytes =
    kRetirementReportHeaderBytes + 16 * kMaxRetirementKeys;
constexpr std::size_t kRetirementFragmentDataBytes = 170;
constexpr std::size_t kRetirementFragmentHeaderBytes = 44;
constexpr std::size_t kMaxRetirementFragments = 4;
constexpr std::size_t kRetirementFrameBytes = 8 + kRetirementFragmentHeaderBytes +
    kRetirementFragmentDataBytes;

struct RetirementEventKey {
    std::uint64_t origin_session{0};
    std::uint64_t sequence{0};
    bool operator==(const RetirementEventKey& other) const {
        return origin_session == other.origin_session && sequence == other.sequence;
    }
    bool operator<(const RetirementEventKey& other) const {
        return origin_session < other.origin_session ||
            (origin_session == other.origin_session && sequence < other.sequence);
    }
};

struct NodeRetirementReportV1 {
    std::uint32_t epoch{0};
    std::uint64_t generation{0};
    std::uint64_t current_origin_session{0};
    std::uint64_t durable_admission_highwater{0};
    std::array<RetirementEventKey, kMaxRetirementKeys> pending{};
    std::uint8_t pending_count{0};
};

struct RetirementFragmentSet {
    std::array<EncodedFrame, kMaxRetirementFragments> frames{};
    std::uint8_t count{0};
    security::Key32 report_hmac{};
};

enum class RetirementAssemblyResult {
    Rejected,
    AcceptedFragment,
    DuplicateFragment,
    Complete
};

// Derive the report MAC key from the installation binding, then MAC the
// canonical logical report. Each resulting frame must still be sealed by
// RuntimeFrameSecurity before radio transmission.
bool derive_retirement_report_key(security::CommissioningCrypto& crypto,
                                  const security::Key32& installation_key,
                                  security::Key32& report_key);
bool encode_retirement_report(const NodeRetirementReportV1& report,
                              security::Bytes& logical);
bool decode_retirement_report(const std::uint8_t* logical, std::size_t size,
                              NodeRetirementReportV1& report);
bool make_retirement_report(const node::NodeRuntimeRecoveryState& snapshot,
                            NodeRetirementReportV1& report);
bool fragment_retirement_report(security::CommissioningCrypto& crypto,
                                const security::Key32& report_key,
                                const NodeRetirementReportV1& report,
                                RetirementFragmentSet& fragments);

class RetirementReportReassembler {
public:
    // Input is plaintext only after RuntimeFrameSecurity::open succeeds.
    RetirementAssemblyResult accept(security::CommissioningCrypto& crypto,
                                    const security::Key32& report_key,
                                    const EncodedFrame& authenticated_plain,
                                    NodeRetirementReportV1& complete_report,
                                    security::Key32& complete_hmac);
    void reset();
    bool active() const { return active_; }

private:
    bool active_{false};
    std::uint64_t generation_{0};
    std::uint16_t logical_length_{0};
    std::uint8_t fragment_count_{0};
    security::Key32 expected_hmac_{};
    std::array<std::array<std::uint8_t, kRetirementFragmentDataBytes>,
               kMaxRetirementFragments> data_{};
    std::array<std::uint16_t, kMaxRetirementFragments> lengths_{};
    std::uint8_t received_mask_{0};
};

struct NodeRetirementAckV1 {
    std::uint32_t epoch{0};
    std::uint64_t generation{0};
    security::Key32 report_hmac{};
};

EncodeResult encode_node_retirement_ack(const NodeRetirementAckV1& ack);
bool decode_node_retirement_ack(const std::uint8_t* data, std::size_t size,
                                NodeRetirementAckV1& ack);

}  // namespace gs::transport
