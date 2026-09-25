#include "firmware/hub/components/registry/registry_persistence.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <string>

using gs::hub::EnrolledNode;
using gs::hub::HubRegistryLoadStatus;
using gs::hub::HubRegistryRepository;
using gs::hub::HubRegistryState;
using gs::hub::NodeRegistry;
using gs::host::security::OpenSslCommissioningCrypto;
using gs::security::Bytes;
using gs::security::CommissioningBinding;
using gs::security::Key32;
using gs::security::SecurityBlobStore;

namespace {
void require(bool okay, const char* message) {
    if (!okay) throw std::runtime_error(message);
}

class MemoryBlob final : public SecurityBlobStore {
public:
    bool read(Bytes& out, bool& found) override {
        if (read_error) return false;
        out = data;
        found = present;
        return true;
    }
    bool write(const Bytes& blob) override {
        if (fail_next_write) {
            fail_next_write = false;
            return false;
        }
        data = blob;
        present = true;
        return true;
    }
    Bytes data;
    bool present{false};
    bool read_error{false};
    bool fail_next_write{false};
};

gs::security::P256PublicKey test_hub_public_key() {
    gs::security::P256PublicKey key{};
    key[0] = 0x04;
    key[1] = 0x79;
    return key;
}

HubRegistryState make_state(unsigned count) {
    HubRegistryState state;
    state.registry.home_id = "test-home";
    state.registry.hub_id = "test-hub";
    for (unsigned i = 1; i <= count; ++i) {
        EnrolledNode record;
        record.device_id = "test-device-" + std::to_string(i);
        record.logical_id = "test-logical-" + std::to_string(i);
        record.room = "test-room-" + std::to_string(i);
        record.function = "motion";
        record.home_id = state.registry.home_id;
        record.hub_id = state.registry.hub_id;
        record.p256_public_key[0] = 0x04;
        record.p256_public_key[1] = static_cast<std::uint8_t>(i);
        record.radio_mac = {0x14, 0x63, 0x93, 0, 0, static_cast<std::uint8_t>(i)};
        record.last_session = i;
        state.registry.active.push_back(record);
        CommissioningBinding binding;
        binding.device_id = record.device_id;
        binding.logical_id = record.logical_id;
        binding.room = record.room;
        binding.function = record.function;
        binding.home_id = record.home_id;
        binding.hub_id = record.hub_id;
        binding.device_public_key = record.p256_public_key;
        binding.hub_public_key = test_hub_public_key();
        binding.installation_key[0] = static_cast<std::uint8_t>(i);
        state.bindings.push_back(binding);
    }
    return state;
}
}

int main() {
    try {
        OpenSslCommissioningCrypto crypto;
        Key32 wrap{};
        require(crypto.random_bytes(wrap.data(), wrap.size()), "test RNG failed");
        MemoryBlob store;
        HubRegistryRepository repo(crypto, store, wrap, "test-home", "test-hub",
                                   test_hub_public_key(), 10, 16);
        auto state = make_state(10);
        Key32 zero_wrap{};
        HubRegistryRepository zero_key(crypto, store, zero_wrap, "test-home", "test-hub",
                                       test_hub_public_key(), 10, 16);
        require(!zero_key.save(state), "zero Hub wrapping key was accepted");
        require(repo.load().status == HubRegistryLoadStatus::Missing,
                "new Hub registry was not missing");
        // A Hub may commit the registry before the Node receives the final
        // commissioning ACK. A later exact, authenticated retry must be able
        // to replace only that unactivated installation key.
        auto pending = make_state(1);
        pending.registry.active[0].last_session = 0;
        MemoryBlob retry_store;
        HubRegistryRepository retry_repo(crypto, retry_store, wrap, "test-home", "test-hub",
                                         test_hub_public_key(), 10, 16);
        require(retry_repo.save(pending), "pending enrollment save failed");
        auto retried = pending;
        retried.bindings[0].installation_key[0] ^= 2;
        require(retry_repo.save(retried), "unactivated retry save failed");
        const auto retried_load = retry_repo.load();
        require(retried_load.status == HubRegistryLoadStatus::Ready &&
                retried_load.state &&
                retried_load.state->bindings[0].installation_key ==
                    retried.bindings[0].installation_key,
                "unactivated exact retry could not replace orphaned key");
        auto activated = retried;
        activated.registry.active[0].last_session = 1;
        require(retry_repo.save(activated), "first rejoin commit failed");
        auto forbidden = activated;
        forbidden.bindings[0].installation_key[0] ^= 1;
        require(!retry_repo.save(forbidden), "activated key was replaced");
        require(repo.save(state), "ten-node encrypted registry save failed");
        require(!store.data.empty() && store.data[0] == 'G' &&
                std::search(store.data.begin(), store.data.end(),
                            state.bindings[0].installation_key.begin(),
                            state.bindings[0].installation_key.end()) == store.data.end(),
                "installation key appeared in cleartext registry blob");
        HubRegistryRepository reopened(crypto, store, wrap, "test-home", "test-hub",
                                       test_hub_public_key(), 10, 16);
        auto loaded = reopened.load();
        require(loaded.status == HubRegistryLoadStatus::Ready && loaded.generation == 1 &&
                loaded.state && loaded.state->registry.active.size() == 10 &&
                loaded.state->bindings[9].installation_key ==
                    state.bindings[9].installation_key,
                "encrypted Hub registry did not survive reopen");
        NodeRegistry restored("test-home", "test-hub", 10, 16);
        require(restored.restore(loaded.state->registry) &&
                restored.rejoin("test-device-1", state.registry.active[0].radio_mac, 1) ==
                    gs::hub::RegistryResult::StaleSession,
                "loaded Hub registry lost authenticated session history");

        auto changed = *loaded.state;
        changed.registry.active[0].last_session++;
        changed.registry.revoked_device_ids.push_back("old-physical-device");
        require(repo.save(changed), "session/revocation progression failed");
        require(repo.load().generation == 2, "registry generation did not advance");
        require(!repo.save(state), "older session or dropped revocation was accepted");
        auto missing_revocation = changed;
        missing_revocation.registry.revoked_device_ids.clear();
        require(!repo.save(missing_revocation), "saved revocation was discarded");
        auto key_changed = changed;
        key_changed.bindings[0].installation_key[0] ^= 1;
        require(!repo.save(key_changed), "enrolled installation key changed silently");
        auto unrevoked_removal = changed;
        unrevoked_removal.registry.active.pop_back();
        unrevoked_removal.bindings.pop_back();
        require(!repo.save(unrevoked_removal),
                "physical identity was removed without a revocation");
        auto revoked_removal = unrevoked_removal;
        revoked_removal.registry.revoked_device_ids.push_back("test-device-10");
        require(repo.save(revoked_removal) && repo.load().generation == 3,
                "removal and revocation were not saved together");
        auto revoked_loaded = repo.load();
        NodeRegistry after_removal("test-home", "test-hub", 10, 16);
        require(revoked_loaded.state && after_removal.restore(revoked_loaded.state->registry) &&
                after_removal.enroll(state.registry.active[9]) ==
                    gs::hub::RegistryResult::RevokedDevice,
                "removed physical identity was admissible after encrypted restore");

        store.fail_next_write = true;
        revoked_removal.registry.active[0].last_session++;
        require(!repo.save(revoked_removal) && repo.load().generation == 3,
                "failed snapshot write changed committed registry");
        Key32 wrong = wrap;
        wrong[0] ^= 1;
        HubRegistryRepository wrong_repo(crypto, store, wrong, "test-home", "test-hub",
                                         test_hub_public_key(), 10, 16);
        require(wrong_repo.load().status == HubRegistryLoadStatus::Corrupt,
                "wrong wrapping key exposed Hub registry");
        auto other_hub_key = test_hub_public_key();
        other_hub_key[1] ^= 1;
        HubRegistryRepository other_hub(crypto, store, wrap, "test-home", "test-hub",
                                        other_hub_key, 10, 16);
        require(other_hub.load().status == HubRegistryLoadStatus::Corrupt,
                "different Hub identity restored association keys");
        const auto committed = store.data;
        store.data.back() ^= 1;
        require(repo.load().status == HubRegistryLoadStatus::Corrupt &&
                !repo.save(changed), "tampered Hub registry was trusted or overwritten");
        store.data = committed;
        store.read_error = true;
        require(repo.load().status == HubRegistryLoadStatus::IoError,
                "Hub storage IO error was treated as missing");
        store.read_error = false;

        auto foreign = changed;
        foreign.registry.home_id = "other-home";
        require(!repo.save(foreign), "foreign Home Hub registry saved");
        MemoryBlob architectural_store;
        HubRegistryRepository architectural(crypto, architectural_store, wrap,
                                            "test-home", "test-hub",
                                            test_hub_public_key(), 25, 50);
        require(architectural.save(make_state(25)),
                "25-node simulated registry save failed");
        const auto architectural_loaded = architectural.load();
        require(architectural_loaded.status == HubRegistryLoadStatus::Ready &&
                architectural_loaded.state &&
                architectural_loaded.state->registry.active.size() == 25 &&
                !architectural.save(make_state(26)),
                "25-node simulated registry boundary failed");
        std::cout << "P2-PERSIST-HUB-REG HOST PASS ten-node security and 25-node simulated boundary\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-PERSIST-HUB-REG HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
