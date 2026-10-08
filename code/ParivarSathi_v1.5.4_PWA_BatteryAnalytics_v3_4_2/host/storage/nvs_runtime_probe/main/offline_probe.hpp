// SDK NVS EMULATED: size-matched objects, not the proposed authenticated format.
// Included in the existing isolated probe to reuse latched flash fault wrappers.
#include <fstream>
#include <string>

bool offline_verify(nvs_handle_t h, const char* prefix, unsigned index, unsigned size, unsigned gen) {
    char key[16];std::snprintf(key,sizeof(key),"%s%u",prefix,index);
    std::vector<std::uint8_t> value(size);size_t n=size;
    if(nvs_get_blob(h,key,value.data(),&n)!=ESP_OK || n!=size)return false;
    unsigned got=0;if(size>=4)std::memcpy(&got,value.data(),4);
    if(size>=4 && got!=gen)return false;
    return std::all_of(value.begin()+std::min(size,4u),value.end(),[=](auto b){return b==static_cast<std::uint8_t>(gen+index);});
}

int offline_probe(int argc,char** argv) {
    REQUIRE(argc>=3);
    std::ifstream input(argv[2]);REQUIRE(input.good());
    unsigned history=0,cow=0,critical=0,arrivals=0;
    input>>history>>cow>>critical>>arrivals;
    std::vector<unsigned> sizes;unsigned bytes=0;
    while(input>>bytes)sizes.push_back(bytes);
    REQUIRE(sizes.size()==20+critical+history+cow+4+32);
    const auto* original=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_NVS,part_name);
    REQUIRE(original);auto synthetic=*original;
    if(const char* p=std::getenv("GS_DIAG_PAGES"))synthetic.size=std::strtoul(p,nullptr,10)*4096;
    // Capacity-only emulator fixtures may explore larger flash proposals.
    // This descriptor is not a production partition table or guard approval.
    pages=synthetic.size/4096;REQUIRE(pages>=32 && pages<=512);
    const auto* part=&synthetic;diag::part=part;
    REQUIRE(esp_partition_erase_range(part,0,part->size)==ESP_OK);
    esp_partition_clear_stats();REQUIRE(nvs_flash_init_partition_ptr(part)==ESP_OK);
    nvs_handle_t h{};REQUIRE(nvs_open_from_partition(part_name,"life",NVS_READWRITE,&h)==ESP_OK);
    diag::active=true;
    const bool schedule=argc>3 && std::strcmp(argv[3],"schedule")==0;
    const unsigned fixed=20+critical;
    const unsigned load=schedule?fixed:static_cast<unsigned>(sizes.size());
    for(unsigned i=0;i<load;++i) {
        const auto rc=put(h,"o",i,sizes[i],0);
        if(rc!=ESP_OK) {
            std::printf("OFFLINE_STOP phase=load object=%u bytes=%u error=%s peak_pages=%u peak_live_entries=%u\n",i,sizes[i],esp_err_to_name(rc),diag::peak_pages,diag::peak_live);
            metric("offline_stop",i,part);nvs_close(h);return 2;
        }
        REQUIRE(offline_verify(h,"o",i,sizes[i],0));
    }
    metric("offline_loaded",load,part);
    if(argc>3 && std::strcmp(argv[3],"fault")==0) {
        REQUIRE(argc>4);
        // Prime deleted entries/GC without changing any committed fixture body.
        for(unsigned i=0;i<40;++i) {
            REQUIRE(put(h,"garbage",0,4096,i+1)==ESP_OK);
            REQUIRE(nvs_erase_key(h,"garbage0")==ESP_OK);REQUIRE(nvs_commit(h)==ESP_OK);
        }
        // Old committed body/selector remains until complete new summary +
        // processed-state checkpoint + independent selector publication.
        REQUIRE(put(h,"txold",0,124,77)==ESP_OK);
        REQUIRE(put(h,"txpick",0,512,77)==ESP_OK);
        const auto erase_before=esp_partition_get_erase_ops();
        const auto cut=std::strtoull(argv[4],nullptr,10);
        diag::units=0;diag::calls=0;diag::latch=true;
        diag::verbose=std::getenv("GS_TRACE")!=nullptr;
        esp_partition_fail_after(cut,ESP_PARTITION_FAIL_AFTER_MODE_BOTH);
        auto a=put(h,"txsum",1,4096,88);
        auto b=a==ESP_OK?put(h,"txcp",1,6144,88):a;
        auto c=b==ESP_OK?put(h,"txpick",1,512,88):b;
        if(c==ESP_OK) {
            c=nvs_erase_key(h,"txold0");
            if(c==ESP_OK)c=nvs_erase_key(h,"txpick0");
            if(c==ESP_OK)c=nvs_commit(h);
        }
        std::printf("OFFLINE_FAULT_IO cut=%llu units=%zu calls=%zu summary_result=%s checkpoint_result=%s final_result=%s frozen=%d transaction_erases=%zu priming_erases=%zu\n",cut,diag::units,diag::calls,esp_err_to_name(a),esp_err_to_name(b),esp_err_to_name(c),diag::frozen,esp_partition_get_erase_ops()-erase_before,erase_before);
        nvs_close(h);REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);
        diag::active=false;diag::frozen=false;esp_partition_fail_after(static_cast<size_t>(-1),ESP_PARTITION_FAIL_AFTER_MODE_BOTH);
        REQUIRE(nvs_flash_init_partition_ptr(part)==ESP_OK);
        REQUIRE(nvs_open_from_partition(part_name,"life",NVS_READWRITE,&h)==ESP_OK);
        const bool old_ok=offline_verify(h,"txpick",0,512,77)&&offline_verify(h,"txold",0,124,77);
        const bool new_ok=offline_verify(h,"txpick",1,512,88)&&offline_verify(h,"txsum",1,4096,88)&&offline_verify(h,"txcp",1,6144,88);
        std::printf("OFFLINE_FAULT_RECOVERY cut=%llu old_valid=%d new_valid=%d\n",cut,old_ok,new_ok);
        REQUIRE(old_ok||new_ok);
        nvs_close(h);REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);
        return 0;
    }
    if(!schedule) {
        // The four extra candidate values were charged during peak admission.
        // Release that temporary workspace before exercising the same transaction.
        const unsigned progress=fixed+history+cow;
        for(unsigned i=progress;i<progress+4;++i){char k[16];std::snprintf(k,sizeof(k),"o%u",i);REQUIRE(nvs_erase_key(h,k)==ESP_OK);}
        REQUIRE(nvs_commit(h)==ESP_OK);
        for(unsigned c=1;c<=32;++c) {
            auto rc=put(h,"newr",c%2,3485,c);
            if(rc==ESP_OK)rc=put(h,"news",c%2,6144,c);
            if(rc==ESP_OK)rc=put(h,"pick",c%2,512,c);
            if(rc!=ESP_OK){std::printf("OFFLINE_STOP phase=progress cycle=%u error=%s\n",c,esp_err_to_name(rc));metric("offline_stop",c,part);return 3;}
            REQUIRE(offline_verify(h,"newr",c%2,3485,c));
            REQUIRE(offline_verify(h,"news",c%2,6144,c));
            REQUIRE(offline_verify(h,"pick",c%2,512,c));
            // Capacity/reclaim witness: old baseline remains valid; selection is
            // abstract, so these temporary objects can be released after readback.
            for(const char* prefix:{"newr","news","pick"}) {char k[16];std::snprintf(k,sizeof(k),"%s%u",prefix,c%2);REQUIRE(nvs_erase_key(h,k)==ESP_OK);}
            REQUIRE(nvs_commit(h)==ESP_OK);
        }
        nvs_close(h);REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);
        REQUIRE(nvs_flash_init_partition_ptr(part)==ESP_OK);
        REQUIRE(nvs_open_from_partition(part_name,"life",NVS_READWRITE,&h)==ESP_OK);
        for(unsigned i=0;i<sizes.size();++i)if(i<progress || i>=progress+4)REQUIRE(offline_verify(h,"o",i,sizes[i],0));
        metric("offline_recovered",32,part);
        std::printf("OFFLINE_PASS pages=%u peak_pages=%u peak_live_entries=%u history=%u cow=%u arrivals=%u\n",pages,diag::peak_pages,diag::peak_live,history,cow,arrivals);
    } else {
        const auto wb=esp_partition_get_write_bytes(),eb=esp_partition_get_erase_ops(),lb=diag::logical_bytes,iw=diag::entry_writes;
        std::vector<size_t> sector_before;
        const auto first=part->address/4096;
        for(unsigned p=0;p<pages;++p)sector_before.push_back(esp_partition_get_sector_erase_count(first+p));
        unsigned completed=0,sealed=0,stage=0,checkpoints=0,reports=0,checkpoint_period=0,local_day=0;
        auto fail=[&](const char* phase,esp_err_t rc){std::printf("OFFLINE_SCHEDULE_STOP phase=%s completed=%u error=%s\n",phase,completed,esp_err_to_name(rc));metric("offline_schedule_stop",completed,part);};
        for(unsigned e=1;e<=arrivals;++e) {
            auto rc=put(h,"evt",(e-1)%32,124,e);
            if(rc!=ESP_OK){fail("event",rc);return 4;}
            ++completed;
            if(e%32==0 || e==arrivals) {
                rc=put(h,"stage",stage,4096,e);if(rc!=ESP_OK){fail("source_seal",rc);return 4;}
                ++stage;
                // 32 * maximum WARM 103 + 1434 context exceeds one extent.
                rc=put(h,"stage",stage,4096,e);if(rc!=ESP_OK){fail("source_seal_second",rc);return 4;}
                ++stage;
                // Combined immutable report generation + durable selector; no full
                // state/meta rewrite per event. Length-matched proposed cadence.
                rc=put(h,"o",6+(reports+1)%3,3485,e);if(rc!=ESP_OK){fail("report",rc);return 4;}
                rc=put(h,"o",12+(reports+1)%2,512,e);if(rc!=ESP_OK){fail("report_root",rc);return 4;}
                for(unsigned j=0;j<((e-1)%32+1);++j){char k[16];std::snprintf(k,sizeof(k),"evt%u",j);REQUIRE(nvs_erase_key(h,k)==ESP_OK);}
                REQUIRE(nvs_commit(h)==ESP_OK);++reports;
            }
            const unsigned elapsed=static_cast<std::uint64_t>(e)*3*86400/arrivals;
            const unsigned day=(elapsed+43200)/86400;
            if(day>local_day) {
                auto daily_rc=put(h,"o",16+local_day,320,e);
                if(daily_rc!=ESP_OK){fail("day_rollover",daily_rc);return 4;}
                local_day=day;
            }
            const unsigned period=elapsed/(6*3600);
            if(e%128==0 || e==arrivals || (e%32==0 && period>checkpoint_period)) {
                checkpoint_period=period;
                auto rc=put(h,"o",9+(checkpoints+1)%3,6144,e);if(rc!=ESP_OK){fail("checkpoint",rc);return 4;}
                const unsigned next=(static_cast<std::uint64_t>(e)*history+arrivals-1)/arrivals;
                while(sealed<next){rc=put(h,"hist",sealed,4096,e);if(rc!=ESP_OK){fail("history",rc);return 4;}++sealed;}
                rc=put(h,"o",12+(checkpoints+1)%2,512,e);if(rc!=ESP_OK){fail("checkpoint_root",rc);return 4;}
                for(unsigned j=0;j<stage;++j){char k[16];std::snprintf(k,sizeof(k),"stage%u",j);REQUIRE(nvs_erase_key(h,k)==ESP_OK);}
                REQUIRE(nvs_commit(h)==ESP_OK);stage=0;++checkpoints;
            }
        }
        REQUIRE(put(h,"o",16+std::min(local_day,3u),320,arrivals)==ESP_OK);
        size_t max_sector=0;for(unsigned p=0;p<pages;++p)max_sector=std::max(max_sector,esp_partition_get_sector_erase_count(first+p)-sector_before[p]);
        const auto logical=diag::logical_bytes-lb,programmed=esp_partition_get_write_bytes()-wb;
        std::printf("OFFLINE_SCHEDULE scenario_records=%u days=3 logical_bytes=%zu programmed_bytes=%zu write_amplification=%.6f entries_written=%zu page_erases=%zu max_sector_erases=%zu checkpoints=%u reports=%u history=%u peak_pages=%u\n",arrivals,logical,programmed,logical?double(programmed)/logical:0,diag::entry_writes-iw,esp_partition_get_erase_ops()-eb,max_sector,checkpoints,reports,sealed,diag::peak_pages);
        const auto back_w=esp_partition_get_write_bytes(),back_e=esp_partition_get_erase_ops();
        for(unsigned j=0;j<sealed;++j) {
            // Proposed manifest-level submission fence BEFORE external IO, then
            // authenticated durable receipt + selector BEFORE body retirement.
            REQUIRE(put(h,"send",j,96,j+1)==ESP_OK);
            REQUIRE(put(h,"done",j,96,j+1)==ESP_OK);
            REQUIRE(put(h,"o",12+j%2,512,j+1)==ESP_OK);
            char k[16];std::snprintf(k,sizeof(k),"hist%u",j);
            REQUIRE(nvs_erase_key(h,k)==ESP_OK);REQUIRE(nvs_commit(h)==ESP_OK);
        }
        std::printf("OFFLINE_BACKFILL chunks=%u programmed_bytes=%zu page_erases=%zu\n",sealed,esp_partition_get_write_bytes()-back_w,esp_partition_get_erase_ops()-back_e);
    }
    nvs_close(h);REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);diag::active=false;
    return 0;
}
