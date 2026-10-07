#include "host/storage/efficient_core.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <new>

static std::size_t allocations=0;
void* operator new(std::size_t size) {
    ++allocations;
    if (void* p=std::malloc(size ? size : 1)) return p;
    throw std::bad_alloc();
}
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }

using namespace gs::host::storage;
static void require(bool good) {
    if (!good) { std::fputs("storage efficiency validation FAILED\n",stderr); std::abort(); }
}
static Event event_for(std::uint64_t sequence) {
    Event e;
    e.key={static_cast<std::uint8_t>(sequence%6),1,1,sequence};
    e.assignment=1; e.sensor=1;
    e.monotonic=static_cast<std::int64_t>(sequence);
    e.occurred=1700000000; e.received=1700000001; e.uncertainty=1;
    return e;
}
static bool equal(const Event& a,const Event& b) {
    EventBuffer x{},y{}; std::size_t nx=0,ny=0;
    return encode_event(a,x,nx) && encode_event(b,y,ny) && nx==ny && x==y;
}
struct ConstantHash { std::uint32_t operator()(const KeyBytes&) const { return 1023; } };

template<std::size_t N,class Hash=KeyHash>
static void index_cases() {
    ExactIndex<N,Hash> index;
    for (std::size_t i=1;i<=N;++i) require(index.insert(event_for(i).key,i)==Insert::Added);
    require(index.size()==N);
    require(index.insert(event_for(N+1).key,1)==Insert::Full);
    require(index.insert(event_for(1).key,1)==Insert::Present);
    require(index.insert(event_for(1).key,2)==Insert::HandleConflict);
    Key invalid{6,1,1,1}; require(index.insert(invalid,1)==Insert::Invalid);
    for (std::size_t i=1;i<=N;i+=2) require(index.erase(event_for(i).key));
    for (std::size_t i=1;i<=N;++i) {
        std::uint32_t handle=0;
        require(index.find(event_for(i).key,handle)==(i%2==0));
        if (i%2==0) require(handle==i);
    }
    for (std::size_t i=1;i<=N;i+=2) require(index.insert(event_for(i).key,i)==Insert::Added);
    // Same origin/sequence in another enrollment must not alias.
    auto replacement=event_for(1).key; replacement.enrollment=2;
    std::uint32_t handle=0; require(!index.find(replacement,handle));
    for (std::size_t i=N;i>0;--i) require(index.erase(event_for(i).key));
    require(index.size()==0 && !index.erase(event_for(1).key));
    Key maximum{5,UINT32_MAX,UINT64_MAX,UINT64_MAX};
    require(index.insert(maximum,UINT32_MAX)==Insert::Added);
    require(index.find(maximum,handle) && handle==UINT32_MAX);
    maximum.sequence=0; require(index.insert(maximum,1)==Insert::Invalid);
}
static void codec_cases() {
    constexpr std::uint8_t crc_golden[]{'1','2','3','4','5','6','7','8','9'};
    require(crc32(crc_golden,sizeof(crc_golden))==0xcbf43926U);
    for (std::uint8_t kind=0;kind<10;++kind) {
        auto e=event_for(1); e.kind=kind;
        if (kind==9) { e.additional=UINT32_MAX; e.first=0; e.last=INT64_MAX; }
        e.key={5,UINT32_MAX,UINT64_MAX,UINT64_MAX}; e.assignment=UINT32_MAX;
        e.monotonic=INT64_MIN; e.occurred=INT64_MAX; e.received=-1;
        e.uncertainty=UINT32_MAX; e.battery=UINT16_MAX; e.rssi=INT16_MIN; e.test=true;
        EventBuffer bytes{}; std::size_t size=0; Event decoded;
        require(encode_event(e,bytes,size) && decode_event(bytes.data(),size,decoded) && equal(e,decoded));
        require(bytes[0]==1 && bytes[4]==5 && bytes[8]==255 && bytes[16]==255);
        for (std::size_t length=0;length<size;++length) {
            auto sentinel=event_for(99);
            require(!decode_event(bytes.data(),length,sentinel) && equal(sentinel,event_for(99)));
        }
        for (std::size_t bit=0;bit<size*8;++bit) {
            auto corrupt=bytes; corrupt[bit/8]^=1U<<(bit%8);
            require(!decode_event(corrupt.data(),size,decoded));
        }
        for (auto offset : {0U,1U,2U,3U,4U,5U}) {
            auto malformed=bytes; malformed[offset]=255;
            put_be(malformed.data()+size-4,crc32(malformed.data(),size-4),4);
            require(!decode_event(malformed.data(),size,decoded));
        }
    }
    auto bad=event_for(1); bad.kind=9; bad.additional=1; bad.first=10; bad.last=9;
    EventBuffer buffer{}; buffer.fill(7); auto original=buffer; std::size_t size=123;
    require(!encode_event(bad,buffer,size) && buffer==original && size==123);
    bad=event_for(1); bad.rssi=INT16_MAX;
    require(encode_event(bad,buffer,size)); Event out;
    require(decode_event(buffer.data(),size,out) && equal(bad,out));
    require(!decode_event(nullptr,size,out));
    auto conflicting=bad; conflicting.battery=1;
    require(key_bytes(conflicting.key)==key_bytes(bad.key) && !equal(conflicting,bad));
    std::array<std::uint8_t,ordinary_bytes*2> segment{};
    for (std::size_t i=0;i<2;++i) {
        require(encode_event(event_for(i+1),buffer,size));
        for (std::size_t j=0;j<size;++j) segment[i*ordinary_bytes+j]=buffer[j];
    }
    RecordCursor cursor(segment.data(),segment.size());
    require(cursor.next(out) && out.key.sequence==1 && cursor.next(out) && out.key.sequence==2);
    require(cursor.done() && !cursor.next(out));
    RecordCursor truncated(segment.data(),segment.size()-1);
    require(truncated.next(out) && !truncated.next(out) && truncated.offset()==ordinary_bytes);
    // Deterministic fuzz input; parser must leave output/offset unchanged on failure.
    std::uint32_t random=12345;
    for (unsigned trial=0;trial<50000;++trial) {
        for (auto& byte:buffer) { random=random*1664525U+1013904223U; byte=random>>24; }
        const auto length=trial%(buffer.size()+1); auto sentinel=event_for(99);
        if (!decode_event(buffer.data(),length,sentinel)) require(equal(sentinel,event_for(99)));
    }
}
static void stats_cases() {
    Moments stats;
    for (std::uint16_t value : {0,2,4,6,8}) require(stats.update(value));
    require(stats.valid() && stats.mean()==4 && stats.variance()==8);
    StatsBuffer bytes{}; require(encode_stats(stats,bytes)); Moments recovered;
    require(decode_stats(bytes.data(),bytes.size(),recovered));
    require(recovered.sum==stats.sum && recovered.squares==stats.squares && recovered.count==5);
    for (std::size_t i=0;i<bytes.size();++i) {
        auto corrupt=bytes; corrupt[i]^=1;
        require(!decode_stats(corrupt.data(),corrupt.size(),recovered));
        require(!decode_stats(bytes.data(),i,recovered));
    }
    Moments maximum{UINT32_MAX,std::uint64_t{UINT32_MAX}*UINT16_MAX,
        std::uint64_t{UINT32_MAX}*UINT16_MAX*UINT16_MAX};
    require(maximum.valid() && encode_stats(maximum,bytes));
    const auto old=maximum; require(!maximum.update(1));
    require(old.count==maximum.count && old.sum==maximum.sum && old.squares==maximum.squares);
    Moments invalid{1,100,1}; require(!invalid.valid() && !encode_stats(invalid,bytes));
    Moments overflow{1,UINT64_MAX,UINT64_MAX}; require(!overflow.update(1));
    Moments sequence;
    for (std::uint16_t i=0;i<1000;++i) require(sequence.update(i));
    require(sequence.mean()==499.5 && std::abs(sequence.variance()-83333.25)<0.0001);
}
static void random_index_churn() {
    ExactIndex<416> index;
    std::array<bool,832> present{};
    std::size_t count=0; std::uint32_t random=42;
    for (unsigned trial=0;trial<50000;++trial) {
        random=random*1664525U+1013904223U;
        const auto selected=(random>>8)%present.size();
        const auto key=event_for(selected+1).key;
        if (random&1) {
            const auto result=index.insert(key,selected);
            if (present[selected]) require(result==Insert::Present);
            else if (count==416) require(result==Insert::Full);
            else { require(result==Insert::Added); present[selected]=true; ++count; }
        } else {
            require(index.erase(key)==present[selected]);
            if (present[selected]) { present[selected]=false; --count; }
        }
        require(index.size()==count);
        if (trial%127==0) for (std::size_t i=0;i<present.size();++i) {
            std::uint32_t handle=0;
            require(index.find(event_for(i+1).key,handle)==present[i]);
            if (present[i]) require(handle==i);
        }
    }
}
static void million_events() {
    // Host-only bounded record fixture, not a persistent/crash-qualified engine.
    // Explicitly retire each owner's references before reuse; no age policy.
    struct Row { EventBuffer payload{}; std::uint8_t owners{0}; };
    std::array<Row,192> records{};
    ExactIndex<416> index;
    const auto allocation_start=allocations;
    for (std::uint64_t i=1;i<=1000000;++i) {
        const auto slot=static_cast<std::size_t>((i-1)%records.size());
        auto& row=records[slot];
        if (row.owners) {
            Event previous; require(decode_event(row.payload.data(),ordinary_bytes,previous));
            // Three logical owners, one immutable blob. A cloud completion
            // alone does not free correctness/history ownership.
            row.owners&=~2U; require(row.owners!=0);
            row.owners&=~1U; require(row.owners!=0);
            row.owners&=~4U; require(row.owners==0);
            require(index.erase(previous.key));
        }
        const auto event=event_for(i); std::size_t length=0;
        require(encode_event(event,row.payload,length) && length==ordinary_bytes);
        row.owners=7;
        require(index.insert(event.key,slot)==Insert::Added);
        std::uint32_t handle=0; require(index.find(event.key,handle) && handle==slot);
        require(index.size()<=192);
        if (i%4096==0) {
            // Reboot-style reconstruct: validate frames before rebuilding exact
            // keys. This does not model flash power cuts/root activation.
            ExactIndex<416> restored;
            for (std::size_t j=0;j<records.size();++j) {
                Event decoded;
                require(records[j].owners && decode_event(records[j].payload.data(),ordinary_bytes,decoded));
                require(restored.insert(decoded.key,j)==Insert::Added);
            }
            index=restored;
        }
    }
    require(index.size()==192 && allocations==allocation_start);
    std::printf("LONG_RUN_EVENTS=1000000 LIVE_RECORDS=192 FIXED_RECORD_POOL_BYTES=%zu INDEX_BYTES=%zu HOT_NEW_ALLOCATIONS=0\n",
        sizeof(records),sizeof(index));
}
int main() {
    codec_cases(); stats_cases();
    index_cases<192>(); index_cases<384>(); index_cases<416>();
    index_cases<416,ConstantHash>();
    random_index_churn();
    million_events();
    std::puts("storage efficiency core validation PASS (codec, CRC, bounds, collisions, wrap, stats, parser, reconstruction)");
}
