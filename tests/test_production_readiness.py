from config_loader import validate_production_readiness


def test_validate_production_readiness_raises_on_bad_cfg(monkeypatch):
    cfg = {
        'worm': {'halt_on_failure': False},
        'secure_transport': {'enabled': False, 'hmac_key_hex': '00112233'},
        'val': {'required_signers': 1},
    }
    monkeypatch.setenv('APP_ENV', 'production')
    try:
        validate_production_readiness(cfg)
        assert False, 'Expected RuntimeError'
    except RuntimeError:
        pass

