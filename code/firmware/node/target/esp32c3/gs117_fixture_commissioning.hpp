#pragma once

#include "firmware/common/security/commissioning_protocol.hpp"
#include "firmware/node/runtime/node_runtime.hpp"

#include <algorithm>

namespace gs::node::target {

// The owner-approved fixture reset may retire only test-marked motion data.
// Any gap marker or non-test record remains a hard stop.
inline bool gs117_fixture_recovery_is_disposable(
        const node::NodeRuntimeRecoveryState& state) {
    if (state.gap_marker_required) return false;
    const auto disposable = [](const gs::DomainEvent& event) {
        return event.is_test &&
            (event.kind == gs::EventKind::Motion ||
             event.kind == gs::EventKind::MotionSummary);
    };
    return std::all_of(state.retained.begin(), state.retained.end(), disposable) &&
           std::all_of(state.pending.begin(), state.pending.end(),
               [&disposable](const node::PendingTx& pending) {
                   return disposable(pending.event);
               });
}

inline bool gs117_fixture_same_device_key(
        const security::CommissioningBinding& prior,
        const security::P256PublicKey& current_public_key,
        const std::string& physical_device_id) {
    return prior.device_id == physical_device_id &&
           prior.device_public_key == current_public_key;
}

inline bool gs117_fixture_offer_matches(
        const security::CommissioningBinding& prior,
        const security::CommissioningOffer& offer,
        const std::string& physical_device_id,
        const std::string& expected_hub_id) {
    return prior.device_id == physical_device_id &&
           offer.hub_id == expected_hub_id &&
           offer.home_id == "gs177-test-product" &&
           offer.device_public_key == prior.device_public_key &&
           offer.logical_id == "bedroom" && offer.room == "Bedroom" &&
           offer.function == "motion";
}

}  // namespace gs::node::target
