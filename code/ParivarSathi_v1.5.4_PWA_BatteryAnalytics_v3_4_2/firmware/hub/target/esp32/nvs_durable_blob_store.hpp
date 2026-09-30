#pragma once

#include "storage/durable_transition.hpp"

namespace gs::hub::target {

enum class NvsDurableError {
    None, NotFound, Io, CorruptValue, KeyMapping, ImmutableCollision,
    PersistedButApiFailed
};

class NvsDurableBlobStore final : public durable::BlobStore {
public:
    bool initialize();
    bool read(const std::string&, security::Bytes&, bool&) override;
    bool write_immutable(const std::string&, const security::Bytes&) override;
    bool replace(const std::string&, const security::Bytes&) override;
    NvsDurableError last_error() const { return last_error_; }
private:
    bool write(const std::string&, const security::Bytes&, bool immutable);
    bool initialized_{false};
    NvsDurableError last_error_{NvsDurableError::None};
};

}  // namespace gs::hub::target
