#include "firmware/common/security/association_persistence.hpp"
#include "firmware/node/target/esp32c3/gs117_fixture_commissioning.hpp"
#include "firmware/node/target/esp32c3/gs117_reassociation_status.hpp"
#include "tests/support/host/security/openssl_commissioning_crypto.hpp"

#include <iostream>
#include <stdexcept>
#include <string>

using namespace gs::security;
using gs::host::security::OpenSslCommissioningCrypto;

namespace {
void require(bool okay, const char* message) {
    if (!okay) throw std::runtime_error(message);
}

class MemoryBlob final : public AssociationBlobStore {
public:
    bool read(Bytes& out, bool& found) override {
        if (read_error) return false;
        found = present;
        out = bytes;
        return true;
    }
    bool write(const Bytes& blob) override {
        if (fail_next_write) {
            fail_next_write = false;
            return false;
        }
        bytes = blob;
        present = true;
        return true;
    }
    Bytes bytes;
    bool present{false};
    bool fail_next_write{false};
    bool read_error{false};
};
}

int main() {
    try {
        using gs::node::target::Gs117ReassociationStatus;
        using gs::node::target::gs117_reassociation_preflight;
        using gs::node::target::gs117_reassociation_status_name;
        require(gs117_reassociation_preflight(false, true, true, false, true) ==
                    Gs117ReassociationStatus::NotRejoining,
                "reassociation did not reject a non-rejoining Node");
        require(gs117_reassociation_preflight(true, false, true, false, true) ==
                    Gs117ReassociationStatus::BindingUnavailable,
                "reassociation did not reject a missing binding");
        require(gs117_reassociation_preflight(true, true, false, false, true) ==
                    Gs117ReassociationStatus::InvalidTargetHub,
                "reassociation did not reject an unapproved Hub");
        require(gs117_reassociation_preflight(true, true, true, false, false) ==
                    Gs117ReassociationStatus::HomeMismatch,
                "reassociation did not reject a Home mismatch");
        require(gs117_reassociation_preflight(true, true, true, true, true) ==
                    Gs117ReassociationStatus::AlreadyBoundToTarget,
                "reassociation did not reject a redundant binding change");
        require(gs117_reassociation_preflight(true, true, true, false, true) ==
                    Gs117ReassociationStatus::Ready,
                "approved same-Home reassociation preflight was rejected");
        require(std::string(gs117_reassociation_status_name(
                    Gs117ReassociationStatus::RecoveryBackupConflict)) ==
                    "recovery_backup_conflict",
                "reassociation refusal reason is not stable for HIL evidence");
        using gs::node::target::gs117_fixture_offer_matches;
        using gs::node::target::gs117_fixture_recovery_is_disposable;
        CommissioningBinding fixture_prior;
        fixture_prior.device_id = "c3-146393c5d158";
        fixture_prior.device_public_key[0] = 0x04;
        CommissioningOffer fixture_offer;
        fixture_offer.hub_id = "hub-e072a1d38d34";
        fixture_offer.home_id = "gs177-test-product";
        fixture_offer.device_public_key = fixture_prior.device_public_key;
        fixture_offer.logical_id = "bedroom";
        fixture_offer.room = "Bedroom";
        fixture_offer.function = "motion";
        require(gs117_fixture_offer_matches(fixture_prior, fixture_offer,
                    "c3-146393c5d158", "hub-e072a1d38d34"),
                "exact physical fixture commissioning offer was rejected");
        fixture_offer.home_id = "another-home";
        require(!gs117_fixture_offer_matches(fixture_prior, fixture_offer,
                    "c3-146393c5d158", "hub-e072a1d38d34"),
                "fixture commissioning accepted an unauthorized Home");
        fixture_offer.home_id = "gs177-test-product";
        fixture_offer.hub_id = "hub-000000000000";
        require(!gs117_fixture_offer_matches(fixture_prior, fixture_offer,
                    "c3-146393c5d158", "hub-e072a1d38d34"),
                "fixture commissioning accepted a different physical Hub");
        fixture_offer.hub_id = "hub-e072a1d38d34";
        fixture_offer.device_public_key[1] = 1;
        require(!gs117_fixture_offer_matches(fixture_prior, fixture_offer,
                    "c3-146393c5d158", "hub-e072a1d38d34"),
                "fixture commissioning accepted a different Node identity key");
        fixture_offer.device_public_key = fixture_prior.device_public_key;
        fixture_offer.room = "Living room";
        require(!gs117_fixture_offer_matches(fixture_prior, fixture_offer,
                    "c3-146393c5d158", "hub-e072a1d38d34"),
                "fixture commissioning accepted a different logical room");
        gs::node::NodeRuntimeRecoveryState fixture_recovery;
        gs::DomainEvent test_motion;
        test_motion.kind = gs::EventKind::Motion;
        test_motion.is_test = true;
        fixture_recovery.retained.push_back(test_motion);
        gs::node::PendingTx test_pending;
        test_pending.event = test_motion;
        fixture_recovery.pending.push_back(test_pending);
        require(gs117_fixture_recovery_is_disposable(fixture_recovery),
                "TEST_ONLY motion fixture data was not recognized as disposable");
        fixture_recovery.retained.front().is_test = false;
        require(!gs117_fixture_recovery_is_disposable(fixture_recovery),
                "fixture retirement accepted a non-test retained event");
        fixture_recovery.retained.front().is_test = true;
        fixture_recovery.gap_marker_required = true;
        require(!gs117_fixture_recovery_is_disposable(fixture_recovery),
                "fixture retirement accepted an unresolved event gap");
        OpenSslCommissioningCrypto crypto;
        Key32 wrapping_key{};
        require(crypto.random_bytes(wrapping_key.data(), wrapping_key.size()),
                "test wrapping key RNG failed");
        MemoryBlob store;
        CommissioningBinding binding;
        binding.device_id = "device-a";
        binding.hub_id = "hub-a";
        binding.home_id = "home-a";
        binding.logical_id = "bathroom";
        binding.room = "Bathroom";
        binding.function = "motion";
        binding.device_public_key[0] = 0x04;
        binding.hub_public_key[0] = 0x04;
        require(crypto.random_bytes(binding.installation_key.data(),
                                    binding.installation_key.size()),
                "test installation key RNG failed");
        {
            AssociationRepository repo(crypto, store, wrapping_key);
            require(repo.load().status == AssociationStatus::Missing,
                    "fresh association was not missing");
            require(repo.save_initial(binding), "initial encrypted save failed");
            require(!repo.save_initial(binding), "paired record was silently overwritten");
        }
        {
            AssociationRepository rebooted(crypto, store, wrapping_key);
            const auto loaded = rebooted.load();
            require(loaded.status == AssociationStatus::Paired && loaded.generation == 1 &&
                    loaded.binding && loaded.binding->device_id == binding.device_id &&
                    loaded.binding->installation_key == binding.installation_key,
                    "association did not survive store reopen");
            store.fail_next_write = true;
            require(!rebooted.factory_reset() &&
                    rebooted.load().status == AssociationStatus::Paired,
                    "failed flash commit revoked a still-paired Node");
            require(rebooted.factory_reset(), "factory reset tombstone did not commit");
            const auto reset = rebooted.load();
            require(reset.status == AssociationStatus::Unpaired && reset.generation == 2 &&
                    !reset.binding, "factory reset retained Home association");
            require(rebooted.save_initial(binding), "recommission after reset failed");
            require(rebooted.load().generation == 3,
                    "association generation did not advance after reset");
        }
        Key32 wrong_key = wrapping_key;
        wrong_key[0] ^= 1;
        AssociationRepository wrong(crypto, store, wrong_key);
        require(wrong.load().status == AssociationStatus::Corrupt,
                "wrong protected wrapping key exposed association");
        const auto original = store.bytes;
        store.bytes.back() ^= 1;
        AssociationRepository corrupted(crypto, store, wrapping_key);
        require(corrupted.load().status == AssociationStatus::Corrupt &&
                !corrupted.factory_reset() && !corrupted.save_initial(binding),
                "corrupt association was silently trusted or overwritten");
        store.bytes = original;
        store.read_error = true;
        require(corrupted.load().status == AssociationStatus::IoError,
                "storage read error was treated as unpaired");

        MemoryBlob reassociation_store;
        MemoryBlob previous_store;
        CommissioningBinding old_binding = binding;
        old_binding.hub_id = "hub-old";
        AssociationRepository old_fixture(crypto, reassociation_store, wrapping_key,
                                          &previous_store);
        require(old_fixture.save_initial(old_binding),
                "reassociation baseline could not be saved");
        CommissioningBinding new_binding = old_binding;
        new_binding.hub_id = "hub-new";
        new_binding.hub_public_key[1] = 0x42;
        require(crypto.random_bytes(new_binding.installation_key.data(),
                                    new_binding.installation_key.size()),
                "new Hub binding key RNG failed");
        CommissioningBinding cross_home = new_binding;
        cross_home.home_id = "home-other";
        require(!old_fixture.save_reassociation(cross_home) &&
                old_fixture.load().binding->hub_id == old_binding.hub_id &&
                !previous_store.present,
                "cross-Home reassociation changed or backed up the active binding");
        using gs::node::target::gs117_fixture_prepare_association_backup;
        require(!gs117_fixture_prepare_association_backup(
                    crypto, old_fixture, old_binding, 1, false) &&
                !previous_store.present,
                "interrupted fixture transfer fabricated a missing backup");
        previous_store.fail_next_write = true;
        const auto active_before_backup = reassociation_store.bytes;
        require(!gs117_fixture_prepare_association_backup(
                    crypto, old_fixture, old_binding, 1, true) &&
                reassociation_store.bytes == active_before_backup && !previous_store.present,
                "failed fixture backup changed the active association");
        require(gs117_fixture_prepare_association_backup(
                    crypto, old_fixture, old_binding, 1, true) &&
                previous_store.bytes == active_before_backup &&
                gs117_fixture_prepare_association_backup(
                    crypto, old_fixture, old_binding, 1, false),
                "first fixture transfer required an already-existing backup");
        require(!gs117_fixture_prepare_association_backup(
                    crypto, old_fixture, cross_home, 1, true) &&
                !gs117_fixture_prepare_association_backup(
                    crypto, old_fixture, old_binding, 2, false),
                "fixture backup accepted changed Home or generation");
        previous_store.bytes.back() ^= 1;
        require(!gs117_fixture_prepare_association_backup(
                    crypto, old_fixture, old_binding, 1, true) &&
                reassociation_store.bytes == active_before_backup,
                "corrupt fixture backup was overwritten or trusted");
        previous_store.bytes.back() ^= 1;
        std::cout << "GS117-FRESH-BACKUP-001 PASS first-use/failure/recovery/identity\n";
        require(old_fixture.preserve_previous_for_reassociation() &&
                previous_store.bytes == reassociation_store.bytes,
                "previous association ciphertext was not durably preserved");
        require(old_fixture.save_reassociation(new_binding),
                "authenticated same-Home reassociation did not commit");
        const auto current_fixture = old_fixture.load();
        const auto prior_fixture = old_fixture.load_previous_association();
        require(current_fixture.status == AssociationStatus::Paired &&
                current_fixture.binding && current_fixture.binding->hub_id == "hub-new" &&
                current_fixture.generation == 2 &&
                current_fixture.binding->installation_key == new_binding.installation_key &&
                prior_fixture.status == AssociationStatus::Paired && prior_fixture.binding &&
                prior_fixture.binding->hub_id == "hub-old" &&
                prior_fixture.binding->installation_key == old_binding.installation_key,
                "reassociation did not retain both recoverable encrypted bindings");
        require(old_fixture.restore_previous_association() &&
                old_fixture.load().binding->hub_id == "hub-old" &&
                old_fixture.load().generation == current_fixture.generation + 1U,
                "previous association recovery rolled back the generation counter");
        std::cout << "P2-PERSIST-ASSOC HOST PASS reboot/write-failure/reset/corruption\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-PERSIST-ASSOC HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
