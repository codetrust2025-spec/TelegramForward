from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.recruitment_mail_api import install_recruitment_mail_routes


def test_dashboard_query_does_not_use_reserved_day_alias():
    source = Path("core/recruitment_mail_api.py").read_text(encoding="utf-8")
    assert "created_at::date day" not in source
    assert "created_at::date AS event_day" in source

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
