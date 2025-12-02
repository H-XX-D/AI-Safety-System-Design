from communication.translator import AirGappedTranslator
from communication.translator_alt import AltTranslator, consensus_compare
from datetime import datetime


def _sample_message(protocol_version: str = "1.0"):
    return {
        'protocol_version': protocol_version,
        'type': 'research_result',
        'topic': 'alignment strategy',
        'from_system': 2,
        'timestamp': datetime.now().isoformat(),
        'findings': 'Preliminary analysis of incentive shaping performance',
        'sources': ['paperA', 'paperB'],
        'confidence': 0.82,
    }


def test_translator_consensus_basic():
    msg = _sample_message()
    t_main = AirGappedTranslator(translator_id=1, protocol_version='1.0', private_key='k1')
    t_alt = AltTranslator(translator_id=99, protocol_version='1.0', private_key='k_alt')
    tr_main = t_main.translate(msg)
    tr_alt = t_alt.translate(msg)
    assert tr_main.original_hash == tr_alt.original_hash
    # basic semantic overlap
    assert consensus_compare(tr_alt, tr_alt)  # self comparison sanity
    assert consensus_compare(tr_alt, tr_main)  # cross implementation comparison
