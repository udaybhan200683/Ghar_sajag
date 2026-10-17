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
    expect(parse(valid + std::string(1024, 'x'), command) == TargetCommandError::Oversized,
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
    const std::string test_key_payload(560, 'A');
    const std::string key_command = "{\"schema\":\"gs68.target.command.v1\",\"case_id\":\"GS68-PHY-001\",\"challenge_nonce\":\"" + nonce +
        "\",\"operation\":\"LOAD_TIME_KEY\",\"payload_b64\":\"" + test_key_payload + "\"}";
    expect(parse(key_command, command) == TargetCommandError::Ok,
           "bounded TEST_ONLY public verification key command accepted");
    expect(std::string(command.payload_base64) == test_key_payload,
           "bounded base64 payload retained");
    const std::string proof_payload(608, 'A');
    const std::string proof_command = "{\"schema\":\"gs68.target.command.v1\",\"case_id\":\"GS68-PHY-001\",\"challenge_nonce\":\"" + nonce +
        "\",\"operation\":\"TIME_PROOF\",\"payload_b64\":\"" + proof_payload + "\"}";
    expect(parse(proof_command, command) == TargetCommandError::Ok,
           "456-byte signed-time proof command fits bounded frame");
    auto challenge_command = valid;
    challenge_command.replace(challenge_command.find("OBSERVE"), 7, "TIME_CHALLENGE");
    expect(parse(challenge_command, command) == TargetCommandError::Ok,
           "authenticated-time challenge command accepted");
    const std::string missing_payload = "{\"schema\":\"gs68.target.command.v1\",\"case_id\":\"GS68-PHY-001\",\"challenge_nonce\":\"" + nonce + "\",\"operation\":\"TIME_PROOF\"}";
    expect(parse(missing_payload, command) != TargetCommandError::Ok,
           "signed-time proof without payload rejected");
    const std::string extra_payload = "{\"schema\":\"gs68.target.command.v1\",\"case_id\":\"GS68-PHY-001\",\"challenge_nonce\":\"" + nonce + "\",\"operation\":\"RUN_CASE\",\"payload_b64\":\"QQ==\"}";
    expect(parse(extra_payload, command) != TargetCommandError::Ok,
           "payload not accepted on non-time operation");
    const std::string too_large_payload(769, 'A');
    const std::string oversized_payload = "{\"schema\":\"gs68.target.command.v1\",\"case_id\":\"GS68-PHY-001\",\"challenge_nonce\":\"" + nonce +
        "\",\"operation\":\"TIME_PROOF\",\"payload_b64\":\"" + too_large_payload + "\"}";
    expect(parse(oversized_payload, command) != TargetCommandError::Ok,
           "oversized signed-time payload rejected");
    using gs::diagnostic::DiagnosticPreflightDisposition;
    expect(gs::diagnostic::classify_missing_identity_response(0, false, false, 0, false) ==
               DiagnosticPreflightDisposition::Blocked,
           "empty pre-network identity rejection is BLOCKED");
    expect(gs::diagnostic::classify_missing_identity_response(200, true, true, 2, true) ==
               DiagnosticPreflightDisposition::Fail,
           "unexpected successful response is FAIL");
    expect(gs::diagnostic::classify_missing_identity_response(0, false, false, 0, true) ==
               DiagnosticPreflightDisposition::Fail,
           "network attempt is FAIL, not BLOCKED");
    expect(gs::diagnostic::classify_missing_identity_response(0, true, false, 0, false) ==
               DiagnosticPreflightDisposition::Fail,
           "unexpected authentication state is FAIL");
    expect(!gs::diagnostic::target_case_id_valid("GS68-PHY-000"), "zero case rejected");
    expect(!gs::diagnostic::target_case_id_valid("GS68-PHY-011"), "unknown high case rejected");

    std::printf("GS68_NODE_PROTOCOL_TESTS=%u PASS\n", checks);
    return 0;
}
