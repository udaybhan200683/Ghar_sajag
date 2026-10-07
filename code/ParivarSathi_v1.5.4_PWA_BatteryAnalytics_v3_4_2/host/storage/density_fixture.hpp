#pragma once
#include "host/storage/context_codec.hpp"
#include <algorithm>
#include <cstring>

namespace gs::host::storage::density {
inline bool equal(const Event& a,const Event& b) {
    EventBuffer x{},y{};std::size_t nx=0,ny=0;
    return encode_event(a,x,nx)&&encode_event(b,y,ny)&&nx==ny&&x==y;
}
// Deterministic semantic fixtures, not measured households or qualified sensors.
// Other events include domain-only Reed/button/control examples. NodeHealth is
// unsequenced and deliberately does not enter this retained event stream.
inline Event trace(std::uint64_t i,std::uint32_t rate,bool jitter=false) {
    const auto day=i/rate;
    const auto within=static_cast<std::uint32_t>(i%rate);
    const std::uint32_t summary_count=rate==384?120:rate==1776?720:11520;
    const std::uint32_t other=rate==384?24:rate==1776?96:192;
    Event e;e.key={static_cast<std::uint8_t>(i%6),1,1+i/20000,i/6+1};
    e.assignment=1;e.sensor=1;
    e.kind=within>=rate-other?static_cast<std::uint8_t>(1+within%5)
        : ((std::uint64_t{within+1}*summary_count/(rate-other))>
           (std::uint64_t{within}*summary_count/(rate-other))?9:0);
    if(e.kind==1||e.kind==2)e.sensor=2;
    if(e.kind==3||e.kind==4)e.sensor=3;
    if(e.kind==5)e.sensor=4;
    const auto seconds=static_cast<std::int64_t>(day*86400+std::uint64_t{within}*86400/rate);
    e.monotonic=1000000+static_cast<std::int64_t>((i%20000)*86400000/rate);
    e.occurred=1700000000+seconds;
    // One multi-hour backend outage/recovery fixture every fourth day does not
    // change Hub receive time/Node online episode profile. A sparse radio delay
    // does change receive time, and remains immutable on cloud retry.
    e.received=e.occurred+(i%211==0?7200:(jitter&&i%7==0?2:1));
    if(jitter)e.monotonic+=static_cast<std::int64_t>((i*23)%50)*20; // GPIO poll granularity
    e.uncertainty=i%997==0?3600:2;
    e.battery=0;e.rssi=static_cast<std::int16_t>(-65-static_cast<int>(i%5));
    if(e.kind==9){e.additional=1+static_cast<std::uint32_t>(i%20);e.first=e.monotonic-45000;e.last=e.monotonic;}
    return e;
}
inline Context context_for(std::uint64_t start,std::uint32_t rate,std::uint64_t serial=1,bool jitter=false) {
    Context c;c.serial=serial;c.count=6;c.domain[0]=42;
    for(std::uint8_t i=0;i<6;++i) {
        c.base[i]=trace(start+i,rate,jitter);c.base[i].kind=0;c.base[i].additional=0;
        c.base[i].first=0;c.base[i].last=0;
    }
    return c;
}
// Mock byte-addressed sector: CRC/commit models tears only, never production
// authentication. Recovery requires externally selected authoritative extent.
struct Sector {
    std::array<std::uint8_t,sector_bytes> bytes{};
    std::array<std::uint16_t,max_records> offsets{};
    std::size_t extent{0},count{0};
    Context context{};
    bool init(const Context& c) {
        ContextBuffer b{};std::size_t n=0;if(!encode_context(c,b,n))return false;
        bytes.fill(255);std::copy_n(b.begin(),n,bytes.begin());
        context=c;extent=n;count=0;return true;
    }
    bool append(const Event& e) {
        Buffer b{};std::size_t n=0;
        if(!encode(Mode::Relations,context,e,b,n)||n>max_plain||extent>sector_bytes)return false;
        const auto total=aligned(2+n+4+4);
        if(count==max_records||total>sector_bytes-extent)return false;
        auto* p=bytes.data()+extent;std::fill_n(p,total,0);
        put_be(p,n,2);std::copy_n(b.begin(),n,p+2);
        put_be(p+2+n,crc32(p,2+n),4);put_be(p+6+n,0xc01dcafeU,4);
        offsets[count++]=static_cast<std::uint16_t>(extent);extent+=total;return true;
    }
    bool read(std::size_t index,Event& out) const {
        if(index>=count)return false;
        const auto offset=offsets[index];if(offset+2U>extent)return false;
        const auto* p=bytes.data()+offset;const auto n=static_cast<std::size_t>(get_be(p,2));
        if(n>max_plain||aligned(n+10)>extent-offset||get_be(p+6+n,4)!=0xc01dcafeU||
           get_be(p+2+n,4)!=crc32(p,n+2))return false;
        return decode(Mode::Relations,context,p+2,n,out);
    }
    bool recover(std::size_t selected_extent,std::size_t selected_count,
                 std::uint64_t serial,std::uint32_t epoch,
                 const std::array<std::uint8_t,16>& domain) {
        if(selected_extent>sector_bytes||selected_count>max_records)return false;
        const auto header=static_cast<std::size_t>(get_be(bytes.data()+6,2));
        Context c;if(header>selected_extent||!decode_context(bytes.data(),header,serial,epoch,domain,c))return false;
        auto at=header;std::array<std::uint16_t,max_records> rebuilt{};
        for(std::size_t i=0;i<selected_count;++i) {
            if(at+2>selected_extent)return false;
            const auto* p=bytes.data()+at;const auto n=static_cast<std::size_t>(get_be(p,2));
            const auto total=aligned(n+10);Event event;
            if(n>max_plain||total>selected_extent-at||get_be(p+6+n,4)!=0xc01dcafeU||
               get_be(p+2+n,4)!=crc32(p,n+2)||!decode(Mode::Relations,c,p+2,n,event))return false;
            for(std::size_t j=n+10;j<total;++j)if(p[j])return false;
            rebuilt[i]=static_cast<std::uint16_t>(at);at+=total;
        }
        if(at!=selected_extent)return false;
        context=c;extent=at;count=selected_count;offsets=rebuilt;return true;
    }
};
} // namespace gs::host::storage::density
