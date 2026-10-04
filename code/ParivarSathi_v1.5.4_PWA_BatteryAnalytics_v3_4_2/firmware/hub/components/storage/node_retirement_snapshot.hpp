#pragma once

#include "firmware/common/transport/node_retirement_protocol.hpp"
#include "firmware/hub/components/storage/durable_transition.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace gs::hub::durable {

constexpr std::size_t kMaxRetirementNodes = 10;
constexpr std::size_t kRetirementSnapshotBankBytes = 5777;
constexpr std::size_t kRetirementLegacyInspectionBytes = 6096;
constexpr std::size_t kRetirementSnapshotBankCount = 3;
constexpr std::size_t kMaxExactEventEvidence = 128;

struct RetirementNodeSnapshot {
    std::array<std::uint8_t, 32> binding_digest{};
    std::uint32_t enrollment_generation{0};
    std::uint64_t report_generation{0};
    std::array<std::uint8_t, 32> report_hmac{};
    std::uint64_t current_origin_session{0};
    std::uint64_t durable_admission_highwater{0};
    std::array<transport::RetirementEventKey, transport::kMaxRetirementKeys> pending{};
    std::uint8_t pending_count{0};
};

struct RetirementSnapshot {
    std::uint32_t storage_epoch{0};
    std::uint64_t generation{0};
    std::array<RetirementNodeSnapshot, kMaxRetirementNodes> nodes{};
    std::uint16_t occupancy_mask{0};
    bool legacy_binding_domain{false};
    std::size_t node_count() const;
};

using RetirementSnapshotReference = ReportSnapshotReference;

enum class RetirementReportApply {
    Prepared,
    Duplicate,
    Stale,
    Conflict,
    Invalid,
    Full,
    StorageFault
};

class RetirementSnapshotRepository {
public:
    RetirementSnapshotRepository(BlobStore& store,
                                 security::CommissioningCrypto& crypto,
                                 security::Key32 key, std::uint32_t epoch);
    ~RetirementSnapshotRepository();
    RetirementSnapshotRepository(const RetirementSnapshotRepository&) = delete;
    RetirementSnapshotRepository& operator=(const RetirementSnapshotRepository&) = delete;

    static bool encode(security::CommissioningCrypto&, const security::Key32&,
                       const RetirementSnapshot&, security::Bytes&);
    static bool decode(security::CommissioningCrypto&, const security::Key32&,
                       const security::Bytes&, RetirementSnapshot&);
    bool load(const RetirementSnapshotReference&, RetirementSnapshot&) const;
    // Authenticated schema-1 inspection is migration input only. Callers must
    // attribute every occupied record before converting it; this does not make
    // a legacy snapshot valid retirement authority.
    bool inspect_legacy_for_migration(const RetirementSnapshotReference&,
                                      RetirementSnapshot&) const;
    // Writes and verifies an unselected bank. A checkpoint must select the
    // returned reference before its contents may be used as retirement proof.
    bool prepare_bank(const RetirementSnapshot&, std::uint8_t referenced_bank_mask,
                      RetirementSnapshotReference&);
    RetirementReportApply apply_authenticated_report(
        const RetirementSnapshot& current,
        const std::array<std::uint8_t, 32>& binding_digest,
        std::uint8_t enrollment_slot,
        std::uint32_t enrollment_generation,
        std::uint64_t authenticated_transport_session,
        const transport::NodeRetirementReportV1&,
        const security::Key32& verified_report_hmac,
        RetirementSnapshot& candidate) const;

private:
    static bool same_node_report(const RetirementNodeSnapshot&,
                                 const transport::NodeRetirementReportV1&,
                                 const security::Key32&);
    BlobStore& store_;
    security::CommissioningCrypto& crypto_;
    security::Key32 key_{};
    std::uint32_t epoch_{0};
};

struct ExactEventEvidence {
    std::uint8_t enrollment_slot{0};
    std::uint32_t enrollment_generation{0};
    std::uint64_t origin_session{0};
    std::uint64_t sequence{0};
    std::array<std::uint8_t, 32> digest{};
};

enum class ExactEventResult { New, Duplicate, Conflict, Stale, Full, Invalid };

// Bounded reducer-facing exact ledger. Durable ownership of its chunks is
// recorded by Checkpoint::dedupe_evidence_chunks.
class ExactEventKeyLedger {
public:
    ExactEventResult classify(const RetirementSnapshot&,
                              std::uint8_t enrollment_slot,
                              std::uint32_t enrollment_generation,
                              std::uint64_t origin_session,
                              std::uint64_t sequence,
                              const std::array<std::uint8_t, 32>& digest) const;
    bool insert(const ExactEventEvidence&);
    bool erase_retirement_eligible(const RetirementSnapshot&);
    const std::array<ExactEventEvidence, kMaxExactEventEvidence>& entries() const {
        return entries_;
    }
    std::size_t size() const { return count_; }
private:
    std::array<ExactEventEvidence, kMaxExactEventEvidence> entries_{};
    std::size_t count_{0};
};

}  // namespace gs::hub::durable
