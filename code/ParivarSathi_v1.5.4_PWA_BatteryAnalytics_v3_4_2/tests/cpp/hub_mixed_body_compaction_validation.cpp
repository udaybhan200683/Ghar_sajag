// Use the established runtime fixtures without rerunning their main here.
#include <functional>
#include <sys/resource.h>
#define GS_CHECKPOINT_EMBEDDED
#include "hub_runtime_checkpoint_validation.cpp"
#undef GS_CHECKPOINT_EMBEDDED

namespace {
using namespace gs::hub::storage;

class PosixSegments final : public SegmentStore {
public:
    explicit PosixSegments(std::uint64_t capacity = 8U * 1024U * 1024U) : capacity_(capacity) {
        char pattern[] = "/tmp/gs_body_compaction_XXXXXX";
        const auto* path = ::mkdtemp(pattern);
        require(path != nullptr, "create isolated body store");
        directory = path;
    }
    ~PosixSegments() override {
        std::error_code error;
        std::filesystem::remove_all(directory, error);
    }
    std::string directory;
    std::uint64_t capacity_;
    std::uint64_t external_used{0};
    std::size_t mutations{0}, fail_at{0};
    bool fail_after{false}, halted{false}, partial{false};
    bool corrupt_sync{false}, bypass_fsync{false};
    std::uint64_t peak_logical{0}, peak_allocated{0};
    std::string segment(std::uint16_t id) const { return "s" + std::to_string(id); }
    bool before() {
        if (halted) return false;
        ++mutations;
        if (fail_at == mutations && !fail_after) { halted = true; return false; }
        return true;
    }
    bool after() {
        measure_peak();
        if (fail_at == mutations && fail_after) { halted = true; return false; }
        return true;
    }
    bool size(const std::string& name, bool& exists, std::uint32_t& bytes) {
        if (halted) return false;
        struct stat info{};
        exists = ::stat((directory + "/" + name).c_str(), &info) == 0;
        bytes = exists ? static_cast<std::uint32_t>(info.st_size) : 0;
        return exists || errno == ENOENT;
    }
    bool read_file(const std::string& name, std::uint32_t offset, std::uint8_t* out,
                   std::size_t requested, std::size_t& actual) {
        actual = 0;
        if (halted) return false;
        FILE* file = std::fopen((directory + "/" + name).c_str(), "rb");
        if (!file) return false;
        bool okay = std::fseek(file, offset, SEEK_SET) == 0;
        if (okay) actual = std::fread(out, 1, requested, file);
        okay = okay && !std::ferror(file);
        return std::fclose(file) == 0 && okay;
    }
    bool append_file(const std::string& name, const std::uint8_t* data, std::size_t length) {
        if (!before()) return false;
        FILE* file = std::fopen((directory + "/" + name).c_str(), "ab");
        if (!file) return false;
        const auto wanted = partial ? length / 2 : length;
        const bool okay = std::fwrite(data, 1, wanted, file) == wanted;
        const bool closed = std::fclose(file) == 0;
        if (partial) { partial = false; halted = true; measure_peak(); return false; }
        return okay && closed && after();
    }
    bool sync_file(const std::string& name) {
        if (!before()) return false;
        if (corrupt_sync && name[0] == 's') {
            FILE* corrupt = std::fopen((directory + "/" + name).c_str(), "r+");
            require(corrupt != nullptr, "candidate corrupt open");
            std::fseek(corrupt, 25, SEEK_SET);
            const auto byte = std::fgetc(corrupt);
            std::fseek(corrupt, 25, SEEK_SET);
            std::fputc(byte ^ 0x80, corrupt);
            std::fclose(corrupt);
            corrupt_sync = false;
        }
        FILE* file = std::fopen((directory + "/" + name).c_str(), "r+");
        if (!file) return false;
        const bool okay = bypass_fsync || ::fsync(fileno(file)) == 0;
        return std::fclose(file) == 0 && okay && after();
    }
    bool read_marker(const std::string& name, Bytes& marker, bool& found) {
        std::uint32_t bytes = 0;
        if (!size(name, found, bytes)) return false;
        marker.clear();
        if (!found) return true;
        if (bytes > 8192) return true;
        marker.resize(bytes);
        std::size_t actual = 0;
        return read_file(name, 0, marker.data(), marker.size(), actual) && actual == marker.size();
    }
    bool publish(const std::string& name, const Bytes& marker) {
        if (!before()) return false;
        const auto temporary = directory + "/" + name + ".new";
        FILE* file = std::fopen(temporary.c_str(), "wb");
        if (!file) return false;
        const bool okay = std::fwrite(marker.data(), 1, marker.size(), file) == marker.size() &&
            std::fflush(file) == 0 && (bypass_fsync || ::fsync(fileno(file)) == 0);
        const bool closed = std::fclose(file) == 0;
        if (!okay || !closed) return false;
        measure_peak(); // Include the temporary marker before its atomic rename.
        if (std::rename(temporary.c_str(), (directory + "/" + name).c_str()) != 0) return false;
        return after();
    }
    bool remove_file(const std::string& name) {
        if (!before()) return false;
        if (::unlink((directory + "/" + name).c_str()) != 0 && errno != ENOENT) return false;
        return after();
    }
    std::uint64_t bytes(bool allocated) const {
        std::uint64_t result = 0;
        for (const auto& entry : std::filesystem::directory_iterator(directory)) {
            struct stat info{};
            require(::stat(entry.path().c_str(), &info) == 0, "measure files");
            result += allocated ? static_cast<std::uint64_t>(info.st_blocks) * 512 : info.st_size;
        }
        return result;
    }
    std::uint64_t body_allocated_bytes() const {
        std::uint64_t result = 0;
        for (const auto& entry : std::filesystem::directory_iterator(directory)) {
            if (entry.path().filename().string().front() != 's') continue;
            struct stat info{};
            require(::stat(entry.path().c_str(), &info) == 0, "measure body files");
            result += static_cast<std::uint64_t>(info.st_blocks) * 512;
        }
        return result;
    }
    void measure_peak() {
        peak_logical = std::max(peak_logical, bytes(false));
        peak_allocated = std::max(peak_allocated, bytes(true));
    }
    void clone_from(const PosixSegments& source) {
        for (const auto& entry : std::filesystem::directory_iterator(source.directory))
            std::filesystem::copy_file(entry.path(), directory + "/" + entry.path().filename().string(),
                                       std::filesystem::copy_options::overwrite_existing);
    }
    std::uint64_t partition_capacity_bytes() const override { return capacity_; }
    bool filesystem_usage(std::uint64_t& total, std::uint64_t& used) override {
        if (halted) return false;
        total = capacity_; used = bytes(true) + external_used; return used <= total;
    }
    bool segment_size(std::uint16_t id, bool& exists, std::uint32_t& bytes) override {
        return size(segment(id), exists, bytes);
    }
    bool read(std::uint16_t id, std::uint32_t offset, std::uint8_t* out, std::size_t n,
              std::size_t& actual) override { return read_file(segment(id), offset, out, n, actual); }
    bool append(std::uint16_t id, const std::uint8_t* data, std::size_t n) override {
        return append_file(segment(id), data, n);
    }
    bool sync(std::uint16_t id) override { return sync_file(segment(id)); }
    bool remove_segment(std::uint16_t id) override { return remove_file(segment(id)); }
    bool read_publication(Bytes& b, bool& f) override { return read_marker("head", b, f); }
    bool publish_publication(const Bytes& b) override { return publish("head", b); }
    bool read_lifecycle_root(Bytes& b, bool& f) override { return read_marker("root", b, f); }
    bool publish_lifecycle_root(const Bytes& b) override { return publish("root", b); }
    bool completion_size(bool& f, std::uint32_t& b) override { return size("completion", f, b); }
    bool read_completion(std::uint32_t offset, std::uint8_t* out, std::size_t n,
                         std::size_t& actual) override { return read_file("completion", offset, out, n, actual); }
    bool append_completion(const std::uint8_t* d, std::size_t n) override { return append_file("completion", d, n); }
    bool sync_completion() override { return sync_file("completion"); }
    bool truncate_completion(std::uint32_t n) override {
        if (!before()) return false;
        const auto path = directory + "/completion";
        if (::truncate(path.c_str(), n) != 0 && !(n == 0 && errno == ENOENT)) return false;
        return after();
    }
    bool read_completion_publication(Bytes& b, bool& f) override { return read_marker("completion.head", b, f); }
    bool publish_completion_publication(const Bytes& b) override { return publish("completion.head", b); }
};

OutboxLimits mixed_limits() {
    OutboxLimits limits;
    limits.segment_count = 8;
    limits.segment_bytes = 4096;
    limits.filesystem_workspace_bytes = 64 * 1024;
    limits.protected_capacity_bytes = 0;
    limits.body_retirement_enabled = true;
    return limits;
}
struct MixedProof {
    std::set<std::uint64_t> protected_ordinals;
    bool current{true};
    std::size_t calls{0}, revoke_at{0};
    DurableEventOutbox* outbox{nullptr};
    bool mutation_checked{false};
};
bool mixed_current(void* opaque) { return static_cast<MixedProof*>(opaque)->current; }
bool mixed_retired(void* opaque, std::uint64_t ordinal, const std::string&, const Bytes&) {
    auto& proof = *static_cast<MixedProof*>(opaque);
    ++proof.calls;
    if (proof.revoke_at && proof.calls == proof.revoke_at) proof.current = false;
    if (proof.outbox && !proof.mutation_checked) {
        proof.mutation_checked = true;
        require(proof.outbox->append("reentrant", Bytes{1}, AdmissionClass::Ordinary) ==
                    OutboxAdmission::RestartRequired && !proof.outbox->mark_backend_completed("e1"),
                "compaction serializes append and completion");
    }
    return proof.current && !proof.protected_ordinals.count(ordinal);
}
RetirementAuthorization mixed_authorization(std::uint64_t boundary, MixedProof& proof) {
    RetirementAuthorization authorization;
    authorization.checkpoint_boundary = boundary;
    authorization.authenticated_report_generation = 1;
    authorization.authenticated_report_digest.fill(0x73);
    authorization.post_sync_retention_satisfied = true;
    authorization.node_retired = mixed_retired;
    authorization.authority_current = mixed_current;
    authorization.context = &proof;
    return authorization;
}
Bytes mixed_payload(std::uint64_t sequence) {
    Bytes payload(160, static_cast<std::uint8_t>(sequence));
    for (unsigned i = 0; i < 8; ++i) payload[i] = static_cast<std::uint8_t>(sequence >> (i * 8));
    return payload;
}
using Bodies = std::map<std::uint64_t, std::pair<std::string, Bytes>>;
Bodies capture(DurableEventOutbox& outbox) {
    Bodies bodies;
    const auto visitor = [](void* opaque, std::uint64_t ordinal, const std::string& key, const Bytes& payload) {
        return static_cast<Bodies*>(opaque)->emplace(ordinal, std::make_pair(key, payload)).second;
    };
    require(outbox.for_each(visitor, &bodies), "stream exact bodies");
    return bodies;
}
void populate(DurableEventOutbox& outbox, std::uint64_t first, std::uint64_t count,
              const std::function<bool(std::uint64_t)>& completed) {
    for (std::uint64_t i = first; i < first + count; ++i) {
        const auto key = "e" + std::to_string(i);
        require(outbox.append(key, mixed_payload(i), AdmissionClass::Ordinary) == OutboxAdmission::Committed,
                "durable fixture admission");
        if (completed(i)) require(outbox.mark_backend_completed(key), "authenticated fixture completion");
    }
}
void normal_body_patterns() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    for (int pattern = 0; pattern < 6; ++pattern) {
        PosixSegments files;
        const auto limits = mixed_limits();
        DurableEventOutbox outbox(files, crypto, key, limits);
        require(outbox.recover() == OutboxRecovery::Empty, "pattern starts empty");
        const auto completed = [pattern](std::uint64_t i) {
            switch (pattern) {
                case 0: return true;
                case 1: return false;
                case 2: return i % 2 == 0;
                case 3: return i < 20;
                case 4: return i >= 20 && i <= 40;
                default: return i > 40;
            }
        };
        populate(outbox, 1, 60, completed);
        const auto original = capture(outbox);
        MixedProof proof;
        proof.protected_ordinals.insert(4); // completed Node-pending exception
        proof.outbox = &outbox;
        auto authorization = mixed_authorization(60, proof);
        BodyCompactionStats stats;
        const auto result = outbox.compact_event_bodies(authorization, stats);
        require(result == (pattern == 1 ? ReclaimResult::NoRecords : ReclaimResult::Reclaimed),
                "all completed, pending and mixed patterns compact safely");
        auto expected = original;
        for (auto it = expected.begin(); it != expected.end();) {
            if (completed(it->first) && it->first != 4) it = expected.erase(it); else ++it;
        }
        require(capture(outbox) == expected, "sparse ordinals and immutable bytes retained");
        DurableEventOutbox rebooted(files, crypto, key, limits);
        require(rebooted.recover() == OutboxRecovery::Ready && capture(rebooted) == expected,
                "pattern reboots with correct sparse completion mapping");
        for (const auto& body : expected) {
            bool done = false;
            require(rebooted.backend_completed(body.second.first, done) && done == completed(body.first),
                    "retained completion bits follow sparse body positions");
            require(rebooted.append(body.second.first, body.second.second, AdmissionClass::Ordinary) ==
                        OutboxAdmission::Duplicate, "lost ACK retry remains duplicate");
            auto conflict = body.second.second; conflict[20] ^= 1;
            require(rebooted.append(body.second.first, conflict, AdmissionClass::Ordinary) ==
                        OutboxAdmission::IdentityConflict, "conflicting payload fails closed");
        }
        require(rebooted.append("e61", mixed_payload(61), AdmissionClass::Ordinary) == OutboxAdmission::Committed &&
                rebooted.record_count() == 61, "capacity admits at original ordinal highwater plus one");
        require(rebooted.mark_backend_completed("e61"), "receipt after compaction");
        proof.outbox = nullptr;
        authorization.checkpoint_boundary = 61;
        require(rebooted.reclaim_completion_metadata(authorization) == ReclaimResult::Reclaimed,
                "completion reclamation remaps appended sparse tail");
        DurableEventOutbox again(files, crypto, key, limits);
        require(again.recover() == OutboxRecovery::Ready, "dense bitmap after subsequent metadata compaction");
    }
}

void crash_body_boundaries() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key(); const auto limits = mixed_limits();
    PosixSegments baseline;
    DurableEventOutbox initial(baseline, crypto, key, limits);
    require(initial.recover() == OutboxRecovery::Empty, "crash fixture starts");
    populate(initial, 1, 24, [](std::uint64_t i) { return i % 2 == 0; });
    const auto original = capture(initial);
    auto retained = original;
    for (auto it = retained.begin(); it != retained.end();) {
        if (it->first % 2 == 0) it = retained.erase(it); else ++it;
    }
    PosixSegments measured; measured.clone_from(baseline);
    DurableEventOutbox measure(measured, crypto, key, limits);
    require(measure.recover() == OutboxRecovery::Ready, "measure cut operation count");
    measured.mutations = 0;
    MixedProof proof; auto authorization = mixed_authorization(24, proof); BodyCompactionStats stats;
    require(measure.compact_event_bodies(authorization, stats) == ReclaimResult::Reclaimed, "uncut body transaction");
    const auto operations = measured.mutations;
    for (bool after : {false, true}) {
        for (std::size_t cut = 1; cut <= operations; ++cut) {
            PosixSegments files; files.clone_from(baseline);
            DurableEventOutbox outbox(files, crypto, key, limits);
            require(outbox.recover() == OutboxRecovery::Ready, "cut fixture recovers");
            files.mutations = 0; files.fail_at = cut; files.fail_after = after;
            const auto result = outbox.compact_event_bodies(authorization, stats);
            require(result != ReclaimResult::Reclaimed && files.halted, "latched cut stops every subsequent mutation");
            files.halted = false; files.fail_at = 0;
            DurableEventOutbox rebooted(files, crypto, key, limits);
            require(rebooted.recover() == OutboxRecovery::Ready, "cut selects old or verified replacement bank");
            const auto actual = capture(rebooted);
            require(actual == original || actual == retained, "publication cuts preserve all pending bodies");
            require(rebooted.compact_event_bodies(authorization, stats) ==
                        (actual == retained ? ReclaimResult::NoRecords : ReclaimResult::Reclaimed),
                    "interrupted cleanup and candidate construction retry deterministically");
            require(capture(rebooted) == retained, "cut retry converges");
        }
    }
    std::cout << "body_crash_mutation_boundaries=" << operations << " before_after_cuts=" << operations * 2 << "\n";
}

void negative_body_tests() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key(); const auto limits = mixed_limits();
    PosixSegments baseline;
    DurableEventOutbox initial(baseline, crypto, key, limits);
    require(initial.recover() == OutboxRecovery::Empty, "negative fixture starts");
    populate(initial, 1, 24, [](std::uint64_t i) { return i % 2 == 0; });
    const auto original = capture(initial);
    for (int mode = 0; mode < 8; ++mode) {
        PosixSegments files; files.clone_from(baseline);
        DurableEventOutbox outbox(files, crypto, key, limits);
        require(outbox.recover() == OutboxRecovery::Ready, "negative recovers");
        MixedProof proof; auto authorization = mixed_authorization(24, proof); BodyCompactionStats stats;
        if (mode == 0) authorization.post_sync_retention_satisfied = false;
        if (mode == 1) authorization.checkpoint_boundary = 23;
        if (mode == 2) authorization.authenticated_report_digest.fill(0);
        if (mode == 3) proof.current = false;
        if (mode == 4) files.external_used = files.capacity_ - files.bytes(true) - 20 * 1024;
        if (mode == 5) files.corrupt_sync = true;
        if (mode == 6) proof.revoke_at = 15;
        if (mode == 7) files.partial = true;
        const auto result = outbox.compact_event_bodies(authorization, stats);
        require(result != ReclaimResult::Reclaimed, "invalid gate, reserve, authority or candidate cannot publish");
        if (mode == 4) require(result == ReclaimResult::InsufficientWorkspace,
                "actual occupancy exhaustion is distinct from an invalid partition configuration");
        files.external_used = 0;
        files.halted = false; files.fail_at = 0; files.capacity_ = 8U * 1024U * 1024U;
        DurableEventOutbox rebooted(files, crypto, key, limits);
        require(rebooted.recover() == OutboxRecovery::Ready && capture(rebooted) == original,
                "negative compaction leaves authoritative history intact");
    }
    const auto snapshot = [](PosixSegments& files) {
        std::map<std::string, Bytes> result;
        for (const auto& entry : std::filesystem::directory_iterator(files.directory)) {
            const auto name = entry.path().filename().string();
            bool found = false; std::uint32_t size = 0; std::size_t actual = 0;
            require(files.size(name, found, size) && found, "snapshot file size");
            auto& bytes = result[name]; bytes.resize(size);
            require(files.read_file(name, 0, bytes.data(), size, actual) && actual == size,
                    "snapshot complete file bytes");
        }
        return result;
    };
    for (const std::uint32_t caller_reserve : {0U, 4096U, 16384U}) {
        PosixSegments files; files.clone_from(baseline);
        auto protected_limits = limits; protected_limits.protected_capacity_bytes = 8192;
        DurableEventOutbox outbox(files, crypto, key, protected_limits);
        require(outbox.recover() == OutboxRecovery::Ready, "protected reserve fixture recovers");
        files.external_used = files.capacity_ - files.bytes(true) - 25 * 1024;
        MixedProof proof; auto authorization = mixed_authorization(24, proof); BodyCompactionStats stats;
        const auto before = snapshot(files);
        require(outbox.compact_event_bodies(authorization, stats, caller_reserve) == ReclaimResult::InsufficientWorkspace &&
                capture(outbox) == original, "compaction preserves protected reserve even with zero caller reserve");
        require(snapshot(files) == before, "reserve refusal neither changes nor deletes any stored file");
        const auto required = stats.temporary_required_bytes +
            std::max(caller_reserve, protected_limits.protected_capacity_bytes);
        files.external_used = files.capacity_ - files.bytes(true) - required + 1;
        require(outbox.compact_event_bodies(authorization, stats, caller_reserve) == ReclaimResult::InsufficientWorkspace &&
                snapshot(files) == before, "one byte below staging plus effective reserve refuses without mutation");
        DurableEventOutbox rebooted(files, crypto, key, protected_limits);
        require(rebooted.recover() == OutboxRecovery::Ready && capture(rebooted) == original,
                "reserve refusal preserves pending bodies across reboot");
        files.external_used = files.capacity_ - files.bytes(true) - required;
        require(rebooted.compact_event_bodies(authorization, stats, caller_reserve) == ReclaimResult::Reclaimed,
                "exact staging plus effective reserve boundary permits compaction");
    }
    {
        PosixSegments files; files.clone_from(baseline);
        const auto before = snapshot(files);
        files.capacity_ = static_cast<std::uint64_t>(limits.segment_count) * limits.segment_bytes - 1;
        DurableEventOutbox invalid(files, crypto, key, limits);
        require(invalid.recover() == OutboxRecovery::UnsupportedConfiguration && snapshot(files) == before,
                "invalid partition capacity fails closed without modifying storage");
    }
    std::cout << "reserve_boundaries=PASS caller_reserves=0,4096,16384 unchanged_files=PASS invalid_partition=PASS\n";
    // After publication selected candidate corruption/missing data fails closed;
    // obsolete or incomplete banks never substitute for it.
    for (bool missing : {false, true}) {
        PosixSegments files; files.clone_from(baseline);
        DurableEventOutbox outbox(files, crypto, key, limits);
        require(outbox.recover() == OutboxRecovery::Ready, "corrupt selected fixture");
        MixedProof proof; auto authorization = mixed_authorization(24, proof); BodyCompactionStats stats;
        require(outbox.compact_event_bodies(authorization, stats) == ReclaimResult::Reclaimed, "publish candidate");
        if (missing) require(files.remove_segment(limits.segment_count), "remove selected body file");
        else { files.corrupt_sync = true; require(files.sync(limits.segment_count), "corrupt selected ciphertext"); }
        DurableEventOutbox rebooted(files, crypto, key, limits);
        require(rebooted.recover() == OutboxRecovery::IntegrityFailure,
                "selected candidate loss fails closed without older-bank fallback");
    }
}

void repeated_body_capacity() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key(); const auto limits = mixed_limits();
    PosixSegments files;
    DurableEventOutbox outbox(files, crypto, key, limits);
    require(outbox.recover() == OutboxRecovery::Empty, "reuse fixture starts");
    MixedProof proof; BodyCompactionStats stats;
    std::uint64_t cumulative = 0, maximum_root = 0, maximum_retained = 0;
    std::uint64_t original_allocated = 0, retained_allocated = 0, original_logical = 0, original_body_allocated = 0;
    for (unsigned window = 0; window < 32; ++window) {
        const auto first = cumulative + 1;
        populate(outbox, first, 100, [](std::uint64_t i) { return i % 7 != 0; });
        cumulative += 100;
        // A few pending records cross every window; one old record stays pending
        // for the entire workload so metadata cannot depend on oldest ordinal.
        const auto before = capture(outbox);
        for (const auto& body : before)
            if (body.first < first && body.first != 7)
                require(outbox.mark_backend_completed(body.second.first), "complete older pending body");
        if (window == 1) {
            original_allocated = files.bytes(true); original_logical = files.bytes(false);
            original_body_allocated = files.body_allocated_bytes();
            files.peak_allocated = original_allocated; files.peak_logical = original_logical;
        }
        auto authorization = mixed_authorization(cumulative, proof);
        require(outbox.compact_event_bodies(authorization, stats) == ReclaimResult::Reclaimed,
                "repeated mixed fill reclaim refill");
        if (window == 1) {
            retained_allocated = files.bytes(true);
            require(retained_allocated < original_allocated && files.body_allocated_bytes() < original_body_allocated,
                    "POSIX allocated event-body blocks recovered independently of completion metadata");
            std::cout << "body_original_allocated=" << original_allocated
                      << " retained_allocated=" << retained_allocated
                      << " actual_host_bytes_recovered=" << original_allocated - retained_allocated
                      << " original_body_allocated=" << original_body_allocated
                      << " retained_body_allocated=" << files.body_allocated_bytes()
                      << " body_allocated_recovered=" << original_body_allocated - files.body_allocated_bytes()
                      << " original_body_logical=" << stats.original_body_bytes
                      << " original_logical=" << original_logical
                      << " retained_body_bytes=" << stats.retained_body_bytes
                      << " temporary_peak_logical=" << files.peak_logical
                      << " temporary_peak_allocated=" << files.peak_allocated
                      << " protected_copy_reserve=" << stats.temporary_required_bytes << "\n";
        }
        const auto bodies = capture(outbox);
        require(bodies.count(7) && bodies.at(7).second == mixed_payload(7) && bodies.size() <= 16,
                "oldest pending event and immutable context survive all reuse windows");
        maximum_retained = std::max<std::uint64_t>(maximum_retained, bodies.size());
        bool found = false; std::uint32_t root_bytes = 0;
        require(files.size("root", found, root_bytes) && found, "bounded root exists");
        maximum_root = std::max<std::uint64_t>(maximum_root, root_bytes);
        require(root_bytes <= 320, "completion bitmap bounded by retained bodies rather than lifetime span");
        require(outbox.recover() == OutboxRecovery::Ready && capture(outbox) == bodies, "repeat reboot equivalence");
        const auto next = "probe" + std::to_string(window);
        require(outbox.append(next, mixed_payload(cumulative + 1), AdmissionClass::Ordinary) == OutboxAdmission::Committed,
                "new admission reuses compacted capacity");
        ++cumulative;
        require(outbox.mark_backend_completed(next), "probe completion");
    }
    std::cout << "mixed_cumulative_admissions=" << cumulative << " windows=32 max_retained_records="
              << maximum_retained << " max_root_bytes=" << maximum_root << " index_bytes=" << outbox.index_memory_bytes() << "\n";
}
void subsequent_admission_and_generation_tests() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key(); const auto limits = mixed_limits();
    PosixSegments baseline;
    DurableEventOutbox original(baseline, crypto, key, limits);
    require(original.recover() == OutboxRecovery::Empty, "subsequent admission starts");
    populate(original, 1, 24, [](std::uint64_t i) { return i % 2 == 0; });
    MixedProof proof; auto authorization = mixed_authorization(24, proof); BodyCompactionStats stats;
    require(original.compact_event_bodies(authorization, stats) == ReclaimResult::Reclaimed,
            "mixed bank published before new admission cuts");
    const auto retained = capture(original);
    for (bool after : {false, true}) {
        for (std::size_t cut = 1; cut <= 3; ++cut) {
            PosixSegments files; files.clone_from(baseline);
            DurableEventOutbox outbox(files, crypto, key, limits);
            require(outbox.recover() == OutboxRecovery::Ready, "subsequent admission cut recovers bank");
            files.mutations = 0; files.fail_at = cut; files.fail_after = after;
            require(outbox.append("e25", mixed_payload(25), AdmissionClass::Ordinary) != OutboxAdmission::Committed &&
                    files.halted, "new admission cannot ACK a failed storage boundary");
            files.halted = false; files.fail_at = 0;
            DurableEventOutbox rebooted(files, crypto, key, limits);
            require(rebooted.recover() == OutboxRecovery::Ready, "new append interruption recovers");
            const auto recovered = capture(rebooted);
            for (const auto& body : retained) require(recovered.at(body.first) == body.second, "old pending survives new append cut");
            const auto retry = rebooted.append("e25", mixed_payload(25), AdmissionClass::Ordinary);
            require((retry == OutboxAdmission::Committed || retry == OutboxAdmission::Duplicate) &&
                    rebooted.record_count() == 25, "exact new-event retry publishes once at preserved ordinal");
        }
    }
    // Staged full-but-unpublished event cannot disappear during compaction.
    PosixSegments staged; staged.clone_from(baseline);
    DurableEventOutbox staged_outbox(staged, crypto, key, limits);
    require(staged_outbox.recover() == OutboxRecovery::Ready, "staged fixture recovers");
    staged.mutations = 0; staged.fail_at = 3;
    require(staged_outbox.append("e25", mixed_payload(25), AdmissionClass::Ordinary) ==
                OutboxAdmission::MetadataPublicationFailure, "publication cut stages full event");
    staged.halted = false; staged.fail_at = 0;
    require(staged_outbox.recover() == OutboxRecovery::Ready &&
            staged_outbox.compact_event_bodies(authorization, stats) == ReclaimResult::RestartRequired &&
            staged_outbox.append("e25", mixed_payload(25), AdmissionClass::Ordinary) == OutboxAdmission::Committed,
            "compaction protects unpublished exact retry body");

    // Empty replacement banks have an authenticated zero-record manifest and a
    // generation-bound completion head. Admission still uses the original HWM.
    PosixSegments empty;
    DurableEventOutbox all_completed(empty, crypto, key, limits);
    require(all_completed.recover() == OutboxRecovery::Empty, "empty replacement starts");
    populate(all_completed, 1, 10, [](std::uint64_t) { return true; });
    authorization.checkpoint_boundary = 10;
    require(all_completed.compact_event_bodies(authorization, stats) == ReclaimResult::Reclaimed &&
            stats.retained_records == 0 && capture(all_completed).empty(), "all-completed segment yields empty authoritative bank");
    require(all_completed.recover() == OutboxRecovery::Ready &&
            all_completed.append("e11", mixed_payload(11), AdmissionClass::Ordinary) == OutboxAdmission::Committed &&
            all_completed.mark_backend_completed("e11"), "empty replacement permits refill and completion");
    authorization.checkpoint_boundary = 11;
    require(all_completed.reclaim_completion_metadata(authorization) == ReclaimResult::Reclaimed &&
            all_completed.recover() == OutboxRecovery::Ready, "empty manifest and later dense completion snapshot recover");

    // Firmware's disabled gate keeps obsolete storage intact even after a
    // previously published host generation is loaded.
    PosixSegments disabled; disabled.clone_from(baseline);
    const Bytes orphan{1, 2, 3};
    require(disabled.append(0, orphan.data(), orphan.size()), "add isolated obsolete-bank fixture");
    auto disabled_limits = limits; disabled_limits.body_retirement_enabled = false;
    DurableEventOutbox gated(disabled, crypto, key, disabled_limits);
    disabled.mutations = 0;
    require(gated.recover() == OutboxRecovery::Ready && disabled.mutations == 0 &&
            capture(gated) == retained, "production disabled recovery never unlinks obsolete bodies");

    // Reusing both bank slots cannot resurrect an older authenticated manifest.
    Bytes first_root; bool found = false;
    require(baseline.read_lifecycle_root(first_root, found) && found, "save old generation root");
    require(original.append("e25", mixed_payload(25), AdmissionClass::Ordinary) == OutboxAdmission::Committed &&
            original.mark_backend_completed("e25"), "later generation adds a receipt");
    proof.protected_ordinals.insert(1);
    for (const auto& body : retained)
        if (body.first != 1) require(original.mark_backend_completed(body.second.first), "retire old pending for next generation");
    authorization.checkpoint_boundary = 25;
    require(original.compact_event_bodies(authorization, stats) == ReclaimResult::Reclaimed, "second bank generation publishes");
    require(baseline.publish_lifecycle_root(first_root), "restore stale authenticated manifest fixture");
    DurableEventOutbox stale(baseline, crypto, key, limits);
    require(stale.recover() == OutboxRecovery::IntegrityFailure, "stale generation cannot select removed old bank");
    std::cout << "subsequent_admission_cuts=6 empty_candidate_generation=PASS disabled_recovery_cleanup=PASS stale_generation=PASS\n";
}

struct RuntimeBodyProof {
    gs::hub::HubRuntime* runtime{nullptr};
    DurableEventOutbox* outbox{nullptr};
    gs::hub::durable::RetirementSnapshot* snapshot{nullptr};
    gs::hub::durable::ReportSnapshotReference* reference{nullptr};
    bool owner_matches{true};
};
bool runtime_body_current(void* opaque) {
    const auto& context = *static_cast<RuntimeBodyProof*>(opaque);
    return context.runtime->durable_admission_open() &&
        context.outbox->replay_fence_matches(context.snapshot->storage_epoch, *context.reference);
}
bool runtime_body_retired(void* opaque, std::uint64_t,
                          const std::string& key, const Bytes& payload) {
    auto& context = *static_cast<RuntimeBodyProof*>(opaque);
    gs::DomainEvent event;
    if (!gs::hub::HubJournal::decode_event_payload(payload, event) || event.key.str() != key ||
        event.key.source_id.size() != 5 || event.key.source_id.substr(0, 4) != "room") return false;
    const auto slot = static_cast<std::uint8_t>(event.key.source_id[4] - '0');
    if (slot >= 6) return false;
    const auto& node = context.snapshot->nodes[slot];
    return context.runtime->identity_retirement_eligibility(event, slot,
        node.enrollment_generation + (context.owner_matches ? 0 : 1), node.binding_digest) ==
            gs::hub::IdentityRetirementEligibility::EligibleWithDurableReplayFence;
}

void six_node_runtime_mixed_cycles() {
    gs::host::security::OpenSslCommissioningCrypto crypto;
    const auto key = storage_key();
    auto limits = mixed_limits(); limits.segment_bytes = 16 * 1024;
    PosixSegments files;
    StateFiles state_files;
    DurableEventOutbox outbox(files, crypto, key, limits);
    require(outbox.recover() == OutboxRecovery::Empty, "six Node runtime starts empty");
    RuntimeStateStore state(state_files, crypto, key);
    OutboxJournalBackend backend(outbox);
    gs::hub::durable::RetirementSnapshot snapshot;
    snapshot.storage_epoch = 7; snapshot.occupancy_mask = 0x3f;
    gs::hub::durable::ReportSnapshotReference reference;
    gs::EventKey permanently_pending("room0", 42, 1, "device-room0");
    std::uint64_t largest_identity = 0, cumulative = 0;
    for (unsigned window = 0; window < 12; ++window) {
        gs::hub::HubRuntime runtime(32, backend);
        runtime.bind_runtime_state(state);
        for (unsigned slot = 0; slot < 6; ++slot) runtime.authorize_node("room" + std::to_string(slot), 42, true);
        if (window != 0)
            require(runtime.bind_replay_fence(snapshot, 7, reference, outbox), "recover current owner replay fence");
        require(runtime.restore_from_journal(), "checkpoint and sparse body replay recover");
        gs::hub::CloudSync cloud(runtime.journal()); cloud.set_connected(true, 1);
        const auto old = capture(outbox);
        for (const auto& body : old) {
            gs::DomainEvent event;
            require(gs::hub::HubJournal::decode_event_payload(body.second.second, event), "old pending event decode");
            if (event.key.str() != permanently_pending.str()) {
                const gs::hub::BackendCommitReply reply{gs::hub::BackendReplyStatus::Committed, event.key, true, false};
                require(cloud.handle_backend_reply(event.key, reply, 1) == gs::hub::BackendReceiptResult::Completed,
                        "delayed pending event backend commit");
            }
        }
        for (unsigned step = 1; step <= 20; ++step) {
            const auto sequence = window * 20ULL + step;
            for (unsigned slot = 0; slot < 6; ++slot) {
                auto message = make_message(sequence);
                message.node_id = "room" + std::to_string(slot);
                message.location = "location" + std::to_string(slot);
                if (step % 5 == 0) { message.event_type = gs::EventKind::DoorOpen; message.sensor_type = gs::SensorType::Reed; }
                if (step % 7 == 0) { message.event_type = gs::EventKind::Gap; message.sensor_type = gs::SensorType::System; }
                std::array<std::uint8_t, 32> owner{}; owner.fill(static_cast<std::uint8_t>(0x31 + slot));
                require(runtime.authenticated_radio_message_callback(message, message.node_id,
                            "device-" + message.node_id, 42, 0, sequence * 1000U + 90000U,
                            slot, 3, owner), "six Node authenticated ingress");
                const auto processed = runtime.run_state_once(static_cast<std::uint16_t>(sequence % 1440));
                require(processed && processed->ack == gs::AckClass::Durable, "six Node ACK after durability");
                ++cumulative;
                if (sequence % 4 != 0 && processed->key.str() != permanently_pending.str()) {
                    const gs::hub::BackendCommitReply reply{gs::hub::BackendReplyStatus::Committed, processed->key, true, false};
                    require(cloud.handle_backend_reply(processed->key, reply, 1) == gs::hub::BackendReceiptResult::Completed,
                            "exact authenticated COMMITTED receipt only");
                }
            }
        }
        snapshot.generation = window + 1;
        reference.bank = static_cast<std::uint8_t>(window % 3); reference.generation = window + 1;
        reference.digest.fill(static_cast<std::uint8_t>(0x60 + window));
        for (unsigned slot = 0; slot < 6; ++slot) {
            auto& node = snapshot.nodes[slot]; node.binding_digest.fill(static_cast<std::uint8_t>(0x31 + slot));
            node.enrollment_generation = 3; node.current_origin_session = 42;
            node.report_generation = window + 1; node.report_hmac.fill(0x52);
            node.durable_admission_highwater = (window + 1) * 20; node.pending_count = 0;
        }
        const auto before = capture(outbox);
        for (const auto& body : before) {
            gs::DomainEvent event; bool completed = false;
            require(gs::hub::HubJournal::decode_event_payload(body.second.second, event) &&
                    outbox.backend_completed(body.second.first, completed), "build exact Node pending snapshot");
            if (!completed) {
                const auto slot = static_cast<unsigned>(event.key.source_id[4] - '0');
                auto& node = snapshot.nodes[slot];
                require(node.pending_count < 32, "Node pending report bounded");
                node.pending[node.pending_count++] = {event.key.session_id, event.key.sequence};
            }
        }
        require(outbox.publish_replay_fence(7, reference, cumulative) &&
                runtime.bind_replay_fence(snapshot, 7, reference, outbox), "publish selected authenticated retirement witness");
        RuntimeBodyProof proof{&runtime, &outbox, &snapshot, &reference, true};
        RetirementAuthorization authorization;
        authorization.checkpoint_boundary = cumulative;
        authorization.post_sync_retention_satisfied = true;
        // Initialize directly: the context belongs to the actual runtime proof.
        authorization.context = &proof; authorization.authority_current = runtime_body_current;
        authorization.node_retired = runtime_body_retired;
        authorization.authenticated_report_generation = reference.generation;
        authorization.authenticated_report_digest = reference.digest;
        BodyCompactionStats stats;
        if (window == 0) {
            proof.owner_matches = false;
            require(outbox.compact_event_bodies(authorization, stats) == ReclaimResult::NoRecords && capture(outbox) == before,
                    "wrong enrollment generation cannot retire mixed events");
            proof.owner_matches = true;
            auto wrong = authorization; wrong.authenticated_report_digest[0] ^= 1;
            require(outbox.compact_event_bodies(wrong, stats) == ReclaimResult::InvalidAuthorization,
                    "stale durable report authority cannot delete bodies");
        }
        Bytes checkpoint_before; std::uint64_t boundary = 0; bool found = false;
        require(state.load_checkpoint(checkpoint_before, boundary, found) && found && boundary == cumulative,
                "reducer coverage checkpoint covers publication boundary");
        const auto body_result = outbox.compact_event_bodies(authorization, stats);
        if (body_result != ReclaimResult::Reclaimed)
            std::cerr << "runtime_window=" << window << " compaction_result=" << static_cast<unsigned>(body_result)
                      << " retained=" << stats.retained_records << " retired=" << stats.retired_records << "\n";
        require(body_result == ReclaimResult::Reclaimed,
                "production runtime proof compacts interleaved six Node events");
        const auto retained = capture(outbox);
        require(retained.size() == 31 && retained.count(1), "all six Node pending events retained");
        for (const auto& body : retained) require(before.at(body.first) == body.second, "original payload timestamps survive compaction");
        largest_identity = std::max<std::uint64_t>(largest_identity, state.identity_bytes());
        IdentityCompactionPlan identity_plan;
        require(runtime.compact_identity_generation(4096, identity_plan) && identity_plan.retained_records == 31,
                "identity compaction joins sparse retired body authority without retaining lifetime metadata");
        require(outbox.recover() == OutboxRecovery::Ready, "six Node reboot outbox");
        RuntimeStateStore reboot_state(state_files, crypto, key);
        gs::hub::HubRuntime rebooted(32, backend); rebooted.bind_runtime_state(reboot_state);
        for (unsigned slot = 0; slot < 6; ++slot) rebooted.authorize_node("room" + std::to_string(slot), 42, true);
        require(rebooted.bind_replay_fence(snapshot, 7, reference, outbox) && rebooted.restore_from_journal(),
                "sparse body, identity and reducer checkpoints recover together");
        Bytes checkpoint_after;
        require(reboot_state.load_checkpoint(checkpoint_after, boundary, found) && found && checkpoint_after == checkpoint_before,
                "original local minute and reducer coverage state are unchanged by compaction");
        auto duplicate = make_message(1); duplicate.node_id = "room0"; duplicate.location = "location0";
        std::array<std::uint8_t, 32> owner{}; owner.fill(0x31);
        require(rebooted.authenticated_radio_message_callback(duplicate, "room0", "device-room0", 42, 0, 999999, 0, 3, owner),
                "pending duplicate retry admitted after mixed compaction and reboot");
        const auto retry = rebooted.run_state_once(900);
        require(retry && retry->ack == gs::AckClass::Durable && !retry->state_changed && outbox.record_count() == cumulative,
                "lost ACK duplicate has no repeated reducer effect");
        std::optional<std::uint16_t> original_minute;
        require(reboot_state.identity_context(permanently_pending, 1, original_minute) &&
                original_minute == std::optional<std::uint16_t>{1},
                "pending retry keeps its original persisted local minute");
        duplicate.battery_mv++;
        require(rebooted.authenticated_radio_message_callback(duplicate, "room0", "device-room0", 42, 0, 999999, 0, 3, owner),
                "conflicting pending retry enters validation");
        const auto conflict = rebooted.run_state_once();
        require(conflict && conflict->ack == gs::AckClass::Rejected, "conflicting retry rejected after compaction");
        auto retired = make_message(window * 20ULL + 2); retired.node_id = "room0"; retired.location = "location0";
        require(!rebooted.authenticated_radio_message_callback(retired, "room0", "device-room0", 42, 0, 999999, 0, 3, owner),
                "retired exact key is fenced after body and identity compaction");
        auto stale_reference = reference; stale_reference.digest[0] ^= 1;
        gs::hub::HubRuntime stale(32, backend); stale.bind_runtime_state(reboot_state);
        require(!stale.bind_replay_fence(snapshot, 7, stale_reference, outbox) && !stale.durable_admission_open(),
                "restart with stale replay witness keeps admission closed");
    }
    std::cout << "six_node_mixed_runtime_admissions=" << cumulative << " windows=12 retained_each_window=31"
              << " max_identity_window_bytes=" << largest_identity << "\n";
}

} // namespace

#ifdef GS_MIXED_BODY_EMBEDDED
int mixed_body_compaction_fixture_main() {
#else
int main() {
#endif
    try {
        normal_body_patterns();
        crash_body_boundaries();
        negative_body_tests();
        repeated_body_capacity();
        subsequent_admission_and_generation_tests();
        six_node_runtime_mixed_cycles();
        struct rusage usage{};
        require(::getrusage(RUSAGE_SELF, &usage) == 0, "measure host process peak RSS");
        std::cout << "host_process_peak_rss_kib=" << usage.ru_maxrss << "\n";
        std::cout << "hub_mixed_body_compaction_validation=PASS\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "hub_mixed_body_compaction_validation=FAIL " << error.what() << "\n";
        return 1;
    }
}
