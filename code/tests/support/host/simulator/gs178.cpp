// GS-178: real production Node/Hub/security/storage/CloudSync components.
// Host input, scheduler, byte files and SDK socket adapter replace hardware.
#include "firmware/common/security/rejoin_protocol.hpp"
#include "firmware/common/security/runtime_frame_security.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "firmware/hub/storage/outbox_journal_backend.hpp"
#include "firmware/hub/storage/runtime_state_store.hpp"
#include "firmware/hub/target/esp32s3/gs40_test_only_bootstrap.hpp"
#include "firmware/node/runtime/node_runtime.hpp"
#include "firmware/node/sensing/sensing.hpp"
#include "firmware/node/storage/node_recovery_persistence.hpp"
#include "tests/support/file_flash.hpp"
#include "tests/support/host/security/openssl_commissioning_crypto.hpp"
#include <arpa/inet.h>
#include <chrono>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <openssl/sha.h>
#include <sstream>
#include <sys/socket.h>
#include <unistd.h>

using namespace gs;
using namespace gs::security;
using namespace gs::hub;
using namespace gs::hub::target;
using namespace gs::hub::storage;
namespace {
void need(bool ok, const char *message) {
  if (!ok)
    throw std::runtime_error(message);
}
std::string hex(const Bytes &v) {
  static const char *d = "0123456789abcdef";
  std::string s;
  for (auto b : v) {
    s += d[b >> 4];
    s += d[b & 15];
  }
  return s;
}
Bytes unhex(const std::string &s) {
  need(s.size() % 2 == 0 && s.size() <= 50000, "bounded hex");
  Bytes b;
  for (std::size_t i = 0; i < s.size(); i += 2) {
    need(s.find_first_not_of("0123456789abcdef", i) > i + 1, "invalid hex");
    b.push_back(std::stoul(s.substr(i, 2), nullptr, 16));
  }
  return b;
}
struct Clock final : S3HubMonotonicClock {
  Milliseconds now_ms() const override {
    return 1000 + std::chrono::duration_cast<std::chrono::milliseconds>(
                      std::chrono::steady_clock::now() - start)
                      .count();
  }
  std::chrono::steady_clock::time_point start =
      std::chrono::steady_clock::now();
};
struct Floor final : AuthenticatedTimeFloorStore {
  std::filesystem::path path;
  std::uint64_t generation = 0;
  EpochSeconds floor = 0;
  explicit Floor(std::filesystem::path p) : path(std::move(p)) {}
  bool save() {
    Bytes b(sizeof(generation) + sizeof(floor));
    std::memcpy(b.data(), &generation, sizeof(generation));
    std::memcpy(b.data() + sizeof(generation), &floor, sizeof(floor));
    return test::write_file(path, b);
  }
  bool begin_boot(std::uint64_t &out) override {
    if (std::filesystem::exists(path)) {
      auto b = test::read_file(path);
      if (b.size() != 16)
        return false;
      std::memcpy(&generation, b.data(), 8);
      std::memcpy(&floor, b.data() + 8, 8);
    }
    out = ++generation;
    return out != 0 && save();
  }
  TrustedTimeFloorRead read_floor(EpochSeconds &out) override {
    out = floor;
    return floor > 0 ? TrustedTimeFloorRead::Valid
                     : TrustedTimeFloorRead::Missing;
  }
  bool commit_floor(EpochSeconds at) override {
    if (at < floor)
      return false;
    floor = at;
    return save();
  }
};
struct Files final : RuntimeStateFiles {
  std::filesystem::path root;
  explicit Files(std::filesystem::path p) : root(std::move(p)) {
    std::filesystem::create_directories(root);
  }
  bool state_size(const char *n, bool &f, std::uint32_t &s) override {
    f = std::filesystem::exists(root / n);
    s = f ? std::filesystem::file_size(root / n) : 0;
    return true;
  }
  bool state_read(const char *n, std::uint32_t offset, std::uint8_t *out,
                  std::size_t size) override {
    auto b = test::read_file(root / n);
    if (offset + size > b.size())
      return false;
    std::copy_n(b.data() + offset, size, out);
    return true;
  }
  bool state_replace(const char *n, const Bytes &b) override {
    return test::write_file(root / n, b);
  }
  bool state_append_sync(const char *n, const Bytes &b) override {
    auto v = test::read_file(root / n);
    v.insert(v.end(), b.begin(), b.end());
    return state_replace(n, v);
  }
  bool state_truncate(const char *n, std::uint32_t size) override {
    auto v = test::read_file(root / n);
    if (size > v.size())
      return false;
    v.resize(size);
    return state_replace(n, v);
  }
  bool state_capacity(std::uint64_t &total, std::uint64_t &used) override {
    total = 4 * 1024 * 1024;
    used = 0;
    for (const auto &f : std::filesystem::directory_iterator(root))
      used += f.file_size();
    return used <= total;
  }
  bool state_remove(const char *n) override {
    std::filesystem::remove(root / n);
    return true;
  }
  bool state_sync(const char *n) override {
    return std::filesystem::exists(root / n);
  }
};
struct SnapshotBlobs final : durable::BlobStore {
  std::filesystem::path root;
  explicit SnapshotBlobs(std::filesystem::path p) : root(std::move(p)) {
    std::filesystem::create_directories(root);
  }
  bool read(const std::string &name, Bytes &out, bool &found) override {
    found = std::filesystem::exists(root / name);
    out = found ? test::read_file(root / name) : Bytes{};
    return true;
  }
  bool write_immutable(const std::string &name, const Bytes &value) override {
    return !std::filesystem::exists(root / name) &&
           test::write_file(root / name, value);
  }
  bool replace(const std::string &name, const Bytes &value) override {
    return test::write_file(root / name, value);
  }
};
struct Peer {
  std::string logical, physical;
  CommissioningBinding binding;
  std::uint64_t session = 10, health_seq = 0;
  std::unique_ptr<node::NodeRuntime> runtime;
  std::unique_ptr<test::FileBlob> blob;
  std::unique_ptr<node::NodeRecoveryRepository> recovery;
  std::unique_ptr<RuntimeFrameSecurity> node_frame, hub_frame;
  Key32 digest{};
  unsigned interval = 300;
  std::string profile = "configured";
};
struct Authority final : CloudRuntimeAuthorityProvider {
  ProvisionedS3CloudTrust &trust;
  std::vector<std::unique_ptr<Peer>> &peers;
  const Clock &clock;
  EpochSeconds domain_anchor = 0;
  Authority(ProvisionedS3CloudTrust &t, std::vector<std::unique_ptr<Peer>> &p,
            const Clock &c)
      : trust(t), peers(p), clock(c) {}
  bool current_binding(CloudAuthorityBinding &b) override {
    return trust.current_binding(b);
  }
  bool original_event_owned(const DomainEvent &e,
                            const CloudAuthorityBinding &b) override {
    CloudAuthorityBinding live;
    if (!current_binding(live) || !(live == b))
      return false;
    for (const auto &p : peers)
      if (e.key.source_id == p->logical &&
          e.key.physical_device_id == p->physical)
        return true;
    return false;
  }
  bool trusted_hub_time(Milliseconds domain_ms,
                        TrustedHubTimeSnapshot &out) override {
    if (!trust.trusted_hub_time(clock.now_ms(), out))
      return false;
    out.monotonic_ms = domain_ms;
    out.utc_now = domain_anchor + domain_ms / 1000;
    return true;
  }
  bool active_nodes(const CloudAuthorityBinding &b,
                    std::vector<CloudNodeEnrollment> &n) override {
    CloudAuthorityBinding live;
    if (!current_binding(live) || !(live == b))
      return false;
    for (const auto &p : peers)
      n.push_back({p->physical, p->logical, 1, p->session, p->profile,
                   p->interval,
                   p->profile == "legacy_120" ? 310U : 3 * p->interval + 10});
    return true;
  }
};

class Fixture {
public:
  host::security::OpenSslCommissioningCrypto crypto;
  Key32 key{};
  test::TempFlash flash;
  test::FileSegments segments{flash.path / "outbox", flash.path};
  Files files{flash.path / "state"};
  SnapshotBlobs snapshots{flash.path / "retirement"};
  durable::RetirementSnapshot snapshot;
  durable::RetirementSnapshotReference snapshot_reference;
  std::unique_ptr<DurableEventOutbox> outbox;
  std::unique_ptr<OutboxJournalBackend> journal;
  std::unique_ptr<RuntimeStateStore> state;
  std::unique_ptr<HubRuntime> hub;
  std::vector<std::unique_ptr<Peer>> peers;
  CloudAuthorityBinding rule_binding;
  bool booted = false;
  explicit Fixture(std::uint64_t initial_session = 10) {
    need(initial_session != 0 &&
             initial_session != std::numeric_limits<std::uint64_t>::max(),
         "Node session seed must be positive and leave restart headroom");
    key.fill(7);
    for (const auto &name : {"bedroom", "bathroom", "kitchen", "door"}) {
      auto p = std::make_unique<Peer>();
      p->logical = name;
      p->physical = "test-c3-" + p->logical;
      p->session = initial_session;
      p->binding.device_id = p->physical;
      p->binding.logical_id = p->logical;
      p->binding.home_id = "gs177-test-product";
      p->binding.hub_id = "test-hub-product";
      p->binding.installation_key.fill(
          static_cast<std::uint8_t>(peers.size() + 1));
      SHA256(reinterpret_cast<const unsigned char *>(p->physical.data()),
             p->physical.size(), p->digest.data());
      p->blob =
          std::make_unique<test::FileBlob>(flash.path / (p->logical + "-node"));
      p->recovery = std::make_unique<node::NodeRecoveryRepository>(
          crypto, *p->blob, key, p->binding.home_id, p->binding.hub_id,
          p->logical);
      p->runtime = std::make_unique<node::NodeRuntime>(p->logical, initial_session);
      need(p->recovery->save(p->runtime->recovery_snapshot()),
           "Node initial persistence");
      p->node_frame =
          std::make_unique<RuntimeFrameSecurity>(crypto, p->binding);
      p->hub_frame = std::make_unique<RuntimeFrameSecurity>(crypto, p->binding);
      peers.push_back(std::move(p));
    }
    restart();
  }
  void rejoin(Peer &p) {
    NodeRejoin node(crypto, p.binding, p.session, 2);
    HubRejoin owner(crypto, p.binding, p.session - 1);
    auto hello = node.begin();
    need(bool(hello), "Node rejoin Hello");
    auto challenge = owner.accept(*hello);
    need(bool(challenge), "Hub rejoin challenge");
    auto final = node.accept(*challenge);
    need(bool(final), "Node rejoin Final");
    auto ack = owner.confirm(*final);
    need(ack && node.commit(*ack), "authenticated rejoin");
    need(p.node_frame->start(p.session, *node.session_salt()) &&
             p.hub_frame->start(p.session, *owner.session_salt()),
         "AEAD session");
    hub->authorize_node(p.logical, p.session, true);
    hub->set_node_offline_timeout(
        p.logical, p.profile == "legacy_120" ? 310U : 3 * p.interval + 10);
  }
  void restart() {
    hub.reset();
    state.reset();
    journal.reset();
    outbox.reset();
    outbox = std::make_unique<DurableEventOutbox>(segments, crypto, key);
    auto recovered = outbox->recover();
    need(recovered == OutboxRecovery::Empty ||
             recovered == OutboxRecovery::Ready,
         "outbox restart");
    journal = std::make_unique<OutboxJournalBackend>(*outbox);
    state = std::make_unique<RuntimeStateStore>(files, crypto, key);
    hub = std::make_unique<HubRuntime>(32, *journal);
    hub->bind_runtime_state(*state);
    for (auto &p : peers) {
      if (booted)
        ++p->session;
      rejoin(*p);
    }
    durable::RetirementSnapshotRepository repository(snapshots, crypto, key, 1);
    if (!booted) {
      snapshot.storage_epoch = 1;
      for (std::size_t i = 0; i < peers.size(); ++i) {
        auto &p = *peers[i];
        need(p.runtime->set_retirement_epoch(1) &&
                 p.recovery->save(p.runtime->recovery_snapshot()),
             "persist Node retirement epoch");
        transport::NodeRetirementReportV1 report, received;
        Key32 report_key{}, verified_mac{};
        transport::RetirementFragmentSet fragments;
        need(transport::make_retirement_report(p.runtime->recovery_snapshot(),
                                               report) &&
                 transport::derive_retirement_report_key(
                     crypto, p.binding.installation_key, report_key) &&
                 transport::fragment_retirement_report(crypto, report_key,
                                                       report, fragments),
             "production Node retirement report");
        transport::RetirementReportReassembler assembler;
        for (unsigned n = 0; n < fragments.count; ++n) {
          SecureFrame wire;
          transport::EncodedFrame opened;
          need(p.node_frame->seal(RuntimeDirection::Uplink, fragments.frames[n],
                                  wire) &&
                   p.hub_frame->open(RuntimeDirection::Uplink, wire, opened),
               "retirement AEAD");
          auto result = assembler.accept(crypto, report_key, opened, received,
                                         verified_mac);
          need(
              result ==
                  (n + 1 == fragments.count
                       ? transport::RetirementAssemblyResult::Complete
                       : transport::RetirementAssemblyResult::AcceptedFragment),
              "authenticated retirement assembly");
        }
        durable::RetirementSnapshot candidate;
        need(repository.apply_authenticated_report(
                 snapshot, p.digest, i, 1, p.session, received, verified_mac,
                 candidate) == durable::RetirementReportApply::Prepared,
             "current authenticated Node retirement witness");
        snapshot = candidate;
      }
      need(repository.prepare_bank(snapshot, 0, snapshot_reference),
           "authenticated fixture snapshot publication");
    }
    durable::RetirementSnapshot selected;
    need(repository.load(snapshot_reference, selected),
         "reload authenticated selected fixture snapshot");
    need(outbox->replay_fence_matches(1, snapshot_reference) ||
             outbox->publish_replay_fence(1, snapshot_reference,
                                          outbox->record_count()),
         "durable owner replay fence publication");
    need(hub->bind_replay_fence(selected, 1, snapshot_reference, *outbox),
         "bind authenticated replay fence");
    need(hub->restore_from_journal(), "reducer recovery");
    booted = true;
  }
  ProcessResult deliver(Peer &p, const NodeMessage &msg, EpochSeconds received,
                        Milliseconds domain, std::uint16_t minute, bool drop,
                        bool reject = false) {
    auto encoded = transport::encode_node_message(msg);
    SecureFrame wire;
    transport::EncodedFrame opened;
    need(
        encoded &&
            p.node_frame->seal(RuntimeDirection::Uplink, encoded.frame, wire) &&
            p.hub_frame->open(RuntimeDirection::Uplink, wire, opened),
        "AEAD Node to Hub");
    auto decoded =
        transport::decode_node_message(opened.bytes.data(), opened.size);
    need(decoded && hub->authenticated_radio_message_callback(
                        *decoded.value, p.logical, p.physical, p.session,
                        received, domain,
                        static_cast<std::uint8_t>(
                            &p == peers[0].get()
                                ? 0
                                : std::find_if(peers.begin(), peers.end(),
                                               [&](const auto &v) {
                                                 return v.get() == &p;
                                               }) -
                                      peers.begin()),
                        1, p.digest),
         "authenticated owner admission");
    need(!p.hub_frame->open(RuntimeDirection::Uplink, wire, opened),
         "replayed radio ciphertext rejected");
    auto result = hub->run_state_once(minute, &rule_binding);
    if (reject) {
      need(result && result->ack == AckClass::Rejected,
           "changed Node payload rejected");
      return *result;
    }
    need(result && (result->ack == AckClass::Durable ||
                    result->ack == AckClass::DiscardedPolicy),
         "durable or explicit policy ACK");
    need(hub->journal().contains(result->key) ==
             (result->ack == AckClass::Durable),
         "policy drop cannot invent durable storage");
    NodeAckMessage ack;
    ack.node_id = msg.node_id;
    ack.session_id = msg.session_id;
    ack.sequence_number = msg.sequence_number;
    ack.ack_type = result->ack;
    auto plain = transport::encode_node_ack(ack);
    SecureFrame reply;
    need(plain &&
             p.hub_frame->seal(RuntimeDirection::Downlink, plain.frame, reply),
         "authenticated ACK encode");
    if (!drop) {
      need(p.node_frame->open(RuntimeDirection::Downlink, reply, opened),
           "ACK authenticate");
      auto answer =
          transport::decode_node_ack(opened.bytes.data(), opened.size);
      need(answer && p.runtime->acknowledge({answer.value->node_id,
                                             answer.value->session_id,
                                             answer.value->sequence_number},
                                            answer.value->ack_type),
           "exact ACK retirement");
      need(p.recovery->save(p.runtime->recovery_snapshot()),
           "Node durable retirement");
    } else
      p.runtime->transport_result(
          {msg.node_id, msg.session_id, msg.sequence_number}, false, domain);
    return *result;
  }
};

Bytes udp_time(const Gs40TestOnlyRuntimeConfig &c,
               const AuthenticatedTimeChallenge &challenge) {
  Bytes request{'G', 'S', 'T', 'Q', 1};
  for (int shift = 56; shift >= 0; shift -= 8)
    request.push_back(challenge.boot_generation >> shift);
  request.insert(request.end(), challenge.nonce.begin(), challenge.nonce.end());
  const auto fd = socket(AF_INET, SOCK_DGRAM, 0);
  need(fd >= 0, "UDP socket");
  timeval timeout{2, 0};
  setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(c.time_port);
  addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  need(sendto(fd, request.data(), request.size(), 0,
              reinterpret_cast<sockaddr *>(&addr), sizeof(addr)) == 45,
       "time request");
  Bytes proof(457);
  const auto n = recv(fd, proof.data(), proof.size(), 0);
  close(fd);
  need(n == 456, "bounded signed-time reply");
  proof.resize(n);
  return proof;
}
} // namespace

int main(int argc, char **argv) {
  try {
    need(argc == 2 || argc == 3,
         "config root DER required; optional initial Node session is TEST_ONLY");
    std::uint64_t initial_session = 10;
    if (argc == 3) {
      std::size_t parsed = 0;
      initial_session = std::stoull(argv[2], &parsed, 10);
      need(parsed == std::strlen(argv[2]) && initial_session != 0 &&
               initial_session != std::numeric_limits<std::uint64_t>::max(),
           "invalid TEST_ONLY initial Node session");
    }
    Clock clock;
    S3AuthenticatedTimeRandomSource random;
    Gs40TestOnlyEnvelopeSession envelope(test::read_file(argv[1]));
    std::array<std::uint8_t, 32> nonce{};
    Bytes target;
    need(envelope.begin(nonce, target), "fresh config challenge");
    std::cout << "{\"stage\":\"CHALLENGE\",\"nonce\":\""
              << hex(Bytes(nonce.begin(), nonce.end())) << "\",\"public\":\""
              << hex(target) << "\"}" << std::endl;
    std::string line;
    need(bool(std::getline(std::cin, line)), "fixture envelope input");
    auto wire = unhex(line);
    need(wire.size() > 4, "length frame");
    Gs40TestOnlyRuntimeConfig config;
    need(envelope.accept(Bytes(wire.begin() + 4, wire.end()), config),
         "authenticated config");
    need(!envelope.accept(Bytes(wire.begin() + 4, wire.end()), config),
         "config replay rejected");
    Fixture fixture(initial_session);
    Floor floor(fixture.flash.path / "time-floor");
    Rsa3072Sha256TimeProofVerifier verifier(config.time_public_key_der);
    AuthenticatedHubTimeProvider time(floor, verifier, random, clock,
                                      {30000, 60000, 300});
    need(time.start(), "authenticated boot generation");
    AuthenticatedTimeChallenge challenge;
    need(time.create_challenge(challenge), "time challenge");
    auto proof = udp_time(config, challenge);
    need(time.accept_authenticated_time(proof), "real signed-time accepted");
    TrustedHubTimeSnapshot trusted;
    need(time.trusted_hub_time(clock.now_ms(), trusted), "trusted time ready");
    Gs40TestOnlyAuthorityLeaseVerifier lease_verifier(
        config.authority_public_key_der);
    Gs40TestOnlyMaterialSource material(std::move(config), time, clock);
    Gs40TestOnlyCloudComposition composition(material, time, clock);
    auto &bootstrap_channel = composition.bootstrap_channel;
    need(gs40_test_only_refresh_authority(material, time, clock, random,
                                          bootstrap_channel, lease_verifier),
         "mTLS current authority bootstrap");
    auto &trust = composition.trust;
    Authority provider(trust, fixture.peers, clock);
    provider.domain_anchor = trusted.utc_now;
    CloudRuntimeAuthoritySource authority(provider);
    need(provider.current_binding(fixture.rule_binding),
         "initial Hub decision owner binding");
    auto &channel = composition.cloud_channel;
    HttpBackendTransport transport(channel);
    auto worker = std::make_unique<CloudSyncWorker>(
        fixture.hub->journal(), *fixture.hub, authority, transport);
    RoutineConfig routine;
    routine.window_id = "gs178-morning";
    routine.start_at = trusted.utc_now;
    routine.end_at = trusted.utc_now + 60;
    routine.grace_end_at = trusted.utc_now + 120;
    fixture.hub->start_window(routine, HomeMode::Home);
    ActivityRuleConfig rules;
    rules.morning_bedroom_location = "bedroom";
    rules.night_bathroom_visit_threshold = 2;
    fixture.hub->configure_activity_rules(rules);
    fixture.hub->start_activity_monitor(trusted.utc_now);
    std::cout << "{\"stage\":\"CLOUDSYNC_READY\",\"utc\":" << trusted.utc_now
              << ",\"boot_generation\":" << trusted.boot_generation << "}"
              << std::endl;
    while (std::getline(std::cin, line)) {
      need(line.size() <= 1024, "bounded command");
      std::istringstream in(line);
      std::string op;
      in >> op;
      if (op == "quit")
        break;
      if (op == "input" || op == "retry" || op == "conflict") {
        unsigned index, minute, drop;
        EpochSeconds at, received;
        Milliseconds domain;
        std::string kind;
        in >> index >> kind >> at >> received >> domain >> minute >> drop;
        need(in && index < fixture.peers.size() && minute < 1440,
             "input parameters");
        auto &p = *fixture.peers[index];
        if (op == "input") {
          EventKind event = EventKind::Motion;
          if (kind == "door_open")
            event = EventKind::DoorOpen;
          else if (kind == "door_close")
            event = EventKind::DoorClosed;
          else if (kind == "ok")
            event = EventKind::OkPressed;
          else if (kind == "help")
            event = EventKind::CallFamily;
          else
            need(kind == "motion", "kind");
          node::QualifiedInput sensor(
              event == EventKind::DoorClosed ? EventKind::DoorOpen : event,
              (event == EventKind::DoorOpen || event == EventKind::DoorClosed)
                  ? std::optional<EventKind>(EventKind::DoorClosed)
                  : std::nullopt,
              150, 1000);
          const bool initially_open = event == EventKind::DoorClosed;
          need(!sensor.sample(initially_open, domain - 200) &&
                   !sensor.sample(!initially_open, domain - 150) &&
                   sensor.sample(!initially_open, domain) == event,
               "production input qualification");
          need(bool(p.runtime->record(event, p.logical, domain, at)),
               "Node event processing");
          need(p.recovery->save(p.runtime->recovery_snapshot()),
               "Node retained before transmit");
        }
        auto msg = p.runtime->next_message(domain);
        need(bool(msg), "Node pending transmission");
        if (op == "conflict")
          msg->event_type = EventKind::DoorOpen;
        auto result = fixture.deliver(p, *msg, received, domain, minute,
                                      drop != 0, op == "conflict");
        std::cout << "{\"ack\":\""
                  << (result.ack == AckClass::Durable ? "DURABLE"
                      : result.ack == AckClass::DiscardedPolicy
                          ? "DISCARDED_POLICY"
                          : "REJECTED")
                  << "\",\"changed\":"
                  << (result.state_changed ? "true" : "false")
                  << ",\"event_key\":\"" << result.key.str()
                  << "\",\"pending\":" << p.runtime->pending()
                  << ",\"signals\":[";
        for (std::size_t n = 0; n < result.rule_signals.size(); ++n) {
          if (n)
            std::cout << ",";
          const auto &s = result.rule_signals[n];
          std::cout << "{\"kind\":" << static_cast<int>(s.kind)
                    << ",\"create\":" << (s.create ? "true" : "false")
                    << ",\"resolves_prior\":"
                    << (s.resolves_prior ? "true" : "false") << "}";
        }
        std::cout << "],\"last_activity_at\":"
                  << fixture.hub->activity_state().last_activity_at.value_or(0)
                  << "}" << std::endl;
      } else if (op == "health") {
        unsigned index;
        Milliseconds domain;
        in >> index >> domain;
        need(in && index < fixture.peers.size(), "health parameters");
        auto &p = *fixture.peers[index];
        NodeHealthSnapshot health;
        health.node_id = p.logical;
        health.session_id = p.session;
        health.health_sequence = ++p.health_seq;
        health.uptime_ms = domain;
        health.free_heap = 40000;
        auto encoded = transport::encode_node_health(health);
        SecureFrame wire;
        transport::EncodedFrame opened;
        need(encoded &&
                 p.node_frame->seal(RuntimeDirection::Uplink, encoded.frame,
                                    wire) &&
                 p.hub_frame->open(RuntimeDirection::Uplink, wire, opened),
             "health AEAD");
        auto decoded =
            transport::decode_node_health(opened.bytes.data(), opened.size);
        need(decoded && fixture.hub->observe_authenticated_health(
                            *decoded.value, p.logical, p.session, domain),
             "authenticated health");
        std::cout << "{\"health\":true}" << std::endl;
      } else if (op == "profile") {
        unsigned index, interval;
        std::string profile;
        in >> index >> profile >> interval;
        need(in && index < fixture.peers.size() &&
                 ((profile == "configured" && interval == 300) ||
                  (profile == "legacy_60" && interval == 60) ||
                  (profile == "legacy_120" && interval == 120)),
             "trusted test profile");
        auto &p = *fixture.peers[index];
        p.profile = profile;
        p.interval = interval;
        fixture.hub->set_node_offline_timeout(
            p.logical, profile == "legacy_120" ? 310U : 3 * interval + 10);
        std::cout << "{\"profile\":true}" << std::endl;
      } else if (op == "sync") {
        Milliseconds domain;
        unsigned connected;
        in >> domain >> connected;
        need(bool(in), "sync parameters");
        auto r = worker->run_once(connected != 0, domain, 16);
        need(worker->refresh_hub_rule_decision_snapshot(),
             "production HubRuntime decision snapshot");
        const auto rule_result = worker->run_hub_rule_decision_once(
            connected != 0, domain, 4);
        unsigned rule_submitted = static_cast<unsigned>(rule_result.submitted);
        unsigned rule_completed = static_cast<unsigned>(rule_result.completed);
        std::vector<HubRuleDecisionReceipt> receipts;
        if (worker->take_hub_rule_decision_receipts(receipts)) {
          for (const auto &receipt : receipts) {
            const bool checkpointed = fixture.hub->acknowledge_hub_rule_decision(receipt);
            worker->finish_hub_rule_decision_receipt(receipt, checkpointed);
            need(checkpointed, "backend COMMITTED receipt checkpoints production decision queue");
          }
          need(worker->refresh_hub_rule_decision_snapshot(),
               "production HubRuntime decision retirement snapshot");
        }
        std::cout << "{\"state\":" << static_cast<int>(r.state)
                  << ",\"submitted\":" << r.submitted
                  << ",\"completed\":" << r.completed
                  << ",\"health_submitted\":" << r.node_health_submitted
                  << ",\"health_accepted\":" << r.node_health_accepted
                  << ",\"rules_submitted\":" << rule_submitted
                  << ",\"rules_completed\":" << rule_completed
                  << ",\"stored\":" << fixture.hub->journal().size() << "}"
                  << std::endl;
      } else if (op == "refresh") {
        bool ready = gs40_test_only_refresh_authority(
            material, time, clock, random, bootstrap_channel, lease_verifier);
        std::cout << "{\"authority\":" << (ready ? "true" : "false") << "}"
                  << std::endl;
      } else if (op == "restart") {
        worker.reset();
        fixture.restart();
        worker = std::make_unique<CloudSyncWorker>(
            fixture.hub->journal(), *fixture.hub, authority, transport);
        std::cout << "{\"restart\":true,\"stored\":"
                  << fixture.hub->journal().size() << "}" << std::endl;
      } else if (op == "deadline") {
        EpochSeconds now;
        unsigned trusted_clock;
        in >> now >> trusted_clock;
        auto d = fixture.hub->deadline(now, trusted_clock != 0,
                                       &fixture.rule_binding);
        std::cout << "{\"create\":" << (d.create ? "true" : "false") << "}"
                  << std::endl;
      } else if (op == "timer") {
        EpochSeconds now;
        unsigned minute, trusted_clock;
        in >> now >> minute >> trusted_clock;
        need(in && minute < 1440 && trusted_clock <= 1,
             "bounded authenticated rule timer input");
        auto signals = fixture.hub->activity_timers(
            now, static_cast<std::uint16_t>(minute), trusted_clock != 0,
            &fixture.rule_binding);
        std::cout << "{\"rule_signals\":" << signals.size() << "}"
                  << std::endl;
      } else if (op == "mode") {
        std::string mode;
        in >> mode;
        need(mode == "home" || mode == "away" || mode == "paused" ||
                 mode == "privacy",
             "mode");
        fixture.hub->set_mode(mode == "away"      ? HomeMode::Away
                              : mode == "paused"  ? HomeMode::Paused
                              : mode == "privacy" ? HomeMode::Privacy
                                                  : HomeMode::Home);
        std::cout << "{\"mode\":true}" << std::endl;
      } else
        throw std::runtime_error("unknown command");
    }
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "GS178 FAIL: " << e.what() << std::endl;
    return 1;
  }
}
