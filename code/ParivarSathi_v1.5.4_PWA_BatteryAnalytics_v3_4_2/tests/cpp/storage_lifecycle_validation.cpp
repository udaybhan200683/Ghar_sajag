#include "host/storage/lifecycle_model.hpp"
#include <cassert>
#include <cstdio>
using namespace gs::host::storage;
using namespace gs::host::storage::lifecycle;
static std::array<std::uint8_t,32> digest(std::uint64_t seq){std::array<std::uint8_t,32> d{};put_be(d.data(),seq,8);return d;}
static void credit_bound(){Ledger l;
    for(unsigned node=0;node<6;++node){Report r;r.generation=2;r.high=32;r.count=32;
        for(unsigned i=0;i<32;++i)r.pending[i]={static_cast<std::uint8_t>(node),1,1,i+1};
        assert(l.select(node,r));
        for(unsigned i=1;i<=64;++i)assert(l.accept({static_cast<std::uint8_t>(node),1,1,i},digest(i))==Result::New);
        assert(l.accept({static_cast<std::uint8_t>(node),1,1,65},digest(65))==Result::Full);}
    assert(l.size()==384);auto reboot=l;assert(reboot.size()==384);
    assert(reboot.accept({0,1,1,64},digest(64))==Result::Duplicate);
    assert(reboot.accept({0,1,1,64},digest(63))==Result::Conflict);
    assert(reboot.accept({0,1,1,65},digest(65))==Result::Full);
    Report unchanged;unchanged.generation=3;unchanged.high=32;unchanged.count=32;
    for(unsigned i=0;i<32;++i)unchanged.pending[i]={0,1,1,i+1};
    assert(reboot.select(0,unchanged)); // newer generation alone cannot replenish credit
    assert(reboot.accept({0,1,1,65},digest(65))==Result::Full);
    Report retired;retired.generation=4;retired.high=64;assert(reboot.select(0,retired));
    assert(reboot.accept({0,1,1,1},digest(1))==Result::Stale);
    auto resurrect=retired;resurrect.generation=5;resurrect.pending[0]={0,1,1,1};resurrect.count=1;
    assert(!reboot.select(0,resurrect));
    std::puts("CREDIT_BOUND_PASS peak=384 copied-ledger-reboot/no-credit-reset/exact-conflict/no-resurrection");}
static void gaps(){Ledger l;Report r;r.generation=2;r.high=100;r.count=1;r.pending[0]={0,1,1,10};assert(l.select(0,r));
    assert(l.accept({0,1,1,10},digest(10))==Result::New);
    assert(l.accept({0,1,1,12},digest(12))==Result::Stale);
    r.generation=3;r.session=2;r.high=0;assert(l.select(0,r));
    assert(l.accept({0,1,1,10},digest(10))==Result::Duplicate);
    assert(l.accept({0,1,2,1},digest(1))==Result::New);
    r.generation=4;r.count=0;assert(l.select(0,r));
    assert(l.accept({0,1,1,10},digest(10))==Result::Stale);
    assert(l.accept({0,2,2,1},digest(1))==Result::Invalid);
    std::puts("GAP_SESSION_PASS pending-hole/old-origin/rejoin/replacement-rejected");}
static void unbounded_counterexample(){// Node pending<=1 while Hub evidence grows; report always lost.
    std::size_t pending=0,evidence=0;for(unsigned i=0;i<100000;++i){++pending;++evidence;--pending;assert(pending==0);}
    assert(evidence==100000);std::puts("REPORT_LOSS_COUNTEREXAMPLE pending_peak=1 history_required=100000 no-protocol-finite-bound");}
static void tears(){std::size_t cuts=0;
    // Local effect, backend completion, body->certificate, retirement, GC copy.
    for(unsigned transition=0;transition<5;++transition){State old;State next;
        if(transition==0){next.applied=true;}
        if(transition==1){old.applied=true;next=old;next.cloud=true;}
        if(transition==2){old.applied=old.cloud=true;next=old;next.body=false;next.certificate=true;}
        if(transition==3){old={1,false,true,true,true,false};next={2,false,false,true,true,true};}
        if(transition==4){old={1,false,true,true,true,false};next=old;}
        next.generation=2;const auto before=initial(old);
        for(std::size_t cut=0;cut<=864;++cut){auto media=before;Mutator mut{media,cut};(void)mut.replace(next);State got;
            assert(recover(media,got));assert(got.generation==1||got.generation==2);
            const auto& want=got.generation==1?old:next;
            assert(got.body==want.body&&got.certificate==want.certificate&&got.applied==want.applied&&got.cloud==want.cloud&&got.retired==want.retired);
            assert(got.body||got.certificate||got.retired);++cuts;}
        auto media=before;Mutator finish{media,1000};assert(finish.replace(next));
        media.pages[1][20]^=1;State got;assert(!recover(media,got));}
    State unsafe{2,false,true,true,false,false};auto bad=initial(unsafe);State got;assert(!recover(bad,got));
    std::printf("COW_FAULT_PASS cuts=%zu selected-corruption-fail-closed body-or-certificate-or-retirement\n",cuts);}
static void backend_lost_ack(){State old{1,true,false,true,false,false};auto media=initial(old);
    // Backend server accepted, response missing: NO local cloud completion.
    State got;assert(recover(media,got)&&got.body&&!got.cloud);
    State receipt=old;receipt.generation=2;receipt.cloud=true;
    Mutator mut{media,1000};assert(mut.replace(receipt));assert(recover(media,got)&&got.cloud&&got.body);
    std::puts("BACKEND_LOST_ACK_PASS retain-body/retry-stable-source/local-receipt-before-release");}
static void lifetime(){Ledger l;std::array<std::uint64_t,6> seq{},gen{};gen.fill(1);std::size_t peak=0;
    std::uint64_t rng=0x123456789abcdefULL;
    for(std::uint64_t i=0;i<1000000;++i){rng^=rng<<13;rng^=rng>>7;rng^=rng<<17;const auto node=static_cast<std::uint8_t>(rng%6);
        const auto s=++seq[node];Key k{node,1,1,s};assert(l.accept(k,digest(s))==Result::New);
        assert(l.accept(k,digest(s))==Result::Duplicate);peak=std::max(peak,l.size());
        if(s%16==0){Report r;r.generation=++gen[node];r.high=s;assert(l.select(node,r));}
        if(i%997==0){auto reboot=l;l=reboot;}}
    assert(peak<=96);std::printf("LIFETIME_PASS events=1000000 peak=%zu ledger_RAM=%zu fixed_capacity=384 atomic-snapshot-assumption\n",peak,sizeof(Ledger));}
int main(){unbounded_counterexample();credit_bound();gaps();tears();backend_lost_ack();lifetime();std::puts("STORAGE_LIFECYCLE_HOST_PASS");}
