#include "firmware/common/security/association_persistence.hpp"
#include "host/security/openssl_commissioning_crypto.hpp"

#include <iostream>
#include <stdexcept>

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
        std::cout << "P2-PERSIST-ASSOC HOST PASS reboot/write-failure/reset/corruption\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-PERSIST-ASSOC HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
