#pragma once
// HOST-ONLY abstract lifecycle model. CRC is a tear oracle, NOT authentication.
// Durable atomic snapshot/root completion are explicit modeling assumptions.
#include "host/storage/efficient_core.hpp"
#include <array>
#include <algorithm>
#include <cstdint>
namespace gs::host::storage::lifecycle {
inline bool same(const Key& a,const Key& b){return key_bytes(a)==key_bytes(b);}
struct Report {
    std::uint32_t enrollment=1;
    std::uint64_t generation=1,session=1,high=0;
    std::array<Key,32> pending{};
    std::size_t count=0;
    bool contains(const Key& k)const {for(std::size_t i=0;i<count;++i)if(same(k,pending[i]))return true;return false;}
    bool covers(const Key& k)const{return k.enrollment==enrollment &&
        (k.session<session||(k.session==session&&k.sequence<=high));}
};
enum class Result {New,Duplicate,Conflict,Stale,Full,Invalid};
struct Witness {Key key{};std::array<std::uint8_t,32> digest{};};
// Proposed CREDIT gate: after each selected complete report at most 32 distinct
// uncovered keys may be accepted. Retries do not spend credits. Reboot must not
// replenish credits; replacement requires authenticated durable revocation.
class Ledger {
    std::array<Witness,384> rows_{};
    std::array<Report,6> reports_{};
    std::array<std::uint8_t,6> spent_{};
    std::size_t count_=0;
public:
    std::size_t size()const{return count_;}
    Result accept(const Key& k,const std::array<std::uint8_t,32>& digest){
        if(!k.valid())return Result::Invalid;
        const auto& r=reports_[k.node];
        if(k.enrollment!=r.enrollment)return Result::Invalid;
        if(r.covers(k)&&!r.contains(k))return Result::Stale;
        for(std::size_t i=0;i<count_;++i)if(same(k,rows_[i].key))return rows_[i].digest==digest?Result::Duplicate:Result::Conflict;
        if(!r.covers(k)&&spent_[k.node]==32)return Result::Full;
        if(count_==rows_.size())return Result::Full;
        rows_[count_++]={k,digest};if(!r.covers(k))++spent_[k.node];return Result::New;
    }
    bool select(std::uint8_t node,const Report& next){
        if(node>=6||next.count>32||!next.generation||!next.session)return false;
        const auto& old=reports_[node];
        if(next.enrollment!=old.enrollment||next.generation<=old.generation||next.session<old.session||
            (next.session==old.session&&next.high<old.high))return false;
        for(std::size_t i=0;i<next.count;++i){const auto& k=next.pending[i];
            if(!k.valid()||k.node!=node||k.enrollment!=next.enrollment||!next.covers(k)||
                (old.covers(k)&&!old.contains(k)))return false;
            for(std::size_t j=0;j<i;++j)if(same(k,next.pending[j]))return false;}
        std::size_t kept=0;std::uint8_t uncovered=0;
        for(std::size_t i=0;i<count_;++i){const auto& k=rows_[i].key;
            if(k.node==node&&next.covers(k)&&!next.contains(k))continue;
            if(k.node==node&&!next.covers(k))++uncovered;
            rows_[kept++]=rows_[i];}
        count_=kept;reports_[node]=next;spent_[node]=uncovered;return true;
    }
};
// One-event COW proof fixture: two independently validated root slots, two
// 256-byte child pages. Root embeds exact child CRC and generation. Real engine
// requires AEAD, reserved unique nonces, durable root erasure, and full manifest.
using Page=std::array<std::uint8_t,256>;
using Root=std::array<std::uint8_t,32>;
struct Media {std::array<Page,2> pages{};std::array<Root,2> roots{};};
struct State {std::uint64_t generation=1;bool body=true,certificate=false,applied=false,cloud=false,retired=false;};
inline Page image(const State& s){Page p{};p.fill(255);put_be(p.data(),s.generation,8);
    p[8]=s.body;p[9]=s.certificate;p[10]=s.applied;p[11]=s.cloud;p[12]=s.retired;
    put_be(p.data()+248,crc32(p.data(),248),4);put_be(p.data()+252,0x434f4d54,4);return p;}
inline Root root(const Page& p,std::uint8_t child){Root r{};r.fill(255);put_be(r.data(),get_be(p.data(),8),8);
    r[8]=child;put_be(r.data()+9,crc32(p.data(),256),4);put_be(r.data()+24,crc32(r.data(),24),4);
    put_be(r.data()+28,0x524f4f54,4);return r;}
inline bool valid_root(const Root& r){return r[8]<2&&get_be(r.data()+28,4)==0x524f4f54&&
    get_be(r.data()+24,4)==crc32(r.data(),24)&&get_be(r.data(),8)>0;}
inline bool recover(const Media& m,State& s){const Root* chosen=nullptr;
    for(const auto& r:m.roots)if(valid_root(r)&&(!chosen||get_be(r.data(),8)>get_be(chosen->data(),8)))chosen=&r;
    if(!chosen)return false;
    const auto& p=m.pages[(*chosen)[8]];
    // Fail closed on corrupt selected child. Never fall back to a stale root.
    if(get_be(chosen->data()+9,4)!=crc32(p.data(),256)||get_be(p.data()+252,4)!=0x434f4d54||
       get_be(p.data()+248,4)!=crc32(p.data(),248)||get_be(p.data(),8)!=get_be(chosen->data(),8))return false;
    for(unsigned i=8;i<=12;++i)if(p[i]>1)return false;
    s={get_be(p.data(),8),bool(p[8]),bool(p[9]),bool(p[10]),bool(p[11]),bool(p[12])};
    return (s.body||s.certificate||s.retired)&&(!s.certificate||(s.applied&&s.cloud));}
// Unit-granular tear model. Erase bytes are monotone to 0xff; program asserts
// 1->0 only. Every cut is reproducible, including retirement of old root.
struct Mutator {Media& m;std::size_t budget,steps=0;
    bool set(std::uint8_t& cell,std::uint8_t v,bool erase=false){if(steps==budget)return false;
        if(!erase&&((cell&v)!=v))return false;
        cell=v;++steps;return true;}
    template<std::size_t N>bool erase(std::array<std::uint8_t,N>& a){for(auto& b:a)if(!set(b,255,true))return false;return true;}
    template<std::size_t N>bool write(std::array<std::uint8_t,N>& a,const std::array<std::uint8_t,N>& b){for(std::size_t i=0;i<N;++i)if(!set(a[i],b[i]))return false;return true;}
    bool replace(const State& next){const auto p=image(next);const auto r=root(p,1);
        if(!erase(m.pages[1])||!write(m.pages[1],p)||!erase(m.roots[1])||!write(m.roots[1],r))return false;
        State check;if(!recover(m,check)||check.generation!=next.generation)return false;
        // Before source erase, EVERY older recovery root must cease pinning it.
        // Restart may retain only the newer valid root. No stale fallback.
        if(!erase(m.roots[0])||!erase(m.pages[0]))return false;
        return true;}
};
inline Media initial(const State& s){Media m;for(auto& p:m.pages)p.fill(255);for(auto& r:m.roots)r.fill(255);
    m.pages[0]=image(s);m.roots[0]=root(m.pages[0],0);return m;}
} // namespace
