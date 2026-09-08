#pragma once

#include "gs/domain.hpp"
#include "storage/journal.hpp"

#include <cstddef>
#include <optional>
#include <vector>

namespace gs::hub {

class CloudSync {
public:
    explicit CloudSync(HubJournal& journal);
    void set_connected(bool connected, Milliseconds now_ms);
    std::vector<DomainEvent> next_batch(Milliseconds now_ms, std::size_t limit = 16);
    bool application_commit_ack(const EventKey& key);
    void record_failure(Milliseconds now_ms);
    bool connected() const { return connected_; }

private:
    HubJournal& journal_;
    bool connected_{false};
    std::size_t failures_{0};
    Milliseconds retry_after_ms_{0};
};

}  // namespace gs::hub
