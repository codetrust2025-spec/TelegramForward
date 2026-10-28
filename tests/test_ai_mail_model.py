import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core import ai_mail_model as policy, ai_gateway, ollama_nodes


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_MAIL_MODEL_STATE_FILE", str(tmp_path / "mail-model.json"))
    monkeypatch.setenv("OLLAMA_NODE_STATE_FILE", str(tmp_path / "nodes.json"))
    monkeypatch.setattr(ollama_nodes, "_request", lambda *a, **kw: {
        "models": [{"name": "lab:7b", "size": 123456}]})
    ollama_nodes.reset_breakers()
    yield
    ollama_nodes.reset_breakers()


def generation(**kw):
    return ai_gateway.AIResult('{}', kw['model'], 10, kw['node_id'], kw['node_id'])


def test_catalog_live_inventory_without_selection_write():
    result = policy.catalog()
    assert len(result['nodes']) == 3
    assert result['nodes'][0]['models'] == [{'name': 'lab:7b', 'size_bytes': 123456}]
    assert not policy._path().exists()


def test_unreachable_nodes_report_offline(monkeypatch):
    monkeypatch.setattr(ollama_nodes, '_request', lambda *a, **kw: (_ for _ in ()).throw(OSError()))
    assert all(not n['available'] for n in policy.catalog()['nodes'])


def test_activation_validates_every_node_and_persists_only_mail_selection(monkeypatch):
    calls = []
    def respond(**kw):
        calls.append(kw)
        return generation(**kw)
    monkeypatch.setattr(ai_gateway, 'chat_structured', respond)
    previous = ai_gateway.configured_models().copy()
    saved = policy.activate('lab:7b', 0, 'test-admin')
    assert saved['model'] == 'lab:7b' and saved['revision'] == 1
    assert len(saved['validated_nodes']) == 3
    assert all(c['schema']['required'] and c['workload'] == 'ai_mail_model_validation' for c in calls)
    assert ai_gateway.configured_models() == previous
    assert not ollama_nodes._state_path().exists()


@pytest.mark.parametrize('failure', ['schema', 'missing', 'one_node'])
def test_failed_validation_retains_previous_bytes(monkeypatch, failure):
    monkeypatch.setattr(ai_gateway, 'chat_structured', generation)
    policy.activate('lab:7b', 0, 'admin')
    before = policy._path().read_bytes()
    if failure == 'schema':
        def fail(**kw):
            raise ai_gateway.AIGatewayError('bad schema', code='OLLAMA_SCHEMA_VALIDATION_FAILED')
        monkeypatch.setattr(ai_gateway, 'chat_structured', fail)
    elif failure == 'one_node':
        real = policy._inventory
        monkeypatch.setattr(policy, '_inventory', lambda n: real(n) if n['id'] == 'rtx4060' else {
            'id': n['id'], 'label': n['label'], 'available': False, 'models': []})
    with pytest.raises(ValueError):
        policy.activate('missing:7b' if failure == 'missing' else 'lab:7b', 1, 'admin')
    assert policy._path().read_bytes() == before


def test_stale_or_racing_save_rejected(monkeypatch):
    monkeypatch.setattr(ai_gateway, 'chat_structured', generation)
    policy.activate('lab:7b', 0, 'admin')
    with pytest.raises(ValueError, match='Refresh'):
        policy.activate('lab:7b', 0, 'admin')
    real = policy.test_model
    def race(model):
        proof = real(model)
        with policy._transaction():
            policy._write({**policy.state(), 'revision': 2})
        return proof
    monkeypatch.setattr(policy, 'test_model', race)
    with pytest.raises(ValueError, match='Refresh'):
        policy.activate('lab:7b', 1, 'admin')
    assert policy.selection()['revision'] == 2


def test_actual_mail_failover_and_observability(monkeypatch):
    monkeypatch.setattr(ai_gateway, 'chat_structured', generation)
    selected = policy.activate('lab:7b', 0, 'admin')
    order = ollama_nodes.candidate_order('lab:7b')
    calls = []
    def inference(**kw):
        calls.append(kw['node_id'])
        if kw['node_id'] == order[0]:
            raise ai_gateway.AIGatewayError('offline', code='OLLAMA_CONNECTION_FAILED')
        return generation(**kw)
    monkeypatch.setattr(ai_gateway, 'chat_structured', inference)
    result = policy.request(selected=selected, model='lab:7b', messages=[], schema={})
    assert calls == order[:2]
    assert result.node_id == order[1]
    assert policy.selection()['last_used']['node_id'] == order[1]
    assert policy.selection()['model'] == 'lab:7b'


def test_failed_persistence_retains_previous_selection(monkeypatch):
    monkeypatch.setattr(ai_gateway, 'chat_structured', generation)
    policy.activate('lab:7b', 0, 'admin')
    before = policy._path().read_bytes()
    monkeypatch.setattr(policy.os, 'replace', lambda *a: (_ for _ in ()).throw(OSError('test disk failure')))
    with pytest.raises(OSError):
        policy.activate('lab:7b', 1, 'admin')
    assert policy._path().read_bytes() == before


def test_worker_analysis_uses_saved_mail_model_and_records_actual_route(monkeypatch):
    from services import recruitment_mail_agent as agent
    monkeypatch.setattr(ai_gateway, 'chat_structured', generation)
    policy.activate('lab:7b', 0, 'admin')
    calls = []
    def classify(**kw):
        calls.append(kw)
        return ai_gateway.AIResult('{"status":"IGNORED_NOT_OFFER_RELATED"}', kw['model'], 10,
                                   kw['node_id'], 'Synthetic node')
    monkeypatch.setattr(ai_gateway, 'chat_structured', classify)
    monkeypatch.setattr(agent, '_requires_independent_validation', lambda *a: False)
    monkeypatch.setattr(agent, 'validate_result', lambda *a: None)
    result, model, _ = agent.analyze({'subject': 'Synthetic notice', 'body': 'No outcome.'})
    assert calls and all(c['model'] == 'lab:7b' for c in calls)
    assert model == 'lab:7b@' + calls[0]['node_id']
    assert result['classification_source'] == 'OLLAMA'
    assert policy.selection()['last_used']['model'] == 'lab:7b'


def test_gateway_pinned_probe_does_not_probe_other_nodes(monkeypatch):
    monkeypatch.setattr(ollama_nodes, 'select_available_node', lambda **kw: pytest.fail('must stay pinned'))
    monkeypatch.setattr(ai_gateway, 'health', lambda **kw: {'endpoint_reachable': True, 'model_available': True})
    urls = []
    def response(*args, **kw):
        urls.append(kw['base_url'])
        return {'message': {'content': '{"ok":true}'}}
    monkeypatch.setattr(ai_gateway, '_request_json', response)
    result = ai_gateway.chat_structured(messages=[], model='lab:7b', schema={'type': 'object'},
                                        node_id='rtx4060', max_retries=0)
    assert result.node_id == 'rtx4060'
    assert urls == [ollama_nodes.base_url_for('rtx4060')]


@pytest.mark.parametrize('method,path,body', [('GET','/mail-model',None), ('POST','/mail-model/test',{'model':'lab:7b'}),
                                           ('PUT','/mail-model',{'model':'lab:7b','revision':0})])
def test_model_routes_require_admin_before_inventory_or_inference(monkeypatch, method, path, body):
    from core import recruitment_mail_api as api
    monkeypatch.setattr(api, 'enabled', lambda: False)
    app = FastAPI()
    api.install_recruitment_mail_routes(app)
    monkeypatch.setattr(api, '_guard', lambda: None)
    def denied(request):
        raise HTTPException(403, 'Admin only')
    monkeypatch.setattr(api, 'require_fleet_admin', denied)
    monkeypatch.setattr(policy, 'catalog', lambda: pytest.fail('unauthorized inventory'))
    monkeypatch.setattr(policy, 'test_model', lambda *a: pytest.fail('unauthorized inference'))
    with TestClient(app) as client:
        assert client.request(method, '/api/ai-recruitment' + path, json=body).status_code == 403
    assert not policy._path().exists()


def test_admin_test_is_read_only_and_save_revalidates_with_revision(monkeypatch):
    from core import recruitment_mail_api as api
    monkeypatch.setattr(api, 'enabled', lambda: False)
    app = FastAPI()
    api.install_recruitment_mail_routes(app)
    monkeypatch.setattr(api, '_guard', lambda: None)
    monkeypatch.setattr(api, 'require_fleet_admin', lambda request: {'username': 'test-admin'})
    calls = []
    def respond(**kw):
        calls.append(kw['node_id'])
        return generation(**kw)
    monkeypatch.setattr(ai_gateway, 'chat_structured', respond)
    with TestClient(app) as client:
        assert client.get('/api/ai-recruitment/mail-model').status_code == 200
        assert client.post('/api/ai-recruitment/mail-model/test', json={'model': 'lab:7b'}).status_code == 200
        assert not policy._path().exists()
        assert client.put('/api/ai-recruitment/mail-model', json={'model': 'lab:7b', 'revision': 0}).status_code == 200
        assert len(calls) == 6  # Test and save each independently exercise all three nodes.
        assert policy.state()['updated_by'] == 'test-admin'
        assert client.put('/api/ai-recruitment/mail-model', json={'model': 'lab:7b', 'revision': 0}).status_code == 409
        assert client.put('/api/ai-recruitment/mail-model', json=[]).status_code == 400
