#pragma once
// HOST-NATIVE correctness reference. Not a production format or NVS adapter.
#include "firmware/hub/components/storage/node_retirement_snapshot.hpp"
#include <array>
#include <optional>

namespace gs::host::storage::native {
using security::Bytes;
using security::Key32;
using transport::NodeRetirementReportV1;

// Missing primitive in BlobStore: durable, linearizable, non-rollback publication
// authority, independent of candidate banks. Single serialized writer required.
// read must refuse lost/corrupt/rolled-back authority, never return an older head.
// CAS may report failure after persistence; exact authority read resolves it.
// Only explicitly authorized fresh provisioning may create an empty authority.
class PublicationAuthority {
public:
    virtual ~PublicationAuthority() = default;
    virtual bool read(Bytes& head) = 0;
    virtual bool provision(const Bytes& head) = 0;
    virtual bool compare_publish(const Bytes& expected, const Bytes& next) = 0;
};

constexpr unsigned kOwners = 6;
constexpr unsigned kPending = 32;
constexpr unsigned kRows = 384;
constexpr unsigned kReducerBytes = 4096;
enum class Phase : std::uint8_t { Empty, Active, Retiring };
enum class Result { Committed, Duplicate, Full, Invalid, Conflict, Retired, Fault };
struct Owner {
    Phase phase{Phase::Empty};
    std::uint32_t generation{0};
    Key32 binding{}, report_key{};
    NodeRetirementReportV1 report{};
    Key32 report_mac{};
    std::uint8_t charged{0};
};
struct Proof {
    // Resolved by the existing authenticated registry/transport boundary. This
    // is not a commissioning API and caller-supplied source IDs are not proof.
    std::uint8_t slot{0};
    std::uint32_t generation{0};
    Key32 binding{};
    std::uint64_t transport_session{0};
};
struct Event {
    Proof owner;
    std::uint64_t origin{0}, sequence{0};
    Bytes body;
};
struct Row {
    std::uint8_t slot{0};
    std::uint32_t owner_generation{0};
    std::uint64_t origin{0}, sequence{0};
    Key32 digest{};
    Bytes body;
    bool retry{true}, local{true}, backend{true};
};
struct State {
    std::uint64_t generation{1};
    std::uint32_t next_owner_generation{1};
    std::array<Owner,kOwners> owners{};
    std::vector<Row> rows;
    Bytes reducer;
    // Fresh boot cannot infer current observation coverage from persisted silence.
};

// Optional host/SDK representation adapter. The transaction still authenticates
// its bank and validates the complete reconstructed native state. pack may write
// immutable dependencies; it must never reclaim a dependency of a published root.
class BankRepresentation {
public:
    virtual ~BankRepresentation() = default;
    virtual bool pack(const Bytes& native_plain, Bytes& compact_plain) = 0;
    virtual bool unpack(const Bytes& compact_plain, Bytes& native_plain) = 0;
    virtual bool begin_publication(const State&, const State&, bool) { return true; }
};

class Transaction {
public:
    Transaction(hub::durable::BlobStore&, security::CommissioningCrypto&,
                PublicationAuthority&, Key32 storage_key, std::uint32_t epoch,
                unsigned window, BankRepresentation* representation = nullptr);
    ~Transaction();
    Transaction(const Transaction&) = delete;
    Transaction& operator=(const Transaction&) = delete;
    bool provision_fresh(); // Explicit factory operation; never recovery fallback.
    bool recover();
    const State* state() const { return ready_ ? &state_ : nullptr; }
    bool observation_available() const { return false; } // Runtime must re-establish coverage.
    unsigned identity_bound() const { return kOwners*(kPending+window_); }
    // These management/consumer APIs belong to the authenticated Hub owner, not
    // a Node request handler. Production authorization and backend receipt checks
    // precede them. The protocol atomically persists their resulting obligations.
    Result enroll(const Key32& authenticated_binding, const Key32& report_key);
    Result revoke(const Proof&); // Retains owner, exact evidence and all dependencies.
    Result release_owner(const Proof&); // Only after complete drained report and no rows.
    Result report(const Proof&, const NodeRetirementReportV1&, const Key32& mac);
    Result admit(const Event&, const Key32& authenticated_mac, const Bytes& next_reducer);
    Result dependencies_complete(const Proof&, std::uint64_t origin,
                                 std::uint64_t sequence, bool local, bool backend);
    Result checkpoint_reducer(const Bytes& reducer);
    // Host boundary certificate after existing authenticated transport validation;
    // not a new Node wire protocol. MAC binds full enrollment and immutable body.
    bool event_mac(const Key32& peer_key, const Event&, Key32&) const;
    static constexpr std::size_t maximum_bank_bytes();
    static constexpr std::size_t head_bytes = 86;
private:
    bool validate(const State&) const;
    bool encode(const State&, unsigned bank, Bytes&);
    bool decode(const Bytes&, unsigned bank, State&);
    bool head(const Bytes&, std::uint64_t&, unsigned&, Key32&);
    bool make_head(std::uint64_t, unsigned, const Key32&, Bytes&);
    bool digest(const Row&, const Owner&, Key32&) const;
    bool owner_matches(const Proof&) const;
    Result publish(State, bool ordinary_admission = false);
    Result durable_duplicate();
    void recompute(State&) const;
    hub::durable::BlobStore& blobs_;
    security::CommissioningCrypto& crypto_;
    PublicationAuthority& authority_;
    Key32 key_;
    std::uint32_t epoch_;
    unsigned window_, bank_{0};
    bool ready_{false};
    State state_;
    Bytes head_;
    BankRepresentation* representation_;
};
// Header33 + six bounded owner records + row count2 + rows + reducer length2.
constexpr std::size_t Transaction::maximum_bank_bytes() {
    return 33 + kOwners*(1+4+32+32+1+2+542+32) + 2 +
        kRows*(1+4+8+8+32+1+2+hub::durable::kMaxCausalInputBytes) + 2+kReducerBytes + 28;
}
} // namespace gs::host::storage::native
