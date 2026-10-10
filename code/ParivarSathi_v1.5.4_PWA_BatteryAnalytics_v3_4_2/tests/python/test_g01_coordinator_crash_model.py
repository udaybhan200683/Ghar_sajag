"""Section 20 architecture model; no production codec/NVS/power-cut qualification.

Records use JSON + HMAC as an abstract authenticated-value representation, not
GMM2/GSRG encoding. Every restart reloads only a serialized physical key/value
image. Partial records fail authentication. An owned preverification child may
be repaired; a partial authority record fails closed. Provider byte/entry caps
are checked separately against the current source constants.
"""
import copy
import hashlib
import hmac
import json
from pathlib import Path
import re
import unittest

KEY = b'architecture-model-key-only'
PHASES = ['Prepared', 'Copying', 'TargetVerified', 'Published', 'Cleanup',
          'BatchDone', 'Activated']


class Closed(Exception):
    pass


class Cut(Exception):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hmac.new(KEY, canonical(value), hashlib.sha256).hexdigest()


def seal(value):
    return canonical(dict(value=value, mac=digest(value)))


def open_record(blob):
    try:
        envelope = json.loads(blob)
        if not hmac.compare_digest(envelope['mac'], digest(envelope['value'])):
            raise Closed('authentication')
        return envelope['value']
    except (ValueError, KeyError, TypeError):
        raise Closed('corrupt record') from None


class Model:
    def __init__(self, image=None):
        self.kv = ({k: bytes.fromhex(v) for k, v in json.loads(image).items()}
                   if image else {})
        self.fault = None
        self.sessions = set()  # always empty on restart
        if image is None:
            self.kv['registry'] = seal(dict(phase='v1', table='T', anchor=''))
            self.kv['ev1'] = seal(dict(domain='legacy', event='event-A', owner='hash'))
            self.kv['e000'] = seal(dict(event='event-B', slot=0, physical='device-B'))
            self.kv['c000'] = seal(dict(event='event-B', slot=0))
            self.kv['tr1'] = seal(dict(ordinal=1, domain='legacy', event='event-C'))
            self.kv['cp0'] = seal(dict(gen=1, frontier=0, table='', domain='legacy',
                view=True, refs=['ev1'], floors=[1, 3, 4, 5], prefix=1, slots=True))
            self.kv['sel0'] = seal(dict(bank=0, gen=1))

    def reboot(self):
        return Model(json.dumps({k: v.hex() for k, v in self.kv.items()}, sort_keys=True))

    def read(self, key):
        if key not in self.kv:
            raise Closed('missing ' + key)
        return open_record(self.kv[key])

    def write(self, key, value):
        blob = seal(value)
        fault, self.fault = self.fault, None
        if fault == 'before':
            raise Cut('before write')
        self.kv[key] = blob[:len(blob)//2] if fault == 'partial' else blob
        if fault in ('partial', 'persist'):
            raise Cut(fault)
        if self.kv[key] != blob:
            raise Closed('readback')

    def exact_erase(self, key, expected):
        fault, self.fault = self.fault, None
        if key not in self.kv:
            return
        if self.kv[key] != expected:
            raise Closed('conditional mismatch')
        if fault in ('before', 'partial'):
            raise Cut('erase not committed')
        del self.kv[key]
        if fault == 'persist':
            raise Cut('erase persisted')

    def checkpoint(self, bank):
        key = 'cp' + str(bank)
        if key in self.kv:
            return self.read(key), self.kv[key]
        _, m = self.manifest()
        virtual = (bank == 0 and not any('cp'+str(b) in self.kv for b in (0, 1)))
        virtual = virtual or bool(m and m.get('virtual') and bank == m['source'])
        if not virtual:
            raise Closed('missing real checkpoint')
        cp = dict(gen=1, frontier=0, table='', domain='legacy', view=True,
                  refs=[], floors=[], prefix=0, slots=True)
        return cp, canonical(cp)  # logical descriptor, no physical blob

    def root_digest(self, bank, source_count=None):
        cp, cp_blob = self.checkpoint(bank)
        count = cp['prefix'] if source_count is None else source_count
        objects = [('checkpoint/' + str(cp['gen']), cp_blob.hex())]
        for key in cp['refs']:
            self.read(key)
            objects.append((key, self.kv[key].hex()))
        for ordinal in range(1, count + 1):
            t = self.read('tr' + str(ordinal))
            if t['ordinal'] != ordinal:
                raise Closed('tail gap')
            objects.append(('tr' + str(ordinal), self.kv['tr' + str(ordinal)].hex()))
        if cp['slots']:
            for key in sorted(k for k in self.kv if re.fullmatch(r'e\d{3}', k)):
                self.read(key)
                objects.append((key, self.kv[key].hex()))
        return digest(sorted(objects))

    def semantic(self, bank):
        cp, _ = self.checkpoint(bank)
        events = [self.read(k)['event'] for k in cp['refs']]
        if cp['slots']:
            events += [self.read(k)['event'] for k in self.kv if re.fullmatch(r'e\d{3}', k)]
        events += [self.read('tr' + str(i))['event'] for i in range(1, cp['prefix']+1)]
        receipts = {}
        bindings = {0: 'event-B', 1: 'event-C'}
        for key in sorted(k for k in self.kv if re.fullmatch(r'c\d{3}', k)):
            receipt = self.read(key)
            slot = int(key[1:])
            if receipt != dict(event=bindings.get(slot), slot=slot) or receipt['event'] not in events:
                raise Closed('completion identity')
            receipts[key] = receipt
        return sorted(events), cp['floors'], receipts

    @staticmethod
    def successor(old, new):
        if old == new:
            return True
        if old['phase'] in ('BatchDone', 'Activated') and new['phase'] == 'Prepared':
            normal = new['normal'] and old['phase'] == 'Activated'
            return (new['frontier'] == old['frontier'] + (0 if normal else 1)
                    and new['source_gen'] == old['target_gen']
                    and (normal or new['source_digest'] == old['target_digest']))
        immutable = ['source', 'source_gen', 'source_digest', 'table', 'frontier',
                     'normal', 'source_count', 'source_key', 'target_key', 'child_digest', 'final', 'virtual']
        if any(old[k] != new[k] for k in immutable):
            return False
        if PHASES.index(new['phase']) != PHASES.index(old['phase']) + 1:
            return False
        return (new['phase'] == 'TargetVerified' or
                (old['target_gen'], old['target_digest']) ==
                (new['target_gen'], new['target_digest']))

    def manifest(self):
        records = [(i, self.read('mig' + str(i))) for i in range(2) if 'mig'+str(i) in self.kv]
        if not records:
            return None, None
        if len(records) == 1:
            bank, m = records[0]
            if m['phase'] != 'Prepared' or m['frontier'] != 1 or m['normal']:
                raise Closed('lost competing authority bank')
            return bank, m
        a, b = records
        if a[1] == b[1]:
            return b
        ab, ba = self.successor(a[1], b[1]), self.successor(b[1], a[1])
        if ab == ba:
            raise Closed('ambiguous manifests')
        return b if ab else a

    def advance(self, phase):
        bank, old = self.manifest()
        new = dict(old, phase=phase)
        if phase == 'TargetVerified':
            target = 1-old['source']
            if self.semantic(old['source']) != self.semantic(target):
                raise Closed('equivalence/floor exception')
            new.update(target_gen=self.read('cp'+str(target))['gen'],
                       target_digest=self.root_digest(target))
        if phase == 'Published':
            target = 1-old['source']
            if self.read('sel1') != dict(bank=target, gen=old['target_gen']):
                raise Closed('selector readback first')
            if self.root_digest(target) != old['target_digest']:
                raise Closed('candidate changed after verification')
        if phase == 'Cleanup':
            if self.kv['cp'+str(old['source'])] != self.kv['cp'+str(1-old['source'])]:
                raise Closed('shadow not exact')
        if phase == 'BatchDone' and old['source_key'] in self.kv and old['source_key']:
            raise Closed('release incomplete')
        if phase == 'Activated':
            reg = self.read('registry')
            if reg['phase'] != 'Activated' or reg['table'] != old['table']:
                raise Closed('registry barrier')
        if not self.successor(old, new):
            raise Closed('illegal successor')
        self.write('mig'+str(1-bank), new)

    def prepare(self, final=False, normal=False):
        bank, old = self.manifest()
        source = self.boot()[0]
        cp, _ = self.checkpoint(source)
        source_key = '' if final else 'ev1'
        target_key = '' if final else 'ev'+str(cp['gen']+1)
        new = dict(phase='Prepared', source=source, source_gen=cp['gen'],
            source_digest=self.root_digest(source, len([k for k in self.kv if k.startswith('tr')])),
            source_count=len([k for k in self.kv if k.startswith('tr')]),
            frontier=(old['frontier'] + (0 if normal else 1)) if old else 1,
            table='T', source_key=source_key, target_key=target_key,
            child_digest=digest(self.kv[source_key].hex()) if source_key else '',
            target_gen=0, target_digest='', final=final, normal=normal,
            virtual=not any('cp'+str(b) in self.kv for b in (0, 1)))
        if old and not self.successor(old, new):
            raise Closed('not linked to prior publication')
        self.write('mig'+str(1-bank if bank is not None else 0), new)

    def candidate(self):
        _, m = self.manifest()
        cp = copy.deepcopy(self.checkpoint(m['source'])[0])
        cp.update(gen=cp['gen']+1, frontier=m['frontier'], domain='registry',
                  table=m['table'], view=not m['final'], prefix=m['source_count'])
        if m['source_key']:
            cp['refs'] = [m['target_key'] if k == m['source_key'] else k for k in cp['refs']]
        return cp

    def stage(self):
        _, m = self.manifest()
        if m['phase'] != 'Copying' or not m['source_key']:
            raise Closed('intent does not own child')
        child = self.read(m['source_key'])
        child.update(domain='registry', owner='slot0-gen1')
        self.write(m['target_key'], child)

    def release(self):
        _, m = self.manifest()
        if m['phase'] != 'Cleanup':
            raise Closed('not cleanup')
        self.boot()
        key = m['source_key']
        if not key or key not in self.kv:
            return
        if any(key in self.read('cp'+str(b))['refs'] for b in (0, 1)):
            raise Closed('reachable source')
        expected = self.kv[key]
        if digest(expected.hex()) != m['child_digest']:
            raise Closed('exact source digest mismatch')
        self.exact_erase(key, expected)

    def boot(self):
        _, m = self.manifest()
        reg = self.read('registry')
        if m is None:
            if reg['phase'] != 'v1' or any(self.read('cp'+str(b))['domain'] != 'legacy'
                                          for b in (0, 1) if 'cp'+str(b) in self.kv):
                raise Closed('lost activation barrier')
            if not any('cp'+str(b) in self.kv for b in (0, 1)):
                self.semantic(0)
                return 0, False
            sel = self.read('sel0')
            return sel['bank'], False
        if reg['table'] != m['table']:
            raise Closed('table mismatch')
        owned = {m['source_key'], m['target_key']}
        prepublication = PHASES.index(m['phase']) < PHASES.index('Published')
        permitted = [m['source']] if prepublication else [1-m['source'], m['source']]
        for bank in permitted:
            try:
                cp, _ = self.checkpoint(bank)
                if not prepublication and self.root_digest(bank) != m['target_digest']:
                    continue
                owned.update(cp['refs'])
            except Closed:
                pass  # root authority is checked below; presence grants nothing
        if any(key.startswith('ev') and key not in owned for key in self.kv):
            raise Closed('unexpected staged object')
        if PHASES.index(m['phase']) < PHASES.index('Published'):
            source = m['source']
            if self.root_digest(source, m['source_count']) != m['source_digest']:
                raise Closed('pinned source changed')
            candidate_key = 'cp'+str(1-source)
            if candidate_key in self.kv:
                try:
                    candidate = self.read(candidate_key)
                except Closed:
                    if m['phase'] == 'TargetVerified':
                        raise
                else:
                    if candidate['gen'] > m['source_gen'] and candidate != self.candidate():
                        raise Closed('wrong authenticated candidate')
            for key in [m['target_key']] if m['target_key'] else []:
                if key in self.kv:
                    try:
                        child = self.read(key)
                    except Closed:
                        if m['phase'] != 'Copying':
                            raise
                    else:
                        expected = dict(self.read(m['source_key']), domain='registry', owner='slot0-gen1')
                        if child != expected:
                            raise Closed('wrong authenticated stage')
            return source, False
        target = 1-m['source']
        legal = [target] + ([m['source']] if m['phase'] in ('Cleanup', 'BatchDone', 'Activated') else [])
        for b in legal:
            try:
                cp = self.read('cp'+str(b))
                if (cp['gen'] != m['target_gen'] or cp['frontier'] < m['frontier'] or
                        cp['table'] != m['table'] or self.root_digest(b) != m['target_digest']):
                    continue
                self.semantic(b)
                ready = (m['phase'] == 'Activated' and reg['phase'] == 'Activated'
                         and reg['anchor'] == m['target_digest'] and not cp['view'])
                if m['phase'] == 'Activated' and not ready:
                    raise Closed('joint activation mismatch')
                return b, ready
            except Closed:
                continue
        raise Closed('no legal root at publication floor')

    def actions(self, final=False, normal=False):
        return [lambda: self.prepare(final, normal),
                lambda: self.write('registry', dict(phase='Prepared', table='T', anchor='')),
                lambda: self.advance('Copying'),
                (lambda: None) if final else self.stage,
                lambda: self.write('cp'+str(1-self.manifest()[1]['source']), self.candidate()),
                lambda: self.advance('TargetVerified'),
                lambda: self.write('sel1', dict(bank=1-self.manifest()[1]['source'],
                                                gen=self.manifest()[1]['target_gen'])),
                lambda: self.advance('Published'), self.shadow,
                lambda: self.advance('Cleanup'), self.release,
                lambda: self.advance('BatchDone')] + ([self.activate_registry,
                lambda: self.advance('Activated')] if final else [])

    def shadow(self):
        _, m = self.manifest()
        # Copy exact ciphertext, including nonce. Model write faults are explicit.
        source, target = 'cp'+str(m['source']), 'cp'+str(1-m['source'])
        fault, self.fault = self.fault, None
        if fault == 'before':
            raise Cut('before shadow')
        self.kv[source] = self.kv[target][:len(self.kv[target])//2] if fault == 'partial' else self.kv[target]
        if fault:
            raise Cut('shadow ' + fault)

    def activate_registry(self):
        _, m = self.manifest()
        self.write('registry', dict(phase='Activated', table='T', anchor=m['target_digest']))

    def cycle(self, final=False, normal=False):
        for action in self.actions(final, normal):
            action()
            self.boot()
        return self.reboot()


class CrashTests(unittest.TestCase):
    def test_every_write_boundary_and_failure_mode(self):
        for final in (False, True):
            initial = Model().cycle() if final else Model()
            for index in range(len(initial.actions(final))):
                for fault in ('before', 'partial', 'persist'):
                    with self.subTest(final=final, index=index, fault=fault):
                        m = initial.reboot()
                        actions = m.actions(final)
                        for action in actions[:index]:
                            action()
                        m.fault = fault
                        try:
                            actions[index]()
                        except Cut:
                            pass
                        r = m.reboot()
                        try:
                            bank, ready = r.boot()
                        except Closed:
                            continue  # corruption may close, never grant lower authority
                        _, manifest = r.manifest()
                        if manifest and manifest['phase'] in ('Published', 'Cleanup', 'BatchDone', 'Activated'):
                            self.assertGreaterEqual(r.read('cp'+str(bank))['frontier'], manifest['frontier'])
                        self.assertEqual(r.read('c000'), dict(event='event-B', slot=0))
                        self.assertEqual(r.read('e000')['event'], 'event-B')
                        if ready:
                            self.assertEqual(r.read('registry')['phase'], 'Activated')

    def test_source_until_published_even_selector_changed(self):
        m = Model()
        for action in m.actions()[:7]: action()
        self.assertEqual(m.reboot().boot(), (0, False))

    def test_publication_cannot_skip_selector(self):
        m = Model()
        for action in m.actions()[:6]: action()
        with self.assertRaises(Closed): m.advance('Published')

    def test_lower_root_never_fallback(self):
        m = Model()
        for action in m.actions()[:8]: action()
        m.kv['cp1'] = b'corrupt'
        with self.assertRaises(Closed): m.reboot().boot()

    def test_exact_shadow_independent_digest(self):
        m = Model().cycle()
        self.assertEqual(m.root_digest(0), m.root_digest(1))
        m.kv['cp1'] = b'corrupt'
        self.assertEqual(m.reboot().boot(), (0, False))

    def test_semantic_shadow_reencryption_is_rejected(self):
        m = Model().cycle()
        altered = m.read('cp0'); altered['nonce_model'] = 9
        m.kv['cp0'] = seal(altered); m.kv['cp1'] = b'corrupt'
        with self.assertRaises(Closed): m.boot()

    def test_corrupt_or_missing_manifest_bank(self):
        for mutation in ('corrupt', 'missing'):
            m = Model().cycle()
            if mutation == 'corrupt': m.kv['mig0'] = b'partial'
            else: del m.kv['mig0']
            with self.assertRaises(Closed): m.reboot().boot()

    def test_same_step_conflict(self):
        m = Model(); m.prepare()
        bad = m.read('mig0'); bad['target_key'] = 'ev999'
        m.kv['mig1'] = seal(bad)
        with self.assertRaises(Closed): m.boot()

    def test_wrong_authenticated_stage(self):
        m = Model()
        for action in m.actions()[:4]: action()
        m.kv['ev2'] = seal(dict(domain='registry', event='wrong', owner='slot0-gen1'))
        with self.assertRaises(Closed): m.reboot().boot()

    def test_partial_named_stage_is_closed_source_retry(self):
        m = Model()
        for action in m.actions()[:3]: action()
        m.kv['ev2'] = b'partial'
        self.assertEqual(m.reboot().boot(), (0, False))
        m.stage()
        self.assertEqual(m.read('ev2')['event'], 'event-A')

    def test_erase_mismatch_preserves_occupant(self):
        m = Model()
        for action in m.actions()[:10]: action()
        other = seal(dict(domain='registry', event='other', owner='slot9-gen1'))
        m.kv['ev1'] = other
        with self.assertRaises(Closed): m.release()
        self.assertEqual(m.kv['ev1'], other)

    def test_cleanup_persisted_failure_retries_absence(self):
        m = Model()
        for action in m.actions()[:10]: action()
        m.fault = 'persist'
        with self.assertRaises(Cut): m.release()
        r = m.reboot(); r.release(); r.advance('BatchDone')
        self.assertNotIn('ev1', r.kv)
        self.assertIn('c000', r.kv); self.assertIn('e000', r.kv)

    def test_activation_requires_both_barriers_and_fresh_rejoin(self):
        m = Model().cycle()
        for action in m.actions(final=True)[:-1]: action()
        self.assertFalse(m.reboot().boot()[1])
        m.advance('Activated')
        r = m.reboot(); self.assertTrue(r.boot()[1]); self.assertFalse(r.sessions)
        r.kv['registry'] = seal(dict(phase='Prepared', table='T', anchor=''))
        with self.assertRaises(Closed): r.boot()

    def test_pending_exception_cannot_disappear(self):
        m = Model()
        for action in m.actions()[:5]: action()
        cp = m.read('cp1'); cp['floors'] = [1, 2, 3, 4, 5]
        m.kv['cp1'] = seal(cp)
        with self.assertRaises(Closed): m.advance('TargetVerified')

    def test_normal_append_does_not_change_protected_digest(self):
        m = Model().cycle().cycle(final=True)
        bank, _ = m.boot(); before = m.root_digest(bank)
        m.kv['tr2'] = seal(dict(ordinal=2, domain='registry', event='event-D'))
        self.assertEqual(m.root_digest(bank), before)
        self.assertTrue(m.reboot().boot()[1])
        m.prepare(final=True, normal=True)
        _, manifest = m.manifest()
        self.assertEqual(manifest['frontier'], 2)
        self.assertEqual(manifest['source_count'], 2)
        self.assertFalse(m.boot()[1])

    def test_independent_receipt_not_a_digest_dependency(self):
        m = Model().cycle().cycle(final=True)
        bank, _ = m.boot(); before = m.root_digest(bank)
        m.kv['c001'] = seal(dict(event='event-C', slot=1))
        self.assertEqual(m.root_digest(bank), before)
        self.assertTrue(m.boot()[1])
        m.kv['c001'] = seal(dict(event='event-B', slot=1))
        with self.assertRaises(Closed): m.boot()

    def test_unowned_stage_fails_closed(self):
        m = Model(); m.prepare()
        m.kv['ev999'] = seal(dict(domain='registry', event='event-A', owner='slot0-gen1'))
        with self.assertRaises(Closed): m.boot()

    def test_candidate_presence_cannot_own_unknown_child(self):
        m = Model(); m.prepare()
        cp = m.candidate(); cp['refs'] = ['ev999']
        m.kv['cp1'] = seal(cp)
        m.kv['ev999'] = seal(dict(domain='registry', event='event-A', owner='slot0-gen1'))
        with self.assertRaises(Closed): m.boot()

    def test_publish_rechecks_exact_verified_digest(self):
        m = Model()
        for action in m.actions()[:7]: action()
        cp = m.read('cp1'); cp['nonce_model'] = 'changed exact bytes'
        m.kv['cp1'] = seal(cp)
        with self.assertRaises(Closed): m.advance('Published')

    def test_virtual_raw_source_at_every_boundary(self):
        initial = Model()
        for key in ('cp0', 'sel0', 'ev1', 'tr1'):
            del initial.kv[key]
        self.assertEqual(initial.reboot().boot(), (0, False))
        for index in range(len(initial.actions(final=True))):
            for fault in ('before', 'partial', 'persist'):
                m = initial.reboot()
                actions = m.actions(final=True)
                for action in actions[:index]: action()
                m.fault = fault
                try:
                    actions[index]()
                except Cut:
                    pass
                try:
                    bank, ready = m.reboot().boot()
                except Closed:
                    continue
                if ready:
                    self.assertEqual(m.read('cp'+str(bank))['domain'], 'registry')
                self.assertIn('e000', m.kv); self.assertIn('c000', m.kv)
        done = initial.cycle(final=True)
        self.assertTrue(done.boot()[1])

    def test_repeated_normal_batches_and_reboots(self):
        m = Model().cycle().cycle(final=True)
        for _ in range(20):
            m = m.cycle(final=True, normal=True)
            self.assertTrue(m.reboot().boot()[1])
            self.assertEqual(m.manifest()[1]['frontier'], 2)
        self.assertEqual(len([k for k in m.kv if k.startswith('ev')]), 1)

    def test_both_missing_after_activation_fails_closed(self):
        m = Model().cycle().cycle(final=True)
        del m.kv['mig0']; del m.kv['mig1']
        with self.assertRaises(Closed): m.boot()

    def test_registry_table_mismatch(self):
        m = Model().cycle().cycle(final=True)
        reg = m.read('registry'); reg['table'] = 'wrong'
        m.kv['registry'] = seal(reg)
        with self.assertRaises(Closed): m.boot()


BASE = Path(__file__).resolve().parents[2]


def entries(payload):
    return 2 + (payload + 31)//32


def ownership_table(records):
    """Deterministic preparation only with independently authenticated identities."""
    if len(records) > 10 or any(not r.get('proved') for r in records):
        raise Closed('capacity or historical identity proof')
    if len({r['physical'] for r in records}) != len(records):
        raise Closed('multiple physical incarnations')
    table = []
    for slot, record in enumerate(sorted(records, key=lambda r: (not r.get('active', True), r['physical']))):
        generation = record.get('generation', 1)
        if not 1 <= generation <= (1 << 32)-1:
            raise Closed('invalid or overflowed generation')
        identity = {k: record[k] for k in ('physical', 'logical', 'public_key')}
        owner = dict(identity, slot=slot, generation=generation)
        table.append(dict(slot=slot, generation=generation, physical=record['physical'],
                          owner_digest=digest(owner), active=record.get('active', True)))
    return table


def extend_ownership_table(table, record):
    if len(table) == 10 or not record.get('proved'):
        raise Closed('no free descriptor or proof')
    if any(owner['physical'] == record['physical'] for owner in table):
        raise Closed('pinned physical owner cannot reenroll')
    slot = len(table)
    identity = {k: record[k] for k in ('physical', 'logical', 'public_key')}
    owner = dict(identity, slot=slot, generation=1)
    return copy.deepcopy(table) + [dict(slot=slot, generation=1,
        physical=record['physical'], owner_digest=digest(owner), active=True)]


def table_binding(table):
    return digest([{k: owner[k] for k in ('slot', 'generation', 'physical', 'owner_digest')}
                   for owner in table] + [None]*(10-len(table)))


def resolve_table_extension(source_digest, intended_digest, registry_phase, table):
    """Inputs must already be authenticated by source-root/GSRG/GMM adapters."""
    current_digest = table_binding(table)
    if registry_phase == 'Activated' and current_digest == source_digest:
        if current_digest == intended_digest:
            raise Closed('extension must introduce a distinct owner')
        return 'cancel-unpersisted-extension', copy.deepcopy(table)
    if registry_phase == 'Prepared' and current_digest == intended_digest and table:
        if table_binding(table[:-1]) != source_digest:
            raise Closed('prepared extension changed historical ownership')
        return 'resume-persisted-extension', copy.deepcopy(table)
    raise Closed('missing/conflicting registry-table projection')


def historical_attribution(record, proofs):
    # Collision itself blocks compressed legacy coordinate migration; no tie-breaker.
    candidates = [p for p in proofs if p['legacy_coordinate'] == record['legacy_coordinate']]
    if len(candidates) != 1 or not candidates[0].get('proved'):
        raise Closed('collision/ambiguous or unproved historical binding')
    candidate = candidates[0]
    if candidate['event_digest'] != record['event_digest']:
        raise Closed('unverifiable event attribution')
    return candidate['slot'], candidate['generation']


def production_caps():
    # The inventory provider owns the admission bounds. The blob-store source
    # only writes values and no longer contains this capacity switch.
    cpp = (BASE/'firmware/hub/target/esp32/nvs_store_inventory.cpp').read_text()
    caps = {name: int(n) for name, n in re.findall(r'case K::(\w+): return (\d+);', cpp)}
    retirement = (BASE/'firmware/hub/components/storage/node_retirement_snapshot.hpp').read_text()
    match = re.search(r'kRetirementLegacyInspectionBytes\s*=\s*(\d+)', retirement)
    if match is None:
        raise AssertionError('retirement inspection bound is missing from provider source')
    caps['RetirementBank'] = int(match.group(1))
    return caps


def ledger(raw=0, archives=32, evidence=33, compact=0):
    caps = production_caps()
    values = [(2, caps['Checkpoint']), (2, 4+8+1+28),
              (4, caps['Transition']), (archives, caps['EffectChunk']),
              (evidence, caps['EvidenceChunk']), (3-compact, caps['RetirementBank']),
              (compact, 19+10*(61+32*16)+28), (2, caps['Bitmap']),
              (128, caps['LegacyCompletion']), (2, caps['MigrationMetadata']),
              (raw, caps['LegacyEvent'])]
    return 1+sum(n*entries(b) for n, b in values), sum(n*b for n, b in values)


class LayoutTests(unittest.TestCase):
    def test_ledger_from_provider_layout(self):
        self.skipTest(
            'classic ESP32 NVS reserve model is historical under GS-D030; '
            'S3 commercial capacity and reserve qualification remain open'
        )
        used, payload = ledger()
        self.assertEqual((used, payload), (3233, 89288))
        self.assertEqual((4032-used, 131072-payload), (799, 41784))
        self.assertGreaterEqual(100*(4032-used)/4032, 20)
        self.assertEqual(ledger(compact=3), (3194, 88019))

    def test_raw_profile_and_extra_object_stop(self):
        self.assertEqual(ledger(raw=128, archives=0, evidence=0), (2901, 74760))
        self.assertGreater(ledger(raw=1)[0], 3233)
        self.assertLess(4032-ledger(raw=1)[0], 799)

    def test_current_codec_hard_bounds(self):
        header = (BASE/'firmware/hub/components/storage/durable_transition.hpp').read_text()
        for name, size in [('kMaxCheckpointBytes', 4549), ('kMigrationManifestBankBytes', 218),
                           ('kMigrationManifestTotalBytes', 436), ('kMigrationManifestTotalEntries', 18)]:
            self.assertRegex(header, rf'{name}\s*=\s*{size}\s*;')
        self.assertEqual(18+184+16, 218)
        self.assertEqual(2*entries(218), 18)
        self.assertEqual(19+10*(61+32*16)+28, 5777)
        self.assertEqual(2*entries(5077), 322)  # separate default-nvs replacement
        fixed_checkpoint_bytes = (4+1+4+8+8+4+32+2 + 1+16*10 + 1+32*8
                                  + 1+32*40 + 1 + 32+2+1 + 28)
        self.assertEqual(fixed_checkpoint_bytes+2723, 4549)
        self.assertEqual(fixed_checkpoint_bytes+41+2682, 4549)

    def test_descriptor_projection_and_overflow(self):
        owners = [(d, i, 1) for i, d in enumerate(sorted(['device-z', 'device-a']))]
        self.assertEqual(owners, [('device-a', 0, 1), ('device-z', 1, 1)])
        self.assertEqual([list(owner) for owner in owners], json.loads(json.dumps(owners)))
        self.assertEqual(10-len(list(range(10))), 0)
        maximum_generation = (1 << 32)-1
        self.assertGreater(maximum_generation+1, maximum_generation)

    def test_prepared_table_is_stable_across_reboot_and_revocation(self):
        records = [dict(physical='z', logical='same-room', public_key='key-z', proved=True),
                   dict(physical='a', logical='other-room', public_key='key-a', proved=True)]
        table = ownership_table(records)
        self.assertEqual([o['physical'] for o in table], ['a', 'z'])
        binding = table_binding(table)
        restored = json.loads(json.dumps(table))
        restored[0]['active'] = False
        self.assertEqual(table_binding(restored), binding)
        self.assertEqual(restored[0]['generation'], 1)
        extended = extend_ownership_table(restored,
            dict(physical='0-before-a', logical='other-room', public_key='new', proved=True))
        self.assertEqual(table_binding(extended[:-1]), binding)
        self.assertNotEqual(table_binding(extended), binding)

    def test_unproved_owner_full_capacity_and_generation_overflow(self):
        records = [dict(physical=f'd{i:02}', logical=f'l{i}', public_key=f'k{i}', proved=True)
                   for i in range(10)]
        baseline = ownership_table(records)
        with self.assertRaises(Closed): ownership_table(records + [records[0]])
        self.assertEqual(ownership_table(records), baseline)
        records[0]['generation'] = 1 << 32
        with self.assertRaises(Closed): ownership_table(records)
        records[0]['generation'] = 1
        records[0]['proved'] = False
        with self.assertRaises(Closed): ownership_table(records)

    def test_legacy_collision_has_no_digest_tie_breaker(self):
        record = dict(legacy_coordinate='hash-slot', event_digest='event-sha')
        proof = dict(legacy_coordinate='hash-slot', event_digest='event-sha',
                     slot=3, generation=1, proved=True)
        self.assertEqual(historical_attribution(record, [proof]), (3, 1))
        collision = dict(proof, slot=8, event_digest='different-event-sha')
        with self.assertRaises(Closed): historical_attribution(record, [proof, collision])

    def test_table_extension_missing_payload_cancels_under_old_binding(self):
        old = ownership_table([dict(physical='old', logical='room', public_key='k', proved=True)])
        new = extend_ownership_table(old,
            dict(physical='replacement', logical='room', public_key='k2', proved=True))
        mode, table = resolve_table_extension(table_binding(old), table_binding(new), 'Activated', old)
        self.assertEqual(mode, 'cancel-unpersisted-extension')
        self.assertEqual(table, old)

    def test_persisted_descriptor_must_resume_cannot_be_discarded(self):
        old = ownership_table([dict(physical='old', logical='room', public_key='k', proved=True)])
        new = extend_ownership_table(old,
            dict(physical='replacement', logical='room', public_key='k2', proved=True))
        new[0]['active'] = False
        mode, table = resolve_table_extension(table_binding(old), table_binding(new), 'Prepared', new)
        self.assertEqual(mode, 'resume-persisted-extension')
        self.assertEqual(table[0]['generation'], 1)
        self.assertFalse(table[0]['active'])
        self.assertEqual(table[1]['slot'], 1)

    def test_changed_old_table_is_not_an_authorized_extension(self):
        old = ownership_table([dict(physical='old', logical='room', public_key='k', proved=True)])
        new = extend_ownership_table(old,
            dict(physical='replacement', logical='room', public_key='k2', proved=True))
        bad = copy.deepcopy(new); bad[0]['owner_digest'] = 'changed historical owner'
        with self.assertRaises(Closed):
            resolve_table_extension(table_binding(old), table_binding(bad), 'Prepared', bad)


class NormalOperand:
    """Focused abstract model of the reused early target-digest field.

No extra persistent intent key: Copying is mig0; verified/cancelled successor is
mig1. Report contents are independent inputs, not inferred from source report.
The source/candidate and exact release use the existing cp/ret banks.
"""
    def __init__(self, image=None):
        self.kv = ({k: bytes.fromhex(v) for k, v in json.loads(image).items()}
                   if image else {})
        if image is None:
            self.kv['ret0'] = seal(dict(highwater=5, pending=[2], report_generation=1))
            self.kv['cp0'] = seal(dict(gen=1, frontier=7, report='ret0'))

    def reboot(self):
        return NormalOperand(json.dumps({k: v.hex() for k, v in self.kv.items()}))

    def root_digest(self, bank):
        cp = open_record(self.kv['cp'+str(bank)])
        return digest([self.kv['cp'+str(bank)].hex(), self.kv[cp['report']].hex()])

    def intent(self, requested):
        self.kv['mig0'] = seal(dict(phase='Copying', frontier=7, gen=2,
            target_digest=digest(requested), source_digest=self.root_digest(0),
            source_child_digest=digest(self.kv['ret0'].hex()), source_key='ret0',
            target_key='ret1', normal=True, cancelled=False))

    def verify_or_cancel(self):
        intent = open_record(self.kv['mig0'])
        if self.root_digest(0) != intent['source_digest']:
            raise Closed('changed normal source')
        present = 'ret1' in self.kv
        target = None
        if present:
            try:
                target = open_record(self.kv['ret1'])
            except Closed:
                pass  # exact named partial stage, never report evidence
        cancelled = target is None
        if target is not None and digest(target) != intent['target_digest']:
            raise Closed('valid wrong planned report')
        report_key = 'ret0' if cancelled else 'ret1'
        self.kv['cp1'] = seal(dict(gen=2, frontier=7, report=report_key))
        verified = dict(intent, phase='TargetVerified', cancelled=cancelled,
                        target_digest=self.root_digest(1))
        if cancelled:
            verified.update(source_key='ret1' if present else '', target_key='ret0',
                source_child_digest=digest(self.kv['ret1'].hex()) if present else '')
        self.kv['mig1'] = seal(verified)

    def publish_and_release(self, persist_then_fail=False):
        m = open_record(self.kv['mig1'])
        if self.root_digest(1) != m['target_digest']:
            raise Closed('verified root mismatch')
        self.kv['sel1'] = seal(dict(bank=1, gen=2))
        self.kv['mig0'] = seal(dict(m, phase='Published'))
        self.kv['cp0'] = self.kv['cp1']
        self.kv['mig1'] = seal(dict(m, phase='Cleanup'))
        key = m['source_key']
        if key and key in self.kv:
            if key in [open_record(self.kv['cp'+str(b)])['report'] for b in (0, 1)]:
                raise Closed('release still reachable')
            expected = self.kv[key]
            if digest(expected.hex()) != m['source_child_digest']:
                raise Closed('source mismatch')
            if self.kv[key] != expected:
                raise Closed('changed occupant')
            del self.kv[key]
            if persist_then_fail:
                raise Cut('released but failure returned')
        return not m['cancelled']  # success ACK only for actual planned update


class NormalPublicationTests(unittest.TestCase):
    def test_intent_binds_new_report_before_creation(self):
        requested = dict(highwater=9, pending=[2], report_generation=2)
        m = NormalOperand(); m.intent(requested)
        self.assertEqual(open_record(m.kv['mig0'])['target_digest'], digest(requested))
        m.kv['ret1'] = seal(requested)
        m = m.reboot(); m.verify_or_cancel()
        self.assertTrue(m.publish_and_release())
        self.assertEqual(open_record(m.kv['ret1']), requested)
        self.assertNotIn('ret0', m.kv)

    def test_valid_wrong_report_is_not_cancellable(self):
        m = NormalOperand(); m.intent(dict(highwater=9, pending=[2], report_generation=2))
        m.kv['ret1'] = seal(dict(highwater=9, pending=[], report_generation=2))
        with self.assertRaises(Closed): m.reboot().verify_or_cancel()

    def test_missing_or_partial_input_cancels_without_ack(self):
        for partial in (False, True):
            m = NormalOperand(); m.intent(dict(highwater=9, pending=[2], report_generation=2))
            old = m.kv['ret0']
            if partial: m.kv['ret1'] = b'partial named stage'
            m = m.reboot(); m.verify_or_cancel(); m = m.reboot()
            self.assertFalse(m.publish_and_release())
            self.assertEqual(m.kv['ret0'], old)
            self.assertNotIn('ret1', m.kv)
            self.assertEqual(open_record(m.kv['cp0'])['frontier'], 7)

    def test_cancelled_cleanup_persist_then_failure(self):
        m = NormalOperand(); m.intent(dict(highwater=9, pending=[2], report_generation=2))
        m.kv['ret1'] = b'partial named stage'; m.verify_or_cancel()
        with self.assertRaises(Cut): m.publish_and_release(persist_then_fail=True)
        m = m.reboot()
        self.assertFalse(m.publish_and_release())
        self.assertEqual(open_record(m.kv['ret0'])['pending'], [2])


if __name__ == '__main__':
    unittest.main()
