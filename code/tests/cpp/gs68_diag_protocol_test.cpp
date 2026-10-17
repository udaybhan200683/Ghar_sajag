#include "gs/gs68_diag_protocol.hpp"

#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <thread>

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
    const std::string auxiliary = "{\"schema\":\"gs68.target.command.v1\",\"case_id\":\"GS68-AUX-TIME-001\",\"challenge_nonce\":\"" + nonce + "\",\"operation\":\"TIME_CHALLENGE\"}";
    expect(parse(auxiliary, command) == TargetCommandError::Ok,
           "signed-time diagnostic uses dedicated auxiliary case ID");
    auto unknown_auxiliary = auxiliary;
    unknown_auxiliary.replace(unknown_auxiliary.find("GS68-AUX-TIME-001"), 17,
                             "GS68-AUX-TIME-099");
    expect(parse(unknown_auxiliary, command) == TargetCommandError::InvalidCase,
           "unknown auxiliary IDs remain rejected");

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

    using gs::diagnostic::TargetCommandFrameResult;
    gs::diagnostic::TargetCommandLineAccumulator line_reader;
    std::array<char, gs::diagnostic::kTargetCommandMaxBytes + 1> framed_line{};
    framed_line.fill('!');
    const auto split = valid.size() / 2;
    for (std::size_t i = 0; i < split; ++i) {
        expect(line_reader.push(valid[i], framed_line.data(), framed_line.size()) ==
                   TargetCommandFrameResult::Pending,
               "partial command remains pending");
    }
    expect(framed_line[0] == '!', "partial command is not exposed before its line ending");
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
    for (std::size_t i = split; i < valid.size(); ++i) {
        expect(line_reader.push(valid[i], framed_line.data(), framed_line.size()) ==
                   TargetCommandFrameResult::Pending,
               "delayed command continuation remains buffered");
    }
    expect(line_reader.push('\r', framed_line.data(), framed_line.size()) ==
               TargetCommandFrameResult::Complete,
           "carriage return completes a command");
    expect(std::string(framed_line.data()) == valid, "partial command reassembles exactly");
    expect(line_reader.push('\n', framed_line.data(), framed_line.size()) ==
               TargetCommandFrameResult::Pending,
           "LF in CRLF is suppressed");

    const std::string second = reordered + "\n" + valid + "\r\n";
    unsigned completed = 0;
    for (char byte : second) {
        const auto state = line_reader.push(byte, framed_line.data(), framed_line.size());
        if (state == TargetCommandFrameResult::Complete) ++completed;
        expect(state != TargetCommandFrameResult::Invalid &&
                   state != TargetCommandFrameResult::Oversized,
               "multiple sequential commands stay within the frame limits");
    }
    expect(completed == 2, "LF and CRLF delimit multiple sequential commands");

    const std::string oversized(gs::diagnostic::kTargetCommandMaxBytes + 1, 'x');
    for (char byte : oversized) {
        expect(line_reader.push(byte, framed_line.data(), framed_line.size()) ==
                   TargetCommandFrameResult::Pending,
               "oversized line is drained without a premature frame");
    }
    expect(line_reader.push('\n', framed_line.data(), framed_line.size()) ==
               TargetCommandFrameResult::Oversized,
           "oversized command rejected exactly at line boundary");
    expect(line_reader.push('{', framed_line.data(), framed_line.size()) ==
               TargetCommandFrameResult::Pending,
           "command after oversized line starts cleanly");
    expect(line_reader.push('\n', framed_line.data(), framed_line.size()) ==
               TargetCommandFrameResult::Complete && framed_line[0] == '{',
           "command after oversized line completes");

    expect(line_reader.push('\0', framed_line.data(), framed_line.size()) ==
               TargetCommandFrameResult::Pending,
           "NUL is retained as an invalid-line condition");
    expect(line_reader.push('\n', framed_line.data(), framed_line.size()) ==
               TargetCommandFrameResult::Invalid,
           "NUL-containing line cannot truncate into a valid command");
    for (char byte : valid) {
        expect(line_reader.push(byte, framed_line.data(), framed_line.size()) ==
                   TargetCommandFrameResult::Pending,
               "valid command after invalid line is accepted incrementally");
    }
    expect(line_reader.push('\n', framed_line.data(), framed_line.size()) ==
               TargetCommandFrameResult::Complete && std::string(framed_line.data()) == valid,
           "invalid line does not poison the next command");

    std::printf("GS68_NODE_PROTOCOL_TESTS=%u PASS\n", checks);
    return 0;
}
