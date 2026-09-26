// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module H04 Hub coverage
// @requirements F08, E01, E03
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// CoverageTracker owns contact and fault state for required nodes. Optional nodes should not invalidate
// unrelated routines. Its current/reasons methods describe the present moment; they do not reconstruct
// whether the entire morning was observable. Store interval history before making that stronger claim.

#pragma once

#include "gs/domain.hpp"
#include "gs/protocol.hpp"

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
    explicit CoverageTracker(EpochSeconds lease_seconds = NodeProtocolPolicy::coverage_after_seconds);
    void require_node(const std::string& node_id);
    void forget_node(const std::string& node_id);
    // @requirements F08, E01, E03
    // Refresh contact telemetry; a heartbeat must not erase an explicit sensor fault.
    void observe(const std::string& node_id, EpochSeconds at, std::uint16_t battery_mv = 0);
    void set_sensor_fault(const std::string& node_id, bool fault);
    // @requirements F08, E01, E03
    // Calculate present required-node coverage; this is not full-window coverage history (G03).
    CoverageState current(EpochSeconds now) const;
    std::vector<std::string> reasons(EpochSeconds now) const;

private:
    EpochSeconds lease_seconds_;
    std::set<std::string> required_nodes_;
    std::map<std::string, NodeHealth> health_;
};

}  // namespace gs::hub
