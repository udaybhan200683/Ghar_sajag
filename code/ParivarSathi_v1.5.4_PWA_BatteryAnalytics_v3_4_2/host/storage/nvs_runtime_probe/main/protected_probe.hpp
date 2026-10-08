// Included after the real NVS Store/Fixture definitions, never a firmware TU.
int protected_reclamation_probe(const esp_partition_t* part) {
    using namespace compact_sdk;
    // The SDK emulator allocates per-sector counters without initializing
    // them. Establish the measurement baseline before this focused fixture.
    esp_partition_clear_stats();
    Proof owner;unsigned completed=0,next=2;std::uint64_t generation=0;
    {
        Fixture f(true);owner=f.enroll(0);
        REQUIRE(f.tx.checkpoint_reducer(Bytes(4096,0x11))==Result::Committed);f.collect();
        // Keep one acknowledged body pinned by a pending backend dependency.
        REQUIRE(f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x11))==Result::Committed);f.collect();
        f.s.protected_space=true;diag::active=true;
        diag::peak_live=0;diag::peak_pages=0;diag::observe();
        const auto erases=esp_partition_get_erase_ops();
        bool rejected=false;
        for(;next<=128;++next) {
            const auto r=f.admit(owner,next,Bytes(448,0x43),Bytes(4096,0x11));
            if(r!=Result::Committed) {
                REQUIRE(f.s.result(r)==SpaceOutcome::InsufficientProtectedSpace);
                rejected=true;break;
            }
            f.collect();
            const auto writes=f.s.writes;
            REQUIRE(f.tx.recover());
            REQUIRE(f.admit(owner,next,Bytes(448,0x43),Bytes{})==Result::Duplicate);
            REQUIRE(f.s.writes==writes); // Lost ACK, no second business effect.
            REQUIRE(f.report(owner,next-1,next)==Result::Committed);f.collect();
            // Host caller supplies trusted local completion and durable backend
            // acceptance. This models a receipt, not a backend implementation.
            REQUIRE(f.tx.dependencies_complete(owner,1,next,true,true)==Result::Committed);f.collect();
            REQUIRE(f.tx.recover()&&f.tx.state()->rows.size()==1&&
                f.tx.state()->rows[0].sequence==1&&f.tx.state()->rows[0].backend&&
                f.tx.state()->rows[0].body==Bytes(448,0x42)&&f.tx.state()->owners[0].charged==0);
            ++completed;
        }
        REQUIRE(rejected&&completed>0);
        generation=f.tx.state()->generation;
        const auto writes=f.s.writes;
        for(unsigned retry=0;retry<3;++retry) {
            REQUIRE(f.s.result(f.admit(owner,next,Bytes(448,0x43),Bytes(4096,0x11)))==
                SpaceOutcome::InsufficientProtectedSpace);
            REQUIRE(f.s.writes==writes&&f.tx.recover()&&f.tx.state()->generation==generation);
        }
        REQUIRE(esp_partition_get_erase_ops()==erases);
        std::printf("RECLAMATION_COUNTEREXAMPLE completed=%u live_rows=1 payload=%zu certified_free_pages=%zu required_pages=%zu gc_erases=0 repeated_reject_writes=0 peak_pages=%u peak_live_entries=%u\n",
            completed,payload(f.s),f.s.certified_free,f.s.reservation.required_free_pages,
            diag::peak_pages,diag::peak_live);
        metric("reclamation_rejected",completed,part);
    }
    remount(part);Fixture f(false);f.s.protected_space=true;
    REQUIRE(f.tx.state()->generation==generation&&f.tx.state()->rows.size()==1&&
        f.tx.state()->rows[0].body==Bytes(448,0x42)&&f.tx.state()->reducer==Bytes(4096,0x11));
    const auto writes=f.s.writes;
    REQUIRE(f.s.result(f.admit(owner,next,Bytes(448,0x43),Bytes(4096,0x11)))==
        SpaceOutcome::InsufficientProtectedSpace);
    REQUIRE(f.s.writes==writes);
    std::printf("RECLAMATION_SAFE_REJECTION_PASS current_root=valid pinned_body=preserved restart=verified sustainable_progress=NOT_IMPLEMENTED\n");
    return 0;
}

int protected_io_probe() {
    using namespace compact_sdk;
    Fixture f(true);const auto owner=f.enroll(0);
    REQUIRE(f.tx.checkpoint_reducer(Bytes(4096,0x11))==Result::Committed);f.collect();
    f.s.protected_space=true;const auto generation=f.tx.state()->generation;
    for(const auto refusal:{Store::RefuseIO::Immutable,Store::RefuseIO::Manifest,Store::RefuseIO::Head}) {
        f.s.refuse_io=refusal;
        const auto result=f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x22));
        REQUIRE(f.s.result(result)==(refusal==Store::RefuseIO::Immutable?
            SpaceOutcome::RestartRequired:SpaceOutcome::MetadataPublicationFailure));
        REQUIRE(f.tx.recover()&&f.tx.state()->generation==generation&&f.tx.state()->rows.empty()&&
            f.tx.state()->owners[0].charged==0&&f.tx.state()->reducer==Bytes(4096,0x11));
    }
    // A further failed CONTROL publication can occupy the final reducer slot.
    // Ordinary admission must protect that slot, reject without writes, and
    // resume only after authorized dependency collection, never blind deletion.
    REQUIRE(f.tx.checkpoint_reducer(Bytes(4096,0x33))==Result::Fault);
    REQUIRE(f.tx.recover()&&f.tx.state()->generation==generation);
    const auto blocked_writes=f.s.writes;
    f.s.refuse_io=Store::RefuseIO::None;
    REQUIRE(f.s.result(f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x22)))==
        SpaceOutcome::InsufficientProtectedSpace);
    REQUIRE(f.s.writes==blocked_writes&&f.tx.state()->generation==generation);
    f.collect();
    REQUIRE(f.s.result(f.admit(owner,1,Bytes(448,0x42),Bytes(4096,0x22)))==SpaceOutcome::Committed);
    const auto writes=f.s.writes;
    REQUIRE(f.s.result(f.admit(owner,1,Bytes(448,0x42),Bytes{}))==SpaceOutcome::Duplicate&&f.s.writes==writes);
    std::printf("PROTECTED_TYPED_IO_PASS dependency_refusal=restart_required manifest_head_refusal=metadata_failure reducer_slot_reserve=protected authorized_collection=resumed ack=only_after_publication\n");
    return 0;
}

int protected_max_report_probe(const esp_partition_t* part) {
    using namespace compact_sdk;
    Fixture f(true);std::array<Proof,6> owners;
    for(unsigned n=0;n<6;++n){owners[n]=f.enroll(n);REQUIRE(f.report(owners[n],1,32,true)==Result::Committed);f.collect();}
    REQUIRE(f.tx.checkpoint_reducer(Bytes(4096,0x11))==Result::Committed);f.collect();
    f.s.protected_space=true;diag::active=true;diag::peak_live=0;diag::peak_pages=0;
    REQUIRE(f.admit(owners[0],1,Bytes(448,0x42),Bytes(4096,0x22))==Result::Committed);
    REQUIRE(f.s.reservation.operation_pages==10&&f.s.reservation.control_pages==8&&
        f.s.reservation.required_free_pages==19);
    REQUIRE(f.tx.recover()&&f.tx.state()->rows.size()==1&&f.tx.state()->owners[0].charged==0);
    REQUIRE(f.compact.collect_selected(*f.tx.state()));
    REQUIRE(f.report(owners[0],2,32)==Result::Committed);
    REQUIRE(f.tx.recover()&&f.tx.state()->owners[0].report.generation==2&&
        !f.tx.state()->rows[0].retry&&f.tx.state()->rows[0].backend);
    const auto writes=f.s.writes;
    REQUIRE(f.admit(owners[0],1,Bytes(448,0x42),Bytes{})==Result::Duplicate&&f.s.writes==writes);
    std::printf("PROTECTED_MAX_REPORT_PASS six_owners=1 max_pending_reports=1 manifest_crosses_4000=1 old_new_dependencies=protected peak_pages=%u peak_live_entries=%u\n",
        diag::peak_pages,diag::peak_live);
    metric("protected_max_report",1,part);return 0;
}

int protected_probe(const esp_partition_t* part, bool legacy_full, unsigned body_size, bool changing_reducer) {
    using namespace compact_sdk;
    unsigned accepted=0, reports=0;Proof owner;
    {
        Fixture f(true);owner=f.enroll(0);
        REQUIRE(f.tx.checkpoint_reducer(Bytes(4096,0x11))==Result::Committed);f.collect();
        if(legacy_full) {
            REQUIRE(f.admit(owner,1,Bytes(body_size,0x42),Bytes(4096,0x11))==Result::Committed);
            accepted=1;f.collect();prime_gc(f.s);
        }
        f.s.protected_space=true;
        diag::active=true;diag::peak_live=0;diag::peak_pages=0;diag::observe();
        const auto erase_before=esp_partition_get_erase_ops();
        if(!legacy_full)for(unsigned seq=1;seq<=384;++seq) {
            const auto result=f.admit(owner,seq,Bytes(body_size,0x42),
                Bytes(4096,changing_reducer?0x20+(seq%2):0x11));
            if(result!=Result::Committed) {
                REQUIRE(f.s.result(result)==SpaceOutcome::InsufficientProtectedSpace);break;
            }
            ++accepted;f.collect();
            if(seq%16==0){REQUIRE(f.report(owner,++reports,seq)==Result::Committed);f.collect();}
        }
        REQUIRE(accepted>0);
        if(!legacy_full&&!changing_reducer)REQUIRE(accepted>16&&reports>0);
        const auto gen=f.tx.state()->generation, saved=payload(f.s);
        const auto charge=f.tx.state()->owners[0].charged;
        const auto reducer=f.tx.state()->reducer;
        const auto ordinary_reserve=f.s.reservation;
        const auto writes=f.s.writes;const auto units=diag::units;
        for(unsigned attempt=0;attempt<3;++attempt) {
            REQUIRE(f.s.result(f.admit(owner,accepted+1,Bytes(body_size,0x42),Bytes(4096,0x33)))==
                SpaceOutcome::InsufficientProtectedSpace);
            REQUIRE(f.s.writes==writes&&diag::units==units&&f.tx.recover());
            REQUIRE(f.tx.state()->generation==gen&&f.tx.state()->rows.size()==accepted&&
                f.tx.state()->owners[0].charged==charge&&f.tx.state()->reducer==reducer);
        }
        const auto reserve=f.s.reservation;
        std::printf("PROTECTED_BOUNDARY pages=%u body=%u accepted=%u payload=%zu certified_free=%zu operation_pages=%zu control_pages=%zu required_free_pages=%zu repeated_reject_writes=0\n",
            part->size/4096,body_size,accepted,saved,f.s.certified_free,reserve.operation_pages,
            reserve.control_pages,reserve.required_free_pages);
        if(!legacy_full)std::printf("PROTECTED_ORDINARY_LIMIT operation_pages=%zu control_pages=%zu required_free_pages=%zu reserve_bytes=%zu\n",
            ordinary_reserve.operation_pages,ordinary_reserve.control_pages,
            ordinary_reserve.required_free_pages,(ordinary_reserve.control_pages+1)*4096);
        REQUIRE(f.s.result(f.admit(owner,accepted,Bytes(body_size,0x42),Bytes{0xee}))==SpaceOutcome::Duplicate);
        REQUIRE(f.s.writes==writes&&diag::units==units); // Lost ACK bypasses space rejection.
        if(!legacy_full) {
            REQUIRE(f.report(owner,++reports,accepted)==Result::Committed);f.collect();
            REQUIRE(f.tx.state()->owners[0].charged==0);
            REQUIRE(f.tx.checkpoint_reducer(Bytes(4096,0x55))==Result::Committed);f.collect();
            REQUIRE(f.tx.recover()&&f.tx.state()->reducer==Bytes(4096,0x55));
            REQUIRE(esp_partition_get_erase_ops()==erase_before); // Certified operations avoid GC.
        } else {
            REQUIRE(f.tx.checkpoint_reducer(Bytes(4096,0x55))==Result::Fault);
            REQUIRE(f.s.outcome==SpaceOutcome::InsufficientProtectedSpace);
            REQUIRE(f.tx.recover()&&f.tx.state()->reducer==reducer);
        }
        // Required dependencies cannot be silently dropped by reclaiming old
        // candidates. Every acknowledged body is checked before/after restart.
        for(const auto& row:f.tx.state()->rows)REQUIRE(row.body==Bytes(body_size,0x42));
        std::printf("PROTECTED_PEAK nonblank_pages=%u bytes=%u live_entries=%u gc_erases=%zu credit_checkpoint=%s\n",
            diag::peak_pages,diag::peak_pages*4096,diag::peak_live,
            esp_partition_get_erase_ops()-erase_before,legacy_full?"safe_rejection":"committed");
        metric("protected_boundary",accepted,part);
    }
    remount(part);Fixture recovered(false);recovered.s.protected_space=true;
    REQUIRE(recovered.tx.state()->rows.size()==accepted);
    for(const auto& row:recovered.tx.state()->rows)REQUIRE(row.body==Bytes(body_size,0x42));
    REQUIRE(recovered.s.result(recovered.admit(owner,accepted,Bytes(body_size,0x42),Bytes{}))==SpaceOutcome::Duplicate);
    // Unsupported layout is explicitly rejected without mutation.
    const auto writes=recovered.s.writes;auto bad=*part;bad.size=65536;diag::part=&bad;
    REQUIRE(recovered.s.result(recovered.admit(owner,accepted+1,Bytes(body_size,0x42),Bytes(4096,0x66)))==
        SpaceOutcome::UnsupportedConfiguration);
    REQUIRE(recovered.s.writes==writes);diag::part=part;
    std::printf("PROTECTED_SDK_PASS restart_preserved=%u unsupported_reject=1 lost_ack_duplicate=1\n",accepted);
    return 0;
}
