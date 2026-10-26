#include "firmware/node/target/esp32c3/node_security_link.hpp"
#include "firmware/common/transport/node_retirement_protocol.hpp"

#include "firmware/common/security/target_wrapping_key.hpp"
#include "firmware/node/target/esp32c3/nvs_session_provider.hpp"
#include "firmware/node/target/esp32c3/gs117_fixture_commissioning.hpp"

#include "esp_log.h"

#include <cstdio>
#include <limits>
#include <utility>

namespace gs::node::target {
namespace {
constexpr char kTag[] = "gs117_fixture";

class CommissioningBindingKeyWiper {
public:
    CommissioningBindingKeyWiper(security::CommissioningCrypto& crypto,
                                security::CommissioningBinding& binding)
        : crypto_(crypto), binding_(binding) {}
    ~CommissioningBindingKeyWiper() {
        crypto_.secure_zero(binding_.installation_key.data(),
                            binding_.installation_key.size());
    }
private:
    security::CommissioningCrypto& crypto_;
    security::CommissioningBinding& binding_;
};

class AssociationStateKeyWiper {
public:
    AssociationStateKeyWiper(security::CommissioningCrypto& crypto,
                             security::AssociationState& state)
        : crypto_(crypto), state_(state) {}
    ~AssociationStateKeyWiper() {
        if (state_.binding)
            crypto_.secure_zero(state_.binding->installation_key.data(),
                                state_.binding->installation_key.size());
    }
private:
    security::CommissioningCrypto& crypto_;
    security::AssociationState& state_;
};

std::string id_for_mac(const NodeSecurityLink::Mac& mac, const char* prefix) {
    char text[32]{};
    std::snprintf(text, sizeof(text), "%s-%02x%02x%02x%02x%02x%02x", prefix,
                  mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return text;
}

bool mac_from_hub_id(const std::string& id, NodeSecurityLink::Mac& mac) {
    if (id.size() != 16 || id.compare(0, 4, "hub-") != 0) return false;
    for (std::size_t index = 0; index < mac.size(); ++index) {
        const auto decode = [](char ch) -> int {
            if (ch >= '0' && ch <= '9') return ch - '0';
            if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
            return -1;
        };
        const int high = decode(id[4 + index * 2]);
        const int low = decode(id[5 + index * 2]);
        if (high < 0 || low < 0) return false;
        mac[index] = static_cast<std::uint8_t>((high << 4) | low);
    }
    return true;
}
}  // namespace

NodeSecurityLink::NodeSecurityLink() = default;

NodeSecurityLink::~NodeSecurityLink() {
    if (binding_)
        crypto_.secure_zero(binding_->installation_key.data(),
                            binding_->installation_key.size());
    crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
    crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
}

bool NodeSecurityLink::initialize(const Mac& physical_mac, std::uint64_t session,
                                   std::uint64_t now_ms) {
    if (phase_ != Phase::Uninitialized || session == 0 || !crypto_.ready() ||
        !identity_.initialize() ||
        !security::load_or_create_target_wrapping_key(crypto_, wrapping_key_)) {
        phase_ = Phase::Fault;
        return false;
    }
    physical_id_ = id_for_mac(physical_mac, "c3");
    session_ = session;
    security::Bytes recovery_salt(physical_id_.begin(), physical_id_.end());
    constexpr char kRecoveryContext[] = "GharSajag/NodeRecovery/v1";
    const security::Bytes recovery_context(
        kRecoveryContext, kRecoveryContext + sizeof(kRecoveryContext) - 1U);
    if (!crypto_.hkdf_sha256(wrapping_key_, recovery_salt, recovery_context,
                             recovery_key_)) {
        crypto_.secure_zero(recovery_salt.data(), recovery_salt.size());
        crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
        phase_ = Phase::Fault;
        return false;
    }
    crypto_.secure_zero(recovery_salt.data(), recovery_salt.size());
    repository_ = std::make_unique<security::AssociationRepository>(
        crypto_, store_, wrapping_key_, &previous_store_);
    crypto_.secure_zero(wrapping_key_.data(), wrapping_key_.size());
    const auto loaded = repository_->load();
    if (loaded.status == security::AssociationStatus::Corrupt ||
        loaded.status == security::AssociationStatus::IoError) {
        phase_ = Phase::Fault;
        return false;
    }
    if (loaded.status == security::AssociationStatus::Paired) {
        if (!loaded.binding || loaded.binding->device_id != physical_id_ ||
            !mac_from_hub_id(loaded.binding->hub_id, hub_mac_)) {
            phase_ = Phase::Fault;
            return false;
        }
        security::P256PublicKey actual_public{};
        if (!identity_.public_key("node", actual_public) ||
            !crypto_.constant_time_equal(actual_public.data(),
                                         loaded.binding->device_public_key.data(),
                                         actual_public.size())) {
            phase_ = Phase::Fault;
            return false;
        }
        binding_ = *loaded.binding;
        const auto pinned = health_ack_pinned_for_hub(binding_->hub_id);
        if (!pinned) {
            phase_ = Phase::Fault;
            return false;
        }
        pinned_v2_ = *pinned;
        phase_ = Phase::Rejoining;
        return true;
    }
    security::Key32 installer_code{};
    if (!security::load_target_installer_code(crypto_, installer_code)) {
        phase_ = Phase::Fault;
        return false;
    }
    commissioning_ = std::make_unique<security::NodeCommissioning>(
        crypto_, "node", physical_id_, installer_code);
    crypto_.secure_zero(installer_code.data(), installer_code.size());
    if (!commissioning_->enable_window(now_ms, 10U * 60U * 1000U)) {
        phase_ = Phase::Fault;
        return false;
    }
#if GS_HIL_CONTROL && !GS_HIL_BUILD && !GS_BAT_C8_PHYSICAL_WAKE
    if (loaded.status == security::AssociationStatus::Unpaired &&
        physical_id_ == "c3-146393c5d158") {
        auto previous = repository_->load_previous_association();
        Mac fixture_hub_mac{};
        if (previous.status == security::AssociationStatus::Paired &&
            previous.binding && previous.binding->device_id == physical_id_ &&
            previous.binding->hub_id != "hub-e072a1d38d34" &&
            loaded.generation == previous.generation + 1U &&
            mac_from_hub_id("hub-e072a1d38d34", fixture_hub_mac)) {
            hub_mac_ = fixture_hub_mac;
            expected_reassociation_hub_id_ = "hub-e072a1d38d34";
            test_fresh_commissioning_pending_ = true;
        }
        if (previous.binding)
            crypto_.secure_zero(previous.binding->installation_key.data(),
                                previous.binding->installation_key.size());
    }
#endif
    phase_ = Phase::Commissioning;
    return true;
}

Gs117ReassociationStatus NodeSecurityLink::begin_gs117_test_reassociation(
        const std::string& expected_hub_id, std::uint64_t now_ms) {
    constexpr char kFixtureHub[] = "hub-e072a1d38d34";
    constexpr char kFixtureHome[] = "gs177-test-product";
    Mac target_hub_mac{};
    const auto preflight = gs117_reassociation_preflight(
        phase_ == Phase::Rejoining, binding_.has_value() && repository_ != nullptr,
        expected_hub_id == kFixtureHub && mac_from_hub_id(expected_hub_id, target_hub_mac),
        binding_ && binding_->hub_id == expected_hub_id,
        binding_ && binding_->home_id == kFixtureHome);
    if (preflight != Gs117ReassociationStatus::Ready) return preflight;

    // Prove that the previous recovery state is readable before any live
    // association change. Its encrypted bytes are copied to a separate NVS
    // namespace and are retained after a successful re-association.
    node::NodeRecoveryRepository prior_recovery(
        crypto_, recovery_store_, recovery_key_, binding_->home_id,
        binding_->hub_id, binding_->logical_id);
    const auto prior_state = prior_recovery.load();
    if (prior_state.status == node::NodeRecoveryLoadStatus::Corrupt)
        return Gs117ReassociationStatus::RecoveryCorrupt;
    if (prior_state.status == node::NodeRecoveryLoadStatus::IoError)
        return Gs117ReassociationStatus::RecoveryIoError;

    security::Bytes recovery_blob;
    bool recovery_found = false;
    if (!recovery_store_.read(recovery_blob, recovery_found))
        return Gs117ReassociationStatus::RecoverySnapshotReadFailed;
    security::Bytes backup_blob;
    bool backup_found = false;
    if (!previous_recovery_store_.read(backup_blob, backup_found))
        return Gs117ReassociationStatus::RecoverySnapshotReadFailed;
    if (recovery_found) {
        if (prior_state.status != node::NodeRecoveryLoadStatus::Ready ||
            !prior_state.state) return Gs117ReassociationStatus::RecoveryStateUnavailable;
        if (backup_found) {
            if (backup_blob != recovery_blob)
                return Gs117ReassociationStatus::RecoveryBackupConflict;
        } else if (!previous_recovery_store_.write(recovery_blob)) {
            return Gs117ReassociationStatus::RecoveryBackupWriteFailed;
        }
        if (!previous_recovery_store_.read(backup_blob, backup_found) ||
            !backup_found || backup_blob != recovery_blob)
            return Gs117ReassociationStatus::RecoveryBackupVerifyFailed;
    } else if (backup_found) {
        return Gs117ReassociationStatus::RecoveryBackupConflict;
    }
    if (!repository_->preserve_previous_for_reassociation())
        return Gs117ReassociationStatus::AssociationBackupFailed;

    security::Key32 installer_code{};
    if (!security::load_target_installer_code(crypto_, installer_code)) {
        crypto_.secure_zero(installer_code.data(), installer_code.size());
        return Gs117ReassociationStatus::InstallerCodeUnavailable;
    }
    commissioning_ = std::make_unique<security::NodeCommissioning>(
        crypto_, "node", physical_id_, installer_code);
    crypto_.secure_zero(installer_code.data(), installer_code.size());
    if (!commissioning_->enable_window(now_ms, 10U * 60U * 1000U)) {
        commissioning_.reset();
        return Gs117ReassociationStatus::CommissioningWindowFailed;
    }
    hub_mac_ = target_hub_mac;
    expected_reassociation_hub_id_ = expected_hub_id;
    test_reassociation_pending_ = true;
    frames_.reset();
    rejoin_.reset();
    assembler_.reset();
    phase_ = Phase::Commissioning;
    return Gs117ReassociationStatus::Ready;
}

Gs117FreshCommissioningStatus NodeSecurityLink::begin_gs117_test_fresh_commissioning(
        const std::string& expected_hub_id, std::uint64_t now_ms) {
    constexpr char kFixtureNode[] = "c3-146393c5d158";
    constexpr char kFixtureHub[] = "hub-e072a1d38d34";
    if (expected_hub_id != kFixtureHub || !mac_from_hub_id(expected_hub_id, hub_mac_))
        return Gs117FreshCommissioningStatus::InvalidTargetHub;
    if (physical_id_ != kFixtureNode)
        return Gs117FreshCommissioningStatus::WrongPhysicalNode;
    if (repository_ == nullptr ||
        (phase_ != Phase::Rejoining && phase_ != Phase::Commissioning))
        return Gs117FreshCommissioningStatus::NotReady;

    auto active = repository_->load();
    AssociationStateKeyWiper active_key_wiper(crypto_, active);
    security::CommissioningBinding previous_binding;
    CommissioningBindingKeyWiper previous_key_wiper(crypto_, previous_binding);
    bool resetting_active_pair = false;
    if (active.status == security::AssociationStatus::Paired && active.binding) {
        if (phase_ != Phase::Rejoining || !binding_ ||
            active.binding->device_id != physical_id_ ||
            active.binding->hub_id != binding_->hub_id ||
            active.generation == std::numeric_limits<std::uint64_t>::max())
            return Gs117FreshCommissioningStatus::BindingUnavailable;
        previous_binding = *active.binding;
        if (previous_binding.hub_id == kFixtureHub)
            return Gs117FreshCommissioningStatus::AlreadyBoundToTarget;
        resetting_active_pair = true;
    } else if (active.status == security::AssociationStatus::Unpaired) {
        auto previous = repository_->load_previous_association();
        AssociationStateKeyWiper previous_key_wiper(crypto_, previous);
        if (phase_ != Phase::Commissioning ||
            previous.status != security::AssociationStatus::Paired || !previous.binding ||
            previous.binding->device_id != physical_id_ ||
            previous.binding->hub_id == kFixtureHub ||
            previous.generation == std::numeric_limits<std::uint64_t>::max() ||
            active.generation != previous.generation + 1U)
            return Gs117FreshCommissioningStatus::BindingUnavailable;
        previous_binding = *previous.binding;
    } else {
        return Gs117FreshCommissioningStatus::BindingUnavailable;
    }

    security::P256PublicKey actual_public_key{};
    if (!identity_.public_key("node", actual_public_key) ||
        !gs117_fixture_same_device_key(previous_binding, actual_public_key, physical_id_))
        return Gs117FreshCommissioningStatus::BindingUnavailable;

    node::NodeRecoveryRepository prior_recovery(
        crypto_, recovery_store_, recovery_key_, previous_binding.home_id,
        previous_binding.hub_id, previous_binding.logical_id);
    const auto prior = prior_recovery.load();
    if (prior.status == node::NodeRecoveryLoadStatus::Corrupt)
        return Gs117FreshCommissioningStatus::RecoveryCorrupt;
    if (prior.status == node::NodeRecoveryLoadStatus::IoError)
        return Gs117FreshCommissioningStatus::RecoveryIoError;
    if (prior.status == node::NodeRecoveryLoadStatus::Ready &&
        (!prior.state || !gs117_fixture_recovery_is_disposable(*prior.state)))
        return Gs117FreshCommissioningStatus::RecoveryNotDisposable;

    security::Bytes recovery_blob;
    bool recovery_found = false;
    security::Bytes saved_recovery;
    bool saved_found = false;
    if (!recovery_store_.read(recovery_blob, recovery_found) ||
        !previous_recovery_store_.read(saved_recovery, saved_found))
        return Gs117FreshCommissioningStatus::RecoveryBackupFailed;
    if (prior.status == node::NodeRecoveryLoadStatus::Ready) {
        if (!recovery_found || recovery_blob.empty())
            return Gs117FreshCommissioningStatus::RecoveryBackupFailed;
        if (saved_found && saved_recovery != recovery_blob)
            return Gs117FreshCommissioningStatus::RecoveryBackupConflict;
        if (!saved_found && !previous_recovery_store_.write(recovery_blob))
            return Gs117FreshCommissioningStatus::RecoveryBackupFailed;
        if (!previous_recovery_store_.read(saved_recovery, saved_found) ||
            !saved_found || saved_recovery != recovery_blob)
            return Gs117FreshCommissioningStatus::RecoveryBackupFailed;
    } else if (recovery_found || saved_found) {
        // A snapshot that cannot be authenticated for the saved association is
        // not disposable merely because the new Home would not open it.
        return Gs117FreshCommissioningStatus::RecoveryCorrupt;
    }

    const auto prior_association_generation = resetting_active_pair
        ? active.generation : active.generation - 1U;
    if (!gs117_fixture_prepare_association_backup(crypto_, *repository_,
            previous_binding, prior_association_generation,
            resetting_active_pair))
        return Gs117FreshCommissioningStatus::AssociationBackupFailed;
    const auto retired_count = prior.state
        ? static_cast<unsigned>(prior.state->retained.size()) : 0U;
    const auto pending_count = prior.state
        ? static_cast<unsigned>(prior.state->pending.size()) : 0U;
    ESP_LOGI(kTag,
             "GS117_TEST_ONLY_FIXTURE_STATE device=%s old_home=%s old_hub=%s association_generation=%llu recovery_generation=%llu retained=%u pending=%u gap_marker=0 disposal=TEST_ONLY_MOTION_ONLY",
             previous_binding.device_id.c_str(), previous_binding.home_id.c_str(),
             previous_binding.hub_id.c_str(),
             static_cast<unsigned long long>(prior_association_generation),
             static_cast<unsigned long long>(prior.generation), retired_count,
             pending_count);

    // Prepare the existing proof-of-possession exchange before committing the
    // monotonic Unpaired tombstone, so a missing installer secret cannot leave
    // the device needlessly retired.
    security::Key32 installer_code{};
    if (!security::load_target_installer_code(crypto_, installer_code)) {
        crypto_.secure_zero(installer_code.data(), installer_code.size());
        return Gs117FreshCommissioningStatus::InstallerCodeUnavailable;
    }
    auto fresh_commissioning = std::make_unique<security::NodeCommissioning>(
        crypto_, "node", physical_id_, installer_code);
    crypto_.secure_zero(installer_code.data(), installer_code.size());
    if (!fresh_commissioning->enable_window(now_ms, 10U * 60U * 1000U))
        return Gs117FreshCommissioningStatus::CommissioningWindowFailed;

    if (resetting_active_pair) {
        auto preserved = repository_->load_previous_association();
        AssociationStateKeyWiper preserved_key_wiper(crypto_, preserved);
        if (preserved.status != security::AssociationStatus::Paired ||
            !preserved.binding || preserved.generation != active.generation ||
            preserved.binding->device_id != previous_binding.device_id ||
            preserved.binding->hub_id != previous_binding.hub_id ||
            preserved.binding->home_id != previous_binding.home_id ||
            preserved.binding->device_public_key != previous_binding.device_public_key)
            return Gs117FreshCommissioningStatus::AssociationBackupFailed;
        if (!repository_->factory_reset())
            return Gs117FreshCommissioningStatus::TombstoneWriteFailed;
        const auto retired = repository_->load();
        if (retired.status != security::AssociationStatus::Unpaired ||
            retired.generation != active.generation + 1U)
            return Gs117FreshCommissioningStatus::TombstoneWriteFailed;
        ESP_LOGI(kTag,
                 "GS117_TEST_ONLY_FIXTURE_RETIRED device=%s association_generation=%llu recovery_backup=verified identity_key=preserved boot_session_counter=preserved",
                 physical_id_.c_str(),
                 static_cast<unsigned long long>(retired.generation));
    }

    commissioning_ = std::move(fresh_commissioning);
    binding_.reset();
    test_reassociation_pending_ = false;
    test_fresh_commissioning_pending_ = true;
    expected_reassociation_hub_id_ = expected_hub_id;
    frames_.reset();
    rejoin_.reset();
    assembler_.reset();
    phase_ = Phase::Commissioning;
    return Gs117FreshCommissioningStatus::Ready;
}

bool NodeSecurityLink::restore_recovery(node::NodeRuntime& runtime,
                                        Milliseconds now_ms) {
    if (!ready() || !binding_ || recovery_repository_) return false;
    recovery_repository_ = std::make_unique<node::NodeRecoveryRepository>(
        crypto_, recovery_store_, recovery_key_, binding_->home_id,
        binding_->hub_id, binding_->logical_id);
    const auto loaded = recovery_repository_->load();
    if (loaded.status == node::NodeRecoveryLoadStatus::Ready) {
        crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
        if (!loaded.state || !runtime.restore_recovery(*loaded.state, now_ms)) {
            phase_ = Phase::Fault;
            return false;
        }
        return true;
    }
    if (loaded.status == node::NodeRecoveryLoadStatus::Missing) {
        crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
        return true;
    }
    if (loaded.status == node::NodeRecoveryLoadStatus::Corrupt) {
        // An interrupted authenticated Hub reassociation can leave the prior
        // AEAD-bound snapshot under the previous binding. Recover it only from
        // the verified opaque backup and migrate every original EventKey into
        // a new snapshot bound to the new authenticated Hub.
        auto previous = repository_->load_previous_association();
        AssociationStateKeyWiper previous_key_wiper(crypto_, previous);
#if GS_HIL_CONTROL && !GS_HIL_BUILD && !GS_BAT_C8_PHYSICAL_WAKE
        if (binding_->device_id == "c3-146393c5d158" &&
            binding_->hub_id == "hub-e072a1d38d34" &&
            previous.status == security::AssociationStatus::Paired &&
            previous.binding && previous.binding->device_id == binding_->device_id &&
            previous.binding->home_id != binding_->home_id &&
            previous.binding->hub_id != binding_->hub_id &&
            previous.binding->device_public_key == binding_->device_public_key) {
            security::Bytes saved_recovery;
            bool saved_found = false;
            security::Bytes current_recovery;
            bool current_found = false;
            if (!previous_recovery_store_.read(saved_recovery, saved_found) ||
                !recovery_store_.read(current_recovery, current_found) ||
                !saved_found || !current_found || saved_recovery != current_recovery) {
                crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
                phase_ = Phase::Fault;
                return false;
            }
            node::NodeRecoveryRepository prior_repository(
                crypto_, previous_recovery_store_, recovery_key_,
                previous.binding->home_id, previous.binding->hub_id,
                previous.binding->logical_id);
            const auto prior = prior_repository.load();
            if (prior.status != node::NodeRecoveryLoadStatus::Ready || !prior.state ||
                !gs117_fixture_recovery_is_disposable(*prior.state)) {
                crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
                phase_ = Phase::Fault;
                return false;
            }
            node::NodeRuntimeRecoveryState fresh_state;
            fresh_state.node_id = binding_->logical_id;
            fresh_state.prior_boot_session = prior.state->prior_boot_session;
            // The retirement epoch belongs to the old Home. Boot session and
            // report generation remain monotonic; the new authenticated Hub
            // will establish its own ownership epoch.
            fresh_state.retirement_epoch = 0;
            fresh_state.durable_admission_highwater = 0;
            fresh_state.report_generation = prior.state->report_generation;
            crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
            if (!recovery_repository_->initialize_after_gs117_fixture_data_retirement(
                    *prior.state, fresh_state, prior.generation, saved_recovery,
                    previous.binding->home_id, previous.binding->hub_id) ||
                !runtime.restore_recovery(fresh_state, now_ms)) {
                phase_ = Phase::Fault;
                return false;
            }
            test_fresh_commissioning_pending_ = false;
            return true;
        }
#endif
        if (previous.status != security::AssociationStatus::Paired ||
            !previous.binding || previous.binding->hub_id == binding_->hub_id ||
            previous.binding->home_id != binding_->home_id ||
            previous.binding->device_id != binding_->device_id ||
            previous.binding->logical_id != binding_->logical_id ||
            previous.binding->room != binding_->room ||
            previous.binding->function != binding_->function) {
            crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
            phase_ = Phase::Fault;
            return false;
        }
        security::Bytes saved_recovery;
        bool saved_found = false;
        if (!previous_recovery_store_.read(saved_recovery, saved_found) || !saved_found) {
            crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
            phase_ = Phase::Fault;
            return false;
        }
        security::Bytes current_recovery;
        bool current_found = false;
        if (!recovery_store_.read(current_recovery, current_found) || !current_found ||
            current_recovery != saved_recovery) {
            crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
            phase_ = Phase::Fault;
            return false;
        }
        node::NodeRecoveryRepository prior_repository(
            crypto_, previous_recovery_store_, recovery_key_,
            previous.binding->home_id, previous.binding->hub_id,
            previous.binding->logical_id);
        crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
        const auto prior = prior_repository.load();
        if (prior.status != node::NodeRecoveryLoadStatus::Ready || !prior.state ||
            !runtime.restore_recovery(*prior.state, now_ms) ||
            !recovery_repository_->rebind_from_authenticated_previous(
                runtime.recovery_snapshot(), prior.generation, saved_recovery,
                previous.binding->home_id, previous.binding->hub_id)) {
            phase_ = Phase::Fault;
            return false;
        }
        return true;
    }
    crypto_.secure_zero(recovery_key_.data(), recovery_key_.size());
    phase_ = Phase::Fault;
    return false;
}

bool NodeSecurityLink::persist_recovery(const node::NodeRuntime& runtime) {
    if ((phase_ != Phase::Ready && phase_ != Phase::Rejoining) ||
        !recovery_repository_ ||
        !recovery_repository_->save(runtime.recovery_snapshot())) {
        phase_ = Phase::Fault;
        return false;
    }
    return true;
}

bool NodeSecurityLink::retirement_report_key(security::Key32& out) {
    if (!ready() || !binding_) return false;
    return transport::derive_retirement_report_key(
        crypto_, binding_->installation_key, out);
}

bool NodeSecurityLink::fragment_retirement_report(
        const transport::NodeRetirementReportV1& report,
        transport::RetirementFragmentSet& fragments) {
    if (!ready() || !binding_) return false;
    security::Key32 report_key{};
    const bool okay = transport::derive_retirement_report_key(
        crypto_, binding_->installation_key, report_key) &&
        transport::fragment_retirement_report(crypto_, report_key, report, fragments);
    crypto_.secure_zero(report_key.data(), report_key.size());
    return okay;
}

std::optional<NodeSecurityLink::Outbound> NodeSecurityLink::reply(
    const Mac& destination, const security::wire::Message& message) {
    return Outbound{destination, message};
}

bool NodeSecurityLink::matching_hub(const Mac& source) const {
    return source == hub_mac_;
}

std::optional<NodeSecurityLink::Outbound> NodeSecurityLink::begin_rejoin() {
    if (!binding_) return std::nullopt;
    challenge_seen_ = false;
    rejoin_ = std::make_unique<security::NodeRejoin>(crypto_, *binding_, session_,
                                                     rejoin_version_);
    const auto hello = rejoin_->begin();
    security::wire::Message message;
    if (!hello || !security::wire::encode(*hello, message)) {
        phase_ = Phase::Fault;
        return std::nullopt;
    }
    phase_ = Phase::Rejoining;
    return reply(hub_mac_, message);
}

bool NodeSecurityLink::start_rejoin(std::uint64_t session, std::uint8_t version) {
    if (!binding_ || session <= session_ || (version != 1 && version != 2) ||
        (pinned_v2_ && version != 2)) return false;
    frames_.reset();
    rejoin_.reset();
    assembler_.reset();
    health_ack_supported_ = false;
    session_ = session;
    rejoin_version_ = version;
    phase_ = Phase::Rejoining;
    return true;
}

std::optional<NodeSecurityLink::Outbound> NodeSecurityLink::fallback_to_v1() {
    if (phase_ != Phase::Rejoining || rejoin_version_ != 2 || pinned_v2_ ||
        challenge_seen_) return std::nullopt;
    rejoin_version_ = 1;
    rejoin_.reset();
    assembler_.reset();
    return begin_rejoin();
}

std::optional<NodeSecurityLink::Outbound> NodeSecurityLink::initial_message() {
    if (phase_ != Phase::Rejoining || rejoin_) return std::nullopt;
    return begin_rejoin();
}

std::optional<NodeSecurityLink::Outbound> NodeSecurityLink::accept(
    const Mac& source, const std::uint8_t* packet, std::size_t length,
    std::uint64_t now_ms) {
    if (phase_ != Phase::Commissioning && phase_ != Phase::Rejoining)
        return std::nullopt;
    if (phase_ == Phase::Rejoining && !matching_hub(source)) return std::nullopt;
    if (phase_ == Phase::Commissioning && commissioning_ &&
        hub_mac_ != Mac{} && !matching_hub(source)) return std::nullopt;
    const auto message = assembler_.push(packet, length, now_ms);
    if (!message) return std::nullopt;
    security::wire::Message outbound;
    if (phase_ == Phase::Commissioning) {
        if (message->kind == security::wire::Kind::Offer &&
            (hub_mac_ == Mac{} || test_reassociation_pending_ ||
             test_fresh_commissioning_pending_)) {
            security::CommissioningOffer offer;
            bool offer_valid = security::wire::decode(*message, offer) &&
                offer.hub_id == id_for_mac(source, "hub");
            if (offer_valid && test_fresh_commissioning_pending_) {
                auto previous = repository_ == nullptr
                    ? security::AssociationState{}
                    : repository_->load_previous_association();
                offer_valid = previous.status == security::AssociationStatus::Paired &&
                    previous.binding && gs117_fixture_offer_matches(
                        *previous.binding, offer, physical_id_,
                        expected_reassociation_hub_id_);
                if (previous.binding)
                    crypto_.secure_zero(previous.binding->installation_key.data(),
                                        previous.binding->installation_key.size());
            }
            if (!offer_valid ||
                (test_reassociation_pending_ &&
                 (!binding_ || offer.hub_id != expected_reassociation_hub_id_ ||
                  offer.device_public_key != binding_->device_public_key ||
                  offer.home_id != binding_->home_id ||
                  offer.logical_id != binding_->logical_id ||
                  offer.room != binding_->room ||
                  offer.function != binding_->function))) return std::nullopt;
            const auto proof = commissioning_->respond(offer, now_ms);
            if (!proof || !security::wire::encode(*proof, outbound)) return std::nullopt;
            hub_mac_ = source;
            return reply(source, outbound);
        }
        if (message->kind == security::wire::Kind::HubProof && hub_mac_ == source) {
            security::HubProof proof;
            if (!security::wire::decode(*message, proof)) return std::nullopt;
            const auto final = commissioning_->finish(proof, now_ms);
            if (!final || !security::wire::encode(*final, outbound)) return std::nullopt;
            return reply(source, outbound);
        }
        if (message->kind == security::wire::Kind::CommissioningAck &&
            hub_mac_ == source) {
            security::CommissioningAck ack;
            if (!security::wire::decode(*message, ack) ||
                !commissioning_->commit(ack, now_ms) ||
                !commissioning_->binding() ||
                !(test_reassociation_pending_
                    ? repository_->save_reassociation(*commissioning_->binding())
                    : repository_->save_initial(*commissioning_->binding()))) {
                phase_ = Phase::Fault;
                return std::nullopt;
            }
            binding_ = *commissioning_->binding();
            if (test_reassociation_pending_) {
                pinned_v2_ = false;
                health_ack_supported_ = false;
            }
            commissioning_.reset();
            return begin_rejoin();
        }
        return std::nullopt;
    }
    if (message->kind == security::wire::Kind::RejoinChallenge) {
        security::RejoinChallenge challenge;
        if (!security::wire::decode(*message, challenge) || !rejoin_)
            return std::nullopt;
        const auto final = rejoin_->accept(challenge);
        if (!final || !security::wire::encode(*final, outbound)) return std::nullopt;
        challenge_seen_ = true;
        return reply(source, outbound);
    }
    if (message->kind == security::wire::Kind::RejoinAck) {
        security::RejoinAck ack;
        if (!security::wire::decode(*message, ack) || !rejoin_ ||
            !rejoin_->commit(ack) || !rejoin_->session_salt() || !binding_)
            return std::nullopt;
        const bool negotiated =
            (rejoin_->negotiated_capabilities() & security::kHealthAckCapability) != 0;
        if (pinned_v2_ && !negotiated) {
            phase_ = Phase::Fault;
            return std::nullopt;
        }
        if (negotiated && (!pinned_v2_ || test_reassociation_pending_)) {
            if (!pin_health_ack_for_hub(binding_->hub_id)) {
                phase_ = Phase::Fault;
                return std::nullopt;
            }
            pinned_v2_ = true;
        }
        frames_ = std::make_unique<security::RuntimeFrameSecurity>(crypto_, *binding_);
        if (!frames_->start(session_, *rejoin_->session_salt())) {
            phase_ = Phase::Fault;
            return std::nullopt;
        }
        rejoin_.reset();
        health_ack_supported_ = negotiated;
#if GS_HIL_CONTROL && !GS_HIL_BUILD && !GS_BAT_C8_PHYSICAL_WAKE
        if (test_fresh_commissioning_pending_ &&
            binding_->device_id == "c3-146393c5d158" &&
            binding_->hub_id == "hub-e072a1d38d34" &&
            binding_->home_id == "gs177-test-product") {
            std::array<char, security::P256PublicKey{}.size() * 2U + 1U> public_key_hex{};
            constexpr char hex[] = "0123456789abcdef";
            for (std::size_t i = 0; i < binding_->hub_public_key.size(); ++i) {
                public_key_hex[2U * i] = hex[binding_->hub_public_key[i] >> 4];
                public_key_hex[2U * i + 1U] = hex[binding_->hub_public_key[i] & 15U];
            }
            ESP_LOGI(kTag,
                "GS117_TEST_ONLY_FIXTURE_BOUND device=%s hub=%s home=%s hub_public_key=%s proof=AUTHENTICATED_REJOIN",
                binding_->device_id.c_str(), binding_->hub_id.c_str(),
                binding_->home_id.c_str(), public_key_hex.data());
        }
#endif
        test_reassociation_pending_ = false;
        expected_reassociation_hub_id_.clear();
        phase_ = Phase::Ready;
    }
    return std::nullopt;
}

}  // namespace gs::node::target
