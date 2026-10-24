#pragma once

#include <cstdint>

namespace gs::node::target {

enum class Gs117ReassociationStatus : std::uint8_t {
    Ready,
    NotRejoining,
    BindingUnavailable,
    AlreadyBoundToTarget,
    HomeMismatch,
    InvalidTargetHub,
    RecoveryCorrupt,
    RecoveryIoError,
    RecoveryStateUnavailable,
    RecoverySnapshotReadFailed,
    RecoveryBackupConflict,
    RecoveryBackupWriteFailed,
    RecoveryBackupVerifyFailed,
    AssociationBackupFailed,
    InstallerCodeUnavailable,
    CommissioningWindowFailed,
};

constexpr const char* gs117_reassociation_status_name(
        Gs117ReassociationStatus status) {
    switch (status) {
        case Gs117ReassociationStatus::Ready: return "ready";
        case Gs117ReassociationStatus::NotRejoining: return "not_rejoining";
        case Gs117ReassociationStatus::BindingUnavailable: return "binding_unavailable";
        case Gs117ReassociationStatus::AlreadyBoundToTarget: return "already_bound_to_target";
        case Gs117ReassociationStatus::HomeMismatch: return "home_mismatch";
        case Gs117ReassociationStatus::InvalidTargetHub: return "invalid_target_hub";
        case Gs117ReassociationStatus::RecoveryCorrupt: return "recovery_corrupt";
        case Gs117ReassociationStatus::RecoveryIoError: return "recovery_io_error";
        case Gs117ReassociationStatus::RecoveryStateUnavailable: return "recovery_state_unavailable";
        case Gs117ReassociationStatus::RecoverySnapshotReadFailed: return "recovery_snapshot_read_failed";
        case Gs117ReassociationStatus::RecoveryBackupConflict: return "recovery_backup_conflict";
        case Gs117ReassociationStatus::RecoveryBackupWriteFailed: return "recovery_backup_write_failed";
        case Gs117ReassociationStatus::RecoveryBackupVerifyFailed: return "recovery_backup_verify_failed";
        case Gs117ReassociationStatus::AssociationBackupFailed: return "association_backup_failed";
        case Gs117ReassociationStatus::InstallerCodeUnavailable: return "installer_code_unavailable";
        case Gs117ReassociationStatus::CommissioningWindowFailed: return "commissioning_window_failed";
    }
    return "unknown";
}

constexpr Gs117ReassociationStatus gs117_reassociation_preflight(
        bool rejoining, bool binding_available, bool target_hub_valid,
        bool already_bound_to_target, bool home_matches) {
    if (!rejoining) return Gs117ReassociationStatus::NotRejoining;
    if (!binding_available) return Gs117ReassociationStatus::BindingUnavailable;
    if (!target_hub_valid) return Gs117ReassociationStatus::InvalidTargetHub;
    if (already_bound_to_target) return Gs117ReassociationStatus::AlreadyBoundToTarget;
    if (!home_matches) return Gs117ReassociationStatus::HomeMismatch;
    return Gs117ReassociationStatus::Ready;
}

}  // namespace gs::node::target
