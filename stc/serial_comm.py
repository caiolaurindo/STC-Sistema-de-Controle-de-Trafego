"""
Módulo de Comunicação Serial (UART) para Arduino / ESP32.
Envia comandos textuais para acionamento físico dos semáforos da maquete.
Possui fallback automático para Modo Simulado quando não há hardware conectado.
"""

import time
from typing import Optional, Any

try:
    import serial
    SERIAL_DISPONIVEL = True
except ImportError:
    serial = None
    SERIAL_DISPONIVEL = False


class TrafficSerialCommunicator:
    """
    Gerenciador da conexão serial com microcontrolador.
    Protocolo textual padronizado:
      SET:A=<G|Y|R>,B=<G|Y|R>,P=<G|R|F>,T=<segundos>\n
    """

    def __init__(
        self,
        porta: Optional[str] = None,
        baudrate: int = 9600,
        timeout: float = 1.0,
        taxa_heartbeat: float = 1.0,
    ):
        self.porta = porta
        self.baudrate = baudrate
        self.timeout = timeout
        self.taxa_heartbeat = taxa_heartbeat

        self.conexao: Optional[Any] = None
        self.modo_simulado: bool = True
        self.ultima_mensagem_enviada: str = ""
        self.ultimo_envio_timestamp: float = 0.0
        self.ultimo_estado_enviado: str = ""

        self.inicializar()

    def inicializar(self) -> None:
        """Tenta abrir a porta serial indicada; caso indisponível, entra em modo simulado."""
        if not self.porta or self.porta.strip().lower() in ("none", "", "simulado", "mock"):
            self.modo_simulado = True
            return

        if not SERIAL_DISPONIVEL:
            print("[STC-SERIAL] Pacote 'pyserial' não encontrado. Operando em MODO SIMULADO.")
            self.modo_simulado = True
            return

        try:
            self.conexao = serial.Serial(
                port=self.porta,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )
            # Dá tempo para o bootloader do Arduino resetar após a abertura da porta DTR
            time.sleep(1.5)
            self.modo_simulado = False
            print(f"[STC-SERIAL] Conectado com sucesso na porta {self.porta} ({self.baudrate} bps).")
        except Exception as e:
            print(f"[STC-SERIAL] Não foi possível conectar na porta '{self.porta}': {e}")
            print("[STC-SERIAL] Continuando em MODO SIMULADO (sem hardware físico).")
            self.modo_simulado = True

    @staticmethod
    def formatar_comando(via_a: str, via_b: str, pedestre: str, tempo_restante: float) -> str:
        """Formata o comando no protocolo textual padrão."""
        t_int = max(0, int(round(tempo_restante)))
        return f"SET:A={via_a},B={via_b},P={pedestre},T={t_int}\n"

    def enviar_estado(
        self,
        via_a: str,
        via_b: str,
        pedestre: str,
        tempo_restante: float,
        forcar: bool = False,
    ) -> bool:
        """
        Envia o estado semafórico atual via Serial.
        Para economizar largura de banda e evitar gargalos no Arduino,
        envia imediatamente quando o estado das luzes muda ou a cada intervalo
        de heartbeat (padrão 1s) para atualizar o cronômetro do display/placa.
        """
        agora = time.time()
        assinatura_luzes = f"{via_a}_{via_b}_{pedestre}"
        mudou_estado = assinatura_luzes != self.ultimo_estado_enviado
        tempo_decorrido = agora - self.ultimo_envio_timestamp

        if not forcar and not mudou_estado and tempo_decorrido < self.taxa_heartbeat:
            return False

        comando = self.formatar_comando(via_a, via_b, pedestre, tempo_restante)
        self.ultima_mensagem_enviada = comando.strip()
        self.ultimo_estado_enviado = assinatura_luzes
        self.ultimo_envio_timestamp = agora

        if self.modo_simulado or not self.conexao:
            return True

        try:
            self.conexao.write(comando.encode("ascii"))
            self.conexao.flush()
            return True
        except Exception as e:
            print(f"[STC-SERIAL] Erro ao transmitir para porta serial: {e}")
            return False

    def fechar(self) -> None:
        """Encerra a conexão serial com segurança."""
        if self.conexao and hasattr(self.conexao, "is_open") and self.conexao.is_open:
            try:
                self.conexao.close()
            except Exception:
                pass
        self.conexao = None
