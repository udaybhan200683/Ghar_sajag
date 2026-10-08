#!/usr/bin/env python3
"""HOST ONLY: use real ActivityEpisode replay, then the unchanged 72h ledger.

No production episode format/quiet policy is chosen. B's proven-safe fallback
has A's event identities/counts. A reduced B cannot be quantified without the
missing eligibility, progress, loss and recovery contract.
"""
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
import argparse
import csv
import hashlib
import json

from offline_72h_model import Event, ledger

OTHER = {'NORMAL': 72, 'HIGH': 288, 'STRESS': 576, 'PAIRED46': 576,
         'BUSY40': 0, 'BUSY80': 0, 'BUSY120': 0}
OBS = {'NORMAL': 2160, 'HIGH': 11520, 'STRESS': 69120, 'PAIRED46': 67644,
       'BUSY40': 12960, 'BUSY80': 6480, 'BUSY120': 4320}


def inputs(path):
    traces = defaultdict(list)
    with path.open() as f:
        for row in csv.DictReader(f):
            traces[row['scenario']].append(row)
    return traces


def events_for(rows, other_count, profile):
    events = []
    # This is an explicitly SYNTHETIC trusted clock/covered-radio case. The
    # target sends absolute time 0, 86400s uncertainty; applying that actual
    # uncertainty would make every motion ineligible for the Hub summary.
    for i, row in enumerate(sorted(rows, key=lambda r: (int(r['created_ms']), int(r['node'])))):
        at_ms, node = int(row['at_ms']), int(row['node'])
        at = at_ms // 1000
        hour = at // 3600 % 24
        safety = profile == 'mixed' and (
            (node in (0, 1, 2) and 5 <= hour < 11) or
            (node in (1, 4) and (hour >= 21 or hour < 7)))
        events.append(Event(node, 1, int(row['seq']), at, row['kind'],
                            int(row['last_ms']) // 1000, int(row['additional_count']),
                            safety, checkpoint=1 + (i // 128)*100 + (at-43200)//21600,
                            monotonic_ms=at_ms, received_s=int(row['created_ms'])//1000 + 2))
    # Keep the actual last Motion anchor, not the last ignored MotionSummary.
    for node in range(6):
        positions = [i for i, e in enumerate(events) if e.node == node and e.kind == 'motion']
        events[positions[-1]] = replace(events[positions[-1]], safety=True)
    for i in range(other_count):
        events.append(Event(i % 6, 2, i+1, 43200 + i*259200//other_count,
                            ('door_open', 'door_closed', 'call_family', 'i_am_ok')[i % 4],
                            safety=True, checkpoint=1))
    for i in range(24):
        events.append(Event(i % 6, 3, i+1, 43200+i*10800, 'local_outcome',
                            safety=True, checkpoint=1))
    return sorted(events, key=lambda e: (e.at, e.node, e.origin, e.seq))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--events', type=Path, required=True)
    parser.add_argument('--cases', type=Path, required=True)
    args = parser.parse_args()
    traces = inputs(args.events)
    cases = []
    print('ACTUAL_REPLAY_CSV_SHA256=' + hashlib.sha256(args.events.read_bytes()).hexdigest())
    for scenario, rows in traces.items():
        motion = sum(r['kind'] == 'motion' for r in rows)
        native = len(rows)-motion
        repeat_count = sum(int(r['additional_count']) for r in rows)
        assert motion + repeat_count == OBS[scenario]
        print('SOURCE_COUNTS ' + json.dumps(dict(
            scenario=scenario, qualified_observations=OBS[scenario], motion=motion,
            native_summaries=native, other_node_events=OTHER[scenario],
            node_events=len(rows)+OTHER[scenario], local_hub_inputs=24,
            ideal_application_transmissions=len(rows)+OTHER[scenario],
            ideal_recovery_save_operations=2*(len(rows)+OTHER[scenario]),
            boundary='synthetic qualified observations; successful immediate durable ACK; closure tail included')))
        for profile in ('ordinary', 'mixed'):
            events = events_for(rows, OTHER[scenario], profile)
            for option in ('exact', 'bucket'):
                row = ledger(events, option=option)
                print('CAPACITY_MODELED ' + json.dumps(dict(
                    scenario=scenario, profile=profile,
                    option='A_current_or_B_safe_fallback' if option == 'exact' else 'C_Hub_loss_aware',
                    inputs=len(events), exact=row['exact'], native=row['source_summary_exact'],
                    summaries=row['summaries'], represented_points=row['summarized_sources'],
                    backend_representations=row['exact']+row['summaries'],
                    payload_bytes=row['payload_bytes'], peak_bytes=row['protected_peak_bytes'],
                    fits_arithmetic={str(k):row['protected_peak_bytes'] <= k*1024 for k in (128,192,256)},
                    boundary='worst103B source/1434B context; inherited reserve/COW model; not target/guarantee')))
                if option == 'bucket' and scenario in ('NORMAL','HIGH','STRESS'):
                    row.update(scenario=scenario, profile=profile, worst=True, inputs=len(events),
                               option=option, checkpoint_records=128, bucket_seconds=3600, hot_count=32)
                    cases.append(row)
    args.cases.write_text(json.dumps(cases, indent=2)+'\n')
    print('B_REDUCED_COUNTS=UNDETERMINED; B_SAFE_FALLBACK=A; NO_QUIET_GAP_SELECTED')
    print('CAPACITY_MODEL_EXIT=0; PRODUCTION_INTEGRATION=NO')


if __name__ == '__main__':
    main()
