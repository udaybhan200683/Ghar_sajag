#pragma once

#include <array>
#include <cstdint>

namespace gs::node::target {

inline constexpr char kNodeId[] = "node-1";
inline constexpr char kLocation[] = "room1";
inline constexpr std::array<std::uint8_t, 6> kQualifiedNodeMac{
    0x14, 0x63, 0x93, 0xC5, 0xD1, 0x58};
inline constexpr std::array<std::uint8_t, 6> kQualifiedHubMac{
    0x5C, 0x01, 0x3B, 0xBE, 0xB9, 0xF8};

inline constexpr int kPirGpio = 4;
inline constexpr int kLedGpio = 8;
inline constexpr bool kLedActiveLow = true;
inline constexpr std::uint8_t kEspNowChannel = 1;
inline constexpr std::int8_t kTxPowerQuarterDbm = 40;  // 10 dBm

inline constexpr std::uint32_t kPirStabilizationMs = 10000;
inline constexpr std::uint32_t kPirPollMs = 20;
inline constexpr std::uint32_t kPirDebounceMs = 150;
inline constexpr std::uint32_t kPirMinimumRetriggerMs = 1000;

}  // namespace gs::node::target
