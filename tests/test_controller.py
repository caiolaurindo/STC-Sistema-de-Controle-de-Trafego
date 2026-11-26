"""
Testes unitários para a máquina de estados do controlador semafórico adaptativo.
"""

import pytest
from stc.controller import State, TrafficController, TrafficSignal


def test_controller_initial_state():
    ctrl = TrafficController(t_min_verde=5.0, t_base_verde=10.0)
    assert ctrl.estado == State.VIA_A_VERDE
    assert ctrl.sinal_via_a == TrafficSignal.GREEN
    assert ctrl.sinal_via_b == TrafficSignal.RED
    assert ctrl.sinal_pedestre == TrafficSignal.RED
    assert ctrl.tempo_no_estado == 0.0


def test_controller_normal_cycle_without_traffic():
    """Verifica um ciclo completo sem veículos e sem pedestres."""
    ctrl = TrafficController(
        t_min_verde=4.0,
        t_base_verde=6.0,
        t_amarelo=2.0,
        t_clearance=1.0,
    )

    # 1. Via A Verde até t_base_verde
    ctrl.update(dt=5.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)
    # Como via_b também é 0, não antecipa antes do tempo alvo (alvo para 0 carros é t_min_verde=4.0)
    # Em 5.0s (já passou de 4.0), deve ter transicionado para AMARELO
    assert ctrl.estado == State.VIA_A_AMARELO
    assert ctrl.sinal_via_a == TrafficSignal.YELLOW
    assert ctrl.sinal_via_b == TrafficSignal.RED

    # 2. Amarelo Via A por 2.0s
    ctrl.update(dt=2.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.CLEARANCE_A
    assert ctrl.sinal_via_a == TrafficSignal.RED
    assert ctrl.sinal_via_b == TrafficSignal.RED

    # 3. Clearance por 1.0s -> Abre Via B
    ctrl.update(dt=1.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_B_VERDE
    assert ctrl.sinal_via_b == TrafficSignal.GREEN
    assert ctrl.sinal_via_a == TrafficSignal.RED

    # 4. Via B Verde -> Amarelo
    ctrl.update(dt=4.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_B_AMARELO

    # 5. Amarelo Via B -> Clearance B
    ctrl.update(dt=2.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.CLEARANCE_B

    # 6. Clearance B -> Retorna à Via A Verde
    ctrl.update(dt=1.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_A_VERDE
    assert ctrl.total_ciclos == 1


def test_respects_minimum_green_time():
    """Garante que a Via A não feche antes do t_min_verde mesmo com fila gigante na Via B."""
    ctrl = TrafficController(t_min_verde=5.0, t_base_verde=10.0)

    # Passo de 3 segundos com Via A vazia e Via B cheia
    ctrl.update(dt=3.0, carros_via_a=0, carros_via_b=5, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_A_VERDE
    assert ctrl.tempo_no_estado == 3.0

    # Mais 1.5s (total 4.5s < 5.0s mín) -> ainda verde
    ctrl.update(dt=1.5, carros_via_a=0, carros_via_b=5, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_A_VERDE

    # Ao atingir 5.0s mín, deve antecipar para Amarelo imediatamente
    ctrl.update(dt=0.6, carros_via_a=0, carros_via_b=5, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_A_AMARELO


def test_early_transition_when_green_empty():
    """Verifica antecipação da troca quando a via em verde esvazia e a concorrente tem carros."""
    ctrl = TrafficController(t_min_verde=5.0, t_base_verde=15.0)

    # Inicialmente há carros na Via A
    ctrl.update(dt=5.0, carros_via_a=2, carros_via_b=3, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_A_VERDE  # Ainda dentro do tempo com carros

    # No instante seguinte, os carros da Via A passaram (virou 0) e a Via B ainda tem 3
    ctrl.update(dt=0.2, carros_via_a=0, carros_via_b=3, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_A_AMARELO


def test_dynamic_green_extension():
    """Verifica que o verde é estendido quando há mais carros na via aberta."""
    ctrl = TrafficController(
        t_min_verde=5.0,
        t_base_verde=10.0,
        t_max_verde=20.0,
        t_extensao_por_carro=2.5,
    )

    # 4 carros na Via A e 0 na Via B -> alvo = 10 + (4-1)*2.5 = 17.5s
    ctrl.update(dt=12.0, carros_via_a=4, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_A_VERDE  # Deve continuar verde aos 12s pois alvo é 17.5s

    ctrl.update(dt=5.0, carros_via_a=4, carros_via_b=0, pedestre_detectado=False)
    # Atingiu 17s -> aos 18s deve ter transicionado para amarelo
    ctrl.update(dt=1.0, carros_via_a=4, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_A_AMARELO


def test_pedestrian_priority():
    """Valida o ciclo completo de acionamento de pedestre com segurança."""
    ctrl = TrafficController(
        t_min_verde=5.0,
        t_base_verde=8.0,
        t_amarelo=2.0,
        t_clearance=1.0,
        t_pedestre_verde=6.0,
        t_pedestre_alerta=2.0,
        limiar_confirmacao_pedestre=1.0,
    )

    # Pedestre detectado por 0.5s -> ainda não confirmado (filtro de ruído)
    ctrl.update(dt=0.5, carros_via_a=2, carros_via_b=1, pedestre_detectado=True)
    assert not ctrl.pedido_pedestre_pendente

    # Pedestre persiste por mais 0.6s (total 1.1s >= 1.0s) -> confirmado!
    ctrl.update(dt=0.6, carros_via_a=2, carros_via_b=1, pedestre_detectado=True)
    assert ctrl.pedido_pedestre_pendente

    # Avança até terminar o verde base (8.0s)
    ctrl.update(dt=7.0, carros_via_a=2, carros_via_b=1, pedestre_detectado=True)
    assert ctrl.estado == State.VIA_A_AMARELO

    # Amarelo (2.0s) -> Clearance (1.0s)
    ctrl.update(dt=2.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.CLEARANCE_A
    ctrl.update(dt=1.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)

    # Deve entrar em PEDESTRE_VERDE (e não na Via B)
    assert ctrl.estado == State.PEDESTRE_VERDE
    assert ctrl.sinal_pedestre == TrafficSignal.GREEN
    assert ctrl.sinal_via_a == TrafficSignal.RED
    assert ctrl.sinal_via_b == TrafficSignal.RED

    # Travessia verde (6.0s) -> Alerta piscante (2.0s)
    ctrl.update(dt=6.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.PEDESTRE_ALERTA
    assert ctrl.sinal_pedestre == TrafficSignal.FLASH_RED

    # Alerta (2.0s) -> Clearance pós-pedestre
    ctrl.update(dt=2.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.CLEARANCE_P
    assert ctrl.sinal_pedestre == TrafficSignal.RED

    # Clearance pós-pedestre -> Reabre Via B (pois a fase anterior foi Via A)
    ctrl.update(dt=1.0, carros_via_a=0, carros_via_b=0, pedestre_detectado=False)
    assert ctrl.estado == State.VIA_B_VERDE
    assert ctrl.sinal_via_b == TrafficSignal.GREEN
    assert ctrl.sinal_via_a == TrafficSignal.RED
