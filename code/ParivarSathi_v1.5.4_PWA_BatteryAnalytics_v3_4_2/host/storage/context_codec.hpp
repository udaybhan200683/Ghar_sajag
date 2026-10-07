#pragma once

// HOST-ONLY experimental lossless codecs. CRC is not authentication. These
// types do not implement admission, a durable ACK, retirement or flash erase.
#include "host/storage/efficient_core.hpp"
#include <type_traits>

namespace gs::host::storage::density {
constexpr std::size_t max_contexts=6, sector_bytes=4096;
constexpr std::size_t context_prefix=36, context_row=58;
// One context is the smallest context-backed header (114 authenticated bytes).
// Smallest record has 2-byte header + four 1-byte values + 2-byte length.
constexpr std::size_t max_records=(sector_bytes-(context_prefix+context_row+20))/8;
static_assert(max_records==497,"derived independently restartable record bound");
constexpr std::size_t authenticated_context_bytes=context_prefix+max_contexts*context_row+20;
static_assert(authenticated_context_bytes==404,"no per-row padding or derivable header fields");
constexpr std::size_t max_context_bytes=context_prefix+max_contexts*context_row+4;
constexpr std::size_t max_plain=128;
using Buffer=std::array<std::uint8_t,max_plain>;
using ContextBuffer=std::array<std::uint8_t,max_context_bytes>;
enum class Mode : std::uint8_t { Fixed, Varint, Delta, Context, Presence, Relations };
struct Context {
    std::uint64_t serial{1};
    std::uint32_t epoch{1};
    std::array<std::uint8_t,16> domain{};
    std::array<Event,max_contexts> base{};
    std::uint8_t count{0};
};
struct Writer {
    Buffer bytes{};
    std::size_t at{0};
    bool byte(std::uint8_t v) {
        if(at==bytes.size())return false;
        bytes[at++]=v;return true;
    }
    bool var(std::uint64_t v) {
        do {const auto b=static_cast<std::uint8_t>(v&127U);v>>=7;
            if(!byte(static_cast<std::uint8_t>(b|(v?128U:0U))))return false;
        } while(v);
        return true;
    }
};
struct Reader {
    const std::uint8_t* data;
    std::size_t size,at{0};
    bool byte(std::uint8_t& v) {
        if(!data||at==size)return false;
        v=data[at++];return true;
    }
    bool var(std::uint64_t& v) {
        v=0;
        for(unsigned n=0;n<10;++n) {
            std::uint8_t b=0;if(!byte(b))return false;
            if(n==9 && (b&254U))return false;
            v|=static_cast<std::uint64_t>(b&127U)<<(7*n);
            if(!(b&128U))return n==0 || b!=0; // reject overlong encodings
        }
        return false;
    }
};
inline std::uint64_t zig(std::int64_t v) {
    return v>=0 ? static_cast<std::uint64_t>(v)<<1
        : (static_cast<std::uint64_t>(-(v+1))<<1)|1U;
}
inline std::int64_t unzig(std::uint64_t v) {
    return signed64((v>>1)^(0U-(v&1U)));
}
inline bool subtract(std::int64_t value,std::int64_t base,std::int64_t& out) {
    if((base>0 && value<INT64_MIN+base)||(base<0 && value>INT64_MAX+base))return false;
    out=value-base;return true;
}
inline bool add(std::int64_t base,std::int64_t delta,std::int64_t& out) {
    if((delta>0 && base>INT64_MAX-delta)||(delta<0 && base<INT64_MIN-delta))return false;
    out=base+delta;return true;
}
inline bool same_binding(const Event& a,const Event& b) {
    return a.key.node==b.key.node && a.key.enrollment==b.key.enrollment &&
        a.assignment==b.assignment && a.key.session==b.key.session;
}
inline bool valid_context(const Context& c) {
    if(!c.serial||!c.epoch||c.count>max_contexts)return false;
    for(std::size_t i=0;i<c.count;++i) {
        if(!valid_event(c.base[i])||c.base[i].kind==9)return false;
        for(std::size_t j=0;j<i;++j)if(same_binding(c.base[i],c.base[j]))return false;
    }
    return true;
}
inline bool encode_context(const Context& c,ContextBuffer& out,std::size_t& size) {
    if(!valid_context(c))return false;
    ContextBuffer b{};
    b[0]='G';b[1]='D';b[2]='C';b[3]='1';b[4]=2;b[5]=c.count;
    const auto n=context_prefix+context_row*c.count+4;
    put_be(b.data()+6,n,2);put_be(b.data()+8,c.serial,8);put_be(b.data()+16,c.epoch,4);
    for(std::size_t i=0;i<c.domain.size();++i)b[20+i]=c.domain[i];
    for(std::size_t i=0;i<c.count;++i) {
        const auto& e=c.base[i];auto* p=b.data()+context_prefix+i*context_row;
        p[0]=e.key.node;p[1]=e.sensor;
        put_be(p+2,e.key.enrollment,4);put_be(p+6,e.assignment,4);
        put_be(p+10,e.key.session,8);put_be(p+18,e.key.sequence,8);
        put_be(p+26,static_cast<std::uint64_t>(e.monotonic),8);
        put_be(p+34,static_cast<std::uint64_t>(e.occurred),8);
        put_be(p+42,static_cast<std::uint64_t>(e.received),8);
        put_be(p+50,e.uncertainty,4);put_be(p+54,e.battery,2);
        put_be(p+56,static_cast<std::uint16_t>(e.rssi),2);
    }
    put_be(b.data()+n-4,crc32(b.data(),n-4),4);out=b;size=n;return true;
}
inline bool decode_context(const std::uint8_t* p,std::size_t n,
                           std::uint64_t serial,std::uint32_t epoch,
                           const std::array<std::uint8_t,16>& domain,Context& out) {
    if(!p||n<context_prefix+4||n>max_context_bytes||p[0]!='G'||p[1]!='D'||p[2]!='C'||
       p[3]!='1'||p[4]!=2||p[5]>max_contexts||get_be(p+6,2)!=n||
       n!=context_prefix+context_row*p[5]+4||get_be(p+8,8)!=serial||
       get_be(p+16,4)!=epoch||
       get_be(p+n-4,4)!=crc32(p,n-4))return false;
    Context c;c.serial=serial;c.epoch=epoch;c.count=p[5];c.domain=domain;
    for(std::size_t i=0;i<domain.size();++i)if(p[20+i]!=domain[i])return false;
    for(std::size_t i=0;i<c.count;++i) {
        const auto* q=p+context_prefix+i*context_row;auto& e=c.base[i];
        e.key.node=q[0];e.sensor=q[1];e.test=false;
        e.key.enrollment=static_cast<std::uint32_t>(get_be(q+2,4));
        e.assignment=static_cast<std::uint32_t>(get_be(q+6,4));
        e.key.session=get_be(q+10,8);e.key.sequence=get_be(q+18,8);
        e.monotonic=signed64(get_be(q+26,8));e.occurred=signed64(get_be(q+34,8));
        e.received=signed64(get_be(q+42,8));e.uncertainty=static_cast<std::uint32_t>(get_be(q+50,4));
        e.battery=static_cast<std::uint16_t>(get_be(q+54,2));
        const auto r=static_cast<std::uint16_t>(get_be(q+56,2));
        e.rssi=r<=INT16_MAX?static_cast<std::int16_t>(r):static_cast<std::int16_t>(-1-static_cast<std::int32_t>(UINT16_MAX-r));
    }
    if(!valid_context(c))return false;
    out=c;return true;
}
enum Bits : std::uint16_t { Identity=1,Sensor=2,Uncertainty=4,Battery=8,Rssi=16,
    SeqAbsolute=32,MonoAbsolute=64,OccurredAbsolute=128,ReceivedAbsolute=256,
    FirstAbsolute=512,LastAbsolute=1024,MillisInSeconds=2048,ReceivedFromOccurred=4096 };
constexpr std::uint16_t allowed_mask=8191;
inline bool encode(Mode mode,const Context& c,const Event& e,Buffer& out,std::size_t& size) {
    if(!valid_event(e)||!valid_context(c)||static_cast<unsigned>(mode)>5)return false;
    if(mode==Mode::Fixed) {
        EventBuffer b{};std::size_t n=0;if(!encode_event(e,b,n))return false;
        Buffer candidate{};for(std::size_t i=0;i<n-4;++i)candidate[i]=b[i];
        out=candidate;size=n-4;return true;
    }
    std::uint8_t selector=7;
    if(mode!=Mode::Varint)for(std::uint8_t i=0;i<c.count;++i)
        if(same_binding(e,c.base[i])){selector=i;break;}
    const bool based=selector!=7;
    const Event defaults=based?c.base[selector]:Event{};
    const bool sparse=mode==Mode::Presence||mode==Mode::Relations;
    std::uint16_t mask=0;
    if(!based||mode==Mode::Varint||mode==Mode::Delta)mask|=Identity;
    if(!sparse||!based||e.sensor!=defaults.sensor)mask|=Sensor;
    if(!sparse||!based||e.uncertainty!=defaults.uncertainty)mask|=Uncertainty;
    if(!sparse||!based||e.battery!=defaults.battery)mask|=Battery;
    if(!sparse||!based||e.rssi!=defaults.rssi)mask|=Rssi;
    std::uint64_t seq=e.key.sequence;
    if(!based||e.key.sequence<defaults.key.sequence)mask|=SeqAbsolute;
    else seq-=defaults.key.sequence;
    const std::array<std::int64_t,5> values{e.monotonic,e.occurred,e.received,e.first,e.last};
    const std::array<std::int64_t,5> bases{defaults.monotonic,defaults.occurred,defaults.received,defaults.monotonic,defaults.monotonic};
    const std::array<std::uint16_t,5> flags{MonoAbsolute,OccurredAbsolute,ReceivedAbsolute,FirstAbsolute,LastAbsolute};
    std::array<std::int64_t,5> deltas{};
    for(std::size_t i=0;i<values.size();++i) {
        if(!based||!subtract(values[i],bases[i],deltas[i])){deltas[i]=values[i];mask|=flags[i];}
    }
    if(e.kind!=9)mask=static_cast<std::uint16_t>(mask&~(FirstAbsolute|LastAbsolute));
    if(mode==Mode::Relations&&based) {
        const auto absolutes=static_cast<std::uint16_t>(MonoAbsolute|(e.kind==9?(FirstAbsolute|LastAbsolute):0));
        if(!(mask&absolutes)&&deltas[0]%1000==0&&
           (e.kind!=9||(deltas[3]%1000==0&&deltas[4]%1000==0))) {
            mask|=MillisInSeconds;deltas[0]/=1000;deltas[3]/=1000;deltas[4]/=1000;
        }
        std::int64_t offset=0,previous=0;
        if(subtract(e.received,e.occurred,offset)&&subtract(defaults.received,defaults.occurred,previous)&&offset==previous) {
            mask|=ReceivedFromOccurred;mask=static_cast<std::uint16_t>(mask&~ReceivedAbsolute);
        }
    }
    Writer w;
    if(!w.byte(static_cast<std::uint8_t>(e.kind|(selector<<4)|(e.test?128U:0U)))||
       !w.var(mask))return false;
    if(mask&Identity)if(!w.var(e.key.node)||!w.var(e.key.enrollment)||!w.var(e.assignment)||!w.var(e.key.session))return false;
    if(!w.var(seq))return false;
    for(std::size_t i=0;i<3;++i)if((i!=2||!(mask&ReceivedFromOccurred))&&!w.var(zig(deltas[i])))return false;
    if(mask&Sensor)if(!w.var(e.sensor))return false;
    if(mask&Uncertainty)if(!w.var(e.uncertainty))return false;
    if(mask&Battery)if(!w.var(e.battery))return false;
    if(mask&Rssi)if(!w.var(zig(e.rssi)))return false;
    if(e.kind==9)if(!w.var(e.additional)||!w.var(zig(deltas[3]))||!w.var(zig(deltas[4])))return false;
    out=w.bytes;size=w.at;return true;
}
inline bool decode(Mode mode,const Context& c,const std::uint8_t* p,std::size_t n,Event& out) {
    if(!p||!n||n>max_plain||!valid_context(c)||static_cast<unsigned>(mode)>5)return false;
    if(mode==Mode::Fixed) {
        if(n!=ordinary_bytes-4&&n!=summary_bytes-4)return false;
        EventBuffer b{};for(std::size_t i=0;i<n;++i)b[i]=p[i];
        put_be(b.data()+n,crc32(b.data(),n),4);return decode_event(b.data(),n+4,out);
    }
    Reader r{p,n};std::uint8_t h=0;std::uint64_t bits=0;
    if(!r.byte(h)||!r.var(bits)||bits>allowed_mask)return false;
    const auto selector=static_cast<std::uint8_t>((h>>4)&7U);
    const auto mask=static_cast<std::uint16_t>(bits);
    const bool based=selector!=7;
    if((based&&selector>=c.count)||(mask&~allowed_mask)||(!based&&!(mask&Identity))||
       (mode==Mode::Varint&&based))return false;
    Event e=based?c.base[selector]:Event{};e.kind=h&15U;e.test=(h&128U)!=0;
    e.additional=0;e.first=0;e.last=0;
    if(e.kind>9||(e.kind!=9&&(mask&(FirstAbsolute|LastAbsolute))))return false;
    auto field=[&](auto& target,std::uint64_t max) {
        std::uint64_t v=0;if(!r.var(v)||v>max)return false;
        target=static_cast<std::remove_reference_t<decltype(target)>>(v);return true;
    };
    if(mask&Identity) {
        if(!field(e.key.node,5)||!field(e.key.enrollment,UINT32_MAX)||
           !field(e.assignment,UINT32_MAX)||!field(e.key.session,UINT64_MAX))return false;
        if(based&&!same_binding(e,c.base[selector]))return false;
    }
    std::uint64_t seq=0;if(!r.var(seq))return false;
    if(mask&SeqAbsolute)e.key.sequence=seq;
    else {if(!based||seq>UINT64_MAX-c.base[selector].key.sequence)return false;e.key.sequence=c.base[selector].key.sequence+seq;}
    const std::array<std::uint16_t,5> flags{MonoAbsolute,OccurredAbsolute,ReceivedAbsolute,FirstAbsolute,LastAbsolute};
    const Event base=based?c.base[selector]:Event{};
    const std::array<std::int64_t,5> bases{base.monotonic,base.occurred,base.received,base.monotonic,base.monotonic};
    std::array<std::int64_t*,5> fields{&e.monotonic,&e.occurred,&e.received,&e.first,&e.last};
    for(std::size_t i=0;i<(e.kind==9?5U:3U);++i) {
        // Summary count precedes its two timestamps.
        if(i==3&&!field(e.additional,UINT32_MAX))return false;
        if(i==2&&(mask&ReceivedFromOccurred)) {
            std::int64_t offset=0;
            if(!based||!subtract(base.received,base.occurred,offset)||!add(e.occurred,offset,e.received))return false;
        } else {
            std::uint64_t v=0;if(!r.var(v))return false;
            auto delta=unzig(v);
            if((i==0||i>=3)&&(mask&MillisInSeconds)) {
                if(!based||(mask&flags[i])||delta>INT64_MAX/1000||delta<INT64_MIN/1000)return false;
                delta*=1000;
            }
            if(mask&flags[i])*fields[i]=delta;
            else if(!based||!add(bases[i],delta,*fields[i]))return false;
        }
        if(i==2) {
            if(mask&Sensor)if(!field(e.sensor,5))return false;
            if(mask&Uncertainty)if(!field(e.uncertainty,UINT32_MAX))return false;
            if(mask&Battery)if(!field(e.battery,UINT16_MAX))return false;
            if(mask&Rssi){std::uint64_t rss=0;if(!r.var(rss))return false;const auto s=unzig(rss);
                if(s<INT16_MIN||s>INT16_MAX)return false;
                e.rssi=static_cast<std::int16_t>(s);}
        }
    }
    if(r.at!=n||!valid_event(e))return false;
    // Canonical form detects superfluous masks/escapes and mode mismatch.
    Buffer canonical{};std::size_t bytes=0;if(!encode(mode,c,e,canonical,bytes)||bytes!=n)return false;
    for(std::size_t i=0;i<n;++i)if(canonical[i]!=p[i])return false;
    out=e;return true;
}
static_assert(max_plain>=101,"absolute escape worst-case content fits");
inline std::size_t aligned(std::size_t n){return (n+3)&~std::size_t{3};}
inline std::size_t hot_bytes(std::size_t plain){return aligned(plain+2+16+4);}
inline std::size_t warm_bytes(std::size_t plain){return plain+2;}
} // namespace gs::host::storage::density
