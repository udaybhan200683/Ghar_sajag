#pragma once

#include "firmware/hub/components/storage/journal.hpp"

namespace gs::hub::target {

// Independent NVS partition; no key material is stored here. The caller must
// initialize it explicitly and fail closed if an upgraded board lacks it.
class NvsJournalSlotStore final : public JournalSlotStore {
public:
    bool initialize();
    bool read(std::size_t slot, security::Bytes& blob, bool& found) override;
    bool write(std::size_t slot, const security::Bytes& blob) override;
private:
    bool initialized_{false};
};

}  // namespace gs::hub::target
