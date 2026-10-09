#include "firmware/hub/components/storage/durable_event_outbox.hpp"
#include "firmware/hub/components/storage/journal.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using gs::security::Bytes;
using gs::security::Key32;
using gs::hub::storage::AdmissionClass;
using gs::hub::storage::DurableEventOutbox;
using gs::hub::storage::IdentityLookup;
using gs::hub::storage::OutboxAdmission;
using gs::hub::storage::OutboxLimits;
using gs::hub::storage::OutboxRecovery;
using gs::hub::storage::SegmentStore;

namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

class MemorySegments final : public SegmentStore {
public:
    explicit MemorySegments(std::uint64_t capacity, std::size_t count = 16)
        : capacity_(capacity), files_(count), exists_(count, false) {}

    std::uint64_t partition_capacity_bytes() const override { return capacity_; }
    bool segment_size(std::uint16_t segment, bool& exists,
                      std::uint32_t& bytes) override {
        if (segment >= files_.size()) return false;
        exists = exists_[segment];
        bytes = static_cast<std::uint32_t>(files_[segment].size());
        return true;
    }
    bool read(std::uint16_t segment, std::uint32_t offset,
              std::uint8_t* output, std::size_t requested,
              std::size_t& actual) override {
        if (segment >= files_.size()) return false;
        const auto& file = files_[segment];
        if (offset > file.size()) { actual = 0; return true; }
        actual = std::min(requested, file.size() - offset);
        std::copy_n(file.data() + offset, actual, output);
        return true;
    }
    bool append(std::uint16_t segment, const std::uint8_t* data,
                std::size_t length) override {
        if (segment >= files_.size()) return false;
        exists_[segment] = true;
        if (partial_append_once) {
            const auto partial = std::min(partial_append_bytes, length);
            files_[segment].insert(files_[segment].end(), data, data + partial);
            partial_append_once = false;
            return false;
        }
        files_[segment].insert(files_[segment].end(), data, data + length);
        return true;
    }
    bool sync(std::uint16_t segment) override {
        if (segment >= files_.size()) return false;
        if (sync_failure_once) { sync_failure_once = false; return false; }
        return true;
    }
    bool read_publication(Bytes& marker, bool& found) override {
        found = publication_found_;
        marker = publication_;
        return true;
    }
    bool publish_publication(const Bytes& marker) override {
        if (publication_failure_once) {
            publication_failure_once = false;
            return false;
        }
        publication_ = marker;
        publication_found_ = true;
        return true;
    }
    bool completion_size(bool& exists, std::uint32_t& bytes) override {
        exists = completion_found_;
        bytes = static_cast<std::uint32_t>(completion_.size());
        return true;
    }
    bool read_completion(std::uint32_t offset, std::uint8_t* output,
                         std::size_t requested, std::size_t& actual) override {
        if (offset > completion_.size()) { actual = 0; return true; }
        actual = std::min(requested, completion_.size() - offset);
        if (actual != 0) std::copy_n(completion_.data() + offset, actual, output);
        return true;
    }
    bool append_completion(const std::uint8_t* data, std::size_t length) override {
        if (completion_append_failure_once) {
            completion_append_failure_once = false;
            return false;
        }
        completion_.insert(completion_.end(), data, data + length);
        completion_found_ = true;
        return true;
    }
    bool sync_completion() override { return true; }
    bool truncate_completion(std::uint32_t bytes) override {
        if (bytes > completion_.size()) return false;
        completion_.resize(bytes);
        completion_found_ = !completion_.empty();
        return true;
    }
    bool read_completion_publication(Bytes& marker, bool& found) override {
        marker = completion_publication_;
        found = completion_publication_found_;
        return true;
    }
    bool publish_completion_publication(const Bytes& marker) override {
        if (completion_publication_failure_once) {
            completion_publication_failure_once = false;
            return false;
        }
        completion_publication_ = marker;
        completion_publication_found_ = true;
        return true;
    }
    void corrupt(std::uint16_t segment, std::size_t offset) {
        files_.at(segment).at(offset) ^= 0x80U;
    }
    void remove_publication() { publication_.clear(); publication_found_ = false; }
    void corrupt_publication() { publication_.at(20) ^= 0x80U; }

    bool partial_append_once{false};
    std::size_t partial_append_bytes{0};
    bool sync_failure_once{false};
    bool publication_failure_once{false};
    bool completion_append_failure_once{false};
    bool completion_publication_failure_once{false};

private:
    std::uint64_t capacity_;
    std::vector<Bytes> files_;
    std::vector<bool> exists_;
    Bytes publication_;
    bool publication_found_{false};
    Bytes completion_;
    bool completion_found_{false};
    Bytes completion_publication_;
    bool completion_publication_found_{false};
};

Key32 test_key() {
    Key32 key{};
    for (std::size_t i = 0; i < key.size(); ++i)
        key[i] = static_cast<std::uint8_t>(0x71U + i);
    return key;
}

bool make_event(std::uint64_t sequence, std::string& key, Bytes& payload) {
    gs::DomainEvent event;
    event.key = gs::EventKey("room" + std::to_string(sequence % 6U), 301, sequence,
                             "node-device-" + std::to_string(sequence % 6U));
    event.location = "room" + std::to_string(sequence % 6U);
    event.monotonic_ms = static_cast<gs::Milliseconds>(sequence * 1100U);
    event.occurred_at = static_cast<gs::EpochSeconds>(1800000000U + sequence);
    event.received_at = event.occurred_at;
    event.battery_mv = 2900;
    event.sensor_type = gs::SensorType::Pir;
    switch (sequence % 8U) {
        case 0: event.kind = gs::EventKind::Motion; break;
        case 1: event.kind = gs::EventKind::DoorOpen; event.sensor_type = gs::SensorType::Reed; break;
        case 2: event.kind = gs::EventKind::DoorClosed; event.sensor_type = gs::SensorType::Reed; break;
        case 3: event.kind = gs::EventKind::CallFamily; event.sensor_type = gs::SensorType::Button; break;
        case 4: event.kind = gs::EventKind::OkPressed; event.sensor_type = gs::SensorType::Button; break;
        case 5: event.kind = gs::EventKind::Gap; event.sensor_type = gs::SensorType::System; break;
        case 6: event.kind = gs::EventKind::Heartbeat; event.sensor_type = gs::SensorType::Heartbeat; break;
        default:
            event.kind = gs::EventKind::MotionSummary;
            event.motion_aggregate = gs::DomainEvent::MotionAggregate{
                3, event.monotonic_ms - 1500, event.monotonic_ms};
            break;
    }
    key = event.key.str();
    return gs::hub::HubJournal::encode_event_payload(event, payload);
}

struct VisitState { std::uint64_t count{0}; bool valid{true}; };
struct CountState { std::uint64_t count{0}; bool ordered{true}; };

bool count_visit(void* context, std::uint64_t ordinal, const std::string&,
                 const Bytes&) {
    auto& state = *static_cast<CountState*>(context);
    state.ordered = state.ordered && ordinal == state.count + 1;
    ++state.count;
    return state.ordered;
}

bool validate_visit(void* context, std::uint64_t ordinal, const std::string& key,
                    const Bytes& payload) {
    auto& state = *static_cast<VisitState*>(context);
    std::string expected_key;
    Bytes expected_payload;
    state.valid = state.valid && ordinal == state.count + 1 &&
                  make_event(ordinal, expected_key, expected_payload) &&
                  key == expected_key && payload == expected_payload;
    ++state.count;
    return state.valid;
}

std::uint64_t scalable_append_and_reboot(
    gs::host::security::OpenSslCommissioningCrypto& crypto, const Key32& key) {
    MemorySegments flash(4U * 1024U * 1024U);
    OutboxLimits limits;
    DurableEventOutbox outbox(flash, crypto, key, limits);
    require(outbox.recover() == OutboxRecovery::Empty, "fresh outbox recovery");
    constexpr std::uint64_t checkpoints[] = {129, 385, 728, 3278, 6556};
    std::size_t checkpoint = 0;
    for (std::uint64_t sequence = 1; sequence <= checkpoints[4]; ++sequence) {
        std::string event_key;
        Bytes payload;
        require(make_event(sequence, event_key, payload), "encode test event");
        const auto admitted = outbox.append(event_key, payload, AdmissionClass::Protected);
        if (admitted != OutboxAdmission::Committed) {
            std::cerr << "append failure sequence=" << sequence << " result="
                      << static_cast<unsigned>(admitted) << " records="
                      << outbox.record_count() << " used="
                      << outbox.capacity_budget_used_bytes() << " capacity="
                      << outbox.log_capacity_bytes() << "\n";
            require(false, "append exceeded byte-backed capacity before stress target");
        }
        if (sequence == checkpoints[checkpoint]) {
            require(outbox.record_count() == sequence, "count checkpoint mismatch");
            ++checkpoint;
        }
    }
    require(outbox.committed_frame_bytes() < outbox.log_capacity_bytes(),
            "stress frame size should remain within byte capacity");

    std::string retry_key;
    Bytes retry_payload;
    require(make_event(385, retry_key, retry_payload), "encode retry fixture");
    DurableEventOutbox rebooted(flash, crypto, key, limits);
    require(rebooted.recover() == OutboxRecovery::Ready &&
            rebooted.record_count() == checkpoints[4], "recover 6,556 exact records");
    require(rebooted.append(retry_key, retry_payload, AdmissionClass::Protected) ==
                OutboxAdmission::Duplicate,
            "lost-ACK retry must deduplicate after reboot");
    bool found = false;
    require(rebooted.contains(retry_key, found) == IdentityLookup::Found && found,
            "recovered identity index lookup");
    retry_payload.push_back(0x55);
    require(rebooted.append(retry_key, retry_payload, AdmissionClass::Protected) ==
                OutboxAdmission::IdentityConflict,
            "same EventKey with changed payload must not be accepted");

    VisitState visited;
    require(rebooted.for_each(validate_visit, &visited) && visited.valid &&
            visited.count == checkpoints[4], "stream iteration preserves ordered exact payloads");
    return rebooted.committed_frame_bytes();
}

void capacity_reserve(gs::host::security::OpenSslCommissioningCrypto& crypto,
                      const Key32& key) {
    MemorySegments flash(512U * 1024U, 8);
    OutboxLimits limits;
    limits.segment_count = 8;
    limits.segment_bytes = 64U * 1024U;
    limits.filesystem_workspace_bytes = 0;
    limits.protected_capacity_bytes = 64U * 1024U;
    DurableEventOutbox outbox(flash, crypto, key, limits);
    require(outbox.recover() == OutboxRecovery::Empty, "reserve fixture initialization");
    std::uint64_t sequence = 1;
    OutboxAdmission result = OutboxAdmission::Committed;
    while (result == OutboxAdmission::Committed) {
        std::string event_key;
        Bytes payload;
        require(make_event(sequence, event_key, payload), "reserve fixture event");
        result = outbox.append(event_key, payload, AdmissionClass::Ordinary);
        if (result == OutboxAdmission::Committed) ++sequence;
    }
    require(result == OutboxAdmission::ReserveProtected,
            "ordinary admission must stop at the configured byte reserve");
    std::string critical_key;
    Bytes critical_payload;
    require(make_event(sequence, critical_key, critical_payload), "protected event fixture");
    require(outbox.append(critical_key, critical_payload, AdmissionClass::Protected) ==
                OutboxAdmission::Committed,
            "protected-class event may consume candidate reserve");
    ++sequence;
    OutboxAdmission final_result = OutboxAdmission::Committed;
    while (final_result == OutboxAdmission::Committed) {
        std::string final_key;
        Bytes final_payload;
        require(make_event(sequence, final_key, final_payload), "capacity edge fixture");
        final_result = outbox.append(final_key, final_payload, AdmissionClass::Protected);
        if (final_result == OutboxAdmission::Committed) ++sequence;
    }
    require(final_result == OutboxAdmission::CapacityExhausted,
            "protected admission must stop at physical byte capacity");
    std::string rejected_key;
    Bytes rejected_payload;
    require(make_event(sequence + 1, rejected_key, rejected_payload), "full rejection fixture");
    require(outbox.append(rejected_key, rejected_payload, AdmissionClass::Ordinary) ==
                OutboxAdmission::CapacityExhausted,
            "full capacity must be distinguished from reserve protection");
}

void interrupted_write_and_sync(gs::host::security::OpenSslCommissioningCrypto& crypto,
                                const Key32& key) {
    OutboxLimits limits;
    limits.segment_count = 4;
    limits.segment_bytes = 2048;
    limits.filesystem_workspace_bytes = 0;
    limits.protected_capacity_bytes = 0;

    MemorySegments torn_flash(8192, 4);
    DurableEventOutbox writer(torn_flash, crypto, key, limits);
    require(writer.recover() == OutboxRecovery::Empty, "torn-write fixture init");
    std::string event_key;
    Bytes payload;
    require(make_event(91, event_key, payload), "torn-write event");
    torn_flash.partial_append_once = true;
    torn_flash.partial_append_bytes = 11;
    require(writer.append(event_key, payload, AdmissionClass::Protected) ==
                OutboxAdmission::RestartRequired,
            "partial append must be rejected without ACK");
    DurableEventOutbox retry(torn_flash, crypto, key, limits);
    require(retry.recover() == OutboxRecovery::Empty && retry.record_count() == 0,
            "partial tail is not recovered as committed");
    require(retry.append(event_key, payload, AdmissionClass::Protected) ==
                OutboxAdmission::Committed,
            "retry progresses to a fresh segment after torn tail");
    DurableEventOutbox after_torn_retry(torn_flash, crypto, key, limits);
    require(after_torn_retry.recover() == OutboxRecovery::Ready &&
            after_torn_retry.record_count() == 1,
            "later segment recovers after earlier torn tail");
    CountState after_torn_visit;
    require(after_torn_retry.for_each(count_visit, &after_torn_visit) &&
            after_torn_visit.ordered && after_torn_visit.count == 1,
            "streaming crosses an earlier torn segment tail");

    MemorySegments uncertain_flash(8192, 4);
    DurableEventOutbox uncertain(uncertain_flash, crypto, key, limits);
    require(uncertain.recover() == OutboxRecovery::Empty, "sync-cut fixture init");
    uncertain_flash.sync_failure_once = true;
    require(uncertain.append(event_key, payload, AdmissionClass::Protected) ==
                OutboxAdmission::RestartRequired,
            "failed durability barrier must not receive ACK");
    DurableEventOutbox after_cut(uncertain_flash, crypto, key, limits);
    require(after_cut.recover() == OutboxRecovery::IntegrityFailure,
            "unpublished first record without an older authority fails closed");
}

void publication_recovery(gs::host::security::OpenSslCommissioningCrypto& crypto,
                          const Key32& key) {
    OutboxLimits limits;
    limits.segment_count = 4;
    limits.segment_bytes = 2048;
    limits.filesystem_workspace_bytes = 0;
    limits.protected_capacity_bytes = 0;
    MemorySegments flash(8192, 4);
    DurableEventOutbox writer(flash, crypto, key, limits);
    require(writer.recover() == OutboxRecovery::Empty, "publication fixture init");
    std::string first_key;
    Bytes first_payload;
    std::string next_key;
    Bytes next_payload;
    require(make_event(201, first_key, first_payload) &&
            make_event(202, next_key, next_payload), "publication fixtures");
    require(writer.append(first_key, first_payload, AdmissionClass::Protected) ==
                OutboxAdmission::Committed,
            "initial root publication");

    // Simulate power loss after event sync but before publication. The operation
    // is not ACKed; exact retry after reboot publishes it exactly once.
    flash.publication_failure_once = true;
    require(writer.append(next_key, next_payload, AdmissionClass::Protected) ==
                OutboxAdmission::MetadataPublicationFailure,
            "failed publication must not be ACKed");
    DurableEventOutbox recovered(flash, crypto, key, limits);
    require(recovered.recover() == OutboxRecovery::Ready &&
            recovered.record_count() == 1,
            "old published root recovers with one staged next record");
    bool staged_found = false;
    require(recovered.contains(next_key, staged_found) == IdentityLookup::Staged &&
            staged_found,
            "identity query distinguishes staged from published record");
    require(recovered.append(next_key, next_payload, AdmissionClass::Protected) ==
                OutboxAdmission::Committed && recovered.record_count() == 2,
            "exact retry completes staged publication");
    DurableEventOutbox lost_ack(flash, crypto, key, limits);
    require(lost_ack.recover() == OutboxRecovery::Ready && lost_ack.record_count() == 2 &&
            lost_ack.append(next_key, next_payload, AdmissionClass::Protected) ==
                OutboxAdmission::Duplicate,
            "lost ACK after publication is deduplicated after restart");
    CountState visits;
    require(lost_ack.for_each(count_visit, &visits) && visits.ordered && visits.count == 2,
            "streaming only exposes published records");

    MemorySegments missing(8192, 4);
    DurableEventOutbox source(missing, crypto, key, limits);
    require(source.recover() == OutboxRecovery::Empty &&
            source.append(first_key, first_payload, AdmissionClass::Protected) ==
                OutboxAdmission::Committed,
            "missing-marker fixture committed");
    missing.remove_publication();
    DurableEventOutbox missing_root(missing, crypto, key, limits);
    require(missing_root.recover() == OutboxRecovery::IntegrityFailure,
            "missing published marker beside event data fails closed");

    MemorySegments corrupt(8192, 4);
    DurableEventOutbox corrupt_source(corrupt, crypto, key, limits);
    require(corrupt_source.recover() == OutboxRecovery::Empty &&
            corrupt_source.append(first_key, first_payload, AdmissionClass::Protected) ==
                OutboxAdmission::Committed,
            "corrupt-marker fixture committed");
    corrupt.corrupt_publication();
    DurableEventOutbox corrupt_root(corrupt, crypto, key, limits);
    require(corrupt_root.recover() == OutboxRecovery::IntegrityFailure,
            "corrupt latest publication marker fails closed");

    MemorySegments torn_then_staged(8192, 4);
    DurableEventOutbox first_writer(torn_then_staged, crypto, key, limits);
    std::string base_key;
    Bytes base_payload;
    require(first_writer.recover() == OutboxRecovery::Empty &&
            make_event(203, base_key, base_payload) &&
            first_writer.append(base_key, base_payload, AdmissionClass::Protected) ==
                OutboxAdmission::Committed,
            "torn-then-staged base commit");
    std::string retry_after_torn_key;
    Bytes retry_after_torn_payload;
    require(make_event(204, retry_after_torn_key, retry_after_torn_payload),
            "torn-then-staged retry event");
    torn_then_staged.partial_append_once = true;
    torn_then_staged.partial_append_bytes = 11;
    require(first_writer.append(retry_after_torn_key, retry_after_torn_payload,
                                AdmissionClass::Protected) ==
                OutboxAdmission::RestartRequired,
            "partial event after root is not ACKed");
    DurableEventOutbox retry_writer(torn_then_staged, crypto, key, limits);
    require(retry_writer.recover() == OutboxRecovery::Ready &&
            retry_writer.record_count() == 1,
            "published root survives earlier torn tail");
    torn_then_staged.publication_failure_once = true;
    require(retry_writer.append(retry_after_torn_key, retry_after_torn_payload,
                                AdmissionClass::Protected) ==
                OutboxAdmission::MetadataPublicationFailure,
            "publication interruption after prior torn attempt is not ACKed");
    DurableEventOutbox staged_recovery(torn_then_staged, crypto, key, limits);
    require(staged_recovery.recover() == OutboxRecovery::Ready &&
            staged_recovery.record_count() == 1 &&
            staged_recovery.append(retry_after_torn_key, retry_after_torn_payload,
                                   AdmissionClass::Protected) ==
                OutboxAdmission::Committed && staged_recovery.record_count() == 2,
            "exact retry publishes complete frame after prior partial attempt");
}

void corruption_fails_closed(gs::host::security::OpenSslCommissioningCrypto& crypto,
                             const Key32& key) {
    MemorySegments flash(8192, 4);
    OutboxLimits limits;
    limits.segment_count = 4;
    limits.segment_bytes = 2048;
    limits.filesystem_workspace_bytes = 0;
    limits.protected_capacity_bytes = 0;
    DurableEventOutbox outbox(flash, crypto, key, limits);
    require(outbox.recover() == OutboxRecovery::Empty, "corruption fixture init");
    std::string event_key;
    Bytes payload;
    require(make_event(92, event_key, payload), "corruption event");
    require(outbox.append(event_key, payload, AdmissionClass::Protected) ==
                OutboxAdmission::Committed,
            "corruption fixture commit");
    flash.corrupt(0, 24);
    DurableEventOutbox rebooted(flash, crypto, key, limits);
    require(rebooted.recover() == OutboxRecovery::IntegrityFailure && !rebooted.healthy(),
            "corrupt committed record must fail closed");
}
}  // namespace

int main() {
    try {
        gs::host::security::OpenSslCommissioningCrypto crypto;
        const auto key = test_key();
        const auto stress_frame_bytes = scalable_append_and_reboot(crypto, key);
        capacity_reserve(crypto, key);
        interrupted_write_and_sync(crypto, key);
        publication_recovery(crypto, key);
        corruption_fails_closed(crypto, key);
        std::cout << "durable_event_outbox_validation=PASS records=6556 frame_bytes="
                  << stress_frame_bytes << " scenarios=5\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "durable_event_outbox_validation=FAIL reason=" << error.what() << '\n';
        return 1;
    }
}
