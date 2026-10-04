#include "storage/node_retirement_snapshot.hpp"

#include <algorithm>
#include <cstring>
#include <limits>

namespace gs::hub::durable {
namespace {
using security::Bytes;
constexpr std::uint8_t kSchema = 2;
constexpr std::size_t kSnapshotHeaderBytes = 19;
constexpr std::size_t kAeadOverhead = 28;
constexpr char kAadLabelV1[] = "hub-retirement-snapshot-v1";

struct Writer {
    Bytes bytes;
    void u8(std::uint8_t value) { bytes.push_back(value); }
    void u16(std::uint16_t value) {
        bytes.push_back(static_cast<std::uint8_t>(value >> 8));
        bytes.push_back(static_cast<std::uint8_t>(value));
    }
    void u32(std::uint32_t value) {
        for (int shift = 24; shift >= 0; shift -= 8)
            bytes.push_back(static_cast<std::uint8_t>(value >> shift));
    }
    void u64(std::uint64_t value) {
        for (int shift = 56; shift >= 0; shift -= 8)
            bytes.push_back(static_cast<std::uint8_t>(value >> shift));
    }
    void raw(const std::uint8_t* data, std::size_t size) {
        bytes.insert(bytes.end(), data, data + size);
    }
};
struct Reader {
    const Bytes& bytes;
    std::size_t position{0};
    bool raw(std::uint8_t* out, std::size_t count) {
        if (position > bytes.size() || count > bytes.size() - position) return false;
        std::copy_n(bytes.begin() + position, count, out);
        position += count;
        return true;
    }
    bool u8(std::uint8_t& out) {
        if (position == bytes.size()) return false;
        out = bytes[position++]; return true;
    }
    bool u16(std::uint16_t& out) {
        std::uint64_t value = 0;
        if (!number(2, value)) return false;
        out = static_cast<std::uint16_t>(value); return true;
    }
    bool u32(std::uint32_t& out) {
        std::uint64_t value = 0;
        if (!number(4, value)) return false;
        out = static_cast<std::uint32_t>(value); return true;
    }
    bool u64(std::uint64_t& out) { return number(8, out); }
    bool number(std::size_t count, std::uint64_t& out) {
        if (position > bytes.size() || count > bytes.size() - position) return false;
        out = 0;
        for (std::size_t i = 0; i < count; ++i)
            out = (out << 8) | bytes[position++];
        return true;
    }
};
bool nonzero(const std::uint8_t* data, std::size_t size) {
    return std::any_of(data, data + size, [](std::uint8_t byte) { return byte != 0; });
}
bool valid_node(const RetirementNodeSnapshot& node, bool legacy) {
    if ((legacy && !nonzero(node.binding_digest.data(), node.binding_digest.size())) ||
        node.enrollment_generation == 0 || node.report_generation == 0 ||
        !nonzero(node.report_hmac.data(), node.report_hmac.size()) ||
        node.current_origin_session == 0 || node.pending_count > transport::kMaxRetirementKeys)
        return false;
    for (std::size_t i = 0; i < node.pending_count; ++i) {
        const auto& key = node.pending[i];
        if (key.origin_session == 0 || key.sequence == 0 ||
            key.origin_session > node.current_origin_session ||
            (key.origin_session == node.current_origin_session &&
             key.sequence > node.durable_admission_highwater) ||
            (i != 0 && !(node.pending[i - 1] < key))) return false;
    }
    return true;
}
bool valid_snapshot(const RetirementSnapshot& snapshot) {
    if (snapshot.storage_epoch == 0 || snapshot.generation == 0 ||
        (snapshot.occupancy_mask & ~static_cast<std::uint16_t>((1U << kMaxRetirementNodes) - 1U)) != 0)
        return false;
    for (std::size_t i = 0; i < kMaxRetirementNodes; ++i) {
        if ((snapshot.occupancy_mask & (1U << i)) == 0) continue;
        if (!valid_node(snapshot.nodes[i], snapshot.legacy_binding_domain)) return false;
        for (std::size_t j = 0; j < i; ++j)
            if (snapshot.legacy_binding_domain &&
                (snapshot.occupancy_mask & (1U << j)) != 0 &&
                snapshot.nodes[i].binding_digest == snapshot.nodes[j].binding_digest &&
                snapshot.nodes[i].enrollment_generation == snapshot.nodes[j].enrollment_generation)
                return false;
    }
    return true;
}
std::string bank_key(std::uint8_t bank) { return "ret" + std::to_string(bank); }
bool key_equal(const ExactEventEvidence& a, const ExactEventEvidence& b) {
    return a.enrollment_slot == b.enrollment_slot &&
        a.enrollment_generation == b.enrollment_generation &&
        a.origin_session == b.origin_session && a.sequence == b.sequence;
}
bool report_contains(const RetirementNodeSnapshot& node,
                     std::uint64_t session, std::uint64_t sequence) {
    for (std::size_t i = 0; i < node.pending_count; ++i)
        if (node.pending[i].origin_session == session &&
            node.pending[i].sequence == sequence) return true;
    return false;
}
}  // namespace

RetirementSnapshotRepository::RetirementSnapshotRepository(
    BlobStore& store, security::CommissioningCrypto& crypto, security::Key32 key,
    std::uint32_t epoch)
    : store_(store), crypto_(crypto), key_(key), epoch_(epoch) {}

RetirementSnapshotRepository::~RetirementSnapshotRepository() {
    crypto_.secure_zero(key_.data(), key_.size());
}

bool RetirementSnapshotRepository::encode(security::CommissioningCrypto& crypto,
        const security::Key32& key, const RetirementSnapshot& snapshot, Bytes& blob) {
    blob.clear();
    if (snapshot.legacy_binding_domain || !valid_snapshot(snapshot)) return false;
    Writer plain;
    plain.raw(reinterpret_cast<const std::uint8_t*>("GRS1"), 4);
    plain.u8(kSchema);
    plain.u32(snapshot.storage_epoch);
    plain.u64(snapshot.generation);
    plain.u16(snapshot.occupancy_mask);
    if (plain.bytes.size() != kSnapshotHeaderBytes) return false;
    for (std::size_t i = 0; i < kMaxRetirementNodes; ++i) {
        if ((snapshot.occupancy_mask & (1U << i)) == 0) continue;
        const auto& node = snapshot.nodes[i];
        plain.u32(node.enrollment_generation);
        plain.u64(node.report_generation);
        plain.raw(node.report_hmac.data(), node.report_hmac.size());
        plain.u64(node.current_origin_session);
        plain.u64(node.durable_admission_highwater);
        plain.u8(node.pending_count);
        for (std::size_t j = 0; j < node.pending_count; ++j) {
            plain.u64(node.pending[j].origin_session);
            plain.u64(node.pending[j].sequence);
        }
    }
    security::Nonce12 nonce{};
    security::GcmTag tag{};
    Bytes cipher;
    const Bytes aad(kAadLabelV1, kAadLabelV1 + sizeof(kAadLabelV1) - 1);
    if (!crypto.random_bytes(nonce.data(), nonce.size()) ||
        !crypto.seal_aes256_gcm(key, nonce, aad, plain.bytes, cipher, tag)) return false;
    blob.assign(nonce.begin(), nonce.end());
    blob.insert(blob.end(), cipher.begin(), cipher.end());
    blob.insert(blob.end(), tag.begin(), tag.end());
    return blob.size() == plain.bytes.size() + kAeadOverhead &&
           blob.size() <= 5777 && blob.size() <= kRetirementSnapshotBankBytes;
}

bool RetirementSnapshotRepository::decode(security::CommissioningCrypto& crypto,
        const security::Key32& key, const Bytes& blob, RetirementSnapshot& snapshot) {
    if (blob.size() < kSnapshotHeaderBytes + kAeadOverhead ||
        blob.size() > kRetirementLegacyInspectionBytes) return false;
    security::Nonce12 nonce{};
    security::GcmTag tag{};
    std::copy_n(blob.begin(), nonce.size(), nonce.begin());
    std::copy_n(blob.end() - tag.size(), tag.size(), tag.begin());
    const Bytes cipher(blob.begin() + nonce.size(), blob.end() - tag.size());
    Bytes plain;
    const Bytes aad(kAadLabelV1, kAadLabelV1 + sizeof(kAadLabelV1) - 1);
    const bool opened=crypto.open_aes256_gcm(key,nonce,aad,cipher,tag,plain);
    if (!opened || plain.size() < 18) return false;
    Reader reader{plain};
    std::array<std::uint8_t, 4> magic{};
    std::uint8_t schema = 0;
    if (!reader.raw(magic.data(), magic.size()) ||
        magic != std::array<std::uint8_t, 4>{'G','R','S','1'} ||
        !reader.u8(schema) || (schema != 1 && schema != kSchema) ||
        !reader.u32(snapshot.storage_epoch) || !reader.u64(snapshot.generation))
        return false;
    snapshot.legacy_binding_domain = schema == 1;
    if (schema == 1) {
        std::uint8_t count = 0;
        if (!reader.u8(count) || count > kMaxRetirementNodes) return false;
        for (std::size_t i = 0; i < count; ++i) {
            auto& node = snapshot.nodes[i];
            if (!reader.raw(node.binding_digest.data(), node.binding_digest.size()) ||
                !reader.u32(node.enrollment_generation) || !reader.u64(node.report_generation) ||
                !reader.raw(node.report_hmac.data(), node.report_hmac.size()) ||
                !reader.u64(node.current_origin_session) ||
                !reader.u64(node.durable_admission_highwater) || !reader.u8(node.pending_count) ||
                node.pending_count > transport::kMaxRetirementKeys) return false;
            for (std::size_t j = 0; j < node.pending_count; ++j)
                if (!reader.u64(node.pending[j].origin_session) ||
                    !reader.u64(node.pending[j].sequence)) return false;
            snapshot.occupancy_mask |= static_cast<std::uint16_t>(1U << i);
        }
    } else {
        if (!reader.u16(snapshot.occupancy_mask) ||
            (snapshot.occupancy_mask & ~static_cast<std::uint16_t>((1U << kMaxRetirementNodes) - 1U)) != 0)
            return false;
        for (std::size_t i = 0; i < kMaxRetirementNodes; ++i) {
            if ((snapshot.occupancy_mask & (1U << i)) == 0) continue;
            auto& node = snapshot.nodes[i];
            if (!reader.u32(node.enrollment_generation) || !reader.u64(node.report_generation) ||
                !reader.raw(node.report_hmac.data(), node.report_hmac.size()) ||
                !reader.u64(node.current_origin_session) ||
                !reader.u64(node.durable_admission_highwater) || !reader.u8(node.pending_count) ||
                node.pending_count > transport::kMaxRetirementKeys) return false;
            for (std::size_t j = 0; j < node.pending_count; ++j)
                if (!reader.u64(node.pending[j].origin_session) ||
                    !reader.u64(node.pending[j].sequence)) return false;
        }
    }
    const bool okay = reader.position == plain.size() && valid_snapshot(snapshot);
    crypto.secure_zero(plain.data(), plain.size());
    return okay;
}

bool RetirementSnapshotRepository::load(const RetirementSnapshotReference& reference,
                                         RetirementSnapshot& snapshot) const {
    if (!reference.valid()) return false;
    Bytes blob;
    bool found = false;
    if (!store_.read(bank_key(reference.bank), blob, found) || !found) return false;
    security::Key32 digest{};
    if (!crypto_.hmac_sha256(key_, blob, digest) ||
        !crypto_.constant_time_equal(digest.data(), reference.digest.data(), digest.size()) ||
        !decode(crypto_, key_, blob, snapshot)) return false;
    return snapshot.storage_epoch == epoch_ && snapshot.generation == reference.generation &&
           !snapshot.legacy_binding_domain;
}

bool RetirementSnapshotRepository::inspect_legacy_for_migration(
        const RetirementSnapshotReference& reference,
        RetirementSnapshot& snapshot) const {
    if (!reference.valid()) return false;
    Bytes blob;
    bool found = false;
    if (!store_.read(bank_key(reference.bank), blob, found) || !found ||
        blob.size() > kRetirementLegacyInspectionBytes) return false;
    security::Key32 digest{};
    if (!crypto_.hmac_sha256(key_, blob, digest) ||
        !crypto_.constant_time_equal(digest.data(), reference.digest.data(), digest.size()) ||
        !decode(crypto_, key_, blob, snapshot)) return false;
    return snapshot.storage_epoch == epoch_ && snapshot.generation == reference.generation &&
           snapshot.legacy_binding_domain;
}

bool RetirementSnapshotRepository::prepare_bank(const RetirementSnapshot& snapshot,
        std::uint8_t referenced_bank_mask, RetirementSnapshotReference& reference) {
    if (snapshot.storage_epoch != epoch_ || !valid_snapshot(snapshot)) return false;
    std::uint8_t bank = 0xff;
    for (std::uint8_t i = 0; i < kRetirementSnapshotBankCount; ++i)
        if ((referenced_bank_mask & static_cast<std::uint8_t>(1U << i)) == 0) {
            bank = i; break;
        }
    if (bank == 0xff) return false;
    Bytes blob;
    if (!encode(crypto_, key_, snapshot, blob)) return false;
    (void)store_.replace(bank_key(bank), blob);
    Bytes verify;
    bool found = false;
    RetirementSnapshot decoded;
    if (!store_.read(bank_key(bank), verify, found) || !found || verify != blob ||
        !decode(crypto_, key_, verify, decoded) || decoded.generation != snapshot.generation ||
        decoded.storage_epoch != epoch_) return false;
    reference = {};
    reference.bank = bank;
    reference.generation = snapshot.generation;
    if (!crypto_.hmac_sha256(key_, verify, reference.digest)) return false;
    return reference.valid();
}

bool RetirementSnapshotRepository::same_node_report(const RetirementNodeSnapshot& node,
        const transport::NodeRetirementReportV1& report, const security::Key32& mac) {
    if (node.report_generation != report.generation || node.report_hmac != mac ||
        node.current_origin_session != report.current_origin_session ||
        node.durable_admission_highwater != report.durable_admission_highwater ||
        node.pending_count != report.pending_count) return false;
    return std::equal(node.pending.begin(), node.pending.begin() + node.pending_count,
                      report.pending.begin());
}

RetirementReportApply RetirementSnapshotRepository::apply_authenticated_report(
        const RetirementSnapshot& current,
        const std::array<std::uint8_t, 32>& binding_digest,
        std::uint8_t enrollment_slot,
        std::uint32_t enrollment_generation,
        std::uint64_t authenticated_transport_session,
        const transport::NodeRetirementReportV1& report,
        const security::Key32& verified_report_hmac,
        RetirementSnapshot& candidate) const {
    if (epoch_ == 0 || current.storage_epoch != epoch_ || current.legacy_binding_domain ||
        enrollment_generation == 0 ||
        enrollment_slot >= kMaxRetirementNodes ||
        !nonzero(binding_digest.data(), binding_digest.size()) ||
        !nonzero(verified_report_hmac.data(), verified_report_hmac.size()) ||
        report.epoch != epoch_ || report.generation == 0 ||
        report.current_origin_session == 0 ||
        report.current_origin_session > authenticated_transport_session ||
        report.pending_count > transport::kMaxRetirementKeys) return RetirementReportApply::Invalid;
    for (std::size_t i = 0; i < report.pending_count; ++i) {
        const auto& key = report.pending[i];
        if (key.origin_session == 0 || key.sequence == 0 ||
            key.origin_session > report.current_origin_session ||
            (key.origin_session == report.current_origin_session &&
             key.sequence > report.durable_admission_highwater) ||
            (i != 0 && !(report.pending[i - 1] < key))) return RetirementReportApply::Invalid;
    }
    const std::size_t index = enrollment_slot;
    const bool occupied = (current.occupancy_mask & (1U << index)) != 0;
    if (occupied && current.nodes[index].enrollment_generation != enrollment_generation)
        return RetirementReportApply::Conflict;
    if (!occupied && current.node_count() == kMaxRetirementNodes) return RetirementReportApply::Full;
    if (occupied) {
        const auto& previous = current.nodes[index];
        if (report.generation < previous.report_generation) return RetirementReportApply::Stale;
        if (report.generation == previous.report_generation)
            return same_node_report(previous, report, verified_report_hmac)
                ? RetirementReportApply::Duplicate : RetirementReportApply::Conflict;
        if (report.current_origin_session < previous.current_origin_session ||
            (report.current_origin_session == previous.current_origin_session &&
             report.durable_admission_highwater < previous.durable_admission_highwater))
            return RetirementReportApply::Invalid;
        for (std::size_t i = 0; i < report.pending_count; ++i) {
            const auto& key = report.pending[i];
            const bool previously_covered = key.origin_session < previous.current_origin_session ||
                (key.origin_session == previous.current_origin_session &&
                 key.sequence <= previous.durable_admission_highwater);
            if (previously_covered &&
                !report_contains(previous, key.origin_session, key.sequence))
                return RetirementReportApply::Conflict;
        }
    }
    if (current.generation == std::numeric_limits<std::uint64_t>::max())
        return RetirementReportApply::Invalid;
    candidate = current;
    candidate.generation = current.generation + 1;
    candidate.storage_epoch = epoch_;
    candidate.occupancy_mask |= static_cast<std::uint16_t>(1U << index);
    candidate.legacy_binding_domain = false;
    auto& saved = candidate.nodes[index];
    saved = {};
    saved.enrollment_generation = enrollment_generation;
    saved.report_generation = report.generation;
    saved.report_hmac = verified_report_hmac;
    saved.current_origin_session = report.current_origin_session;
    saved.durable_admission_highwater = report.durable_admission_highwater;
    saved.pending_count = report.pending_count;
    std::copy_n(report.pending.begin(), report.pending_count, saved.pending.begin());
    return RetirementReportApply::Prepared;
}

ExactEventResult ExactEventKeyLedger::classify(const RetirementSnapshot& snapshot,
        std::uint8_t slot, std::uint32_t enrollment_generation,
        std::uint64_t origin_session, std::uint64_t sequence,
        const std::array<std::uint8_t, 32>& digest) const {
    if (slot >= kMaxRetirementNodes || enrollment_generation == 0 ||
        origin_session == 0 || sequence == 0 ||
        !nonzero(digest.data(), digest.size())) return ExactEventResult::Invalid;
    const bool has_report = slot < kMaxRetirementNodes &&
        (snapshot.occupancy_mask & (1U << slot)) != 0 &&
        snapshot.nodes[slot].enrollment_generation == enrollment_generation;
    if (has_report) {
        const auto& node = snapshot.nodes[slot];
        if (origin_session > node.current_origin_session) return ExactEventResult::Invalid;
        const bool covered = origin_session < node.current_origin_session ||
            (origin_session == node.current_origin_session &&
             sequence <= node.durable_admission_highwater);
        if (covered && !report_contains(node, origin_session, sequence))
            return ExactEventResult::Stale;
    }
    for (std::size_t i = 0; i < count_; ++i) {
        const auto& entry = entries_[i];
        if (entry.enrollment_slot == slot &&
            entry.enrollment_generation == enrollment_generation &&
            entry.origin_session == origin_session && entry.sequence == sequence)
            return entry.digest == digest ? ExactEventResult::Duplicate
                                          : ExactEventResult::Conflict;
    }
    return count_ == kMaxExactEventEvidence ? ExactEventResult::Full : ExactEventResult::New;
}

bool ExactEventKeyLedger::insert(const ExactEventEvidence& entry) {
    if (entry.enrollment_slot >= kMaxRetirementNodes ||
        entry.enrollment_generation == 0 || entry.origin_session == 0 ||
        entry.sequence == 0 || !nonzero(entry.digest.data(), entry.digest.size()) ||
        count_ == kMaxExactEventEvidence) return false;
    for (std::size_t i = 0; i < count_; ++i)
        if (key_equal(entries_[i], entry)) return false;
    entries_[count_++] = entry;
    return true;
}

bool ExactEventKeyLedger::erase_retirement_eligible(const RetirementSnapshot& snapshot) {
    std::size_t kept = 0;
    for (std::size_t i = 0; i < count_; ++i) {
        const auto& entry = entries_[i];
        bool eligible = false;
        if (entry.enrollment_slot < kMaxRetirementNodes &&
            (snapshot.occupancy_mask & (1U << entry.enrollment_slot)) != 0) {
            const auto& report = snapshot.nodes[entry.enrollment_slot];
            if (report.enrollment_generation == entry.enrollment_generation) {
                const bool covered = entry.origin_session < report.current_origin_session ||
                    (entry.origin_session == report.current_origin_session &&
                     entry.sequence <= report.durable_admission_highwater);
                eligible = covered && !report_contains(report, entry.origin_session,
                                                       entry.sequence);
            }
        }
        if (!eligible) entries_[kept++] = entry;
    }
    for (std::size_t i = kept; i < count_; ++i) entries_[i] = {};
    const bool changed = kept != count_;
    count_ = kept;
    return changed;
}

}  // namespace gs::hub::durable

std::size_t gs::hub::durable::RetirementSnapshot::node_count() const {
    std::size_t count = 0;
    for (std::size_t i = 0; i < kMaxRetirementNodes; ++i)
        if ((occupancy_mask & (1U << i)) != 0) ++count;
    return count;
}
