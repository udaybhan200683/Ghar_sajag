#include "host/storage/density_fixture.hpp"
#include <openssl/evp.h>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <new>

static std::size_t allocations=0;
void* operator new(std::size_t n){++allocations;if(auto* p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p)noexcept{std::free(p);}
void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}
void operator delete[](void* p,std::size_t)noexcept{std::free(p);}
using namespace gs::host::storage;
using namespace gs::host::storage::density;

static void roundtrip(const Context& c,const Event& e) {
    for(auto m:{Mode::Fixed,Mode::Varint,Mode::Delta,Mode::Context,Mode::Presence,Mode::Relations}) {
        Buffer b{};std::size_t n=0;Event decoded;
        assert(encode(m,c,e,b,n)&&n<=max_plain);
        assert(decode(m,c,b.data(),n,decoded)&&equal(e,decoded));
        for(std::size_t cut=0;cut<n;++cut) {
            assert(!decode(m,c,b.data(),cut,decoded)&&equal(e,decoded));
        }
        assert(!decode(m,c,b.data(),n+1,decoded)&&equal(e,decoded));
    }
}
static void boundaries() {
    const auto c=context_for(0,384);
    const auto jittered=context_for(0,384,1,true);
    for(std::uint64_t i=0;i<50;++i)roundtrip(jittered,trace(i,384,true));
    for(std::uint8_t kind=0;kind<=9;++kind) {
        auto example=trace(0,384);example.kind=kind;
        if(kind==9){example.additional=1;example.first=0;example.last=INT64_MAX;}
        roundtrip(c,example);
    }
    for(auto value:{std::uint64_t{0},std::uint64_t{1},std::uint64_t{127},std::uint64_t{128},
                    std::uint64_t{16383},std::uint64_t{16384},std::uint64_t{UINT64_MAX}}) {
        Writer w;assert(w.var(value));Reader r{w.bytes.data(),w.at};std::uint64_t v=0;
        assert(r.var(v)&&v==value&&r.at==w.at);
    }
    const std::uint8_t overlong[]{128,0};Reader bad{overlong,2};std::uint64_t v=0;assert(!bad.var(v));
    const std::uint8_t overflow[]{255,255,255,255,255,255,255,255,255,2};Reader too_big{overflow,10};assert(!too_big.var(v));
    for(auto time:{INT64_MIN,INT64_MIN+1,std::int64_t{-1},std::int64_t{0},std::int64_t{1},INT64_MAX}) {
        auto e=trace(0,384);e.monotonic=time;e.occurred=time;e.received=time;
        e.key.sequence=UINT64_MAX;e.key.session=UINT64_MAX;e.key.enrollment=UINT32_MAX;
        e.assignment=UINT32_MAX;e.uncertainty=UINT32_MAX;e.battery=UINT16_MAX;e.rssi=INT16_MIN;
        roundtrip(c,e);assert(unzig(zig(time))==time);
    }
    auto e=trace(1,384);e.kind=9;e.additional=UINT32_MAX;e.first=0;e.last=INT64_MAX;roundtrip(c,e);
    auto extreme=c;extreme.base[0].monotonic=INT64_MIN;extreme.base[0].occurred=INT64_MAX;
    e=extreme.base[0];e.monotonic=INT64_MAX;e.occurred=INT64_MIN;roundtrip(extreme,e);
    auto high_sequence=c;high_sequence.base[0].key.sequence=UINT64_MAX;
    e=high_sequence.base[0];e.key.sequence=1;roundtrip(high_sequence,e);
    e=trace(1,384);++e.assignment;roundtrip(c,e); // dictionary miss: absolute escape
    e.key.sequence=0;Buffer b{};std::size_t n=99;assert(!encode(Mode::Presence,c,e,b,n)&&n==99);
    ContextBuffer cb{};std::size_t cn=0;assert(encode_context(c,cb,cn));Context restored;
    assert(decode_context(cb.data(),cn,c.serial,c.epoch,c.domain,restored));
    assert(!decode_context(cb.data(),cn,c.serial+1,c.epoch,c.domain,restored));
    assert(!decode_context(cb.data(),cn,c.serial,c.epoch+1,c.domain,restored));
    auto wrong_domain=c.domain;wrong_domain[0]^=1;
    assert(!decode_context(cb.data(),cn,c.serial,c.epoch,wrong_domain,restored));
    for(std::size_t i=0;i<cn;++i){auto corrupt=cb;corrupt[i]^=1;assert(!decode_context(corrupt.data(),cn,c.serial,c.epoch,c.domain,restored));}
    for(std::size_t i=0;i<cn;++i)assert(!decode_context(cb.data(),i,c.serial,c.epoch,c.domain,restored));
    auto duplicate=c;duplicate.base[1]=duplicate.base[0];assert(!encode_context(duplicate,cb,cn));
    auto full=c;full.count=7;assert(!encode_context(full,cb,cn));
    Context none;roundtrip(none,trace(1,384)); // full absolute escape
    auto largest=trace(0,384);largest.key={5,UINT32_MAX,UINT64_MAX,UINT64_MAX};
    largest.assignment=UINT32_MAX;largest.kind=9;largest.sensor=5;largest.test=true;
    largest.monotonic=INT64_MIN;largest.occurred=INT64_MIN;largest.received=INT64_MIN;
    largest.uncertainty=UINT32_MAX;largest.battery=UINT16_MAX;largest.rssi=INT16_MIN;
    largest.additional=UINT32_MAX;largest.first=INT64_MAX;largest.last=INT64_MAX;
    roundtrip(none,largest);Buffer maximum{};std::size_t maximum_size=0;
    assert(encode(Mode::Relations,none,largest,maximum,maximum_size)&&maximum_size==101);
    assert(hot_bytes(maximum_size)==124&&warm_bytes(maximum_size)==103);
    auto malformed=cb;assert(encode_context(c,malformed,cn));malformed[4]=3;
    put_be(malformed.data()+cn-4,crc32(malformed.data(),cn-4),4);
    assert(!decode_context(malformed.data(),cn,c.serial,c.epoch,c.domain,restored));
    std::uint64_t random=42;
    for(unsigned i=0;i<50000;++i){Buffer fuzz{};for(auto& byte:fuzz){random=random*6364136223846793005ULL+1;byte=static_cast<std::uint8_t>(random>>56);}
        Event out;if(decode(Mode::Presence,c,fuzz.data(),1+i%max_plain,out)){Buffer canonical{};std::size_t len=0;assert(encode(Mode::Presence,c,out,canonical,len));}}
}
// Host AES-GCM binding experiment, not target key/nonce allocation. Binds full
// independently recovered context + physical offset/length as AAD. Crypto heap
// behavior is outside the portable codec allocation measurement.
static void authentication() {
    auto c=context_for(0,384);ContextBuffer context{};std::size_t cn=0;assert(encode_context(c,context,cn));
    Buffer b{},cipher{},opened{};std::size_t n=0;assert(encode(Mode::Relations,c,trace(10,384),b,n));
    std::array<std::uint8_t,32> key{};key[0]=42;std::array<std::uint8_t,12> nonce{};
    put_be(nonce.data(),c.serial,8);put_be(nonce.data()+8,428,4);
    std::array<std::uint8_t,max_context_bytes+6> aad{};
    std::copy_n(context.begin(),cn,aad.begin());put_be(aad.data()+cn,428,4);put_be(aad.data()+cn+4,n,2);
    std::array<std::uint8_t,16> tag{};auto* ctx=EVP_CIPHER_CTX_new();assert(ctx);int size=0,tail=0;
    assert(EVP_EncryptInit_ex(ctx,EVP_aes_256_gcm(),nullptr,key.data(),nonce.data())==1);
    assert(EVP_EncryptUpdate(ctx,nullptr,&size,aad.data(),static_cast<int>(cn+6))==1);
    assert(EVP_EncryptUpdate(ctx,cipher.data(),&size,b.data(),static_cast<int>(n))==1);
    assert(EVP_EncryptFinal_ex(ctx,cipher.data()+size,&tail)==1);
    assert(EVP_CIPHER_CTX_ctrl(ctx,EVP_CTRL_GCM_GET_TAG,16,tag.data())==1);
    auto verify=[&](const auto& auth,const auto& iv,const auto& payload,std::size_t length,const auto& proof) {
        EVP_CIPHER_CTX_reset(ctx);
        assert(EVP_DecryptInit_ex(ctx,EVP_aes_256_gcm(),nullptr,key.data(),iv.data())==1);
        assert(EVP_DecryptUpdate(ctx,nullptr,&size,auth.data(),static_cast<int>(cn+6))==1);
        assert(EVP_DecryptUpdate(ctx,opened.data(),&size,payload.data(),static_cast<int>(length))==1);
        auto writable=proof;assert(EVP_CIPHER_CTX_ctrl(ctx,EVP_CTRL_GCM_SET_TAG,16,writable.data())==1);
        return EVP_DecryptFinal_ex(ctx,opened.data()+size,&tail)==1;
    };
    assert(verify(aad,nonce,cipher,n,tag));assert(std::equal(b.begin(),b.begin()+n,opened.begin()));
    for(std::size_t i=0;i<cn+6;++i){auto wrong=aad;wrong[i]^=1;assert(!verify(wrong,nonce,cipher,n,tag));}
    for(std::size_t i=0;i<n;++i){auto wrong=cipher;wrong[i]^=1;assert(!verify(aad,nonce,wrong,n,tag));}
    for(std::size_t cut=0;cut<n;++cut)assert(!verify(aad,nonce,cipher,cut,tag));
    auto wrong_nonce=nonce;wrong_nonce[7]^=1;assert(!verify(aad,wrong_nonce,cipher,n,tag));
    auto wrong_tag=tag;wrong_tag[0]^=1;assert(!verify(aad,nonce,cipher,n,wrong_tag));
    EVP_CIPHER_CTX_free(ctx);
}
static void faults() {
    Sector before;auto c=context_for(0,384);assert(before.init(c));assert(before.append(trace(0,384)));
    auto after=before;assert(after.append(trace(1,384)));
    for(std::size_t cut=before.extent;cut<=after.extent;++cut){auto torn=before;
        std::copy_n(after.bytes.begin()+before.extent,cut-before.extent,torn.bytes.begin()+before.extent);
        assert(torn.recover(before.extent,before.count,c.serial,c.epoch,c.domain));
        const bool newer=torn.recover(after.extent,after.count,c.serial,c.epoch,c.domain);
        if(cut<after.extent)assert(!newer);else assert(newer);
    }
    for(std::size_t i=0;i<after.extent;++i){auto corrupt=after;corrupt.bytes[i]^=1;
        assert(!corrupt.recover(after.extent,after.count,c.serial,c.epoch,c.domain));}
    // Selected complete destination after COW; old/new roots are model inputs.
    Sector destination;auto newer_context=c;newer_context.serial=2;assert(destination.init(newer_context));
    Event e;for(std::size_t i=0;i<after.count;++i){assert(after.read(i,e)&&destination.append(e));}
    for(std::size_t cut=0;cut<=destination.extent;++cut){Sector torn;torn.bytes.fill(255);
        std::copy_n(destination.bytes.begin(),cut,torn.bytes.begin());
        assert(after.recover(after.extent,after.count,c.serial,c.epoch,c.domain));
        if(cut<destination.extent)assert(!torn.recover(destination.extent,destination.count,2,c.epoch,c.domain));
        else assert(torn.recover(destination.extent,destination.count,2,c.epoch,c.domain));}
    // Removal/truncation cannot be accepted under an authoritative selected extent.
    assert(!after.recover(after.extent-1,after.count,c.serial,c.epoch,c.domain));
    // CRC cannot promise protection against malicious replacement; AES AAD above does.
}
static void lifetime() {
    std::array<Sector,6> pool{};ExactIndex<416> index;std::uint64_t serial=1;
    const auto baseline=allocations;std::size_t peak=0;
    for(std::uint64_t i=0;i<1000000;++i) {
        const auto s=static_cast<std::size_t>((i/32)%pool.size());auto& segment=pool[s];
        if(i%32==0){Event prior;for(std::size_t j=0;j<segment.count;++j){assert(segment.read(j,prior));assert(index.erase(prior.key));}
            // Fixture explicitly releases all lifecycle owners; no product retirement inference.
            assert(segment.init(context_for(i,23232,serial++)));}
        const auto e=trace(i,23232);assert(segment.append(e));
        const auto handle=static_cast<std::uint32_t>(s*sector_bytes+segment.offsets[segment.count-1]);
        assert(index.insert(e.key,handle)==Insert::Added);std::uint32_t found=0;
        assert(index.find(e.key,found)&&found==handle);Event restored;
        assert(segment.read(segment.count-1,restored)&&equal(e,restored));
        assert(index.insert(e.key,handle)==Insert::Present);
        if(i%4096==0){ExactIndex<416> reboot;
            for(std::size_t slot=0;slot<pool.size();++slot){auto& p=pool[slot];if(!p.extent)continue;
                assert(p.recover(p.extent,p.count,p.context.serial,p.context.epoch,p.context.domain));
                for(std::size_t j=0;j<p.count;++j){assert(p.read(j,restored));assert(reboot.insert(restored.key,static_cast<std::uint32_t>(slot*sector_bytes+p.offsets[j]))==Insert::Added);}}
            index=reboot;}
        peak=std::max(peak,index.size());assert(index.size()<=192);
    }
    assert(allocations==baseline);
    std::printf("DENSITY_LONG_RUN events=1000000 peak_keys=%zu fixed_pool_RAM=%zu index_RAM=%zu hot_new=0\n",peak,sizeof(pool),sizeof(index));
}
int main(){boundaries();authentication();faults();lifetime();std::puts("STORAGE_DENSITY_HOST_PASS codec/context/random-access/AEAD-binding/byte-tears/COW-model/bounded-lifetime");}
