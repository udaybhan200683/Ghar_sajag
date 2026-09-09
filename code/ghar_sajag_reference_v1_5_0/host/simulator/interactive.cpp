// @module T01 Host integration adapter | @requirements E01,E02,E03,E04,E05,F05,F06,F07,F08,F10
// Executes the existing node/hub components in a single-owner host process.
// stdin is a test transport, not ESP-NOW. Stores remain volatile across reset/restart.
#include "firmware/node/runtime/node_runtime.hpp"
#include "firmware/hub/runtime/hub_runtime.hpp"
#include "cloud/cloud_sync.hpp"
#include "host/logging/file_log_sink.hpp"
#include "gs/feature_flags.hpp"
#if GS_PRODUCT_AI || !GS_FEATURE_MORNING_ROUTINE || !GS_FEATURE_CALL_FAMILY || !GS_FEATURE_LOCAL_OFFLINE
#error "The interactive lab requires the default Base P0 profile; use the component matrix for other flag combinations."
#endif
#include <array>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>

using namespace gs;
namespace {
const std::array<std::string,4> names{"room1", "kitchen", "entry", "pooja"};
const std::array<const char*,10> kinds{"MOTION","DOOR_OPEN","DOOR_CLOSED","OK_PRESSED","CALL_FAMILY","HEARTBEAT","PRIVACY_ON","PRIVACY_OFF","GAP","INVALID"};
struct Simulation {
    EpochSeconds now{1000};
    bool trusted{true};
    std::array<bool,4> online{true,true,true,true};
    std::array<std::unique_ptr<node::NodeRuntime>,4> nodes;
    hub::HubRuntime hub{64,4096};
    hub::CloudSync cloud{hub.journal()};
    std::optional<DomainEvent> last_business;
    std::string reason{"window_not_due"};
    std::string ack{"none"};
    bool decision_pending{false};
    EpochSeconds decision_at{0};
    Simulation() {
        hub.start_window({"sim-morning",1000,2000,2300,{"kitchen","pooja"},true},HomeMode::Home);
        for (std::size_t i=0;i<4;++i) {
            nodes[i]=std::make_unique<node::NodeRuntime>(names[i],1,128,128);
            hub.authorize_node(names[i],1,true);
        }
        cloud.set_connected(true,now*1000);
        heartbeats();
    }
    void deliver(std::size_t i) {
        if (!online[i]) return;
        for (unsigned n=0;n<128;++n) {
            auto event=nodes[i]->next_transmission(now*1000);
            if (!event) break;
            event->received_at=now;
            const bool copied=hub.radio_callback(*event);
            nodes[i]->transport_result(event->key,copied,now*1000);
            if (!copied) break;
            auto result=hub.run_state_once();
            if (!result) break;
            ack=result->ack==AckClass::Durable?"DURABLE_MODEL":result->ack==AckClass::DiscardedPolicy?"DISCARDED_POLICY":"REJECTED";
            nodes[i]->acknowledge(result->key,result->ack);
            if (is_business_event(event->kind)) last_business=event;
        }
    }
    void event(std::size_t i,EventKind kind) {
        if (!nodes[i]->record(kind,names[i],now*1000,now,0,3800)) throw std::runtime_error("node_capacity");
        deliver(i);
    }
    void heartbeats() { for(std::size_t i=0;i<4;++i) if(online[i]) event(i,EventKind::Heartbeat); }
    void deadline() {
        const auto d=hub.deadline(now,trusted); reason=d.reason;
        if(d.create) { decision_pending=true; decision_at=now; } // Volatile adapter outbox; retain observation time on replay.
    }
    void advance(int seconds) {
        // Test clock advances in heartbeat-sized steps; no wall-clock wait and no new production scheduler.
        while(seconds>0) { int step=seconds>60?60:seconds; now+=step; seconds-=step; heartbeats(); }
        deadline();
    }
    void print() {
        const auto& state=hub.routine_state();
        const auto batch=cloud.next_batch(now*1000,4096);
        std::cout<<"{\"now\":"<<now<<",\"wan\":"<<(cloud.connected()?"true":"false")
          <<",\"clock_trusted\":"<<(trusted?"true":"false")
          <<",\"activity_seen\":"<<(state.activity_seen?"true":"false")
          <<",\"explicit_ok\":"<<(state.explicit_ok?"true":"false")
          <<",\"coverage\":\""<<(state.coverage==CoverageState::Covered?"COVERED":"UNKNOWN")
          <<"\",\"mode\":\""<<(state.mode==HomeMode::Privacy?"PRIVACY":"HOME")
          <<"\",\"reason\":\""<<reason<<"\",\"last_ack\":\""<<ack
          <<"\",\"journal_records\":"<<hub.journal().size()
          <<",\"pending_cloud\":"<<hub.journal().pending_cloud(4096).size()
          <<",\"evidence_count\":"<<state.evidence_ids.size()
          <<",\"missing_pending\":"<<(decision_pending?"true":"false")<<",\"missing_at\":"<<decision_at<<",\"nodes\":[";
        for(std::size_t i=0;i<4;++i) {
            if(i) std::cout<<',';
            std::cout<<"{\"id\":\""<<names[i]<<"\",\"online\":"<<(online[i]?"true":"false")<<",\"retained\":"<<nodes[i]->persisted()<<'}';
        }
        std::cout<<"],\"events\":[";
        for(std::size_t i=0;i<batch.size();++i) {
            if(i) std::cout<<',';
            const auto& e=batch[i];
            std::cout<<"{\"event_id\":\""<<e.key.str()<<"\",\"kind\":\""<<kinds.at(static_cast<std::size_t>(e.kind))
              <<"\",\"location\":\""<<e.location<<"\",\"occurred_at\":"<<e.occurred_at<<",\"hub_received_at\":"<<e.received_at<<'}';
        }
        std::cout<<"]}"<<std::endl;
    }
};
}
int main() {
    host::FileLogSink sink("logs/e2e_cpp.txt",131072,2); log::set_sink(&sink);
    auto sim=std::make_unique<Simulation>();
    std::string line;
    while(std::getline(std::cin,line)) {
        try {
            std::istringstream in(line); std::string cmd; in>>cmd;
            if(cmd=="reset") sim=std::make_unique<Simulation>();
            else if(cmd=="advance") {int n=-1;in>>n;if(n<0||n>3600)throw std::runtime_error("invalid_step");sim->advance(n);}
            else if(cmd=="event") {int i=-1,k=-1;in>>i>>k;if(i<0||i>3||k<0||k>8)throw std::runtime_error("invalid_event");sim->event(static_cast<std::size_t>(i),static_cast<EventKind>(k));sim->deadline();}
            else if(cmd=="node") {int i=-1,v=-1;in>>i>>v;if(i<0||i>3||(v!=0&&v!=1))throw std::runtime_error("invalid_node");sim->online[static_cast<std::size_t>(i)]=v!=0;sim->deliver(static_cast<std::size_t>(i));sim->deadline();}
            else if(cmd=="wan"||cmd=="clock") {int v=-1;in>>v;if(v!=0&&v!=1)throw std::runtime_error("invalid_bool");if(cmd=="wan")sim->cloud.set_connected(v!=0,sim->now*1000);else sim->trusted=v!=0;sim->deadline();}
            else if(cmd=="deadline") sim->deadline();
            else if(cmd=="duplicate") {if(!sim->last_business)throw std::runtime_error("no_business_event");sim->hub.radio_callback(*sim->last_business);sim->hub.run_state_once();sim->deadline();}
            else if(cmd=="ack") {std::string key;in>>key;for(const auto& e:sim->hub.journal().pending_cloud(4096))if(e.key.str()==key)sim->cloud.application_commit_ack(e.key);}
            else if(cmd=="ack_missing") sim->decision_pending=false;
            else if(cmd!="state") throw std::runtime_error("unknown_command");
            sim->print();
        } catch(const std::exception&) {
            GS_ERROR(log::Category::Hub,"T01","simulation.command_failed","invalid_command_or_capacity");
            std::cout<<"{\"error\":\"command_failed\"}"<<std::endl;
        }
    }
}
