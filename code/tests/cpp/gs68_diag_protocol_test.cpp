#include "gs/gs68_diag_protocol.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>

namespace {
unsigned checks = 0;

void expect(bool condition, const char* label) {
    ++checks;
    if (!condition) {
        std::fprintf(stderr, "FAIL %s\n", label);
        std::exit(1);
    }
}

gs::diagnostic::TargetCommandError parse(const std::string& value,
                                         gs::diagnostic::TargetCommand& command) {
    return gs::diagnostic::parse_target_command(value.data(), value.size(), command);
}
}  // namespace

int main() {
    using gs::diagnostic::TargetCommand;
    using gs::diagnostic::TargetCommandError;
    TargetCommand command{};
    const std::string nonce(64, 'a');
    const std::string valid = "{\"schema\":\"gs68.target.command.v1\",\"case_id\":\"GS68-PHY-006\",\"challenge_nonce\":\"" + nonce + "\",\"operation\":\"OBSERVE\"}";
    expect(parse(valid, command) == TargetCommandError::Ok, "valid command");
    expect(std::string(command.case_id) == "GS68-PHY-006" &&
           std::string(command.operation) == "OBSERVE" &&
           std::string(command.challenge_nonce) == nonce, "parsed fields");

    const std::string reordered = "{ \"operation\":\"PING\", \"challenge_nonce\":\"" + nonce + "\", \"schema\":\"gs68.target.command.v1\", \"case_id\":\"GS68-PHY-010\" }";
    expect(parse(reordered, command) == TargetCommandError::Ok, "field order independent");
    expect(std::string(command.case_id) == "GS68-PHY-010", "reordered case id");
    auto s3_case = valid;
    s3_case.replace(s3_case.find("OBSERVE"), 7, "RUN_CASE");
    expect(parse(s3_case, command) == TargetCommandError::Ok,
           "existing S3 runner command remains supported");

    expect(parse("{}", command) == TargetCommandError::Malformed, "missing fields");
    const auto duplicate = "{\"schema\":\"gs68.target.command.v1\",\"schema\":\"gs68.target.command.v1\",\"case_id\":\"GS68-PHY-006\",\"challenge_nonce\":\"" + nonce + "\",\"operation\":\"OBSERVE\"}";
    const auto duplicate_result = parse(duplicate, command);
    expect(duplicate_result == TargetCommandError::DuplicateField ||
           duplicate_result == TargetCommandError::Malformed, "duplicate field rejected");
    const auto extra = "{\"schema\":\"gs68.target.command.v1\",\"case_id\":\"GS68-PHY-006\",\"challenge_nonce\":\"" + nonce + "\",\"operation\":\"OBSERVE\",\"extra\":\"x\"}";
    expect(parse(extra, command) != TargetCommandError::Ok, "extra field rejected");
    expect(parse(valid + std::string(512, 'x'), command) == TargetCommandError::Oversized,
           "oversized command rejected");
    auto bad_case = valid;
    bad_case.replace(bad_case.find("GS68-PHY-006"), 12, "GS68-PHY-099");
    expect(parse(bad_case, command) == TargetCommandError::InvalidCase, "unknown case rejected");
    auto bad_nonce = valid;
    bad_nonce.replace(bad_nonce.find(nonce), nonce.size(), std::string(63, 'a'));
    expect(parse(bad_nonce, command) == TargetCommandError::InvalidNonce, "short nonce rejected");
    auto uppercase_nonce = valid;
    uppercase_nonce.replace(uppercase_nonce.find(nonce), nonce.size(), std::string(64, 'A'));
    expect(parse(uppercase_nonce, command) == TargetCommandError::InvalidNonce, "noncanonical nonce rejected");
    auto unsupported_operation = valid;
    unsupported_operation.replace(unsupported_operation.find("OBSERVE"), 7, "RESET");
    expect(parse(unsupported_operation, command) == TargetCommandError::InvalidOperation,
           "unsupported command rejected");
    auto escaped = valid;
    escaped.replace(escaped.find("OBSERVE"), 7, "OBS\\u0045RVE");
    expect(parse(escaped, command) == TargetCommandError::Malformed, "escaped string rejected");
    expect(!gs::diagnostic::target_case_id_valid("GS68-PHY-000"), "zero case rejected");
    expect(!gs::diagnostic::target_case_id_valid("GS68-PHY-011"), "unknown high case rejected");

    std::printf("GS68_NODE_PROTOCOL_TESTS=%u PASS\n", checks);
    return 0;
}
