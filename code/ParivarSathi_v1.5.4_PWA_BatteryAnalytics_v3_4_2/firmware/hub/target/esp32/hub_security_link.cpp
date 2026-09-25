#include "firmware/hub/target/esp32/hub_security_link.hpp"

#include "firmware/common/security/target_wrapping_key.hpp"

#include "nvs.h"

#include <algorithm>
#include <cstdio>
#include <utility>

namespace gs::hub::target {
namespace {
std::string id_for_mac(const HubSecurityLink::Mac& mac, const char* prefix) {
    char text[32]{};
    std::snprintf(text, sizeof(text), "%s-%02x%02x%02x%02x%02x%02x", prefix,
                  mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return text;
}

bool load_or_create_home_id(security::CommissioningCrypto& crypto,
                            std::string& home_id) {
    nvs_handle_t handle = 0;
    if (nvs_open("gs_home", NVS_READWRITE, &handle) != ESP_OK) return false;
    std::array<std::uint8_t, 16> raw{};
    std::size_t length = raw.size();
    const auto read = nvs_get_blob(handle, "id", raw.data(), &length);
    if (read == ESP_ERR_NVS_NOT_FOUND) {
        if (!crypto.random_bytes(raw.data(), raw.size()) ||
            nvs_set_blob(handle, "id", raw.data(), raw.size()) != ESP_OK ||
            nvs_commit(handle) != ESP_OK) {
            nvs_close(handle);
            return false;
        }
        std::array<std::uint8_t, 16> checked{};
        length = checked.size();
        const bool committed = nvs_get_blob(handle, "id", checked.data(),
                                            &length) == ESP_OK &&
                               length == raw.size() && checked == raw;
        crypto.secure_zero(checked.data(), checked.size());
        if (!committed) {
            nvs_close(handle);
            return false;
        }
    } else if (read != ESP_OK || length != raw.size()) {
        nvs_close(handle);
        return false;
    }
    nvs_close(handle);
    if (std::all_of(raw.begin(), raw.end(), [](std::uint8_t byte) { return byte == 0; }))
        return false;
    constexpr char hex[] = "0123456789abcdef";
    home_id = "home-";
    for (auto byte : raw) {
        home_id.push_back(hex[byte >> 4]);
        home_id.push_back(hex[byte & 0x0f]);
    }
    crypto.secure_zero(raw.data(), raw.size());
    return true;
}
}  // namespace

HubSecurityLink::HubSecurityLink() = default;

HubSecurityLink::~HubSecurityLink() {
    for (auto& binding : bindings_)
        crypto_.secure_zero(binding.installation_key.data(),
                            binding.installation_key.size());
    crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
    crypto_.secure_zero(journal_key_.data(), journal_key_.size());
}

bool HubSecurityLink::initialize(const Mac& hub_mac) {
    if (registry_ || !crypto_.ready() || !identity_.initialize() ||
        !identity_.public_key("hub", hub_public_key_) ||
        !security::load_or_create_target_wrapping_key(crypto_, wrapping_key_) ||
        !load_or_create_home_id(crypto_, home_id_)) {
        faulted_ = true;
        return false;
    }
    hub_id_ = id_for_mac(hub_mac, "hub");
    security::Bytes journal_salt(home_id_.begin(), home_id_.end());
    journal_salt.insert(journal_salt.end(), hub_id_.begin(), hub_id_.end());
    constexpr char kJournalContext[] = "GharSajag/HubJournal/v1";
    const security::Bytes journal_context(kJournalContext,
                                          kJournalContext + sizeof(kJournalContext) - 1U);
    if (!crypto_.hkdf_sha256(wrapping_key_, journal_salt, journal_context,
                             journal_key_)) {
        crypto_.secure_zero(journal_salt.data(), journal_salt.size());
        crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
        faulted_ = true;
        return false;
    }
    crypto_.secure_zero(journal_salt.data(), journal_salt.size());
    repository_ = std::make_unique<HubRegistryRepository>(
        crypto_, store_, wrapping_key_, home_id_, hub_id_, hub_public_key_,
        kInstalledCapacity, kInstalledCapacity);
    crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
    registry_ = std::make_unique<NodeRegistry>(home_id_, hub_id_,
                                               kInstalledCapacity, kInstalledCapacity);
    const auto loaded = repository_->load();
    if (loaded.status == HubRegistryLoadStatus::Corrupt ||
        loaded.status == HubRegistryLoadStatus::IoError ||
        (loaded.status == HubRegistryLoadStatus::Ready &&
         (!loaded.state || !registry_->restore(loaded.state->registry)))) {
        faulted_ = true;
        return false;
    }
    if (loaded.status == HubRegistryLoadStatus::Ready) bindings_ = loaded.state->bindings;
    return true;
}

bool HubSecurityLink::attach_event_journal(hub::HubJournal& journal,
                                           hub::JournalSlotStore& store) {
    return !faulted_ && registry_ && repository_ &&
           std::any_of(journal_key_.begin(), journal_key_.end(),
                       [](std::uint8_t byte) { return byte != 0; }) &&
           journal.attach_persistence(crypto_, store, journal_key_);
}

bool HubSecurityLink::persist_candidate(
    NodeRegistry& candidate,
    const std::vector<security::CommissioningBinding>& bindings) {
    HubRegistryState state{candidate.snapshot(), bindings};
    return repository_->save(state);
}

std::optional<HubSecurityLink::Outbound> HubSecurityLink::reply(
    const Mac& destination, const security::wire::Message& message) {
    return Outbound{destination, message};
}

const security::CommissioningBinding* HubSecurityLink::binding_for(
    const std::string& device_id) const {
    const auto found = std::find_if(bindings_.begin(), bindings_.end(),
        [&](const auto& value) { return value.device_id == device_id; });
    return found == bindings_.end() ? nullptr : &*found;
}

bool HubSecurityLink::expected_source(const Mac& source) const {
    if (expected_ && expected_->radio_mac == source) return true;
    if (!registry_) return false;
    for (const auto& record : registry_->snapshot().active)
        if (record.radio_mac == source && !record.quarantined) return true;
    return false;
}

std::optional<HubSecurityLink::Mac> HubSecurityLink::expire_candidate(
    std::uint64_t now_ms) {
    if (!expected_ || now_ms <= pairing_deadline_ms_) return std::nullopt;
    const Mac expired = expected_->radio_mac;
    expected_.reset();
    commissioning_.reset();
    assemblers_.erase(expired);
    for (const auto& enrolled : registry_->snapshot().active)
        if (enrolled.radio_mac == expired) return std::nullopt;
    return expired;
}

std::optional<HubSecurityLink::Outbound> HubSecurityLink::begin_commissioning(
    const ExpectedNode& exact, std::uint64_t now_ms) {
    if (faulted_ || !registry_ || expected_ ||
        exact.device_id != id_for_mac(exact.radio_mac, "c3") ||
        exact.public_key[0] != 0x04 || registry_->size() >= kInstalledCapacity ||
        registry_->is_revoked(exact.device_id) ||
        registry_->find(exact.device_id)) return std::nullopt;
    commissioning_.reset();
    expected_.reset();
    commissioning_ = std::make_unique<security::HubCommissioning>(
        crypto_, "hub", hub_id_, home_id_, exact.device_id,
        exact.public_key, exact.installer_code, exact.logical_id,
        exact.room, exact.function);
    const auto offer = commissioning_->open(now_ms, 120000);
    security::wire::Message message;
    if (!offer || !security::wire::encode(*offer, message)) {
        commissioning_.reset();
        return std::nullopt;
    }
    expected_ = exact;
    crypto_.secure_zero(expected_->installer_code.data(),
                        expected_->installer_code.size());
    pairing_deadline_ms_ = now_ms + 120000;
    return reply(exact.radio_mac, message);
}

std::optional<HubSecurityLink::Outbound> HubSecurityLink::accept(
    const Mac& source, const std::uint8_t* packet, std::size_t length,
    std::uint64_t now_ms) {
    if (faulted_ || !expected_source(source)) return std::nullopt;
    auto& assembler = assemblers_.try_emplace(source).first->second;
    const auto message = assembler.push(packet, length, now_ms);
    if (!message) return std::nullopt;
    security::wire::Message outbound;
    if (message->kind == security::wire::Kind::NodeProof &&
        expected_ && expected_->radio_mac == source && commissioning_) {
        security::NodeProof proof;
        if (!security::wire::decode(*message, proof)) return std::nullopt;
        const auto response = commissioning_->accept(proof, now_ms);
        if (!response || !security::wire::encode(*response, outbound)) return std::nullopt;
        return reply(source, outbound);
    }
    if (message->kind == security::wire::Kind::CommissioningFinal &&
        expected_ && expected_->radio_mac == source && commissioning_) {
        security::CommissioningFinal final;
        if (!security::wire::decode(*message, final)) return std::nullopt;
        const auto ack = commissioning_->confirm(final, now_ms);
        if (!ack || !commissioning_->binding()) return std::nullopt;
        if (!security::wire::encode(*ack, outbound)) return std::nullopt;
        const auto already = registry_->find(commissioning_->binding()->device_id);
        if (already && already->radio_mac == source &&
            already->p256_public_key == commissioning_->binding()->device_public_key)
            return reply(source, outbound);  // Lost final ACK: resend safely.
        auto candidate = std::make_unique<NodeRegistry>(home_id_, hub_id_,
                                                        kInstalledCapacity, kInstalledCapacity);
        if (!candidate->restore(registry_->snapshot())) return std::nullopt;
        EnrolledNode record;
        const auto& binding = *commissioning_->binding();
        record.device_id = binding.device_id;
        record.p256_public_key = binding.device_public_key;
        record.radio_mac = source;
        record.home_id = binding.home_id;
        record.hub_id = binding.hub_id;
        record.logical_id = binding.logical_id;
        record.room = binding.room;
        record.function = binding.function;
        if (candidate->enroll(record) != RegistryResult::Accepted) return std::nullopt;
        auto next_bindings = bindings_;
        next_bindings.push_back(binding);
        if (!persist_candidate(*candidate, next_bindings)) return std::nullopt;
        registry_ = std::move(candidate);
        bindings_ = std::move(next_bindings);
        return reply(source, outbound);
    }
    if (message->kind == security::wire::Kind::RejoinHello) {
        security::RejoinHello hello;
        if (!security::wire::decode(*message, hello)) return std::nullopt;
        const auto record = registry_->find(hello.device_id);
        const auto* binding = binding_for(hello.device_id);
        if (!record || record->quarantined || record->radio_mac != source ||
            !binding) return std::nullopt;
        auto pending = std::make_unique<PendingRejoin>(crypto_, *binding,
                                                       record->last_session);
        const auto challenge = pending->protocol.accept(hello);
        if (!challenge || !security::wire::encode(*challenge, outbound))
            return std::nullopt;
        rejoining_[source] = std::move(pending);
        return reply(source, outbound);
    }
    if (message->kind == security::wire::Kind::RejoinFinal) {
        const auto found = rejoining_.find(source);
        if (found == rejoining_.end()) return std::nullopt;
        security::RejoinFinal final;
        if (!security::wire::decode(*message, final)) return std::nullopt;
        auto& pending = *found->second;
        const auto ack = pending.protocol.confirm(final);
        if (!ack || !pending.protocol.session_salt()) return std::nullopt;
        if (!pending.committed) {
            auto candidate = std::make_unique<NodeRegistry>(
                home_id_, hub_id_, kInstalledCapacity, kInstalledCapacity);
            if (!candidate->restore(registry_->snapshot()) ||
                candidate->rejoin(pending.binding.device_id, source,
                    pending.protocol.authenticated_session()) != RegistryResult::Accepted ||
                !persist_candidate(*candidate, bindings_)) return std::nullopt;
            auto frames = std::make_unique<security::RuntimeFrameSecurity>(
                crypto_, pending.binding);
            if (!frames->start(pending.protocol.authenticated_session(),
                               *pending.protocol.session_salt())) return std::nullopt;
            registry_ = std::move(candidate);
            auto record = registry_->find(pending.binding.device_id);
            if (!record) return std::nullopt;
            active_[source] = ActiveSession{*record, std::move(frames)};
            pending.committed = true;
            if (expected_ && expected_->radio_mac == source) {
                expected_.reset();
                commissioning_.reset();
            }
        }
        if (!security::wire::encode(*ack, outbound)) return std::nullopt;
        return reply(source, outbound);
    }
    return std::nullopt;
}

const EnrolledNode* HubSecurityLink::ready_node(const Mac& source) const {
    const auto found = active_.find(source);
    return found == active_.end() ? nullptr : &found->second.record;
}

security::RuntimeFrameSecurity* HubSecurityLink::frames_for(const Mac& source) {
    const auto found = active_.find(source);
    return found == active_.end() ? nullptr : found->second.frames.get();
}

std::vector<HubSecurityLink::Mac> HubSecurityLink::enrolled_macs() const {
    std::vector<Mac> out;
    if (!registry_) return out;
    for (const auto& record : registry_->snapshot().active)
        if (!record.quarantined) out.push_back(record.radio_mac);
    return out;
}

}  // namespace gs::hub::target
