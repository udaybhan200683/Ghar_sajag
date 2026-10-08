#pragma once
#include "host/storage/native_transaction.hpp"
#include "host/storage/protected_nvs_space.hpp"

namespace gs::host::storage::native {
// Bounded host/SDK enumeration, not a new firmware storage API.
class CompactObjectStore : public hub::durable::BlobStore {
public:
    virtual bool objects(std::vector<std::string>& keys) = 0;
    // Default keeps the original memory proof unchanged. A target adapter must
    // certify the whole bounded plan BEFORE the first immutable write.
    virtual bool prepare_publication(const PublicationPlan&) { return true; }
};

// Format experiment: one immutable encrypted body, shared across two small
// manifests; reducer is independently encrypted and referenced. Native admission,
// report/credit and semantic validation remain in Transaction.
class CompactRepresentation final : public BankRepresentation {
public:
    CompactRepresentation(CompactObjectStore&, security::CommissioningCrypto&,
                          Key32 key, std::uint32_t epoch);
    ~CompactRepresentation();
    bool pack(const Bytes&, Bytes&) override;
    bool unpack(const Bytes&, Bytes&) override;
    bool begin_publication(const State&, const State&, bool ordinary) override {
        ordinary_=ordinary; return true;
    }
    // Trusted single-writer maintenance ONLY after successful authority recovery.
    // Exactly one root is authorized. Older candidate banks are not recovery roots.
    // Never invoke this with guessed state or after failed recovery/publication.
    bool collect_selected(const State& authenticated_selected);
    static constexpr unsigned event_objects = kRows+1;
    static constexpr unsigned reducer_objects = 3;
    static std::string object_name(char kind, const Key32& digest);
private:
    bool id(char, const Bytes&, Key32&);
    bool put(char, const Bytes&, Key32&);
    bool get(char, const Key32&, Bytes&);
    CompactObjectStore& store_;
    security::CommissioningCrypto& crypto_;
    Key32 key_;
    std::uint32_t epoch_;
    bool ordinary_{false};
};
} // namespace
