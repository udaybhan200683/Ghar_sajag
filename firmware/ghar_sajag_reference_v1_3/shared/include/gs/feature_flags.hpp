#pragma once

#include <cstddef>

// P0 capabilities are on by default. P1/P2 capabilities stay off until their
// safety, privacy and hardware acceptance gates are passed.
#ifndef GS_FEATURE_MORNING_ROUTINE
#define GS_FEATURE_MORNING_ROUTINE 1
#endif
#ifndef GS_FEATURE_CALL_FAMILY
#define GS_FEATURE_CALL_FAMILY 1
#endif
#ifndef GS_FEATURE_DOOR_HISTORY
#define GS_FEATURE_DOOR_HISTORY 1
#endif
#ifndef GS_FEATURE_DAILY_SUMMARY
#define GS_FEATURE_DAILY_SUMMARY 1
#endif
#ifndef GS_FEATURE_LOCAL_OFFLINE
#define GS_FEATURE_LOCAL_OFFLINE 1
#endif
#ifndef GS_FEATURE_TEMP_CONTEXT
#define GS_FEATURE_TEMP_CONTEXT 0
#endif
#ifndef GS_FEATURE_EXTERNAL_CAMERA
#define GS_FEATURE_EXTERNAL_CAMERA 0
#endif
#ifndef GS_FEATURE_FALL_DETECTION
#define GS_FEATURE_FALL_DETECTION 0
#endif
#ifndef GS_FEATURE_PRO_RESPONSE
#define GS_FEATURE_PRO_RESPONSE 0
#endif

namespace gs {
enum class Feature : std::size_t {
    MorningRoutine, CallFamily, DoorHistory, DailySummary, LocalOffline,
    TemperatureContext, ExternalCamera, FallDetection, ProfessionalResponse, Count
};

struct FeatureFlags {
    static constexpr bool enabled(Feature feature) noexcept {
        switch (feature) {
            case Feature::MorningRoutine: return GS_FEATURE_MORNING_ROUTINE != 0;
            case Feature::CallFamily: return GS_FEATURE_CALL_FAMILY != 0;
            case Feature::DoorHistory: return GS_FEATURE_DOOR_HISTORY != 0;
            case Feature::DailySummary: return GS_FEATURE_DAILY_SUMMARY != 0;
            case Feature::LocalOffline: return GS_FEATURE_LOCAL_OFFLINE != 0;
            case Feature::TemperatureContext: return GS_FEATURE_TEMP_CONTEXT != 0;
            case Feature::ExternalCamera: return GS_FEATURE_EXTERNAL_CAMERA != 0;
            case Feature::FallDetection: return GS_FEATURE_FALL_DETECTION != 0;
            case Feature::ProfessionalResponse: return GS_FEATURE_PRO_RESPONSE != 0;
            case Feature::Count: return false;
        }
        return false;
    }

    static constexpr const char* name(Feature feature) noexcept {
        switch (feature) {
            case Feature::MorningRoutine: return "morning_routine";
            case Feature::CallFamily: return "call_family";
            case Feature::DoorHistory: return "door_history";
            case Feature::DailySummary: return "daily_summary";
            case Feature::LocalOffline: return "local_offline";
            case Feature::TemperatureContext: return "temperature_context";
            case Feature::ExternalCamera: return "external_camera";
            case Feature::FallDetection: return "fall_detection";
            case Feature::ProfessionalResponse: return "professional_response";
            case Feature::Count: return "count";
        }
        return "unknown";
    }
};
}  // namespace gs
