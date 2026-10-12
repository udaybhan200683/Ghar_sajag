#include "firmware/common/transport/node_retirement_protocol.hpp"

#include <algorithm>
#include <cstring>

namespace gs::transport {
namespace {
constexpr std::uint8_t kReportVersion = 1;
constexpr char kReportKeyLabel[] = "GS-RETIRE-REPORT-v1";

void put_u32(security::Bytes& out, std::uint32_t value) {
    for (int shift = 24; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}
void put_u64(security::Bytes& out, std::uint64_t value) {
    for (int shift = 56; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}
bool get_unsigned(const std::uint8_t* data, std::size_t size, std::size_t& pos,
                  std::size_t count, std::uint64_t& value) {
    if (pos > size || count > size - pos) return false;
    value = 0;
    for (std::size_t i = 0; i < count; ++i) value = (value << 8) | data[pos++];
    return true;
}
void set_header(EncodedFrame& frame, FrameType type, std::size_t payload_size) {
    frame.bytes[0] = 0x47; frame.bytes[1] = 0x53;
    frame.bytes[2] = 0x44; frame.bytes[3] = 0x50;
    frame.bytes[4] = kDataPlaneVersion;
    frame.bytes[5] = static_cast<std::uint8_t>(type);
    frame.bytes[6] = static_cast<std::uint8_t>(payload_size >> 8);
    frame.bytes[7] = static_cast<std::uint8_t>(payload_size);
    frame.size = 8 + payload_size;
}
bool report_frame_header(const std::uint8_t* data, std::size_t size,
                         FrameType type, std::size_t& payload_size) {
    if (!data || size < 8 || data[0] != 0x47 || data[1] != 0x53 ||
        data[2] != 0x44 || data[3] != 0x50 ||
        data[4] != kDataPlaneVersion || data[5] != static_cast<std::uint8_t>(type))
        return false;
    payload_size = (static_cast<std::size_t>(data[6]) << 8) | data[7];
    return size == 8 + payload_size;
}
bool valid_report(const NodeRetirementReportV1& report) {
    if (report.epoch == 0 || report.generation == 0 ||
        report.current_origin_session == 0 || report.pending_count > kMaxRetirementKeys)
        return false;
    for (std::size_t i = 0; i < report.pending_count; ++i) {
        const auto& key = report.pending[i];
        if (key.origin_session == 0 || key.sequence == 0 ||
            key.origin_session > report.current_origin_session ||
            (key.origin_session == report.current_origin_session &&
             key.sequence > report.durable_admission_highwater) ||
            (i != 0 && !(report.pending[i - 1] < key))) return false;
    }
    return true;
}
}  // namespace

bool derive_retirement_report_key(security::CommissioningCrypto& crypto,
                                  const security::Key32& installation_key,
                                  security::Key32& report_key) {
    const security::Bytes label(kReportKeyLabel,
                                kReportKeyLabel + sizeof(kReportKeyLabel) - 1);
    return crypto.hmac_sha256(installation_key, label, report_key);
}

bool encode_retirement_report(const NodeRetirementReportV1& report,
                              security::Bytes& logical) {
    logical.clear();
    if (!valid_report(report)) return false;
    logical.reserve(kRetirementReportHeaderBytes + 16 * report.pending_count);
    logical.push_back(kReportVersion);
    put_u32(logical, report.epoch);
    put_u64(logical, report.generation);
    put_u64(logical, report.current_origin_session);
    put_u64(logical, report.durable_admission_highwater);
    logical.push_back(report.pending_count);
    for (std::size_t i = 0; i < report.pending_count; ++i) {
        put_u64(logical, report.pending[i].origin_session);
        put_u64(logical, report.pending[i].sequence);
    }
    return logical.size() <= kMaxRetirementReportBytes;
}

bool decode_retirement_report(const std::uint8_t* logical, std::size_t size,
                              NodeRetirementReportV1& report) {
    if (!logical || size < kRetirementReportHeaderBytes ||
        size > kMaxRetirementReportBytes || logical[0] != kReportVersion)
        return false;
    std::size_t pos = 1;
    std::uint64_t value = 0;
    if (!get_unsigned(logical, size, pos, 4, value)) return false;
    report.epoch = static_cast<std::uint32_t>(value);
    if (!get_unsigned(logical, size, pos, 8, report.generation) ||
        !get_unsigned(logical, size, pos, 8, report.current_origin_session) ||
        !get_unsigned(logical, size, pos, 8, report.durable_admission_highwater) ||
        pos >= size) return false;
    report.pending_count = logical[pos++];
    if (report.pending_count > kMaxRetirementKeys ||
        size != kRetirementReportHeaderBytes + 16 * report.pending_count) return false;
    for (std::size_t i = 0; i < report.pending_count; ++i) {
        if (!get_unsigned(logical, size, pos, 8, report.pending[i].origin_session) ||
            !get_unsigned(logical, size, pos, 8, report.pending[i].sequence)) return false;
    }
    return pos == size && valid_report(report);
}

bool make_retirement_report(const node::NodeRuntimeRecoveryState& snapshot,
                            NodeRetirementReportV1& report) {
    if (snapshot.pending.size() > kMaxRetirementKeys) return false;
    report = {};
    report.epoch = snapshot.retirement_epoch;
    report.generation = snapshot.report_generation;
    report.current_origin_session = snapshot.prior_boot_session;
    report.durable_admission_highwater = snapshot.durable_admission_highwater;
    report.pending_count = static_cast<std::uint8_t>(snapshot.pending.size());
    for (std::size_t i = 0; i < snapshot.pending.size(); ++i) {
        report.pending[i] = {snapshot.pending[i].event.key.session_id,
                             snapshot.pending[i].event.key.sequence};
    }
    std::sort(report.pending.begin(), report.pending.begin() + report.pending_count);
    security::Bytes encoded;
    return encode_retirement_report(report, encoded);
}

bool fragment_retirement_report(security::CommissioningCrypto& crypto,
                                const security::Key32& report_key,
                                const NodeRetirementReportV1& report,
                                RetirementFragmentSet& fragments) {
    security::Bytes logical;
    if (!encode_retirement_report(report, logical)) return false;
    const std::size_t count = (logical.size() + kRetirementFragmentDataBytes - 1) /
                              kRetirementFragmentDataBytes;
    if (count == 0 || count > kMaxRetirementFragments) return false;
    security::Key32 mac{};
    if (!crypto.hmac_sha256(report_key, logical, mac)) return false;
    fragments = {};
    fragments.count = static_cast<std::uint8_t>(count);
    fragments.report_hmac = mac;
    for (std::size_t index = 0; index < count; ++index) {
        const std::size_t begin = index * kRetirementFragmentDataBytes;
        const std::size_t chunk = std::min(kRetirementFragmentDataBytes,
                                           logical.size() - begin);
        auto& frame = fragments.frames[index];
        set_header(frame, FrameType::NodeRetirementFragment,
                   kRetirementFragmentHeaderBytes + chunk);
        std::size_t pos = 8;
        for (int shift = 56; shift >= 0; shift -= 8)
            frame.bytes[pos++] = static_cast<std::uint8_t>(report.generation >> shift);
        std::copy(mac.begin(), mac.end(), frame.bytes.begin() + pos);
        pos += mac.size();
        frame.bytes[pos++] = static_cast<std::uint8_t>(index);
        frame.bytes[pos++] = static_cast<std::uint8_t>(count);
        frame.bytes[pos++] = static_cast<std::uint8_t>(logical.size() >> 8);
        frame.bytes[pos++] = static_cast<std::uint8_t>(logical.size());
        std::copy_n(logical.begin() + begin, chunk, frame.bytes.begin() + pos);
    }
    crypto.secure_zero(logical.data(), logical.size());
    return true;
}

RetirementAssemblyResult RetirementReportReassembler::accept(
    security::CommissioningCrypto& crypto, const security::Key32& report_key,
    const EncodedFrame& frame, NodeRetirementReportV1& complete_report,
    security::Key32& complete_hmac) {
    std::size_t payload_size = 0;
    if (!report_frame_header(frame.bytes.data(), frame.size,
            FrameType::NodeRetirementFragment, payload_size) ||
        payload_size < kRetirementFragmentHeaderBytes ||
        payload_size > kRetirementFragmentHeaderBytes + kRetirementFragmentDataBytes)
        return RetirementAssemblyResult::Rejected;

    std::size_t pos = 8;
    std::uint64_t generation = 0, logical_len = 0;
    if (!get_unsigned(frame.bytes.data(), frame.size, pos, 8, generation) || generation == 0)
        return RetirementAssemblyResult::Rejected;
    security::Key32 mac{};
    std::copy_n(frame.bytes.begin() + pos, mac.size(), mac.begin());
    pos += mac.size();
    const std::uint8_t index = frame.bytes[pos++];
    const std::uint8_t count = frame.bytes[pos++];
    if (!get_unsigned(frame.bytes.data(), frame.size, pos, 2, logical_len) ||
        logical_len < kRetirementReportHeaderBytes ||
        logical_len > kMaxRetirementReportBytes || count == 0 ||
        count > kMaxRetirementFragments || index >= count ||
        count != (logical_len + kRetirementFragmentDataBytes - 1) /
                    kRetirementFragmentDataBytes) return RetirementAssemblyResult::Rejected;
    const std::size_t offset = static_cast<std::size_t>(index) * kRetirementFragmentDataBytes;
    const std::size_t expected_len = std::min(kRetirementFragmentDataBytes,
        static_cast<std::size_t>(logical_len) - offset);
    const std::size_t data_len = payload_size - kRetirementFragmentHeaderBytes;
    if (data_len != expected_len || pos + data_len != frame.size)
        return RetirementAssemblyResult::Rejected;

    if (!active_) {
        active_ = true;
        generation_ = generation;
        logical_length_ = static_cast<std::uint16_t>(logical_len);
        fragment_count_ = count;
        expected_hmac_ = mac;
    } else if (generation_ != generation || logical_length_ != logical_len ||
               fragment_count_ != count || expected_hmac_ != mac) {
        return RetirementAssemblyResult::Rejected;
    }

    const auto bit = static_cast<std::uint8_t>(1U << index);
    if ((received_mask_ & bit) != 0) {
        if (lengths_[index] != data_len ||
            !std::equal(frame.bytes.begin() + pos, frame.bytes.begin() + pos + data_len,
                        data_[index].begin())) {
            reset();
            return RetirementAssemblyResult::Rejected;
        }
        return RetirementAssemblyResult::DuplicateFragment;
    }
    std::copy_n(frame.bytes.begin() + pos, data_len, data_[index].begin());
    lengths_[index] = static_cast<std::uint16_t>(data_len);
    received_mask_ = static_cast<std::uint8_t>(received_mask_ | bit);
    const auto complete_mask = static_cast<std::uint8_t>((1U << fragment_count_) - 1U);
    if (received_mask_ != complete_mask) return RetirementAssemblyResult::AcceptedFragment;

    security::Bytes logical;
    logical.reserve(logical_length_);
    for (std::size_t i = 0; i < fragment_count_; ++i)
        logical.insert(logical.end(), data_[i].begin(), data_[i].begin() + lengths_[i]);
    security::Key32 actual{};
    NodeRetirementReportV1 decoded;
    const bool verified = logical.size() == logical_length_ &&
        crypto.hmac_sha256(report_key, logical, actual) &&
        crypto.constant_time_equal(actual.data(), expected_hmac_.data(), actual.size()) &&
        decode_retirement_report(logical.data(), logical.size(), decoded) &&
        decoded.generation == generation_;
    crypto.secure_zero(logical.data(), logical.size());
    if (!verified) {
        reset();
        return RetirementAssemblyResult::Rejected;
    }
    complete_report = decoded;
    complete_hmac = expected_hmac_;
    reset();
    return RetirementAssemblyResult::Complete;
}

void RetirementReportReassembler::reset() {
    active_ = false;
    generation_ = 0;
    logical_length_ = 0;
    fragment_count_ = 0;
    received_mask_ = 0;
    expected_hmac_.fill(0);
    lengths_.fill(0);
    for (auto& fragment : data_) fragment.fill(0);
}

EncodeResult encode_node_retirement_ack(const NodeRetirementAckV1& ack) {
    EncodeResult result;
    if (ack.epoch == 0 || ack.generation == 0 ||
        std::all_of(ack.report_hmac.begin(), ack.report_hmac.end(),
                    [](std::uint8_t value) { return value == 0; })) {
        result.error = CodecError::InvalidValue;
        return result;
    }
    set_header(result.frame, FrameType::NodeRetirementAck, 44);
    std::size_t pos = 8;
    result.frame.bytes[pos++] = static_cast<std::uint8_t>(ack.epoch >> 24);
    result.frame.bytes[pos++] = static_cast<std::uint8_t>(ack.epoch >> 16);
    result.frame.bytes[pos++] = static_cast<std::uint8_t>(ack.epoch >> 8);
    result.frame.bytes[pos++] = static_cast<std::uint8_t>(ack.epoch);
    for (int shift = 56; shift >= 0; shift -= 8)
        result.frame.bytes[pos++] = static_cast<std::uint8_t>(ack.generation >> shift);
    std::copy(ack.report_hmac.begin(), ack.report_hmac.end(), result.frame.bytes.begin() + pos);
    return result;
}

bool decode_node_retirement_ack(const std::uint8_t* data, std::size_t size,
                                NodeRetirementAckV1& ack) {
    std::size_t payload = 0;
    if (!report_frame_header(data, size, FrameType::NodeRetirementAck, payload) ||
        payload != 44) return false;
    std::size_t pos = 8;
    std::uint64_t value = 0;
    if (!get_unsigned(data, size, pos, 4, value)) return false;
    ack.epoch = static_cast<std::uint32_t>(value);
    if (!get_unsigned(data, size, pos, 8, ack.generation)) return false;
    std::copy_n(data + pos, ack.report_hmac.size(), ack.report_hmac.begin());
    return ack.epoch != 0 && ack.generation != 0;
}

bool derive_retirement_enrollment_binding(
        security::CommissioningCrypto& crypto,
        const security::Key32& journal_key,
        const std::string& authenticated_logical_id,
        RetirementEnrollmentBinding& binding) {
    if (authenticated_logical_id.empty()) return false;
    const security::Bytes identity(authenticated_logical_id.begin(),
                                   authenticated_logical_id.end());
    RetirementEnrollmentBinding derived;
    if (!crypto.hmac_sha256(journal_key, identity, derived.digest)) return false;
    derived.slot = static_cast<std::uint8_t>(derived.digest[0] % 10U);
    derived.generation = (static_cast<std::uint32_t>(derived.digest[1]) << 24U) |
        (static_cast<std::uint32_t>(derived.digest[2]) << 16U) |
        (static_cast<std::uint32_t>(derived.digest[3]) << 8U) |
        static_cast<std::uint32_t>(derived.digest[4]);
    if (derived.generation == 0) derived.generation = 1;
    binding = derived;
    return true;
}

}  // namespace gs::transport
