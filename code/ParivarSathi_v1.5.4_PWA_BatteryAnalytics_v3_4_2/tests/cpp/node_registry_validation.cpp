#include "firmware/hub/components/registry/node_registry.hpp"

#include <iostream>
#include <stdexcept>
#include <string>

using gs::hub::EnrolledNode;
using gs::hub::NodeRegistry;
using gs::hub::RegistryResult;

namespace {
void require(bool value, const char* message) {
    if (!value) throw std::runtime_error(message);
}

EnrolledNode node(unsigned index) {
    EnrolledNode value;
    value.device_id = "physical-" + std::to_string(index);
    value.p256_public_key[0] = 0x04;
    value.p256_public_key[1] = static_cast<std::uint8_t>(index);
    value.radio_mac = {0x14, 0x63, 0x93, 0x00, 0x00, static_cast<std::uint8_t>(index)};
    value.home_id = "home-a";
    value.hub_id = "hub-a";
    value.logical_id = "room-node-" + std::to_string(index);
    value.room = "room-" + std::to_string(index);
    value.function = "motion";
    return value;
}

void capacity_and_isolation() {
    NodeRegistry invalid("home-a", "hub-a", 9, 0);
    require(invalid.capacity() == 0 && invalid.enroll(node(1)) == RegistryResult::InvalidRecord,
            "invalid product configuration did not fail closed");
    NodeRegistry registry("home-a", "hub-a", 10, 16);
    for (unsigned i = 1; i <= 10; ++i)
        require(registry.enroll(node(i)) == RegistryResult::Accepted, "max-1/max enrollment failed");
    require(registry.size() == 10 && registry.capacity() == 10, "registry capacity mismatch");
    require(registry.enroll(node(11)) == RegistryResult::CapacityFull, "max+1 was not rejected");
    require(registry.size() == 10 && !registry.find("physical-11"), "capacity rejection mutated registry");
    for (unsigned i = 1; i <= 10; ++i) {
        const auto found = registry.find("physical-" + std::to_string(i));
        require(found && found->logical_id == "room-node-" + std::to_string(i),
                "per-node assignment was contaminated");
    }
    std::cout << "P2-REG-CAPACITY HOST PASS max-1/max/max+1\n";
}

void identity_rejoin_and_quarantine() {
    NodeRegistry registry("home-a", "hub-a", 10, 16);
    auto first = node(1);
    require(registry.enroll(first) == RegistryResult::Accepted, "initial enrollment failed");
    require(registry.enroll(first) == RegistryResult::AlreadyEnrolled, "idempotent enrollment failed");
    auto reassigned = first; reassigned.room = "unapproved-room";
    require(registry.enroll(reassigned) == RegistryResult::DuplicateLogicalIdentity,
            "duplicate enrollment silently changed room");
    require(registry.find(first.device_id)->room == first.room,
            "rejected assignment changed the existing room");
    auto foreign = node(2); foreign.home_id = "home-b";
    require(registry.enroll(foreign) == RegistryResult::ForeignInstallation, "foreign Home accepted");
    foreign = node(2); foreign.hub_id = "hub-b";
    require(registry.enroll(foreign) == RegistryResult::ForeignInstallation, "foreign Hub accepted");
    auto duplicate_mac = node(2); duplicate_mac.radio_mac = first.radio_mac;
    require(registry.enroll(duplicate_mac) == RegistryResult::DuplicateRadioAddress,
            "duplicate radio address accepted");
    auto duplicate_logical = node(2); duplicate_logical.logical_id = first.logical_id;
    require(registry.enroll(duplicate_logical) == RegistryResult::DuplicateLogicalIdentity,
            "duplicate logical identity accepted");
    require(registry.rejoin("unknown", first.radio_mac, 1) == RegistryResult::UnknownDevice,
            "unknown device rejoined");
    require(registry.rejoin(first.device_id, first.radio_mac, 1) == RegistryResult::Accepted,
            "fresh authenticated rejoin failed");
    require(registry.rejoin(first.device_id, first.radio_mac, 1) == RegistryResult::StaleSession,
            "stale session accepted");
    auto clone = first; clone.radio_mac[5] = 9;
    require(registry.enroll(clone) == RegistryResult::DuplicatePhysicalIdentity,
            "conflicting physical identity accepted");
    require(registry.find(first.device_id)->quarantined, "identity conflict did not quarantine");
    require(registry.rejoin(first.device_id, first.radio_mac, 2) ==
            RegistryResult::DuplicatePhysicalIdentity, "quarantined identity rejoined");
    require(registry.counters().quarantined == 1, "quarantine accounting missing");
    std::cout << "P2-REG-IDENTITY HOST PASS foreign/duplicate/rejoin/quarantine\n";
}

void incomplete_commissioning_retry() {
    NodeRegistry registry("home-a", "hub-a", 10, 10);
    const auto first = node(1);
    require(registry.enroll(first) == RegistryResult::Accepted,
            "initial enrollment failed");
    const auto snapshot = registry.snapshot();
    NodeRegistry restarted("home-a", "hub-a", 10, 10);
    require(restarted.restore(snapshot), "unactivated enrollment did not survive restart");
    require(restarted.can_retry_unactivated(first),
            "exact unactivated identity could not retry after restart");
    for (unsigned index = 2; index <= 10; ++index)
        require(restarted.enroll(node(index)) == RegistryResult::Accepted,
                "capacity setup for retry failed");
    require(restarted.size() == 10 && restarted.can_retry_unactivated(first),
            "full registry blocked exact unactivated retry");
    auto altered = first;
    altered.p256_public_key[1] ^= 1;
    require(!restarted.can_retry_unactivated(altered), "different key could retry");
    altered = first; altered.radio_mac[5] ^= 1;
    require(!restarted.can_retry_unactivated(altered), "different radio source could retry");
    altered = first; altered.room = "other-room";
    require(!restarted.can_retry_unactivated(altered), "assignment change could retry");
    require(restarted.rejoin(first.device_id, first.radio_mac, 1) == RegistryResult::Accepted,
            "first authenticated rejoin failed");
    require(!restarted.can_retry_unactivated(first),
            "activated identity could be recommissioned");
    require(restarted.remove(first.device_id) == RegistryResult::Accepted,
            "remove failed");
    require(!restarted.can_retry_unactivated(first),
            "revoked identity could retry commissioning");
    std::cout << "P2-COM-RETRY HOST PASS unactivated-only exact retry\n";
}

void removal_and_replacement() {
    NodeRegistry registry("home-a", "hub-a", 10, 16);
    for (unsigned i = 1; i <= 10; ++i)
        require(registry.enroll(node(i)) == RegistryResult::Accepted, "full registry setup failed");
    auto replacement = node(11);
    replacement.logical_id = "room-node-3";
    replacement.room = "room-3";
    require(registry.replace("physical-3", replacement) == RegistryResult::Accepted,
            "replacement at capacity failed");
    require(registry.size() == 10 && registry.is_revoked("physical-3"),
            "replacement lost capacity or tombstone");
    require(registry.find("physical-11")->logical_id == "room-node-3",
            "replacement did not inherit logical slot");
    require(registry.rejoin("physical-3", node(3).radio_mac, 7) == RegistryResult::RevokedDevice,
            "replaced device rejoined");
    auto invalid = node(12); invalid.logical_id = "room-node-4"; invalid.room = "wrong-room";
    require(registry.replace("physical-4", invalid) == RegistryResult::DuplicateLogicalIdentity,
            "invalid replacement assignment accepted");
    require(registry.find("physical-4") && !registry.find("physical-12"),
            "failed replacement partially changed registry");
    require(registry.remove("physical-5") == RegistryResult::Accepted, "remove failed");
    require(registry.enroll(node(5)) == RegistryResult::RevokedDevice,
            "removed device was silently re-enrolled");
    require(registry.size() == 9 && registry.tombstone_count() == 2,
            "remove/replacement accounting wrong");
    std::cout << "P2-REG-LIFECYCLE HOST PASS replace/remove/revoke\n";
}

void revocation_capacity_fails_closed() {
    NodeRegistry registry("home-a", "hub-a", 10, 2);
    for (unsigned i = 1; i <= 3; ++i)
        require(registry.enroll(node(i)) == RegistryResult::Accepted,
                "revocation capacity setup failed");
    require(registry.remove("physical-1") == RegistryResult::Accepted &&
            registry.tombstone_count() == 1, "max-1 revocation failed");
    require(registry.remove("physical-2") == RegistryResult::Accepted &&
            registry.tombstone_count() == 2, "max revocation failed");
    require(registry.remove("physical-3") == RegistryResult::RevocationCapacityFull,
            "max+1 removal was not explicitly rejected");
    require(registry.tombstone_count() == 2 && registry.size() == 1 &&
            registry.is_revoked("physical-1") && registry.is_revoked("physical-2"),
            "capacity pressure discarded a prior revocation or changed registry size");
    require(registry.enroll(node(1)) == RegistryResult::RevokedDevice &&
            registry.rejoin("physical-1", node(1).radio_mac, 1) ==
                RegistryResult::RevokedDevice,
            "oldest revoked identity became admissible after capacity pressure");
    require(registry.find("physical-3")->quarantined &&
            registry.rejoin("physical-3", node(3).radio_mac, 1) ==
                RegistryResult::DuplicatePhysicalIdentity,
            "unrecorded removal left the active identity usable");
    require(registry.remove("physical-3") == RegistryResult::RevocationCapacityFull &&
            registry.counters().quarantined == 1,
            "repeated full-store removal changed quarantine state");

    NodeRegistry replacement("home-a", "hub-a", 10, 1);
    require(replacement.enroll(node(4)) == RegistryResult::Accepted &&
            replacement.enroll(node(5)) == RegistryResult::Accepted,
            "replacement capacity setup failed");
    require(replacement.remove("physical-4") == RegistryResult::Accepted,
            "replacement capacity tombstone setup failed");
    auto next = node(6);
    next.logical_id = node(5).logical_id;
    next.room = node(5).room;
    require(replacement.replace("physical-5", next) ==
                RegistryResult::RevocationCapacityFull &&
            replacement.size() == 1 && !replacement.find(next.device_id) &&
            replacement.find("physical-5")->quarantined &&
            replacement.is_revoked("physical-4"),
            "full-store replacement partially enrolled or lost revocation");
    require(replacement.rejoin("physical-5", node(5).radio_mac, 1) ==
                RegistryResult::DuplicatePhysicalIdentity,
            "failed replacement left old physical identity usable");
    std::cout << "P2-REG-REVOCATION HOST PASS max-1/max/max+1 and quarantine\n";
}

void snapshot_restore_is_atomic() {
    NodeRegistry original("home-a", "hub-a", 10, 2);
    for (unsigned i = 1; i <= 3; ++i)
        require(original.enroll(node(i)) == RegistryResult::Accepted,
                "snapshot setup enrollment failed");
    require(original.rejoin("physical-1", node(1).radio_mac, 7) == RegistryResult::Accepted,
            "snapshot session setup failed");
    require(original.remove("physical-2") == RegistryResult::Accepted,
            "snapshot revocation setup failed");
    auto clone = node(3);
    clone.radio_mac[5] = 33;
    require(original.enroll(clone) == RegistryResult::DuplicatePhysicalIdentity,
            "snapshot quarantine setup failed");
    const auto saved = original.snapshot();
    NodeRegistry restored("home-a", "hub-a", 10, 2);
    require(restored.restore(saved) && restored.size() == 2 &&
            restored.is_revoked("physical-2") &&
            restored.find("physical-3")->quarantined &&
            restored.find("physical-1")->last_session == 7,
            "restore lost association security state");
    require(restored.rejoin("physical-1", node(1).radio_mac, 7) ==
                RegistryResult::StaleSession &&
            restored.rejoin("physical-3", node(3).radio_mac, 8) ==
                RegistryResult::DuplicatePhysicalIdentity &&
            restored.enroll(node(2)) == RegistryResult::RevokedDevice,
            "restored registry admitted stale quarantined or revoked Node");
    require(!restored.restore(saved), "live registry accepted a second restore");

    auto corrupt = saved;
    corrupt.active[0].logical_id = corrupt.active[1].logical_id;
    NodeRegistry fresh("home-a", "hub-a", 10, 2);
    require(!fresh.restore(corrupt) && fresh.size() == 0 &&
            fresh.tombstone_count() == 0,
            "invalid snapshot partially changed registry");
    corrupt = saved;
    corrupt.revoked_device_ids.push_back(corrupt.revoked_device_ids.front());
    require(!fresh.restore(corrupt) && fresh.size() == 0,
            "duplicate revoked identity restored");
    corrupt = saved;
    corrupt.home_id = "foreign-home";
    require(!fresh.restore(corrupt) && fresh.size() == 0,
            "foreign Home snapshot restored");
    std::cout << "P2-REG-SNAPSHOT HOST PASS sessions/revocations/quarantine/atomicity\n";
}
}  // namespace

int main() {
    try {
        capacity_and_isolation();
        identity_rejoin_and_quarantine();
        incomplete_commissioning_retry();
        removal_and_replacement();
        revocation_capacity_fails_closed();
        snapshot_restore_is_atomic();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "P2-REGISTRY HOST FAIL " << error.what() << '\n';
        return 1;
    }
}
