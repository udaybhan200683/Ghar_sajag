#include "firmware/node/runtime/node_runtime.hpp"

#include <iostream>
#include <stdexcept>

using gs::EventKind;
using gs::node::NodeRuntime;

namespace {
void require(bool okay, const char* message) {
    if (!okay) throw std::runtime_error(message);
}
}

int main() {
    try {
        NodeRuntime original("bathroom", 7);
        const auto motion = original.record(EventKind::Motion, "Bathroom", 100, 0);
        const auto call = original.record(EventKind::CallFamily, "Bathroom", 101, 0);
        require(motion && call && original.persisted() == 2 && original.pending() == 2,
                "pre-restart retained state was not created");
        const auto first = original.next_message(101);
        require(first && first->sequence_number == motion->sequence,
                "pre-restart first event was not due");
        original.transport_result(*motion, false, 101);
        const auto saved = original.recovery_snapshot();
        require(saved.pending.size() == 2 && saved.retained.size() == 2 &&
                saved.pending[0].attempt == 1,
                "retry or retained state was missing from snapshot");

        NodeRuntime recovered("bathroom", 8);
        require(recovered.restore_recovery(saved, 0) && recovered.persisted() == 2 &&
                recovered.pending() == 2,
                "prior event identities did not restore under newer session");
        const auto retransmit = recovered.next_message(0);
        require(retransmit && retransmit->session_id == 7 &&
                retransmit->sequence_number == motion->sequence,
                "old event identity was rewritten or old clock delay survived reboot");
        recovered.transport_result(*motion, false, 0);
        require(recovered.radio_stats().retries == 1,
                "retained retry attempt was not continued");
        const auto fresh = recovered.record(EventKind::DoorOpen, "Bathroom", 1, 0);
        require(fresh && fresh->session_id == 8 && fresh->sequence == 1,
                "new event did not use a separate fresh boot session");
        require(recovered.acknowledge(*motion, gs::AckClass::Durable) &&
                recovered.persisted() == 2 && recovered.pending() == 2,
                "ACK did not retire only the matching old event");

        auto corrupt = saved;
        corrupt.retained.pop_back();
        NodeRuntime orphan("bathroom", 8);
        require(!orphan.restore_recovery(corrupt, 0) && orphan.pending() == 0 &&
                orphan.persisted() == 0, "orphaned pending business event restored");
        corrupt = saved;
        corrupt.pending.push_back(corrupt.pending.front());
        NodeRuntime duplicate("bathroom", 8);
        require(!duplicate.restore_recovery(corrupt, 0) && duplicate.pending() == 0,
                "duplicate pending identity restored");
        corrupt = saved;
        corrupt.retained[0].location = "wrong-room";
        NodeRuntime mismatched("bathroom", 8);
        require(!mismatched.restore_recovery(corrupt, 0),
                "retained and in-flight payload mismatch restored");
        NodeRuntime stale("bathroom", 7);
        NodeRuntime foreign("kitchen", 8);
        NodeRuntime too_small("bathroom", 8, 1, 1);
        require(!stale.restore_recovery(saved, 0) &&
                !foreign.restore_recovery(saved, 0) &&
                !too_small.restore_recovery(saved, 0),
                "stale foreign or over-capacity runtime accepted restart state");
        NodeRuntime full_store("bathroom", 9, 1, 2);
        require(full_store.record(EventKind::DoorOpen, "Bathroom", 1, 0) &&
                !full_store.record(EventKind::CallFamily, "Bathroom", 2, 0),
                "gap-marker setup did not reach retained capacity");
        const auto with_gap = full_store.recovery_snapshot();
        NodeRuntime after_gap("bathroom", 10, 1, 2);
        require(with_gap.gap_marker_required &&
                after_gap.restore_recovery(with_gap, 0) &&
                after_gap.recovery_snapshot().gap_marker_required,
                "storage gap marker was lost across restart");
        std::cout << "P2-NODE-RECOVERY HOST PASS retained/in-flight/retry/session isolation\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-NODE-RECOVERY HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
