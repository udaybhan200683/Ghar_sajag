#pragma once

#include "gs/domain.hpp"

#include <cstdint>

namespace gs::node::target::gs68 {

void start_node_observer();
void publish_runtime_state(const char* node_id, const char* hub_id,
                          const char* physical_device_id,
                          std::uint64_t boot_generation,
                          std::uint32_t reset_reason,
                          bool hub_authenticated, bool hub_outage,
                          std::uint32_t retained_count,
                          std::uint32_t pending_count,
                          std::uint32_t retry_count,
                          const gs::EventKey* oldest_pending_key);
void publish_event_admitted(const gs::EventKey& key,
                            const char* physical_device_id);
void publish_transmission_attempt(const gs::EventKey& key,
                                  const char* physical_device_id);
void publish_hub_ack(const gs::EventKey& key, const char* physical_device_id,
                     gs::AckClass ack_class, bool authenticated,
                     bool matched_pending, bool retired, bool durable);

}  // namespace gs::node::target::gs68
