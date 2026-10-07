#include "host/storage/rawflash_model.hpp"
#include <cstdio>
using namespace gs::host::storage;
using namespace gs::host::storage::rawflash;
static Selection selected(const Media& m,std::array<Event,max_records>& e){Selection s;assert(recover(m,s,e));return s;}
int main(){Image old;assert(old.init(context_for(0,384,1,true)));assert(old.append(trace(0,384,true)));
    const auto before=initial(old);std::array<Event,max_records> events{};const auto source=selected(before,events);
    Image append=old;assert(append.append(trace(1,384,true)));
    Image copy;assert(copy.init(context_for(0,384,2,true)));assert(copy.append(trace(0,384,true)));assert(copy.append(trace(1,384,true)));
    std::size_t cuts=0;
    for(bool gc:{false,true}){const auto& next=gc?copy:append;auto finish=before;FlashWriter all{finish,SIZE_MAX};assert(all.publish(source,next,gc));
        for(std::size_t cut=0;cut<=all.steps;++cut){auto media=before;FlashWriter writer{media,cut};(void)writer.publish(source,next,gc);
            auto got=selected(media,events);assert(got.generation==1||got.generation==2);
            assert(got.count==(got.generation==1?1:2));assert(equal(events[0],trace(0,384,true)));
            if(got.count==2)assert(equal(events[1],trace(1,384,true)));
            if(cut%1024==0){
                // Second crash during recovery cleanup: selected child/root
                // stay pinned; resume is idempotent, no free-page guess.
                for(auto second:{0U,1U,4U,4095U,4096U,4100U,8195U,8196U}){
                    auto retry=media;FlashWriter cleaning{retry,second};(void)cleaning.cleanup(got);
                    auto stable=selected(retry,events);assert(stable.generation==got.generation&&stable.count==got.count);
                    FlashWriter finish_cleanup{retry,SIZE_MAX};assert(finish_cleanup.cleanup(stable));
                    assert(blank(retry.pages[1-stable.child])&&blank(retry.pages[stable.root==2?3:2]));
                }
            }
            ++cuts;
        }
        std::printf("RAW_FAULT_MODE gc=%d operations=%zu exhaustive_cuts=%zu PASS\n",gc,all.steps,all.steps+1);
        auto bad=finish;bad.pages[gc?1:0][405]^=1;Selection s;assert(!recover(bad,s,events));
        bad=finish;bad.pages[gc?1:0][20]^=1;assert(!recover(bad,s,events));
        bad=finish;bad.pages[3][48]^=1;assert(!recover(bad,s,events));
    }
    auto media=before;
    for(unsigned iteration=0;iteration<64;++iteration){auto current=selected(media,events);Image next;
        assert(next.init(context_for(0,384,current.serial+1,true)));
        for(std::size_t i=0;i<current.count;++i)assert(next.append(events[i]));
        FlashWriter writer{media,SIZE_MAX};assert(writer.publish(current,next,true));
        auto recovered=selected(media,events);assert(recovered.generation==current.generation+1);assert(recovered.count==1);
    }
    // An interrupted append tail is not reusable with the same serial/offset IV.
    auto torn=before;FlashWriter interrupted{torn,1};assert(!interrupted.publish(source,append,false));
    assert(torn.pages[0][source.extent]!=255);assert(selected(torn,events).count==1);
    auto wrong=before;auto s=source;++s.serial;s.generation=2;s.root=3;wrong.pages[3]=root_image(s);Selection recovered;
    assert(!recover(wrong,recovered,events));
    std::printf("STORAGE_RAWFLASH_HOST_PASS cuts=%zu sector_bytes=4096 fixed_media=%zu scan_bound=16384 AES-GCM/context-position/root-binding\n",cuts,sizeof(Media));
    std::puts("RAW_LIMITS external-unique-serials numeric-context-only prefix-erase-no-freshness-fence no-production-allocator-proof");
}
