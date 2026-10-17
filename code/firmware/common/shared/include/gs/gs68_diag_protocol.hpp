#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace gs::diagnostic {

constexpr std::size_t kTargetCommandMaxBytes = 1024;
constexpr std::size_t kTargetCaseIdCapacity = 16;
constexpr std::size_t kTargetNonceCapacity = 65;
constexpr std::size_t kTargetOperationCapacity = 24;
constexpr std::size_t kTargetPayloadBase64Capacity = 769;

enum class TargetCommandFrameResult : std::uint8_t {
    Pending,
    Complete,
    Invalid,
    Oversized,
};

// Incremental, bounded stdin framing for the isolated target diagnostic.
// A caller can feed bytes as they arrive; incomplete input remains buffered.
// CR, LF, and CRLF are accepted without treating the LF in a CRLF pair as a
// second empty command. Oversized or NUL-containing lines are drained to their
// delimiter and reported once, so the next command starts at a clean boundary.
class TargetCommandLineAccumulator {
public:
    TargetCommandFrameResult push(char byte, char* output,
                                  std::size_t output_capacity) {
        if (suppress_lf_after_cr_) {
            suppress_lf_after_cr_ = false;
            if (byte == '\n') return TargetCommandFrameResult::Pending;
        }

        if (byte == '\r' || byte == '\n') {
            const bool was_cr = byte == '\r';
            TargetCommandFrameResult result = TargetCommandFrameResult::Complete;
            if (oversized_) {
                result = TargetCommandFrameResult::Oversized;
            } else if (invalid_) {
                result = TargetCommandFrameResult::Invalid;
            } else if (output == nullptr || output_capacity <= size_) {
                result = TargetCommandFrameResult::Invalid;
            } else {
                std::memcpy(output, bytes_, size_);
                output[size_] = '\0';
            }
            reset_line();
            suppress_lf_after_cr_ = was_cr;
            return result;
        }

        if (oversized_) return TargetCommandFrameResult::Pending;
        if (byte == '\0') {
            invalid_ = true;
            return TargetCommandFrameResult::Pending;
        }
        if (size_ == sizeof(bytes_)) {
            oversized_ = true;
            return TargetCommandFrameResult::Pending;
        }
        bytes_[size_++] = byte;
        return TargetCommandFrameResult::Pending;
    }

private:
    void reset_line() {
        std::memset(bytes_, 0, sizeof(bytes_));
        size_ = 0;
        invalid_ = false;
        oversized_ = false;
    }

    char bytes_[kTargetCommandMaxBytes]{};
    std::size_t size_ = 0;
    bool invalid_ = false;
    bool oversized_ = false;
    bool suppress_lf_after_cr_ = false;
};

enum class TargetCommandError : std::uint8_t {
    Ok,
    Oversized,
    Malformed,
    UnknownField,
    DuplicateField,
    InvalidSchema,
    InvalidCase,
    InvalidNonce,
    InvalidOperation,
};

struct TargetCommand {
    char case_id[kTargetCaseIdCapacity]{};
    char challenge_nonce[kTargetNonceCapacity]{};
    char operation[kTargetOperationCapacity]{};
    char payload_base64[kTargetPayloadBase64Capacity]{};
};

inline bool target_case_id_valid(const char* value) {
    if (value == nullptr || std::strlen(value) != 12 ||
        std::strncmp(value, "GS68-PHY-", 9) != 0) return false;
    return (value[9] == '0' && value[10] == '0' &&
            value[11] >= '1' && value[11] <= '9') ||
           (value[9] == '0' && value[10] == '1' && value[11] == '0');
}

inline bool target_nonce_valid(const char* value) {
    if (value == nullptr || std::strlen(value) != 64) return false;
    for (std::size_t i = 0; i < 64; ++i) {
        const char ch = value[i];
        if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'))) return false;
    }
    return true;
}

namespace detail {
inline const char* skip_target_space(const char* cursor, const char* end) {
    while (cursor < end && (*cursor == ' ' || *cursor == '\t' ||
           *cursor == '\r' || *cursor == '\n')) ++cursor;
    return cursor;
}

inline bool parse_target_ascii_string(const char*& cursor, const char* end,
                                      char* output, std::size_t capacity) {
    if (cursor >= end || *cursor != '"' || capacity == 0) return false;
    ++cursor;
    std::size_t size = 0;
    while (cursor < end && *cursor != '"') {
        const auto ch = static_cast<unsigned char>(*cursor++);
        // Deliberately accept only printable, unescaped ASCII. This keeps the
        // command grammar bounded and avoids alternate JSON interpretations.
        if (ch < 0x21 || ch > 0x7e || ch == '\\' || size + 1 >= capacity) return false;
        output[size++] = static_cast<char>(ch);
    }
    if (cursor >= end || *cursor != '"') return false;
    ++cursor;
    output[size] = '\0';
    return true;
}
}  // namespace detail

inline TargetCommandError parse_target_command(const char* bytes, std::size_t size,
                                               TargetCommand& output) {
    output = {};
    if (bytes == nullptr || size == 0) return TargetCommandError::Malformed;
    if (size > kTargetCommandMaxBytes) return TargetCommandError::Oversized;
    const char* cursor = bytes;
    const char* end = bytes + size;
    cursor = detail::skip_target_space(cursor, end);
    if (cursor >= end || *cursor++ != '{') return TargetCommandError::Malformed;

    bool schema_seen = false;
    bool case_seen = false;
    bool nonce_seen = false;
    bool operation_seen = false;
    bool payload_seen = false;
    bool closed = false;
    unsigned field_count = 0;
    while (field_count < 5) {
        cursor = detail::skip_target_space(cursor, end);
        char key[32]{};
        char value[kTargetPayloadBase64Capacity]{};
        if (!detail::parse_target_ascii_string(cursor, end, key, sizeof(key)))
            return TargetCommandError::Malformed;
        cursor = detail::skip_target_space(cursor, end);
        if (cursor >= end || *cursor++ != ':') return TargetCommandError::Malformed;
        cursor = detail::skip_target_space(cursor, end);
        if (!detail::parse_target_ascii_string(cursor, end, value, sizeof(value)))
            return TargetCommandError::Malformed;

        if (std::strcmp(key, "schema") == 0) {
            if (schema_seen) return TargetCommandError::DuplicateField;
            schema_seen = true;
            if (std::strcmp(value, "gs68.target.command.v1") != 0)
                return TargetCommandError::InvalidSchema;
        } else if (std::strcmp(key, "case_id") == 0) {
            if (case_seen) return TargetCommandError::DuplicateField;
            case_seen = true;
            if (std::strlen(value) >= sizeof(output.case_id)) return TargetCommandError::InvalidCase;
            std::memcpy(output.case_id, value, std::strlen(value) + 1);
        } else if (std::strcmp(key, "challenge_nonce") == 0) {
            if (nonce_seen) return TargetCommandError::DuplicateField;
            nonce_seen = true;
            if (std::strlen(value) >= sizeof(output.challenge_nonce)) return TargetCommandError::InvalidNonce;
            std::memcpy(output.challenge_nonce, value, std::strlen(value) + 1);
        } else if (std::strcmp(key, "operation") == 0) {
            if (operation_seen) return TargetCommandError::DuplicateField;
            operation_seen = true;
            if (std::strlen(value) >= sizeof(output.operation)) return TargetCommandError::InvalidOperation;
            std::memcpy(output.operation, value, std::strlen(value) + 1);
        } else if (std::strcmp(key, "payload_b64") == 0) {
            if (payload_seen) return TargetCommandError::DuplicateField;
            payload_seen = true;
            if (value[0] == '\0') return TargetCommandError::Malformed;
            std::memcpy(output.payload_base64, value, std::strlen(value) + 1);
        } else {
            return TargetCommandError::UnknownField;
        }
        ++field_count;
        cursor = detail::skip_target_space(cursor, end);
        if (cursor >= end) return TargetCommandError::Malformed;
        if (*cursor == '}') {
            ++cursor;
            closed = true;
            break;
        }
        if (*cursor++ != ',') return TargetCommandError::Malformed;
    }
    cursor = detail::skip_target_space(cursor, end);
    if (!closed || cursor != end || !schema_seen || !case_seen || !nonce_seen || !operation_seen)
        return TargetCommandError::Malformed;
    if (!target_case_id_valid(output.case_id)) return TargetCommandError::InvalidCase;
    if (!target_nonce_valid(output.challenge_nonce)) return TargetCommandError::InvalidNonce;
    if (std::strcmp(output.operation, "PING") != 0 &&
        std::strcmp(output.operation, "OBSERVE") != 0 &&
        std::strcmp(output.operation, "RUN_CASE") != 0 &&
        std::strcmp(output.operation, "LOAD_TIME_KEY") != 0 &&
        std::strcmp(output.operation, "TIME_CHALLENGE") != 0 &&
        std::strcmp(output.operation, "TIME_PROOF") != 0)
        return TargetCommandError::InvalidOperation;
    const bool time_payload_operation =
        std::strcmp(output.operation, "LOAD_TIME_KEY") == 0 ||
        std::strcmp(output.operation, "TIME_PROOF") == 0;
    const bool time_operation = time_payload_operation ||
        std::strcmp(output.operation, "TIME_CHALLENGE") == 0;
    if (time_payload_operation != payload_seen || (payload_seen && !time_operation))
        return TargetCommandError::Malformed;
    return TargetCommandError::Ok;
}

enum class DiagnosticPreflightDisposition : std::uint8_t { Blocked, Fail };

// The expected test-only identity rejection occurs before transport setup.
// Any response metadata, body, or attempted request is an unexpected result
// and must never be recorded as BLOCKED.
inline DiagnosticPreflightDisposition classify_missing_identity_response(
    unsigned status, bool server_authenticated, bool message_complete,
    std::size_t body_size, bool request_attempted) {
    return status == 0 && !server_authenticated && !message_complete &&
                   body_size == 0 && !request_attempted
        ? DiagnosticPreflightDisposition::Blocked
        : DiagnosticPreflightDisposition::Fail;
}

}  // namespace gs::diagnostic
