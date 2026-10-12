#pragma once
#include "hub_runtime.hpp"
namespace gs::hub {
class HubCheckpointCodec {
public:
    static bool encode(HubRuntime&, security::Bytes&);
    static bool restore(HubRuntime&, const security::Bytes&);
};
}
