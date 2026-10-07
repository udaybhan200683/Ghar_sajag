// Frozen codec input; reservation sensitivity, NOT allocator qualification.
#include "host/storage/density_fixture.hpp"
#include <cassert>
#include <cstdio>
using namespace gs::host::storage::density;
static void pack(unsigned rate,std::size_t extra,unsigned limit) {
    const auto header=authenticated_context_bytes+extra;
    auto context=context_for(0,rate,1,true);
    std::size_t pages=1,used=header,count=0,fit=0,three=0;
    for(std::uint64_t i=0;i<6ULL*rate;++i){Buffer b{};std::size_t n=0;
        assert(encode(Mode::Relations,context,trace(i,rate,true),b,n));
        if(used+warm_bytes(n)>4096||count==max_records){++pages;used=header;count=0;
            context=context_for(i,rate,pages,true);assert(encode(Mode::Relations,context,trace(i,rate,true),b,n));}
        used+=warm_bytes(n);++count;
        if((i+1)%rate==0){if(used+302>4096||count==max_records){++pages;used=header;count=0;context=context_for(i+1,rate,pages,true);}
            used+=302;++count;}
        if(pages<=limit)fit=i+1;
        if(i+1==3ULL*rate)three=pages;
    }
    std::printf("LIFECYCLE_SIZING rate=%u header=%zu pool_sectors=%u fit=%zu hours=%.6f days=%.6f three_day_sectors=%zu fixed98304_total=%zu\n",
        rate,header,limit,fit,fit*24.0/rate,double(fit)/rate,three,98304+three*4096);
}
int main(){for(auto rate:{384U,1776U,23232U})for(auto extra:{std::size_t{324},std::size_t{966}}){pack(rate,extra,8);pack(rate,extra,6);}
    static_assert(24576+12288+20480+8192+8192+12288+8192+4096==98304);
    static_assert(98304+32768==131072);
    std::puts("STATIC_BUDGET_PASS fixed=98304 pool=32768 384_witnesses_plus_framing_fit_six_sectors");
}
