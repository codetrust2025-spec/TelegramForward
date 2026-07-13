from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.recruitment_mail_api import install_recruitment_mail_routes

def app_client(monkeypatch):
    monkeypatch.delenv('DASHBOARD_PASSWORD',raising=False)
    app=FastAPI();install_recruitment_mail_routes(app);return TestClient(app)

def test_feature_config_is_available_when_disabled(monkeypatch):
    monkeypatch.setenv('AI_INTERVIEW_OFFER_TRACKING_ENABLED','false')
    response=app_client(monkeypatch).get('/api/ai-recruitment/config')
    assert response.status_code==200
    assert response.json()['enabled'] is False

def test_review_api_is_feature_guarded(monkeypatch):
    monkeypatch.setenv('AI_INTERVIEW_OFFER_TRACKING_ENABLED','false')
    response=app_client(monkeypatch).get('/api/ai-recruitment/review')
    assert response.status_code==404
