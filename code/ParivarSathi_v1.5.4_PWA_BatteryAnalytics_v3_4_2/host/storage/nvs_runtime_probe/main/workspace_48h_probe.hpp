// Focused negative qualification, not an authenticated history implementation.
// Frozen NORMAL/mixed/48h objects stay pinned. Only the four unselected temporary
// metadata values of the existing size fixture may be removed. No cloud receipt.
namespace workspace48 {
constexpr unsigned object_count=89, temporary_begin=53, temporary_end=57;
using Sizes=std::array<unsigned,object_count>;

void verify(nvs_handle_t h,const Sizes& sizes,bool require_temporaries) {
    for(unsigned i=0;i<sizes.size();++i)
        if(require_temporaries||i<temporary_begin||i>=temporary_end)
            REQUIRE(offline_verify(h,"o",i,sizes[i],0));
}
void reclaim_temporaries(nvs_handle_t h) {
    for(unsigned i=temporary_begin;i<temporary_end;++i) {
        char name[16];std::snprintf(name,sizeof(name),"o%u",i);
        const auto rc=nvs_erase_key(h,name);
        REQUIRE(rc==ESP_OK||rc==ESP_ERR_NVS_NOT_FOUND);
    }
    REQUIRE(nvs_commit(h)==ESP_OK);
}
void certificate(const esp_partition_t* part,const char* phase) {
    using namespace compact_sdk;
    Store adapter;adapter.protected_space=true;
    // A LOWER BOUND on any ordinary publication: new event object, bank and
    // head, no new reducer. Each of these costs at least two page activations.
    // This is deliberately optimistic, NOT a serializer or a proposed codec.
    PublicationPlan minimum;minimum.ordinary_admission=true;
    minimum.blobs={531,4000,Transaction::head_bytes};
    minimum.control_manifest_bytes=control_manifest_bound(1);
    minimum.event_objects_after=1;minimum.reducer_objects_after=1;
    REQUIRE(workspace(minimum).required_free_pages==15);
    const auto writes=esp_partition_get_write_bytes(),erases=esp_partition_get_erase_ops();
    for(unsigned attempt=0;attempt<3;++attempt) {
        REQUIRE(!adapter.prepare_publication(minimum));
        REQUIRE(adapter.outcome==SpaceOutcome::InsufficientProtectedSpace);
        REQUIRE(adapter.writes==0&&esp_partition_get_write_bytes()==writes&&
            esp_partition_get_erase_ops()==erases);
    }
    const auto media=inspect(part);
    const auto min_live_pages=(media.live+125)/126;
    // Include one possible lazy page, as the real adapter does. Even perfect
    // repacking cannot certify this reserve while these live entries coexist.
    REQUIRE(min_live_pages+adapter.reservation.required_free_pages+1>pages);
    std::printf("WORKSPACE48_CERT phase=%s occupied_pages=%u raw_erased_pages=%u live_entries=%u deleted_entries=%u certified_pages=%zu required_pages=%zu minimum_live_pages=%u ideal_packed_shortfall_pages=%zu attempts=3 reject_writes=0 ack_eligible=0\n",
        phase,media.allocated,pages-media.allocated,media.live,media.erased,
        adapter.certified_free,adapter.reservation.required_free_pages,min_live_pages,
        min_live_pages+adapter.reservation.required_free_pages+1-pages);
    PublicationPlan maximum=minimum;
    maximum.blobs={531,4124,control_manifest_bound(kRows),Transaction::head_bytes};
    maximum.control_manifest_bytes=control_manifest_bound(kRows);
    REQUIRE(workspace(maximum).required_free_pages==25);
    REQUIRE(!adapter.prepare_publication(maximum));
    REQUIRE(adapter.writes==0&&esp_partition_get_write_bytes()==writes);
    std::printf("WORKSPACE48_MAXIMUM phase=%s control_reserve_bytes=49152 complete_plan_pages=%zu available_certified_pages=%zu\n",
        phase,adapter.reservation.required_free_pages,adapter.certified_free);
}
} // namespace workspace48

int workspace_48h_probe(int argc,char** argv) {
    using namespace workspace48;
    REQUIRE(argc==3||argc==4);
    std::ifstream input(argv[2]);unsigned history=0,cow=0,critical=0,arrivals=0;
    REQUIRE(input.good());input>>history>>cow>>critical>>arrivals;
    REQUIRE(history==23&&cow==8&&critical==2&&arrivals==784);
    Sizes sizes{};unsigned logical=0;
    for(auto& size:sizes){REQUIRE(bool(input>>size)&&size>0&&size<=6144);logical+=size;}
    unsigned extra=0;REQUIRE(!(input>>extra)&&logical==213646);
    const auto* original=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_NVS,part_name);
    REQUIRE(original);auto part=*original;part.size=262144;pages=64;diag::part=&part;
    REQUIRE(esp_partition_erase_range(&part,0,part.size)==ESP_OK);
    esp_partition_clear_stats();REQUIRE(nvs_flash_init_partition_ptr(&part)==ESP_OK);
    nvs_handle_t h{};REQUIRE(nvs_open_from_partition(part_name,"life",NVS_READWRITE,&h)==ESP_OK);
    diag::active=true;
    for(unsigned i=0;i<sizes.size();++i)REQUIRE(put(h,"o",i,sizes[i],0)==ESP_OK);
    verify(h,sizes,true);certificate(&part,"loaded");metric("workspace48_loaded",89,&part);
    if(argc==4) {
        nvs_close(h);REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);
        const auto child=fork();REQUIRE(child>=0);
        if(child==0) {
            REQUIRE(nvs_flash_init_partition_ptr(&part)==ESP_OK);
            REQUIRE(nvs_open_from_partition(part_name,"life",NVS_READWRITE,&h)==ESP_OK);
            diag::hard_stop=true;diag::units=0;diag::calls=0;
            const auto cut=std::strtoul(argv[3],nullptr,10);
            esp_partition_fail_after(cut,ESP_PARTITION_FAIL_AFTER_MODE_BOTH);
            reclaim_temporaries(h);
            std::printf("WORKSPACE48_RECLAIM_IO cut=%lu units=%zu calls=%zu\n",cut,diag::units,diag::calls);
            _exit(0);
        }
        int status=0;REQUIRE(waitpid(child,&status,0)==child&&WIFEXITED(status));
        REQUIRE(WEXITSTATUS(status)==0||WEXITSTATUS(status)==77);
        // The first injected failure exits immediately. No child cleanup or
        // application writes can continue on the supposedly powered-off device.
        REQUIRE(nvs_flash_init_partition_ptr(&part)==ESP_OK);
        REQUIRE(nvs_open_from_partition(part_name,"life",NVS_READWRITE,&h)==ESP_OK);
        verify(h,sizes,false);certificate(&part,"interrupted_reclaim_recovered");
        std::printf("WORKSPACE48_RECLAIM_RECOVERY child_exit=%u pinned_blobs=85 preserved=1\n",WEXITSTATUS(status));
    } else {
        const auto before=esp_partition_get_erase_ops();
        reclaim_temporaries(h);verify(h,sizes,false);
        certificate(&part,"temporaries_removed");metric("workspace48_collected",85,&part);
        // IDF purge zeroes deleted entry data; it is NOT page compaction. Test
        // once, never use blind erase/GC retries or purge accepted objects.
        REQUIRE(nvs_purge_all(h)==ESP_OK&&nvs_commit(h)==ESP_OK);
        REQUIRE(esp_partition_get_erase_ops()==before);
        verify(h,sizes,false);certificate(&part,"purged_deleted_metadata");
        metric("workspace48_purged",85,&part);
    }
    nvs_close(h);REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);
    REQUIRE(nvs_flash_init_partition_ptr(&part)==ESP_OK);
    REQUIRE(nvs_open_from_partition(part_name,"life",NVS_READWRITE,&h)==ESP_OK);
    verify(h,sizes,false);certificate(&part,"restart");
    nvs_close(h);REQUIRE(nvs_flash_deinit_partition(part_name)==ESP_OK);
    std::printf("WORKSPACE48_COUNTEREXAMPLE_PASS history_preserved=1 cloud_receipts=0 workspace_restoration=FAILED repeated_admission=REJECTED authenticated_history_mapping=NOT_IMPLEMENTED\n");
    return 0;
}
