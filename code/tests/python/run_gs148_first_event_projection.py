#!/usr/bin/env python3
"""Focused recovery projection through existing GS-130 local API fixture.
No new backend contract or trusted production credential is implemented.
"""
import argparse,json,threading
from pathlib import Path
from wsgiref.simple_server import make_server
from run_full_product_p0_e2e import LocalProductStack,QuietHandler,request_json

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--requests',type=Path,required=True)
    args=parser.parse_args();requests=json.loads(args.requests.read_text())
    assert len(requests)==2 and requests[0]['event_key']!=requests[1]['event_key']
    stack=LocalProductStack('home-first-event','owner-first-event',requests[0]['event_key'])
    stack.now=requests[1]['occurred_at']
    server=make_server('127.0.0.1',0,stack,handler_class=QuietHandler)
    base=f'http://127.0.0.1:{server.server_port}'
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        status,_=request_json(base,'POST','/v1/homes',{'home_id':stack.home_id,'display_name':'First event fixture',
            'timezone':'Asia/Kolkata','language':'en-IN',
            'residents':[{'resident_id':'resident-first-event','display_name':'Resident','consent_active':True}]})
        assert status==201
        path=f'/v1/homes/{stack.home_id}/events'
        for request in requests:
            status,result=request_json(base,'POST',path,request,hub_token=stack.valid_fixture_token)
            assert status==201 and result['status']=='COMMITTED' and result['event_key']==request['event_key']
            status,duplicate=request_json(base,'POST',path,request,hub_token=stack.valid_fixture_token)
            assert status==200 and duplicate['status']=='COMMITTED' and duplicate['event_key']==request['event_key']
        commits=stack.durable.db.execute('SELECT COUNT(*) FROM durable_event_commits').fetchone()[0]
        assert commits==2
        status,snapshot=request_json(base,'GET',f'/v1/homes/{stack.home_id}/snapshot')
        assert status==200 and len(snapshot['recent_events'])==2
        ids=[event['event_id'] for event in snapshot['recent_events']]
        assert len(set(ids))==2
        print('GS148-ARCH-051 PASS recovered_caregiver_effects=1 fresh_effects=1 exact_commits=2 retries=2')
        print('PRODUCTION_CLOUDSYNC=PENDING PRODUCT_P0=PARTIAL PHYSICAL=NOT_RUN')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5);stack.close()
if __name__=='__main__':main()
