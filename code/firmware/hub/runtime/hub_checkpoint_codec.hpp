#pragma once
#include "hub_runtime.hpp"
namespace gs::hub {
class HubCheckpointCodec {
public:
    static bool encode(HubRuntime&, security::Bytes&);
    // Apply the real reducer to a bounded copy, never the live state. Refuse
    // before persistence if the next complete state cannot use the same codec.
    static bool encode_after_event(HubRuntime&, const DomainEvent&,
                                  std::optional<std::uint16_t>,
                                  const CloudAuthorityBinding*, security::Bytes&);
    static bool restore(HubRuntime&, const security::Bytes&);
};
}
