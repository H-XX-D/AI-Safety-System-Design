from translator import AirGappedTranslator, Translation
from translator_alt import AltTranslator, consensus_compare, AltTranslation
from datetime import datetime
from typing import Dict, Any


def _msg(topic: str) -> Dict[str, Any]:
    return {
        'protocol_version': '1.0',
        'type': 'research_result',
        'topic': topic,
        'from_system': 3,
        'timestamp': datetime.now().isoformat(),
        'findings': 'Structured assessment of emergent incentive alignment',
        'sources': ['srcA'],
        'confidence': 0.9,
    }


def test_translator_divergence_negative():
    m1 = _msg('alignment strategy')
    m2 = _msg('different topic')  # semantic divergence
    t_main = AirGappedTranslator(translator_id=1, protocol_version='1.0', private_key='k1')
    t_alt = AltTranslator(translator_id=99, protocol_version='1.0', private_key='k_alt')
    tr_main_1: Translation = t_main.translate(m1)
    tr_alt_1: AltTranslation = t_alt.translate(m1)
    assert consensus_compare(tr_alt_1, tr_main_1)  # baseline should pass
    tr_main_2: Translation = t_main.translate(m2)
    tr_alt_2: AltTranslation = t_alt.translate(m2)
    # Hashes differ; consensus must fail
    assert tr_main_1.original_hash != tr_main_2.original_hash
    assert consensus_compare(tr_alt_1, tr_main_2) is False
    assert consensus_compare(tr_alt_2, tr_main_1) is False
