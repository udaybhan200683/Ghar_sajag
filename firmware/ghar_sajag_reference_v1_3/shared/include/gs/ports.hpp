#pragma once

#include "gs/domain.hpp"

#include <optional>
#include <string>
#include <vector>

namespace gs {

class SensorInput {
public:
    virtual ~SensorInput() = default;
    virtual bool read_level() const = 0;
};

class RadioTransport {
public:
    virtual ~RadioTransport() = default;
    virtual bool send(const DomainEvent& event) = 0;
};

class EventStore {
public:
    virtual ~EventStore() = default;
    virtual bool append(const DomainEvent& event) = 0;
    virtual bool contains(const EventKey& key) const = 0;
};

class Clock {
public:
    virtual ~Clock() = default;
    virtual EpochSeconds wall_time() const = 0;
    virtual Milliseconds monotonic_ms() const = 0;
};

class ResidentOutput {
public:
    virtual ~ResidentOutput() = default;
    virtual void show(const std::string& code, const std::string& detail) = 0;
};

class SignatureVerifier {
public:
    virtual ~SignatureVerifier() = default;
    virtual bool verify(const std::string& signed_payload, const std::string& signature) const = 0;
};

}  // namespace gs
