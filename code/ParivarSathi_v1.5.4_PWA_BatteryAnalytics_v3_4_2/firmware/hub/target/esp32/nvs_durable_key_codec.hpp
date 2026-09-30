#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace gs::hub::target {

enum class DurablePhysicalKeyKind {
    Checkpoint = 1,
    Selector = 2,
    Transition = 3,
    EffectChunk = 4,
    EvidenceChunk = 5,
    Bitmap = 6,
    RetirementBank = 7,
    LegacyEvent = 8,
    LegacyCompletion = 9,
    MigrationMetadata = 10
};

struct DurablePhysicalKeyRecord {
    DurablePhysicalKeyKind kind{DurablePhysicalKeyKind::Checkpoint};
    std::uint64_t id{0};
};

constexpr std::size_t kEspNvsKeyMaxLength = 15;

// Portable physical-key codec used only below BlobStore at the target edge.
bool durable_logical_to_physical_key(const std::string& logical,
                                     std::string& physical);
bool durable_physical_key_record(const std::string& physical,
                                 DurablePhysicalKeyRecord& record);

}  // namespace gs::hub::target
