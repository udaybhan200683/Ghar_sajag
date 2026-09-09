// Ghar Sajag traceability edition 2.0 | source release 1.4.2
// @module S01 Shared contracts
// @requirements F01, E02, E06, E07, NFR-08
// Requirement links identify design responsibility, not completed acceptance coverage.
// See docs/progress/Requirement_Traceability.csv and the v2.0 LLD for boundaries.
// Contracts are the shared vocabulary across languages. Field names and event identity require explicit
// adapters; the C++ enum spelling is not the JSON wire spelling. The current contracts check validates
// source structure, so add producer/consumer golden payload tests before relying on schema compatibility.

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
    // @requirements F01, E02, E06, E07, NFR-08
    // Retain a business event before sending it and surface capacity exhaustion instead of silently
    // dropping evidence.
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
