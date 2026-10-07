// FROZEN density codec; source-derived optimistic NVS entry occupancy only.
#include "host/storage/density_fixture.hpp"
#include <cassert>
#include <cstdio>
using namespace gs::host::storage::density;
constexpr std::size_t ceil_div(std::size_t n,std::size_t d){return (n+d-1)/d;}
constexpr std::size_t blob(std::size_t n){return ceil_div(n,32)+ceil_div(n,4000)+1;}
constexpr std::size_t fixed_entries=1+6*blob(4079)+3*blob(3485)+3*blob(6144)+2*blob(512)+4*blob(4096);
constexpr std::size_t nvs_bytes(std::size_t segments){return (ceil_div(fixed_entries+segments*blob(4096),126)+4)*4096;}
static_assert(fixed_entries==2265);
static_assert(nvs_bytes(9)==131072&&nvs_bytes(10)==135168);
static void sizing(unsigned rate,unsigned extra){const auto header=authenticated_context_bytes+extra;
    auto context=context_for(0,rate,1,true);std::size_t pages=1,used=header,count=0,fit7=0,fit9=0,three=0;
    for(std::uint64_t i=0;i<6ULL*rate;++i){Buffer b{};std::size_t n=0;assert(encode(Mode::Relations,context,trace(i,rate,true),b,n));
        if(used+warm_bytes(n)>4096||count==max_records){++pages;used=header;count=0;context=context_for(i,rate,pages,true);assert(encode(Mode::Relations,context,trace(i,rate,true),b,n));}
        used+=warm_bytes(n);++count;
        if((i+1)%rate==0){if(used+302>4096||count==max_records){++pages;used=header;count=0;context=context_for(i+1,rate,pages,true);}used+=302;++count;}
        if(pages<=7)fit7=i+1;
        if(pages<=9)fit9=i+1;
        if(i+1==3ULL*rate)three=pages;
    }
    std::printf("PHYSICAL_SIZING rate=%u header=%zu raw7_records=%zu raw_hours=%.6f nvs9_optimistic_records=%zu nvs_hours=%.6f three_sectors=%zu raw72=%zu raw_margin=%lld nvs72_lower_bound=%zu nvs_margin=%lld\n",rate,header,fit7,fit7*24.0/rate,fit9,fit9*24.0/rate,three,102400+4096*three,131072LL-static_cast<long long>(102400+4096*three),nvs_bytes(three),131072LL-static_cast<long long>(nvs_bytes(three)));
}
int main(){for(auto size:{16U,32U,36U,53U,124U,404U,512U,3485U,4079U,4096U,6144U}){
    std::printf("NVS_OBJECT logical=%u entries=%zu entry_bytes=%zu occupancy_ratio=%.6f\n",size,blob(size),32*blob(size),32.0*blob(size)/size);}
    std::printf("NVS_GLOBAL fixed_entries=%zu min_fixed_pages=18 reserve_pages=4 fixed_bytes=90112 max_variable_segments=9 incremental_pages=10 variable_bytes=40960\n",fixed_entries);
    for(auto r:{384U,1776U,23232U})for(auto extra:{324U,966U})sizing(r,extra);
    std::puts("PHYSICAL_SIZING_PASS lower-bound-only no-runtime-GC-progress-or-retention-promise");
}
