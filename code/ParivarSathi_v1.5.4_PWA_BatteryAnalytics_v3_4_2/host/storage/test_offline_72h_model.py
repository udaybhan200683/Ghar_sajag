#!/usr/bin/env python3
"""Focused host semantic tests, not implementation qualification."""
import hashlib
import struct
import unittest
from dataclasses import replace
from offline_72h_model import (Event, Summary, Store, Backend, summarize,
                              workload, ledger, RATES, entries)

class OfflineTests(unittest.TestCase):
    def points(self):
        return [Event(0, 1, i+1, 43200+i*70, checkpoint=1) for i in range(4)]

    def test_sparse_points_and_source_membership(self):
        events = self.points()
        events[2] = replace(events[2], seq=17)
        exact, summaries = summarize(events)
        self.assertEqual(len(exact), 0)
        self.assertEqual(len(summaries), 1)
        data = summaries[0].encode()
        self.assertEqual(len(data), 70)
        mask = struct.unpack_from('<Q', data, 21)[0]
        self.assertEqual(mask, (1<<0)|(1<<1)|(1<<3)|(1<<16))
        points = [struct.unpack_from('<BHIh', data, 34+i*9)[1] for i in range(4)]
        self.assertEqual(points, [0,70,210,140])  # ordered by exact source seq
        self.assertNotIn(35, points)  # no invented continuous activity

    def test_exact_safety_classes_and_motion_exclusions(self):
        kinds = ['call_family','i_am_ok','door_open','door_closed','alert','observation_fault','security_fault']
        events = [Event(0,1,i+1,43200+i,kind,safety=True,checkpoint=1) for i,kind in enumerate(kinds)]
        events += [replace(self.points()[0], seq=100, safety=True),
                   replace(self.points()[1], seq=101, delayed=True),
                   replace(self.points()[2], seq=102, uncertainty=3600)]
        exact, summaries = summarize(events)
        self.assertEqual(exact, events)
        self.assertEqual(summaries, [])
        self.assertNotEqual(events[0].key, events[1].key)

    def test_context_epoch_midnight_clock_and_delay_split(self):
        base = Event(0,1,1,86390,checkpoint=1)
        events = [base, replace(base,seq=2,at=86410), replace(base,seq=3,origin=2),
                  replace(base,seq=4,clock_revision=1), replace(base,seq=5,owner=2),
                  replace(base,seq=6,meaning=2), replace(base,seq=7,delayed=True)]
        exact, summaries = summarize(events)
        self.assertEqual(len(exact),1)
        self.assertEqual(len(summaries),6)
        self.assertEqual(len({s.identity for s in summaries}),6)

    def test_native_source_summary_preserves_frozen_exact_body(self):
        e = Event(0,1,1,43210,'source_summary',43230,17,checkpoint=1,monotonic_ms=10123)
        self.assertEqual(summarize([e])[0],[e])
        with self.assertRaises(AssertionError):Summary((e,),3600)

    def test_bounded_summary_and_sparse_sequence_spill(self):
        events = [Event(0,1,i+1,43200+i,checkpoint=1) for i in range(33)]
        self.assertEqual([len(s.events) for s in summarize(events)[1]],[32,1])
        events = [events[0],replace(events[1],seq=65)]
        self.assertEqual(len(summarize(events)[1]),2)
        max_events = [Event(0,1,i+1,43200+i,checkpoint=1) for i in range(32)]
        self.assertEqual(len(Summary(tuple(max_events),3600).encode()),322)
        big = replace(max_events[0],seq=2**63+1)
        self.assertEqual(len(Summary((big,),3600).encode()),43)

    def test_ack_loss_retry_conflict_and_report_retirement(self):
        st = Store()
        e = self.points()[0]
        self.assertEqual(st.ingest(e,False),'failed')
        self.assertFalse(st.acked)
        self.assertEqual(st.ingest(e),'accepted')
        st = st.recover()
        self.assertEqual(st.ingest(e),'duplicate')
        with self.assertRaises(AssertionError): st.ingest(replace(e,at=e.at+1))
        st.compact(Summary((e,),3600))
        st = st.recover()
        self.assertEqual(st.ingest(e),'duplicate')
        self.assertIn(e.key,st.witnesses)
        st.retire({e.key})
        self.assertEqual(st.ingest(e),'stale')

    def test_crashes_twice_at_all_compaction_points(self):
        for cut in ['before_checkpoint','before_summary','before_select','before_reclaim',None]:
            st = Store()
            events = self.points()
            for e in events: self.assertEqual(st.ingest(e),'accepted')
            s = Summary(tuple(events),3600)
            st.compact(s,cut)
            st = st.recover().recover()
            represented = set(st.bodies)
            for summary in st.summaries.values(): represented |= summary.sources
            self.assertEqual(represented,{e.key for e in events})
            self.assertEqual(len(st.witnesses),4)
            if st.bodies: st.compact(s)
            self.assertEqual(st.recover().summaries[s.identity],s)

    def test_backend_lost_ack_and_source_overlap(self):
        st, cloud = Store(),Backend()
        e = self.points()[0]
        st.ingest(e)
        st.compact(Summary((e,),3600))
        identity = next(iter(st.summaries))
        # A request lost before server execution has no completion.
        self.assertNotIn(identity,st.complete)
        st.publish(cloud,identity,lost_ack=True)
        self.assertNotIn(identity,st.recover().complete)
        with self.assertRaises(AssertionError):st.reclaim_completed(identity)
        st.publish(cloud,identity,receipt_commit=False)
        self.assertNotIn(identity,st.recover().complete)
        st.publish(cloud,identity)
        st.publish(cloud,identity)
        self.assertEqual(cloud.effects,{e.key})
        self.assertIn(identity,st.recover().complete)
        st.reclaim_completed(identity)
        self.assertEqual(st.recover().ingest(e),'duplicate')
        with self.assertRaises(AssertionError): cloud.accept(identity,{e.key},'conflict')

    def test_exact_inflight_exclusion_and_exclusive_backend_claim(self):
        st, cloud = Store(), Backend()
        e = self.points()[0]
        self.assertEqual(st.ingest(e,authenticated=False),'unauthorized')
        self.assertEqual(st.ingest(replace(e,owner=2)),'unauthorized')
        self.assertFalse(st.acked)
        st.ingest(e)
        self.assertFalse(st.begin_exact_submit(e.key,False))
        self.assertTrue(st.begin_exact_submit(e.key))
        st = st.recover()
        self.assertEqual(st.ingest(e),'duplicate')
        self.assertEqual(summarize(list(st.bodies.values()))[0],list(st.bodies.values()))
        with self.assertRaises(AssertionError):st.compact(Summary((e,),3600))
        cloud.accept('original-raw',{e.key},e.digest)
        with self.assertRaises(AssertionError):cloud.accept('summary',{e.key},'different shape')
        self.assertEqual(cloud.effects,{e.key})

    def test_no_activity_vs_no_observation_reboot_and_cloud(self):
        # Coverage is a separately durable interval owner, not inferred from count.
        quiet = {'interval':(43200,46800),'status':'covered','activity':[]}
        missing = {'interval':(43200,46800),'status':'unknown','activity':[]}
        import json
        q,m = [json.loads(json.dumps(x)) for x in (quiet,missing)]
        self.assertNotEqual(q,m)
        cloud = Backend()
        for i,row in enumerate((q,m)):
            cloud.accept('coverage-'+str(i),{('coverage',i)},hashlib.sha256(json.dumps(row).encode()).hexdigest())
        self.assertEqual(len(cloud.effects),2)
        e = replace(self.points()[0],coverage='unknown')
        self.assertEqual(summarize([e])[0],[e])

    def test_normal_saturation_preserves_critical_and_fails_closed(self):
        st = Store(normal_limit=2,critical_limit=2)
        events = self.points()
        for e in events[:2]: self.assertEqual(st.ingest(e),'accepted')
        self.assertEqual(st.ingest(events[2]),'full')
        for e in events[2:]: self.assertEqual(st.ingest(replace(e,safety=True)),'accepted')
        critical = Event(1,1,100,43500,'call_family',safety=True,checkpoint=1)
        self.assertEqual(st.ingest(critical),'full')
        self.assertNotIn(critical.key,st.acked)
        self.assertEqual(len(st.recover().acked),4)

    def test_node_report_is_not_backend_history_completion(self):
        st=Store();e=self.points()[0];st.ingest(e);st.retire({e.key})
        self.assertIn(e.key,st.recover().bodies)
        del st.bodies[e.key]
        with self.assertRaises(AssertionError):st.recover()

    def test_192_node_pending_serialized_32_input_flights(self):
        events=[Event(i%6,1,i//6+1,43200+i,checkpoint=1+i//128) for i in range(192)]
        st=Store();pending=[];unsealed=0;peak=0
        for i,e in enumerate(events):
            self.assertEqual(st.ingest(e),'accepted')
            pending.append(e);unsealed+=1;peak=max(peak,unsealed)
            if unsealed==32:
                # Abstract durable original-source seal; source bodies remain
                # before summary/checkpoint selection, including through reboot.
                self.assertTrue({x.key for x in pending} <= set(st.recover().bodies))
                unsealed=0
            if (i+1)%128==0 or i+1==len(events):
                for summary in summarize(pending)[1]:st.compact(summary)
                pending=[]
        self.assertEqual(peak,32)
        self.assertEqual(len(st.witnesses),192)
        self.assertEqual(set().union(*(s.sources for s in st.recover().summaries.values())),{e.key for e in events})
        st.retire({e.key for e in events})
        self.assertTrue(st.recover().summaries) # unsynced history still owns it
        self.assertEqual(st.ingest(events[0]),'stale')

    def test_72h_all_rates_profiles_and_four_days(self):
        for rate in RATES.values():
            for profile in ('ordinary','mixed','door_user','node_loss','simultaneous','saturation','reboot'):
                events = workload(rate,profile)
                self.assertEqual(len({e.at//86400 for e in events}),4)
                exact, summaries = summarize(events)
                sources = [e.key for e in exact]+[e.key for s in summaries for e in s.events]
                self.assertEqual(len(sources),len(set(sources)))
                self.assertEqual(set(sources),{e.key for e in events})
                summarized_keys = {e.key for s in summaries for e in s.events}
                for e in exact:
                    if e.safety: self.assertNotIn(e.key,summarized_keys)
                # Candidate source membership sufficient to keep arrival identity
                # distinct, including clock revision and delayed exact records.
                row = ledger(events)
                self.assertGreater(row['protected_peak_bytes'],row['payload_bytes'])
                self.assertEqual(row['progress_entry_bytes'],10944)
        self.assertEqual(entries(124)*32,192)

if __name__ == '__main__':
    unittest.main(verbosity=2)
