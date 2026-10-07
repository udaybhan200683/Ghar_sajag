#include "host/storage/admission_model.hpp"
#include <cassert>
#include <cstdio>
using namespace gs::host::storage;
using namespace gs::host::storage::admission;
static auto binding(std::uint64_t n){std::array<std::uint8_t,32> b{};put_be(b.data(),n,8);return b;}
template<unsigned W,unsigned C>static void limit(){Gate<W,C> gate;
    for(unsigned node=0;node<6;++node){Report r;r.generation=2;r.high=32;r.count=32;
        for(unsigned j=0;j<32;++j)r.pending[j]={static_cast<std::uint8_t>(node),1,1,j+1};
        assert(gate.select(node,r));
        for(unsigned j=1;j<=32;++j)assert(gate.accept({static_cast<std::uint8_t>(node),1,1,j},binding(j),Class::Normal)==Result::New);
        for(unsigned j=0;j<W-C;++j)assert(gate.accept({static_cast<std::uint8_t>(node),1,1,33+j},binding(33+j),Class::Normal)==Result::New);
        assert(gate.accept({static_cast<std::uint8_t>(node),1,1,33+W-C},binding(33+W-C),Class::Normal)==Result::Full);
        for(unsigned j=W-C;j<W;++j)assert(gate.accept({static_cast<std::uint8_t>(node),1,1,33+j},binding(33+j),Class::Critical)==Result::New);
        assert(gate.accept({static_cast<std::uint8_t>(node),1,1,33+W},binding(33+W),Class::Critical)==Result::Full);
        assert(gate.uncovered(node)==W);
        assert(gate.accept({static_cast<std::uint8_t>(node),1,1,32+W},binding(32+W),Class::Normal)==Result::Duplicate);
        assert(gate.accept({static_cast<std::uint8_t>(node),1,1,32+W},binding(0),Class::Critical)==Result::Conflict);
        auto reboot=gate;gate=reboot; // assumed selected persistent snapshot
        assert(!gate.select(node,r)); // replay
        auto unchanged=r;unchanged.generation=3;assert(gate.select(node,unchanged));
        assert(gate.uncovered(node)==W);assert(!gate.select(node,r));
    }
    assert((gate.size()==Gate<W,C>::maximum));
    Report next;next.generation=4;next.high=32+W;next.count=1;next.pending[0]={0,1,1,7};
    assert(gate.select(0,next));assert(gate.uncovered(0)==0);
    assert(gate.accept({0,1,1,7},binding(7),Class::Critical)==Result::Duplicate);
    assert(gate.accept({0,1,1,8},binding(8),Class::Normal)==Result::Stale);
    next.generation=5;next.session=2;next.high=0;assert(gate.select(0,next));
    assert(gate.accept({0,1,2,1},binding(1),Class::Critical)==Result::New);
    next.generation=6;assert(gate.select(0,next));assert(gate.uncovered(0)==1); // session alone is not credit
    auto bad=next;bad.generation=7;bad.session=1;assert(!gate.select(0,bad));
    bad=next;bad.enrollment=2;assert(!gate.select(0,bad));
    next.generation=UINT64_MAX;assert(gate.select(0,next));next.generation=0;assert(!gate.select(0,next));
    std::printf("ADMISSION_BOUND W=%u C=%u maximum=%u reserve-survives-normal-saturation PASS\n",W,C,Gate<W,C>::maximum);
}
static void lifetime(){Gate<32,4> g; // 4 is a TEST parameter, not a critical-rate promise
    std::array<std::uint64_t,6> seq{},gen{};gen.fill(1);std::size_t peak=0;
    for(std::uint64_t i=0;i<1000000;++i){auto node=static_cast<std::uint8_t>(i%6);auto s=++seq[node];
        Key key{node,1,1,s};assert(g.accept(key,binding(s),s%17?Class::Normal:Class::Critical)==Result::New);
        assert(g.accept(key,binding(s),Class::Normal)==Result::Duplicate);peak=std::max(peak,g.size());
        if(s%24==0){Report r;r.generation=++gen[node];r.high=s;assert(g.select(node,r));}
        if(i%997==0){auto recovered=g;g=recovered;}
    }
    assert(peak<=144);std::printf("ADMISSION_LIFETIME events=1000000 peak=%zu fixed_RAM=%zu atomic-snapshot-assumption PASS\n",peak,sizeof(g));
}
int main(){limit<1,1>();limit<8,2>();limit<32,1>();limit<32,4>();limit<32,16>();limit<32,32>();lifetime();
    std::puts("STORAGE_ADMISSION_HOST_PASS no-false-ACK report-replay/gaps/session/no-credit-reset");}
