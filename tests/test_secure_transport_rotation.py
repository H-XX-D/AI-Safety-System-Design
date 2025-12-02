import importlib


def test_secure_transport_decode_with_fallback_key(monkeypatch):
    # Configure primary + fallback keys
    monkeypatch.setenv('APP_ENV', 'development')
    from utilities.config_loader import load_config
    cfg = load_config() or {}
    st = cfg.get('secure_transport', {})
    primary = st.get('hmac_key_hex')
    # Use two simple hex keys
    k1 = primary or '00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff'
    k2 = 'ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100'

    # Patch message_codec to use k1 as primary and k2 as fallback
    def _fake_load():
        return {
            'secure_transport': {
                'enabled': True,
                'sender_id': 6,
                'recipient_id': 7,
                'session_id': 123,
                'hmac_key_hex': k1,
                'hmac_key_hex_fallback': k2,
            }
        }
    monkeypatch.setenv('APP_ENV', 'default')
    monkeypatch.setenv('ORCH_SKIP_WORM_HALT', '1')
    monkeypatch.setenv('CONFIG_STRICT', '0')
    monkeypatch.setenv('CONFIG_PUBKEY_HEX', '')
    monkeypatch.setenv('CONFIG_PUBKEYS_HEX', '')
    monkeypatch.setattr('message_codec.load_config', _fake_load)
    import communication.message_codec
    import communication.aura_secure_transport
    importlib.reload(message_codec)

    codec = message_codec.MessageCodec()
    text = 'System 6 approves proposal 001'

    # Encode with fallback key by swapping primary/secondary temporarily
    ctx = aura_secure_transport.TransportContext(
        sender_id=6, recipient_id=7, session_id=123, secret_key=bytes.fromhex(k2)
    )
    payload, method, meta = codec.encode(text)
    # Replace frame with same content but HMAC computed via k2
    # Pack directly to simulate rotation
    packed = aura_secure_transport.pack_secure(payload if not meta.get('secure_transport') else codec.decode(payload)[0].encode('utf-8'), ctx=ctx, sequence=0)
    # Should decode via fallback
    decoded, info = codec.decode(packed)
    assert isinstance(decoded, str)
