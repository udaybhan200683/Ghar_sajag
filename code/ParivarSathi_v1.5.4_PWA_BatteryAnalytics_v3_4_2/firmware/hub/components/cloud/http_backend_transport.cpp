#include "cloud/http_backend_transport.hpp"
#include <cctype>
#include <limits>
#include <string_view>

namespace {
// Strict, bounded, nonrecursive parser for the existing receipt schema only.
// Reject duplicate/unknown members, lossy numbers, invalid escapes and trailing data.
class ReceiptParser {
public:
    explicit ReceiptParser(std::string_view input) : input_(input) {}
    bool receipt(gs::EventKey& key, bool& duplicate) {
        if (!take('{')) return false;
        unsigned seen = 0;
        do {
            std::string name;
            if (!string(name, 32) || !take(':')) return false;
            unsigned bit = 0;
            if (name == "event_key") { bit = 1; if (!event_key(key)) return false; }
            else if (name == "status") {
                bit = 2; std::string status;
                if (!string(status, 16) || status != "COMMITTED") return false;
            } else if (name == "duplicate") { bit = 4; if (!boolean(duplicate)) return false; }
            else return false;
            if (seen & bit) return false;
            seen |= bit;
        } while (take(','));
        return seen == 7 && take('}') && end();
    }
private:
    std::string_view input_;
    std::size_t pos_{0};
    void space() {
        while (pos_ < input_.size() && (input_[pos_] == ' ' || input_[pos_] == '\n' ||
               input_[pos_] == '\r' || input_[pos_] == '\t')) ++pos_;
    }
    bool take(char c) {
        space();
        if (pos_ == input_.size() || input_[pos_] != c) return false;
        ++pos_; return true;
    }
    bool end() { space(); return pos_ == input_.size(); }
    bool boolean(bool& value) {
        space();
        for (auto literal : {std::string_view("true"), std::string_view("false")}) {
            if (input_.substr(pos_, literal.size()) == literal) {
                value = literal == "true"; pos_ += literal.size(); return true;
            }
        }
        return false;
    }
    bool hex4(unsigned& code) {
        code = 0;
        for (unsigned i = 0; i < 4; ++i) {
            if (pos_ == input_.size()) return false;
            const char c = input_[pos_++]; unsigned digit;
            if (c >= '0' && c <= '9') digit = c - '0';
            else if (c >= 'a' && c <= 'f') digit = c - 'a' + 10;
            else if (c >= 'A' && c <= 'F') digit = c - 'A' + 10;
            else return false;
            code = (code << 4) | digit;
        }
        return true;
    }
    bool string(std::string& value, std::size_t maximum) {
        if (!take('"')) return false;
        value.clear();
        while (pos_ < input_.size()) {
            unsigned char c = input_[pos_++];
            if (c == '"') return true;
            if (c < 0x20) return false;
            if (c != '\\') value += static_cast<char>(c);
            else {
                if (pos_ == input_.size()) return false;
                c = input_[pos_++];
                switch (c) {
                    case '"': case '\\': case '/': value += static_cast<char>(c); break;
                    case 'b': value += '\b'; break;
                    case 'f': value += '\f'; break;
                    case 'n': value += '\n'; break;
                    case 'r': value += '\r'; break;
                    case 't': value += '\t'; break;
                    case 'u': {
                        unsigned code;
                        if (!hex4(code)) return false;
                        if (code >= 0xd800 && code <= 0xdbff) {
                            unsigned low;
                            if (pos_ + 2 > input_.size() || input_.substr(pos_, 2) != "\\u") return false;
                            pos_ += 2;
                            if (!hex4(low) || low < 0xdc00 || low > 0xdfff) return false;
                            code = 0x10000 + ((code - 0xd800) << 10) + low - 0xdc00;
                        } else if (code >= 0xdc00 && code <= 0xdfff) return false;
                        if (code < 0x80) value += static_cast<char>(code);
                        else if (code < 0x800) {
                            value += static_cast<char>(0xc0 | (code >> 6));
                            value += static_cast<char>(0x80 | (code & 63));
                        } else if (code < 0x10000) {
                            value += static_cast<char>(0xe0 | (code >> 12));
                            value += static_cast<char>(0x80 | ((code >> 6) & 63));
                            value += static_cast<char>(0x80 | (code & 63));
                        } else {
                            value += static_cast<char>(0xf0 | (code >> 18));
                            value += static_cast<char>(0x80 | ((code >> 12) & 63));
                            value += static_cast<char>(0x80 | ((code >> 6) & 63));
                            value += static_cast<char>(0x80 | (code & 63));
                        }
                        break;
                    }
                    default: return false;
                }
            }
            if (value.size() > maximum) return false;
        }
        return false;
    }
    bool positive(std::uint64_t& value) {
        space(); value = 0;
        if (pos_ == input_.size() || input_[pos_] < '1' || input_[pos_] > '9') return false;
        constexpr auto maximum = static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max());
        while (pos_ < input_.size() && input_[pos_] >= '0' && input_[pos_] <= '9') {
            const unsigned digit = input_[pos_++] - '0';
            if (value > (maximum - digit) / 10) return false;
            value = value * 10 + digit;
        }
        return true;
    }
    bool event_key(gs::EventKey& key) {
        if (!take('{')) return false;
        unsigned seen = 0;
        do {
            std::string name;
            if (!string(name, 32) || !take(':')) return false;
            unsigned bit = 0;
            if (name == "physical_device_id") { bit = 1; if (!string(key.physical_device_id, 64) || key.physical_device_id.empty()) return false; }
            else if (name == "logical_node_id") { bit = 2; if (!string(key.source_id, 24) || key.source_id.empty()) return false; }
            else if (name == "origin_session_id") { bit = 4; if (!positive(key.session_id)) return false; }
            else if (name == "event_sequence") { bit = 8; if (!positive(key.sequence)) return false; }
            else return false;
            if (seen & bit) return false;
            seen |= bit;
        } while (take(','));
        return seen == 15 && take('}');
    }
};
}
namespace gs::hub {
BackendCommitReply HttpBackendTransport::decode(const BackendCommitRequest& request,
                                               const BackendHttpResponse& response) {
    BackendCommitReply reply;
    if (!response.server_authenticated || !response.message_complete ||
        response.body.size() > kMaximumResponseBytes) return reply;
    if (response.status == 401 || response.status == 403) {
        reply.status = BackendReplyStatus::AuthenticationFailure; return reply;
    }
    if (response.status >= 500) { reply.status = BackendReplyStatus::TransientFailure; return reply; }
    if (response.status != 200 && response.status != 201) return reply;
    ReceiptParser parser(response.body);
    if (!parser.receipt(reply.key, reply.duplicate) || reply.key.str() != request.event.key.str()) return {};
    reply.status = BackendReplyStatus::Committed;
    reply.authenticated_backend = true;
    return reply;
}
BackendCommitReply HttpBackendTransport::submit(const BackendCommitRequest& request) {
    if (request.home_id.empty() || request.home_id.size() > 64) return {};
    for (unsigned char c : request.home_id)
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '-' || c == '_')) return {};
    const auto body = request.json_body();
    if (body.empty() || body.size() > kMaximumRequestBytes) return {};
    return decode(request, channel_.post("/v1/homes/" + request.home_id + "/events", body));
}
}
