"""
Testes unitários para o módulo de comunicação serial.
"""

from stc.serial_comm import TrafficSerialCommunicator


def test_serial_mock_initialization():
    comm = TrafficSerialCommunicator(porta="none")
    assert comm.modo_simulado is True
    assert comm.conexao is None


def test_serial_formatar_comando():
    cmd = TrafficSerialCommunicator.formatar_comando(
        via_a="G",
        via_b="R",
        pedestre="R",
        tempo_restante=7.8,
    )
    assert cmd == "SET:A=G,B=R,P=R,T=8\n"

    cmd_ped = TrafficSerialCommunicator.formatar_comando(
        via_a="R",
        via_b="R",
        pedestre="F",
        tempo_restante=2.1,
    )
    assert cmd_ped == "SET:A=R,B=R,P=F,T=2\n"


def test_serial_mock_send_and_heartbeat():
    comm = TrafficSerialCommunicator(porta=None, taxa_heartbeat=0.5)

    # Primeiro envio deve ocorrer imediatamente
    enviou = comm.enviar_estado("G", "R", "R", 10.0)
    assert enviou is True
    assert comm.ultima_mensagem_enviada == "SET:A=G,B=R,P=R,T=10"

    # Envio logo em seguida com o mesmo estado não deve enviar (evita flood)
    enviou_repetido = comm.enviar_estado("G", "R", "R", 10.0)
    assert enviou_repetido is False

    # Se o estado mudar (ex: sinal vai para amarelo), envia na hora
    enviou_mudanca = comm.enviar_estado("Y", "R", "R", 3.0)
    assert enviou_mudanca is True
    assert comm.ultima_mensagem_enviada == "SET:A=Y,B=R,P=R,T=3"
