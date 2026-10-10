from pathlib import Path
import json
import pytest
from database import Gateway
from streaming import RunTrace
from demo_studio import execute_demo, SCENARIOS, reset_studio, demo_report
from streamlit.testing.v1 import AppTest

@pytest.mark.parametrize("index,decision", [(0,"ALLOW"),(1,"BLOCK"),(2,"REVIEW")])
def test_studio_scenarios(index, decision, gateway):
    trace=RunTrace();execute_demo(SCENARIOS[index][2],gateway,trace,offline=True)
    assert trace.done and trace.result['mode']=='offline'
    assert trace.result['actions'][0]['decision']==decision
    assert trace.stream_counts=={} and trace.usage==[]
    assert 'simulated_proposal' in [e['event'] for e in trace.snapshot()]
    assert '123456789' not in demo_report(gateway,trace)

def test_studio_approval_single_use(gateway):
    trace=RunTrace();execute_demo(SCENARIOS[2][2],gateway,trace,offline=True)
    row=trace.result['actions'][0]
    assert row['execution']=='pending'
    assert gateway.resolve(row['id'],True,row['digest'])['execution']=='completed'
    with pytest.raises(ValueError):gateway.resolve(row['id'],True,row['digest'])
    with gateway.connect() as c:assert c.execute('SELECT COUNT(*) FROM payments').fetchone()[0]==1

def test_reset_studio_isolated(tmp_path,monkeypatch):
    monkeypatch.setattr('demo_studio.STUDIO_DB',tmp_path/'studio.sqlite3')
    normal=Gateway(tmp_path/'normal.sqlite3');normal.propose('read','read_invoice',{'invoice_id':'INV-1001'})
    studio=Gateway(tmp_path/'studio.sqlite3');studio.propose('read','read_invoice',{'invoice_id':'INV-1001'})
    reset_studio()
    assert studio.history()==[] and len(normal.history())==1

def test_studio_landing_selection_and_no_rerun_calls(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','')
    monkeypatch.setenv('AUDIT_DB_PATH',str(tmp_path/'normal.sqlite3'))
    monkeypatch.setattr('demo_studio.STUDIO_DB',tmp_path/'studio.sqlite3')
    app=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=15).run()
    assert not app.exception and len(app.tabs)==0
    assert app.radio(key='navigation').value=='Demo Studio'
    next(b for b in app.button if b.label=='Try Next Scenario').click().run()
    assert not app.exception and app.text_area(key='studio_request').value==SCENARIOS[1][2]
    next(b for b in app.button if b.label=='Choose Approve $15,000 Payment').click().run()
    assert app.text_area(key='studio_request').value==SCENARIOS[2][2]
    next(b for b in app.button if b.label=='Run Agent').click().run()
    app.run()
    assert not app.exception
    assert len(Gateway(tmp_path/'studio.sqlite3').history())==1
    next(b for b in app.button if b.label=='Approve Studio payment once').click().run()
    app.run()
    assert Gateway(tmp_path/'studio.sqlite3').history()[0]['execution']=='completed'
    # Another browser may reset the shared synthetic DB; stale views stay usable.
    reset_studio()
    app.run()
    assert not app.exception
    next(b for b in app.button if b.label=='Reset Studio Demo').click().run()
    assert not app.exception and Gateway(tmp_path/'studio.sqlite3').history()==[]

def test_active_studio_reset_fails_closed(tmp_path,monkeypatch):
    monkeypatch.setattr('demo_studio.STUDIO_DB',tmp_path/'studio.sqlite3')
    g=Gateway(tmp_path/'studio.sqlite3')
    with g.connect() as c:
        c.execute('CREATE TABLE incoming_events(id TEXT,status TEXT)')
        c.execute("INSERT INTO incoming_events VALUES ('active','running')")
    with pytest.raises(ValueError):reset_studio()

def test_studio_binds_event_before_worker_starts(gateway,monkeypatch):
    from demo_studio import start_demo
    class ImmediateThread:
        def __init__(self,target,args,kwargs,**unused):self.target,self.args,self.kwargs=target,args,kwargs
        def start(self):
            with gateway.connect() as c:
                row=c.execute('SELECT status,run_id FROM incoming_events').fetchone()
                assert row['status']=='running' and row['run_id']==self.args[2].id
            self.target(*self.args,**self.kwargs)
    monkeypatch.setattr('demo_studio.threading.Thread',ImmediateThread)
    t=start_demo(SCENARIOS[0][2],gateway,offline=True)
    with gateway.connect() as c:assert c.execute('SELECT status FROM incoming_events').fetchone()[0]=='completed'
    assert t.done
