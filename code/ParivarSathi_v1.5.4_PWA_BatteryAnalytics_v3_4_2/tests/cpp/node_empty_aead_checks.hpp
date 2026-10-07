#pragma once
#include "firmware/common/security/association_persistence.hpp"
#include <algorithm>
namespace gs::qualification {
struct EmptyAeadResult { bool passed{false}; const char* stage{"not_started"}; unsigned checks{0}; };
// Shared assertions execute unchanged with the real PSA backend on ESP32-C3.
// The repository below is memory-only; no NVS, radio, identity or event state.
inline EmptyAeadResult check_node_empty_aead(security::CommissioningCrypto& crypto) {
    using namespace security;
    EmptyAeadResult result;
#define GS_AEAD_CHECK(expression, label) do { if (!(expression)) { result.stage=label;return result; } ++result.checks; } while(false)
    Key32 key{};Nonce12 nonce{};Bytes aad(28),cipher,opened;GcmTag tag{};
    for(unsigned i=0;i<aad.size();++i)aad[i]=static_cast<uint8_t>(i+1);
    GS_AEAD_CHECK(crypto.seal_aes256_gcm(key,nonce,aad,Bytes{},cipher,tag)&&cipher.empty(),"empty_seal");
    GS_AEAD_CHECK(tag.size()==16&&std::any_of(tag.begin(),tag.end(),[](auto b){return b!=0;}),"tag_generated");
    // Independent AES-256-GCM known answer: key/nonce zero, AAD bytes 1..28,
    // empty payload. This detects a self-consistent but incompatible backend.
    const GcmTag expected{0x48,0xae,0xc0,0x24,0x4e,0x0e,0x0f,0xe3,0x99,0x57,0x60,0x00,0x8a,0xb8,0x4d,0x36};
    GS_AEAD_CHECK(tag==expected,"empty_known_answer");
    GS_AEAD_CHECK(crypto.open_aes256_gcm(key,nonce,aad,cipher,tag,opened)&&opened.empty(),"empty_open");
    auto bad_tag=tag;bad_tag[0]^=1;
    GS_AEAD_CHECK(!crypto.open_aes256_gcm(key,nonce,aad,cipher,bad_tag,opened)&&opened.empty(),"tag_tamper");
    auto wrong_aad=aad;wrong_aad[0]^=1;
    GS_AEAD_CHECK(!crypto.open_aes256_gcm(key,nonce,wrong_aad,cipher,tag,opened)&&opened.empty(),"aad_tamper");
    const Bytes nonempty(71,0xa5);nonce[0]=1;
    GS_AEAD_CHECK(crypto.seal_aes256_gcm(key,nonce,aad,nonempty,cipher,tag)&&crypto.open_aes256_gcm(key,nonce,aad,cipher,tag,opened)&&opened==nonempty,"nonempty_roundtrip");
    class Memory final:public AssociationBlobStore {
    public:Bytes blob;unsigned writes{0};
        bool read(Bytes& out,bool& found)override{out=blob;found=!blob.empty();return true;}
        bool write(const Bytes& value)override{blob=value;++writes;return true;}
    } store;
    EphemeralP256 identity{};
    GS_AEAD_CHECK(crypto.generate_ephemeral(identity),"ephemeral_fixture");
    CommissioningBinding binding;
    binding.device_id="c3-aead-fixture";binding.hub_id="hub-aead-fixture";binding.home_id="home-aead-fixture";
    binding.logical_id="pir";binding.room="test";binding.function="pir";
    binding.device_public_key=identity.public_key;binding.hub_public_key=identity.public_key;binding.installation_key[0]=1;
    crypto.secure_zero(identity.private_scalar.data(),identity.private_scalar.size());
    AssociationRepository association(crypto,store,key);
    GS_AEAD_CHECK(association.save_initial(binding)&&association.load().generation==1,"paired_generation_1");
    GS_AEAD_CHECK(association.factory_reset()&&store.blob.size()==44&&store.blob[4]==1&&store.blob[5]==2,"reset_generation_2_write");
    // A new repository instance follows exactly the production boot/load path.
    AssociationRepository rebooted(crypto,store,key);const auto unpaired=rebooted.load();
    GS_AEAD_CHECK(unpaired.status==AssociationStatus::Unpaired&&unpaired.generation==2&&!unpaired.binding,"reboot_unpaired_load");
    const auto writes=store.writes;
    GS_AEAD_CHECK(rebooted.factory_reset()&&store.writes==writes,"reset_idempotent");
    GS_AEAD_CHECK(rebooted.save_initial(binding)&&rebooted.load().status==AssociationStatus::Paired&&rebooted.load().generation==3,"reenrollment_generation_3");
    result.passed=true;result.stage="complete";
#undef GS_AEAD_CHECK
    return result;
}
}
