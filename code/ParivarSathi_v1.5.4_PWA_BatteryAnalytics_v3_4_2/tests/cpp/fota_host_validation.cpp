#include "firmware/node/fota/boot_health_gate.hpp"
#include "firmware/node/fota/fota_receiver.hpp"
#include "firmware/node/runtime/node_runtime.hpp"

#include <algorithm>
#include <cstdint>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

using gs::fota::MessageType;
using gs::fota::Packet;
using gs::fota::Status;
using gs::node::fota_receiver::IReceiverCallbacks;
using gs::node::fota_receiver::IOtaWriter;
using gs::node::fota_receiver::Receiver;

template <typename T>
void require(const T& value, const std::string& message) {
    if (!static_cast<bool>(value)) throw std::runtime_error(message);
}

struct FakeWriter final : IOtaWriter {
    std::size_t available{4096};
    bool begin_ok{true};
    bool write_ok{true};
    bool finalize_ok{true};
    bool commit_ok{true};
    int begin_calls{0};
    int write_calls{0};
    int finalize_calls{0};
    int commit_calls{0};
    int abort_calls{0};
    std::vector<std::uint8_t> bytes;

    std::size_t capacity() override { return available; }
    bool begin(std::size_t) override { ++begin_calls; return begin_ok; }
    bool write(const std::uint8_t* data, std::size_t size) override {
        ++write_calls;
        if (!write_ok) return false;
        bytes.insert(bytes.end(), data, data + size);
        return true;
    }
    bool finalize() override { ++finalize_calls; return finalize_ok; }
    bool commit_boot() override { ++commit_calls; return commit_ok; }
    void abort() override { ++abort_calls; }
};

struct FakeCallbacks final : IReceiverCallbacks {
    std::vector<gs::fota::Ack> acks;
    std::vector<bool> maintenance_changes;
    bool maintenance{false};
    int timeouts{0};
    int restarts{0};

    void send_ack(const gs::fota::Ack& ack) override { acks.push_back(ack); }
    void set_maintenance(bool active) override {
        maintenance = active;
        maintenance_changes.push_back(active);
    }
    void report_timeout() override { ++timeouts; }
    void request_restart() override { ++restarts; }
    Status last_status() const {
        require(!acks.empty(), "expected FOTA ACK");
        return static_cast<Status>(acks.back().status);
    }
    bool saw(Status status) const {
        return std::any_of(acks.begin(), acks.end(), [status](const auto& ack) {
            return ack.status == static_cast<std::int32_t>(status);
        });
    }
};

struct Fixture {
    FakeWriter writer;
    FakeCallbacks callbacks;
    Receiver receiver{writer, callbacks};
    std::uint64_t now{100};
    std::uint32_t image_size{0};
    std::uint32_t image_crc32{0};

    void send(const Packet& packet) {
        if (packet.type == static_cast<std::uint8_t>(MessageType::Begin) &&
            image_size == 0) {
            image_size = packet.image_size;
            image_crc32 = packet.image_crc32;
        }
        require(receiver.process(packet, now), "packet ignored");
    }
};

Packet base(MessageType type, std::uint32_t session = 17) {
    Packet packet{};
    packet.magic = gs::fota::kMagic;
    packet.protocol_version = gs::fota::kProtocolVersion;
    packet.type = static_cast<std::uint8_t>(type);
    packet.session_id = session;
    return packet;
}

Packet begin_packet(const std::vector<std::uint8_t>& image, std::uint32_t session = 17) {
    auto packet = base(MessageType::Begin, session);
    packet.image_size = static_cast<std::uint32_t>(image.size());
    packet.image_crc32 = gs::fota::crc32(image.data(), image.size());
    return packet;
}

Packet data_packet(const std::vector<std::uint8_t>& image, std::size_t offset,
                   std::size_t size, std::uint32_t sequence,
                   std::uint32_t session = 17) {
    auto packet = base(MessageType::Data, session);
    packet.sequence = sequence;
    packet.image_size = static_cast<std::uint32_t>(image.size());
    packet.image_crc32 = gs::fota::crc32(image.data(), image.size());
    packet.payload_length = static_cast<std::uint16_t>(size);
    std::copy_n(image.data() + offset, size, packet.payload);
    packet.payload_crc32 = gs::fota::crc32(packet.payload, size);
    return packet;
}

void transfer(Fixture& fixture, const std::vector<std::uint8_t>& image) {
    fixture.send(begin_packet(image));
    std::size_t offset = 0;
    std::uint32_t sequence = 0;
    while (offset < image.size()) {
        const std::size_t size = std::min(gs::fota::kChunkBytes, image.size() - offset);
        fixture.send(data_packet(image, offset, size, sequence++));
        offset += size;
    }
}

void finish(Fixture& fixture, std::uint32_t sequence = 0) {
    auto packet = base(MessageType::End);
    packet.sequence = sequence;
    packet.image_size = fixture.image_size;
    packet.image_crc32 = fixture.image_crc32;
    fixture.send(packet);
}

std::vector<std::uint8_t> image(std::size_t size = 401) {
    std::vector<std::uint8_t> bytes(size);
    for (std::size_t i = 0; i < size; ++i) bytes[i] = static_cast<std::uint8_t>((i * 29U) & 0xFFU);
    return bytes;
}

struct TestCase { const char* id; std::function<void()> body; };

std::vector<TestCase> catalog() {
    return {
        {"FOTA-HOST-001", [] { Fixture f; const auto bytes=image(); f.send(begin_packet(bytes));
            require(f.receiver.snapshot().active && f.callbacks.maintenance, "valid begin did not enter maintenance");
            require(f.writer.begin_calls==1 && f.callbacks.last_status()==Status::Ready, "valid begin ACK/writer mismatch"); }},
        {"FOTA-HOST-002", [] { Fixture f; const auto bytes=image(); f.send(begin_packet(bytes));
            f.send(data_packet(bytes,0,200,0)); f.send(data_packet(bytes,200,200,1));
            const auto s=f.receiver.snapshot(); require(s.bytes_written==400 && s.expected_sequence==2, "chunk progression wrong");
            require(f.writer.bytes.size()==400 && f.callbacks.last_status()==Status::DataOk, "writer/data ACK mismatch"); }},
        {"FOTA-HOST-003", [] { Fixture f; const auto bytes=image(8); transfer(f,bytes); finish(f,1);
            require(f.writer.finalize_calls==1 && f.writer.commit_calls==1 && f.callbacks.restarts==1, "finalization/restart not requested");
            require(f.callbacks.last_status()==Status::Complete && f.receiver.snapshot().completion_requested, "completion state missing"); }},
        {"FOTA-HOST-004", [] { Fixture f; const auto bytes=image(); f.send(begin_packet(bytes)); f.send(base(MessageType::Abort));
            require(!f.receiver.snapshot().active && !f.callbacks.maintenance && f.writer.abort_calls==1, "explicit abort did not recover"); }},
        {"FOTA-HOST-005", [] { Fixture f; const auto bytes=image(); f.send(begin_packet(bytes)); f.send(data_packet(bytes,0,20,0,99));
            require(f.callbacks.last_status()==Status::BadSession && f.receiver.snapshot().bytes_written==0, "wrong session changed transfer"); }},
        {"FOTA-HOST-006", [] { Fixture f; const auto bytes=image(); f.send(begin_packet(bytes)); f.send(data_packet(bytes,0,20,2));
            require(f.callbacks.last_status()==Status::BadSequence && f.writer.write_calls==0, "wrong sequence written"); }},
        {"FOTA-HOST-007", [] { Fixture f; const auto bytes=image(); f.send(begin_packet(bytes)); auto first=data_packet(bytes,0,20,0); f.send(first); f.send(first);
            require(f.callbacks.last_status()==Status::Duplicate && f.writer.write_calls==1, "duplicate chunk rewritten");
            f.send(data_packet(bytes,40,20,2)); require(f.callbacks.last_status()==Status::BadSequence, "out-of-order chunk accepted"); }},
        {"FOTA-HOST-008", [] { Fixture f; const auto bytes=image(); f.send(begin_packet(bytes)); auto packet=data_packet(bytes,0,20,0); packet.payload_crc32^=1U; f.send(packet);
            require(f.callbacks.last_status()==Status::BadCrc && f.writer.write_calls==0 && f.receiver.snapshot().active, "chunk CRC semantics changed"); }},
        {"FOTA-HOST-009", [] { Fixture f; const auto bytes=image(20); auto begin=begin_packet(bytes); begin.image_crc32^=1U; f.send(begin); auto data=data_packet(bytes,0,20,0); data.image_crc32=begin.image_crc32; f.send(data); finish(f,1);
            require(f.callbacks.last_status()==Status::BadCrc && f.writer.abort_calls==1 && !f.callbacks.maintenance, "image CRC failure did not abort"); }},
        {"FOTA-HOST-010", [] { Fixture f; const auto bytes=image(20); auto zero=begin_packet(bytes); zero.image_size=0; f.send(zero); require(f.callbacks.last_status()==Status::BadSize, "zero image accepted");
            f.writer.available=10; f.send(begin_packet(bytes)); require(f.callbacks.last_status()==Status::BadSize, "oversize image accepted");
            f.writer.available=4096; f.send(begin_packet(bytes)); auto empty=data_packet(bytes,0,1,0); empty.payload_length=0; f.send(empty); require(f.callbacks.last_status()==Status::BadSize, "empty chunk accepted"); }},
        {"FOTA-HOST-011", [] { Fixture f; const auto bytes=image(); f.send(begin_packet(bytes)); f.receiver.poll(f.now+Receiver::kInactivityTimeoutMs-1); require(f.receiver.snapshot().active, "timeout fired early");
            f.receiver.poll(f.now+Receiver::kInactivityTimeoutMs); require(!f.receiver.snapshot().active && f.callbacks.timeouts==1 && f.writer.abort_calls==1, "timeout boundary failed"); }},
        {"FOTA-HOST-012", [] { Fixture f; const auto bytes=image(); f.send(begin_packet(bytes));
            f.receiver.poll(f.now+Receiver::kInactivityTimeoutMs+5000); require(f.callbacks.timeouts==1 && !f.callbacks.maintenance, "Hub disappearance did not recover"); }},
        {"FOTA-HOST-013", [] { Fixture f; const auto bytes=image(20); f.send(begin_packet(bytes)); f.writer.write_ok=false; f.send(data_packet(bytes,0,20,0));
            require(!f.receiver.snapshot().active && f.writer.abort_calls==1, "write failure did not abort"); f.writer.write_ok=true; transfer(f,bytes); require(f.receiver.snapshot().active, "new transfer did not recover"); }},
        {"FOTA-HOST-014", [] { Fixture f; f.writer.begin_ok=false; f.send(begin_packet(image()));
            require(f.callbacks.last_status()==Status::OtaBegin && !f.receiver.snapshot().active && !f.callbacks.maintenance, "begin failure state wrong"); }},
        {"FOTA-HOST-015", [] { Fixture f; const auto bytes=image(20); f.send(begin_packet(bytes)); f.writer.write_ok=false; f.send(data_packet(bytes,0,20,0));
            require(f.callbacks.last_status()==Status::OtaWrite && f.writer.abort_calls==1 && !f.receiver.snapshot().active, "write failure state wrong"); }},
        {"FOTA-HOST-016", [] { Fixture f; const auto bytes=image(20); f.writer.finalize_ok=false; transfer(f,bytes); finish(f,1);
            require(f.callbacks.last_status()==Status::OtaEnd && f.writer.commit_calls==0 && !f.callbacks.maintenance, "finalize failure state wrong"); }},
        {"FOTA-HOST-017", [] { Fixture f; const auto bytes=image(20); f.writer.commit_ok=false; transfer(f,bytes); finish(f,1);
            require(f.callbacks.last_status()==Status::SetBoot && f.writer.finalize_calls==1 && !f.callbacks.maintenance, "commit failure state wrong"); }},
        {"FOTA-HOST-018", [] { for (int mode=0; mode<4; ++mode) { Fixture f; const auto bytes=image(20); f.send(begin_packet(bytes));
            if(mode==0) f.send(base(MessageType::Abort)); else { if(mode==1) f.writer.write_ok=false; if(mode==2) f.writer.finalize_ok=false; if(mode==3) f.writer.commit_ok=false; f.send(data_packet(bytes,0,20,0)); if(mode>=2) finish(f,1); }
            require(!f.callbacks.maintenance && !f.receiver.snapshot().active, "maintenance remained active after abort/failure"); } }},
        {"FOTA-HOST-019", [] { for(int mode=0;mode<4;++mode){ Fixture f; const auto bytes=image(20); if(mode==0)f.writer.begin_ok=false; f.send(begin_packet(bytes));
            if(mode>0){if(mode==1)f.writer.write_ok=false;if(mode==2)f.writer.finalize_ok=false;if(mode==3)f.writer.commit_ok=false;f.send(data_packet(bytes,0,20,0));if(mode>=2)finish(f,1);} require(!f.callbacks.saw(Status::Complete)&&f.callbacks.restarts==0,"failure falsely completed"); } }},
        {"FOTA-HOST-020", [] { const auto bytes=image(33); for(int cycle=0;cycle<20;++cycle){ Fixture f; transfer(f,bytes); finish(f,1); require(f.callbacks.restarts==1&&f.callbacks.last_status()==Status::Complete,"valid reboot cycle failed"); } }},
        {"FOTA-HOST-021", [] { Fixture f; gs::node::NodeRuntime node("n",1); const auto key=node.record(gs::EventKind::Motion,"room",0,0); require(key,"event setup failed");
            f.send(begin_packet(image())); require(node.persisted()==1&&node.pending()==1,"maintenance altered retained application event"); f.send(base(MessageType::Abort)); require(node.persisted()==1&&node.pending()==1,"abort altered retained event"); }},
        {"FOTA-HOST-022", [] { Fixture f; gs::node::NodeRuntime node("n",1); const auto key=node.record(gs::EventKind::Motion,"room",0,0); require(key,"event setup failed");
            f.send(begin_packet(image())); require(node.acknowledge(*key,gs::AckClass::Durable),"pending application ACK not processed during maintenance"); require(node.persisted()==0&&node.pending()==0&&f.callbacks.maintenance,"ACK retirement incorrectly coupled to FOTA pause"); }},
        {"FOTA-HOST-023", [] { Fixture f; const auto bytes=image(20); f.send(begin_packet(bytes));
            auto changed=begin_packet(bytes); changed.image_crc32^=1U; f.send(changed);
            require(f.callbacks.last_status()==Status::BadPacket && f.writer.begin_calls==1 &&
                    f.receiver.snapshot().active,"changed duplicate Begin restarted or changed transfer");
            f.send(data_packet(bytes,0,20,0)); finish(f,1);
            require(f.callbacks.last_status()==Status::Complete,"original transfer did not survive altered Begin"); }},
        {"FOTA-HOST-024", [] { Fixture f; const auto bytes=image(20); f.send(begin_packet(bytes));
            auto changed=data_packet(bytes,0,20,0); changed.image_size^=1U; f.send(changed);
            require(f.callbacks.last_status()==Status::BadPacket && f.writer.write_calls==0,
                    "changed Data metadata was written");
            f.send(data_packet(bytes,0,20,0)); auto end=base(MessageType::End);
            end.sequence=1; end.image_size=f.image_size; end.image_crc32=f.image_crc32^1U;
            f.send(end);
            require(f.callbacks.last_status()==Status::BadPacket && f.writer.finalize_calls==0,
                    "changed End metadata finalized image");
            end.image_crc32=f.image_crc32; end.sequence=2; f.send(end);
            require(f.callbacks.last_status()==Status::BadSequence && f.writer.finalize_calls==0,
                    "wrong End sequence finalized image");
            finish(f,1); require(f.callbacks.last_status()==Status::Complete,
                                 "valid End did not complete after rejected metadata"); }},
        {"FOTA-HOST-025", [] { Fixture f; const auto bytes=image(20); f.send(begin_packet(bytes));
            f.now += Receiver::kInactivityTimeoutMs-1;
            auto bad=data_packet(bytes,0,20,0); bad.payload_crc32^=1U; f.send(bad);
            f.receiver.poll(100+Receiver::kInactivityTimeoutMs);
            require(f.callbacks.timeouts==1 && !f.receiver.snapshot().active,
                    "malformed traffic extended FOTA inactivity window"); }},
        {"FOTA-HOST-026", [] { Fixture f; auto packet=begin_packet(image(20));
            packet.reserved0=1; require(!f.receiver.process(packet,f.now),
                "nonzero reserved field accepted");
            packet.reserved0=0; packet.session_id=0;
            require(!f.receiver.process(packet,f.now) && f.writer.begin_calls==0,
                    "zero session began FOTA"); }},
        {"FOTA-HOST-027", [] { Fixture f; const auto bytes=image(20); transfer(f,bytes);
            finish(f,1); require(f.callbacks.last_status()==Status::Complete,
                                  "initial final ACK missing");
            finish(f,1); require(f.callbacks.last_status()==Status::Complete &&
                                  f.writer.finalize_calls==1 && f.writer.commit_calls==1 &&
                                  f.callbacks.restarts==1,
                                  "lost final ACK retried finalize or restart");
            f.send(begin_packet(bytes));
            require(f.callbacks.last_status()==Status::BadPacket && f.writer.begin_calls==1,
                    "completed session restarted before reboot"); }},
        {"FOTA-HOST-028", [] {
            using gs::node::fota::BootHealthDecision;
            using gs::node::fota::BootHealthObservation;
            using gs::node::fota::evaluate_boot_health;
            BootHealthObservation state;
            require(evaluate_boot_health(state, 5000)==BootHealthDecision::Wait,
                    "fixed delay accepted unready OTA image");
            state.owner_started=true;
            state.minimum_free_heap=200000;
            state.post_sensing_radio_confirmed=true;
            state.post_sensing_runtime_ticks=5;
            require(evaluate_boot_health(state, 11000)==BootHealthDecision::Wait,
                    "radio success before PIR readiness accepted image");
            state.sensing_ready=true;
            state.post_sensing_radio_confirmed=false;
            require(evaluate_boot_health(state, 11000)==BootHealthDecision::Wait,
                    "PIR readiness without post-sensing radio success accepted image");
            state.post_sensing_radio_confirmed=true;
            state.minimum_free_heap=8191;
            require(evaluate_boot_health(state, 11000)==BootHealthDecision::Wait,
                    "unsafe heap accepted image");
            state.minimum_free_heap=8192;
            state.post_sensing_runtime_ticks=1;
            require(evaluate_boot_health(state, 11000)==BootHealthDecision::Wait,
                    "one post-sensing runtime tick accepted image");
            state.post_sensing_runtime_ticks=2;
            require(evaluate_boot_health(state, 89999)==BootHealthDecision::Validate,
                    "healthy pending image was not validated");
            state.maintenance_active=true;
            require(evaluate_boot_health(state, 89999)==BootHealthDecision::Wait,
                    "maintenance image was validated");
            require(evaluate_boot_health(state, 90000)==BootHealthDecision::Rollback,
                    "health deadline did not request rollback");
        }},
    };
}

}  // namespace

int main() {
    std::size_t failed = 0;
    const auto tests = catalog();
    for (const auto& test : tests) {
        try {
            test.body();
            std::cout << "PASS\t" << test.id << '\n';
        } catch (const std::exception& error) {
            ++failed;
            std::cout << "FAIL\t" << test.id << '\t' << error.what() << '\n';
        }
    }
    std::cout << "SUMMARY\t" << tests.size() << '\t' << tests.size()-failed << '\t' << failed << '\n';
    return failed == 0 ? 0 : 1;
}
