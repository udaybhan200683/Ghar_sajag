#include "host/storage/efficient_core.hpp"
#include "storage/journal.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>

static std::size_t allocation_calls=0,live_bytes=0;
struct alignas(std::max_align_t) Allocation { std::size_t size; };
void* operator new(std::size_t size) {
    auto* header=static_cast<Allocation*>(std::malloc(sizeof(Allocation)+(size ? size : 1)));
    if (!header) throw std::bad_alloc();
    header->size=size; ++allocation_calls; live_bytes+=size;
    return header+1;
}
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete(void* pointer) noexcept {
    if (!pointer) return;
    auto* header=static_cast<Allocation*>(pointer)-1;
    live_bytes-=header->size; std::free(header);
}
void operator delete[](void* p) noexcept { ::operator delete(p); }
void operator delete(void* p,std::size_t) noexcept { ::operator delete(p); }
void operator delete[](void* p,std::size_t) noexcept { ::operator delete(p); }

using namespace gs::host::storage;
using Clock=std::chrono::steady_clock;
static volatile std::uint64_t sink=0;
template<class Operation>
static double median_ns(Operation op,std::size_t iterations=200000) {
    std::array<double,9> times{};
    for (unsigned round=0;round<10;++round) {
        const auto start=Clock::now();
        for (std::size_t i=0;i<iterations;++i) sink+=op(i);
        const auto elapsed=std::chrono::duration<double,std::nano>(Clock::now()-start).count()/iterations;
        if (round) times[round-1]=elapsed;
    }
    std::sort(times.begin(),times.end()); return times[4];
}
static Event event_for(std::size_t i) {
    Event e; e.key={static_cast<std::uint8_t>(i%6),1,1,i+1};
    e.assignment=1; e.kind=0; e.sensor=1; e.monotonic=i;
    e.occurred=1700000000; e.received=1700000001; return e;
}
static gs::DomainEvent domain_for(std::size_t i) {
    gs::DomainEvent e;
    auto physical=std::string(32,'p'); physical.back()=static_cast<char>('a'+i%6);
    e.key=gs::EventKey("node-"+std::to_string(i%6+1),1,i+1,physical);
    e.location="kitchen"; e.kind=gs::EventKind::Motion; e.sensor_type=gs::SensorType::Pir;
    e.monotonic_ms=i; e.occurred_at=1700000000; e.received_at=1700000001;
    return e;
}
template<std::size_t N>
static void lookup_comparison() {
    std::array<KeyBytes,N> keys{},sorted{};
    std::array<std::uint16_t,N> fingerprints{};
    std::array<std::array<KeyBytes,N>,6> per_node{};
    std::array<std::size_t,6> counts{};
    ExactIndex<N> index;
    for (std::size_t i=0;i<N;++i) {
        const auto key=event_for(i).key;
        keys[i]=key_bytes(key); sorted[i]=keys[i];
        fingerprints[i]=static_cast<std::uint16_t>(KeyHash{}(keys[i]));
        per_node[key.node][counts[key.node]++]=keys[i];
        if (index.insert(key,i)!=Insert::Added) std::abort();
    }
    std::sort(sorted.begin(),sorted.end());
    const auto linear=median_ns([&](std::size_t i) {
        const auto& key=keys[i%N];
        for (std::size_t j=0;j<N;++j) if (keys[j]==key) return j+1;
        return std::size_t{0};
    });
    const auto binary=median_ns([&](std::size_t i) {
        const auto& key=keys[i%N];
        const auto found=std::lower_bound(sorted.begin(),sorted.end(),key);
        return found!=sorted.end() && *found==key;
    });
    const auto hash=median_ns([&](std::size_t i) {
        std::uint32_t handle=0; return index.find(event_for(i%N).key,handle) ? handle+1U : 0U;
    });
    const auto fingerprint=median_ns([&](std::size_t i) {
        const auto& key=keys[i%N]; const auto h=static_cast<std::uint16_t>(KeyHash{}(key));
        for (std::size_t j=0;j<N;++j)
            if (fingerprints[j]==h && keys[j]==key) return j+1;
        return std::size_t{0};
    });
    const auto node=median_ns([&](std::size_t i) {
        const auto& key=keys[i%N]; const auto& row=per_node[key[0]];
        const auto found=std::lower_bound(row.begin(),row.begin()+counts[key[0]],key);
        return found!=row.begin()+counts[key[0]] && *found==key;
    });
    const auto mutation=median_ns([&](std::size_t i) {
        const auto key=event_for(i%N).key;
        const auto removed=index.erase(key);
        const auto added=index.insert(key,i%N)==Insert::Added;
        return removed && added;
    });
    std::array<double,9> retire_times{};
    for (unsigned round=0;round<10;++round) {
        double elapsed=0;
        for (unsigned batch=0;batch<128;++batch) {
            ExactIndex<N> fresh;
            for (std::size_t i=0;i<N;++i) fresh.insert(event_for(i).key,i);
            const auto start=Clock::now();
            for (std::size_t i=0;i<N;++i) sink+=fresh.erase(event_for(i).key);
            elapsed+=std::chrono::duration<double,std::nano>(Clock::now()-start).count()/N/128;
        }
        if (round) retire_times[round-1]=elapsed;
    }
    std::sort(retire_times.begin(),retire_times.end());
    std::printf("LOOKUP N=%zu ns median9 linear=%.2f sorted=%.2f hash=%.2f fingerprint_exact=%.2f per_node_sorted=%.2f erase_insert=%.2f index_RAM=%zu\n",
        N,linear,binary,hash,fingerprint,node,mutation,sizeof(index));
    std::printf("RETIRE N=%zu hash_erase_ns=%.2f (128 batches/round, median9)\n",N,retire_times[4]);
}
template<std::size_t N>
static void pipeline_comparison() {
    std::array<gs::DomainEvent,N> domains{};
    std::array<Event,N> events{};
    for (std::size_t i=0;i<N;++i) { domains[i]=domain_for(i); events[i]=event_for(i); }
    std::array<double,9> old_new{},new_new{};
    std::size_t baseline_heap=0,baseline_allocations=0;
    for (unsigned round=0;round<10;++round) {
      double old_time=0,new_time=0;
      for (unsigned batch=0;batch<128;++batch) {
        gs::hub::HubJournal journal(N); // Volatile reference; not production persistence.
        auto allocated=allocation_calls; auto live=live_bytes;
        auto start=Clock::now();
        for (const auto& event:domains) sink+=journal.commit(event)==gs::hub::CommitResult::Stored;
        old_time+=std::chrono::duration<double,std::nano>(Clock::now()-start).count()/N/128;
        baseline_heap=live_bytes-live; baseline_allocations=allocation_calls-allocated;
        ExactIndex<N> index; std::array<EventBuffer,N> records{};
        allocated=allocation_calls;
        start=Clock::now();
        for (std::size_t i=0;i<N;++i) {
            std::size_t length=0;
            if (!encode_event(events[i],records[i],length)) std::abort();
            sink+=index.insert(events[i].key,i)==Insert::Added;
        }
        new_time+=std::chrono::duration<double,std::nano>(Clock::now()-start).count()/N/128;
        if (allocation_calls!=allocated) std::abort();
        // Keep the entire encoded outputs observable, not merely success flags.
        for (const auto& record:records) sink+=crc32(record.data(),ordinary_bytes);
      }
        if (round) { old_new[round-1]=old_time; new_new[round-1]=new_time; }
    }
    std::sort(old_new.begin(),old_new.end()); std::sort(new_new.begin(),new_new.end());
    gs::hub::HubJournal journal(N);
    for (const auto& event:domains) journal.commit(event);
    const auto current_duplicate=median_ns([&](std::size_t i) {
        return journal.commit(domains[i%N])==gs::hub::CommitResult::Duplicate;
    });
    ExactIndex<N> index;
    for (std::size_t i=0;i<N;++i) index.insert(events[i].key,i);
    const auto optimized_lookup=median_ns([&](std::size_t i) {
        std::uint32_t handle=0; return index.find(events[i%N].key,handle);
    });
    const auto calls_before=allocation_calls;
    for (unsigned i=0;i<1000;++i) journal.commit(domains[i%N]);
    const auto duplicate_allocations=allocation_calls-calls_before;
    std::printf("PIPELINE N=%zu ns median9 current_volatile_commit=%.2f proposed_CRC_encode_index=%.2f current_key_duplicate=%.2f proposed_key_lookup=%.2f baseline_retained_heap=%zu baseline_new_calls=%zu duplicate_new_calls_per1000=%zu proposed_heap=0 fixed_index_plus_frames=%zu\n",
        N,old_new[4],new_new[4],current_duplicate,optimized_lookup,baseline_heap,baseline_allocations,
        duplicate_allocations,sizeof(index)+N*sizeof(EventBuffer));
}
int main() {
    std::puts("HOST_ONLY timings; no ESP32 cycle or persistent commit performance claims. Warmup + median of 9 rounds; new insertions 128 batches/round.");
    lookup_comparison<192>(); lookup_comparison<384>(); lookup_comparison<416>();
    pipeline_comparison<192>(); pipeline_comparison<384>(); pipeline_comparison<416>();
    auto event=event_for(1); EventBuffer buffer{}; std::size_t length=0;
    encode_event(event,buffer,length); Event decoded;
    const auto encode=median_ns([&](std::size_t i) { event.key.sequence=i+1; return encode_event(event,buffer,length); });
    const auto decode=median_ns([&](std::size_t) { return decode_event(buffer.data(),length,decoded) ? decoded.key.sequence : 0; });
    Moments moments; StatsBuffer stats{};
    const auto update=median_ns([&](std::size_t i) { return moments.update(i%65536) ? moments.sum : 0; });
    encode_stats(moments,stats); Moments restored;
    const auto stats_encode=median_ns([&](std::size_t) { return encode_stats(moments,stats); });
    const auto stats_decode=median_ns([&](std::size_t) { return decode_stats(stats.data(),stats.size(),restored) ? restored.sum : 0; });
    std::array<std::uint8_t,256*stats_bytes> checkpoint{};
    const auto checkpoint_encode=median_ns([&](std::size_t) {
        for (std::size_t i=0;i<256;++i) {
            if (!encode_stats(moments,stats)) std::abort();
            std::memcpy(checkpoint.data()+i*stats_bytes,stats.data(),stats.size());
        }
        return checkpoint[24];
    },2000);
    const auto checkpoint_decode=median_ns([&](std::size_t) {
        std::uint64_t total=0;
        for (std::size_t i=0;i<256;++i) {
            if (!decode_stats(checkpoint.data()+i*stats_bytes,stats_bytes,restored)) std::abort();
            total+=restored.count;
        }
        return total;
    },2000);
    std::array<std::uint8_t,ordinary_bytes*32> records{};
    for (std::size_t i=0;i<32;++i) std::memcpy(records.data()+i*ordinary_bytes,buffer.data(),ordinary_bytes);
    const auto parse=median_ns([&](std::size_t) {
        RecordCursor cursor(records.data(),records.size()); std::uint64_t total=0;
        while (cursor.next(decoded)) total+=decoded.key.sequence;
        return total;
    },5000);
    gs::security::Bytes old_encoded;
    const auto old_event=domain_for(1);
    gs::hub::HubJournal::encode_event_payload(old_event,old_encoded);
    const auto old_encode=median_ns([&](std::size_t) {
        return gs::hub::HubJournal::encode_event_payload(old_event,old_encoded) ? old_encoded.size() : 0;
    });
    std::printf("PRIMITIVES ns CRC_event_encode=%.2f CRC_event_decode=%.2f current_payload_encode_reused_vector=%.2f moments_update=%.2f stats_encode=%.2f stats_decode=%.2f checkpoint_fixture_7168B_encode=%.2f checkpoint_fixture_decode=%.2f segment_parse_32records=%.2f\n",
        encode,decode,old_encode,update,stats_encode,stats_decode,checkpoint_encode,checkpoint_decode,parse);
    std::printf("SIZES current_sample_payload=%zu legacy_envelope=%zu DomainEvent=%zu EventKey=%zu compact_frame=%zu summary_frame=%zu Moments=%zu checksum=%llu\n",
        old_encoded.size(),old_encoded.size()+28,sizeof(gs::DomainEvent),sizeof(gs::EventKey),ordinary_bytes,summary_bytes,sizeof(Moments),
        static_cast<unsigned long long>(sink));
}
