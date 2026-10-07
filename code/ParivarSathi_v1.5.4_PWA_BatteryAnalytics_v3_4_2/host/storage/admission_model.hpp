#pragma once
// HOST ONLY. Selected Ledger snapshots are atomic model inputs, not a flash
// protocol. W/C are experiment parameters, NOT approved product limits.
#include "host/storage/lifecycle_model.hpp"
namespace gs::host::storage::admission {
using namespace lifecycle;
enum class Class { Normal, Critical };
template<unsigned Window, unsigned Critical>
class Gate {
    static_assert(Window>0 && Window<=32 && Critical<=Window);
    struct Charge { Key key{}; Class kind=Class::Normal; };
    Ledger ledger_{};
    std::array<Report,6> reports_{};
    std::array<std::array<Charge,Window>,6> charges_{};
    std::array<unsigned,6> counts_{};
public:
    static constexpr unsigned maximum=6*(32+Window);
    std::size_t size()const{return ledger_.size();}
    unsigned uncovered(unsigned node)const{return counts_[node];}
    unsigned normal(unsigned node)const{unsigned n=0;
        for(unsigned j=0;j<counts_[node];++j)n+=charges_[node][j].kind==Class::Normal;
        return n;}
    Result accept(const Key& key,const std::array<std::uint8_t,32>& binding,Class kind){
        // Copy is deliberate: model transactional admission with no partial
        // credit spend. Production should use a bounded prepared transition.
        auto candidate=ledger_;const auto result=candidate.accept(key,binding);
        if(result!=Result::New)return result; // retries/conflicts never spend
        const auto node=key.node;
        if(!reports_[node].covers(key)){
            if(counts_[node]>=Window || (kind==Class::Normal && normal(node)>=Window-Critical))return Result::Full;
            charges_[node][counts_[node]++]={key,kind};
        }
        ledger_=candidate;return Result::New;
    }
    bool select(unsigned node,const Report& next){
        if(node>=6)return false;
        auto candidate=ledger_;if(!candidate.select(static_cast<std::uint8_t>(node),next))return false;
        unsigned kept=0;
        for(unsigned j=0;j<counts_[node];++j)if(!next.covers(charges_[node][j].key))charges_[node][kept++]=charges_[node][j];
        counts_[node]=kept;reports_[node]=next;ledger_=candidate;return true;
    }
};
} // namespace
