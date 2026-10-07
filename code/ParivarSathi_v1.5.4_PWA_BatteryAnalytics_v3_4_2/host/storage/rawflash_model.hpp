#pragma once
// HOST ONLY: full erase sectors and real host AES-GCM around the FROZEN codec.
// Serial reservation/root anti-rollback/target flash driver are NOT implemented.
#include "host/storage/density_fixture.hpp"
#include <openssl/evp.h>
#include <cassert>
namespace gs::host::storage::rawflash {
using namespace density;
using Page=std::array<std::uint8_t,4096>;
struct Media {std::array<Page,4> pages{};Media(){for(auto& p:pages)p.fill(255);}};
inline bool blank(const Page& p){return std::all_of(p.begin(),p.end(),[](auto v){return v==255;});}
inline auto nonce(std::uint64_t serial,std::uint32_t position){std::array<std::uint8_t,12> n{};put_be(n.data(),serial,8);put_be(n.data()+8,position,4);return n;}
// Separate synthetic root/data keys prevent cross-domain IV reuse. No claim
// about OpenSSL heap use or production key derivation.
inline bool crypt(bool seal,bool root_key,const std::array<std::uint8_t,12>& iv,
                  const std::uint8_t* aad,std::size_t an,const std::uint8_t* in,
                  std::size_t n,std::uint8_t* out,std::uint8_t* tag){
    if(an>8192||n>4096)return false;
    std::array<std::uint8_t,32> key{};key[0]=root_key?43:42;
    auto* c=EVP_CIPHER_CTX_new();assert(c);int len=0,tail=0;bool ok;
    if(seal){ok=EVP_EncryptInit_ex(c,EVP_aes_256_gcm(),nullptr,key.data(),iv.data())==1 &&
        EVP_EncryptUpdate(c,nullptr,&len,aad,static_cast<int>(an))==1 &&
        EVP_EncryptUpdate(c,out,&len,in,static_cast<int>(n))==1 &&
        EVP_EncryptFinal_ex(c,out+len,&tail)==1 && EVP_CIPHER_CTX_ctrl(c,EVP_CTRL_GCM_GET_TAG,16,tag)==1;
    }else{ok=EVP_DecryptInit_ex(c,EVP_aes_256_gcm(),nullptr,key.data(),iv.data())==1 &&
        EVP_DecryptUpdate(c,nullptr,&len,aad,static_cast<int>(an))==1 &&
        EVP_DecryptUpdate(c,out,&len,in,static_cast<int>(n))==1 &&
        EVP_CIPHER_CTX_ctrl(c,EVP_CTRL_GCM_SET_TAG,16,tag)==1 && EVP_DecryptFinal_ex(c,out+len,&tail)==1;}
    EVP_CIPHER_CTX_free(c);return ok;
}
struct Image {Page page{};Context context{};std::size_t extent=404,count=0;
    bool init(const Context& c){ContextBuffer plain{};std::size_t n=0;if(!encode_context(c,plain,n)||n!=388)return false;
        page.fill(255);context=c;extent=404;count=0;std::copy_n(plain.begin(),36,page.begin());
        return crypt(true,false,nonce(c.serial,UINT32_MAX),page.data(),36,plain.data()+36,n-36,page.data()+36,page.data()+n);}
    bool append(const Event& e){Buffer b{};std::size_t n=0;if(!encode(Mode::Relations,context,e,b,n))return false;
        const auto total=hot_bytes(n);if(count==max_records||total>4096-extent)return false;
        auto* p=page.data()+extent;std::fill_n(p,total,0);put_be(p,n,2);
        std::array<std::uint8_t,410> aad{};std::copy_n(page.begin(),404,aad.begin());put_be(aad.data()+404,extent,4);put_be(aad.data()+408,n,2);
        if(!crypt(true,false,nonce(context.serial,static_cast<std::uint32_t>(extent)),aad.data(),aad.size(),b.data(),n,p+2,p+2+n))return false;
        put_be(p+2+n+16,0xc01dcafe,4);extent+=total;++count;return true;}
};
struct Selection {std::uint64_t generation=0,serial=0;std::uint8_t child=0,root=0;std::size_t extent=0,count=0;std::uint32_t epoch=0;std::array<std::uint8_t,16> domain{};};
inline Page root_image(const Selection& s){Page p{};p.fill(255);put_be(p.data(),0x52415731,4);p[4]=1;p[5]=s.child;p[6]=p[7]=0;
    put_be(p.data()+8,s.generation,8);put_be(p.data()+16,s.serial,8);put_be(p.data()+24,s.extent,2);put_be(p.data()+26,s.count,2);put_be(p.data()+28,s.epoch,4);
    std::copy(s.domain.begin(),s.domain.end(),p.begin()+32);std::uint8_t dummy=0;
    assert(crypt(true,true,nonce(s.generation,s.root),p.data(),48,&dummy,0,&dummy,p.data()+48));put_be(p.data()+64,0x434f4d54,4);return p;}
inline bool root_read(const Page& p,unsigned slot,Selection& s){
    if(get_be(p.data()+64,4)!=0x434f4d54)return false;
    auto tag=std::array<std::uint8_t,16>{};std::copy_n(p.data()+48,16,tag.begin());std::uint8_t dummy=0;
    const auto generation=get_be(p.data()+8,8);
    if(!generation||get_be(p.data(),4)!=0x52415731||p[4]!=1||p[5]>1||p[6]||p[7]||
       !crypt(false,true,nonce(generation,slot),p.data(),48,&dummy,0,&dummy,tag.data()))return false;
    s={generation,get_be(p.data()+16,8),p[5],static_cast<std::uint8_t>(slot),static_cast<std::size_t>(get_be(p.data()+24,2)),static_cast<std::size_t>(get_be(p.data()+26,2)),static_cast<std::uint32_t>(get_be(p.data()+28,4)),{}};
    std::copy_n(p.data()+32,16,s.domain.begin());return s.serial&&s.extent>=404&&s.extent<=4096&&s.count<=max_records&&s.epoch;
}
inline bool recover(const Media& m,Selection& selected,std::array<Event,max_records>& events){
    bool found=false;
    for(unsigned i=2;i<4;++i){Selection s;
        if(get_be(m.pages[i].data()+64,4)==0x434f4d54&&!root_read(m.pages[i],i,s))return false;
        if(root_read(m.pages[i],i,s)&&(!found||s.generation>selected.generation)){selected=s;found=true;}}
    if(!found)return false;
    const auto& page=m.pages[selected.child];ContextBuffer plain{};std::copy_n(page.begin(),36,plain.begin());
    auto tag=std::array<std::uint8_t,16>{};std::copy_n(page.data()+388,16,tag.begin());
    if(!crypt(false,false,nonce(selected.serial,UINT32_MAX),page.data(),36,page.data()+36,352,plain.data()+36,tag.data()))return false;
    Context c;if(!decode_context(plain.data(),388,selected.serial,selected.epoch,selected.domain,c))return false;
    std::size_t at=404;
    for(std::size_t i=0;i<selected.count;++i){if(at+2>selected.extent)return false;
        const auto* p=page.data()+at;const auto n=static_cast<std::size_t>(get_be(p,2));const auto size=hot_bytes(n);
        if(n>max_plain||size>selected.extent-at||get_be(p+2+n+16,4)!=0xc01dcafe)return false;
        for(std::size_t j=n+22;j<size;++j)if(p[j])return false;
        std::array<std::uint8_t,410> aad{};std::copy_n(page.begin(),404,aad.begin());put_be(aad.data()+404,at,4);put_be(aad.data()+408,n,2);
        Buffer opened{};std::copy_n(p+2+n,16,tag.begin());
        if(!crypt(false,false,nonce(selected.serial,static_cast<std::uint32_t>(at)),aad.data(),aad.size(),p+2,n,opened.data(),tag.data())||
           !decode(Mode::Relations,c,opened.data(),n,events[i]))return false;
        at+=size;
    }
    return at==selected.extent;
}
// Byte-cut flash driver. Erase is a deterministic monotone prefix model, not
// every hardware brownout bit pattern. Program checks 1->0 only.
struct FlashWriter {Media& media;std::size_t budget,steps=0;
    bool set(std::uint8_t& byte,std::uint8_t value,bool erase=false){if(steps==budget)return false;
        if(!erase&&(byte&value)!=value)return false;
        byte=value;++steps;return true;}
    bool erase(unsigned sector){for(auto& byte:media.pages[sector])if(!set(byte,255,true))return false;return true;}
    bool write(unsigned sector,const Page& p,std::size_t first,std::size_t last){for(auto i=first;i<last;++i)if(!set(media.pages[sector][i],p[i]))return false;return true;}
    bool cleanup(const Selection& selected){
        const unsigned other_root=selected.root==2?3:2;
        for(unsigned i=64;i<68;++i)if(!set(media.pages[other_root][i],0))return false;
        return erase(other_root)&&erase(1-selected.child);
    }
    bool publish(const Selection& old,const Image& next,bool gc){
        Selection s=old;++s.generation;s.root=old.root==2?3:2;s.extent=next.extent;s.count=next.count;s.serial=next.context.serial;s.child=gc?1-old.child:old.child;
        if(!blank(media.pages[s.root]))return false; // recovery must release old scratch first
        if(gc){if(!erase(s.child)||!write(s.child,next.page,0,next.extent))return false;}
        else if(!write(s.child,next.page,old.extent,next.extent))return false;
        const auto root=root_image(s);if(!write(s.root,root,0,68))return false;
        Selection got;std::array<Event,max_records> events{};if(!recover(media,got,events)||got.generation!=s.generation)return false;
        // Safe monotone retirement AFTER verified new root; never update selected
        // root in place. Invalidate marker before erase so torn old-root erase
        // cannot resemble committed but damaged authority.
        for(unsigned i=64;i<68;++i)if(!set(media.pages[old.root][i],0))return false;
        if(!erase(old.root))return false;
        if(gc&&!erase(old.child))return false;
        return true;
    }
};
inline Media initial(const Image& image){Media m;m.pages[0]=image.page;
    Selection s{1,image.context.serial,0,2,image.extent,image.count,image.context.epoch,image.context.domain};m.pages[2]=root_image(s);return m;}
} // namespace
