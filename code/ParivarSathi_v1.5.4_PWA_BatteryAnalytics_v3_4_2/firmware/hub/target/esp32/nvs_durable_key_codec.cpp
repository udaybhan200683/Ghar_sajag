#include "nvs_durable_key_codec.hpp"

#include <array>
#include <limits>

namespace gs::hub::target {
namespace {
constexpr char kBase36[] = "0123456789abcdefghijklmnopqrstuvwxyz";
constexpr std::size_t kBase36Width = 13;

bool starts_with(const std::string& value, const char* prefix) {
    const std::string p(prefix);
    return value.compare(0, p.size(), p) == 0;
}

bool decimal_u64(const std::string& text, std::uint64_t& value) {
    if (text.empty() || (text.size() > 1 && text.front() == '0')) return false;
    value = 0;
    for (const char ch : text) {
        if (ch < '0' || ch > '9') return false;
        const auto digit = static_cast<std::uint64_t>(ch - '0');
        if (value > (std::numeric_limits<std::uint64_t>::max() - digit) / 10U)
            return false;
        value = value * 10U + digit;
    }
    return true;
}

std::string encode36(std::uint64_t value) {
    std::array<char, kBase36Width> digits{};
    for (std::size_t i = digits.size(); i > 0; --i) {
        digits[i - 1] = kBase36[value % 36U];
        value /= 36U;
    }
    if (value != 0) return {};
    return {digits.begin(), digits.end()};
}

bool decode36(const std::string& text, std::uint64_t& value) {
    if (text.size() != kBase36Width) return false;
    value = 0;
    for (const char ch : text) {
        unsigned digit = 0;
        if (ch >= '0' && ch <= '9') digit = static_cast<unsigned>(ch - '0');
        else if (ch >= 'a' && ch <= 'z') digit = 10U + static_cast<unsigned>(ch - 'a');
        else return false;
        if (value > (std::numeric_limits<std::uint64_t>::max() - digit) / 36U)
            return false;
        value = value * 36U + digit;
    }
    return encode36(value) == text;
}

bool fixed_record(const std::string& key, DurablePhysicalKeyRecord& out) {
    const auto indexed = [&](const char* prefix, std::uint64_t max,
                             DurablePhysicalKeyKind kind) {
        if (!starts_with(key, prefix)) return false;
        const auto suffix = key.substr(std::string(prefix).size());
        if (suffix.size() != 1 || suffix[0] < '0' || suffix[0] > '9') return false;
        const auto id = static_cast<std::uint64_t>(suffix[0] - '0');
        if (id > max) return false;
        out = {kind, id};
        return true;
    };
    if (indexed("cp", 1, DurablePhysicalKeyKind::Checkpoint) ||
        indexed("sel", 1, DurablePhysicalKeyKind::Selector) ||
        indexed("tr", 3, DurablePhysicalKeyKind::Transition) ||
        indexed("bm", 1, DurablePhysicalKeyKind::Bitmap) ||
        indexed("ret", 2, DurablePhysicalKeyKind::RetirementBank)) return true;
    if (key == "mig0" || key == "mig1") {
        out = {DurablePhysicalKeyKind::MigrationMetadata,
               static_cast<std::uint64_t>(key.back() - '0')};
        return true;
    }

    if (key.size() == 4 && (key[0] == 'e' || key[0] == 'c') &&
        key[1] >= '0' && key[1] <= '9' && key[2] >= '0' && key[2] <= '9' &&
        key[3] >= '0' && key[3] <= '9') {
        const auto id = static_cast<std::uint64_t>((key[1] - '0') * 100 +
            (key[2] - '0') * 10 + (key[3] - '0'));
        if (id > 127) return false;
        out = {key[0] == 'e' ? DurablePhysicalKeyKind::LegacyEvent
                             : DurablePhysicalKeyKind::LegacyCompletion, id};
        return true;
    }
    return false;
}
}  // namespace

bool durable_logical_to_physical_key(const std::string& logical,
                                     std::string& physical) {
    physical.clear();
    if (logical.size() <= kEspNvsKeyMaxLength) {
        DurablePhysicalKeyRecord fixed;
        if (fixed_record(logical, fixed)) {
            physical = logical;
            return true;
        }
    }
    if (logical.size() < 3) return false;
    const std::string prefix = logical.substr(0, 2);
    if (prefix != "ef" && prefix != "ev") return false;
    std::uint64_t id = 0;
    if (!decimal_u64(logical.substr(2), id)) return false;
    const auto body = encode36(id);
    if (body.size() != kBase36Width) return false;
    physical = prefix + body;
    return physical.size() <= kEspNvsKeyMaxLength;
}

bool durable_physical_key_record(const std::string& physical,
                                 DurablePhysicalKeyRecord& record) {
    record = {};
    if (physical.empty() || physical.size() > kEspNvsKeyMaxLength) return false;
    if (fixed_record(physical, record)) return true;
    if (physical.size() != 2 + kBase36Width) return false;
    const auto prefix = physical.substr(0, 2);
    if (prefix != "ef" && prefix != "ev") return false;
    std::uint64_t id = 0;
    if (!decode36(physical.substr(2), id)) return false;
    record = {prefix == "ef" ? DurablePhysicalKeyKind::EffectChunk
                              : DurablePhysicalKeyKind::EvidenceChunk, id};
    return true;
}

}  // namespace gs::hub::target
