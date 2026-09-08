#pragma once

#include "gs/domain.hpp"

#include <map>
#include <set>
#include <string>
#include <vector>

namespace gs::hub {

struct NodeHealth {
    EpochSeconds last_contact{0};
    std::uint16_t battery_mv{0};
    bool sensor_fault{false};
};

class CoverageTracker {
public:
    explicit CoverageTracker(EpochSeconds lease_seconds = 190);
    void require_node(const std::string& node_id);
    void observe(const std::string& node_id, EpochSeconds at, std::uint16_t battery_mv = 0);
    void set_sensor_fault(const std::string& node_id, bool fault);
    CoverageState current(EpochSeconds now) const;
    std::vector<std::string> reasons(EpochSeconds now) const;

private:
    EpochSeconds lease_seconds_;
    std::set<std::string> required_nodes_;
    std::map<std::string, NodeHealth> health_;
};

}  // namespace gs::hub
