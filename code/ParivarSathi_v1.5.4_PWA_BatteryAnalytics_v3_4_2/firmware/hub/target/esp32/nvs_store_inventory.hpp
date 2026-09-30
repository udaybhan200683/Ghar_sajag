#pragma once

#include "storage/hub_durability_owner.hpp"

namespace gs::hub::target {

class NvsStoreInventory final : public durable::StoreInventory {
public:
    durable::InventorySnapshot scan() override;
};

}  // namespace gs::hub::target
