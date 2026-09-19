#pragma once

#include <array>
#include <cstdint>

namespace gs::hub::target {

inline constexpr char kAuthorizedNodeId[] = "node-1";
inline constexpr std::array<std::uint8_t, 6> kQualifiedHubMac{
    0x5C, 0x01, 0x3B, 0xBE, 0xB9, 0xF8};
inline constexpr std::array<std::uint8_t, 6> kQualifiedNodeMac{
    0x14, 0x63, 0x93, 0xC5, 0xD1, 0x58};
inline constexpr std::uint8_t kEspNowChannel = 1;

}  // namespace gs::hub::target
