import dataclasses

from app.config import config as real_config
from app.handlers import dashboard
from tests.helpers import FakeMessage, make_user


async def test_dashboard_requires_registration():
    m = FakeMessage(7001)
    await dashboard.cmd_dashboard(m)
    assert any("ro'yxatdan o'ting" in a for a in m.answers)


async def test_dashboard_without_webapp_url_shows_not_configured(monkeypatch):
    await make_user("viewer", 7002)
    monkeypatch.setattr(dashboard, "config", dataclasses.replace(real_config, webapp_url=""))
    m = FakeMessage(7002)
    await dashboard.cmd_dashboard(m)
    assert any("hali sozlanmagan" in a for a in m.answers)


async def test_dashboard_with_webapp_url_sends_button(monkeypatch):
    await make_user("viewer", 7003)
    monkeypatch.setattr(
        dashboard, "config", dataclasses.replace(real_config, webapp_url="https://1-2-3-4.sslip.io")
    )
    m = FakeMessage(7003)
    await dashboard.cmd_dashboard(m)
    assert m.answers
    assert m.last_markup is not None
    button = m.last_markup.inline_keyboard[0][0]
    assert button.web_app.url == "https://1-2-3-4.sslip.io"
