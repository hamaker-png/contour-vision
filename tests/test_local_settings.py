from backend import local_settings
from fastapi.testclient import TestClient
from backend.app import app

def test_local_key_reuse_and_public_mode_disables_all_automatic_keys(tmp_path,monkeypatch):
    monkeypatch.setattr(local_settings,'KEY_FILE',tmp_path/'private/settings.json')
    monkeypatch.delenv('CONTOUR_PUBLIC',raising=False);monkeypatch.setenv('OPENAI_API_KEY','environment-test-key')
    local_settings.save_local_key('local-test-key',True)
    assert local_settings.server_key()=='local-test-key'
    client=TestClient(app);health=client.get('/api/health').json()
    assert health['server_key'] and health['local_key_saved']
    assert 'local-test-key' not in client.get('/api/health').text
    monkeypatch.setenv('CONTOUR_PUBLIC','1')
    assert not local_settings.server_key() and not client.get('/api/health').json()['local_key_storage']
    assert client.post('/api/local-settings',json={'key':'another-test-key','remember':True}).status_code==400
    monkeypatch.delenv('CONTOUR_PUBLIC');local_settings.save_local_key('',False)
    assert not local_settings.KEY_FILE.exists() and local_settings.server_key()=='environment-test-key'
