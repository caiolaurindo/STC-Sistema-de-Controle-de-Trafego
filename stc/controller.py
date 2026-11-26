"""
Módulo de Controle Semafórico Adaptativo (FSM)
Gerencia a máquina de estados, tempos mínimos e máximos, prioridade de pedestre
e balanceamento dinâmico de tráfego veicular.
"""

from enum import Enum
from typing import Dict, Any, Optional


class State(Enum):
    VIA_A_VERDE = "VIA_A_VERDE"
    VIA_A_AMARELO = "VIA_A_AMARELO"
    CLEARANCE_A = "CLEARANCE_A"
    VIA_B_VERDE = "VIA_B_VERDE"
    VIA_B_AMARELO = "VIA_B_AMARELO"
    CLEARANCE_B = "CLEARANCE_B"
    PEDESTRE_VERDE = "PEDESTRE_VERDE"
    PEDESTRE_ALERTA = "PEDESTRE_ALERTA"
    CLEARANCE_P = "CLEARANCE_P"


class TrafficSignal(Enum):
    RED = "R"
    YELLOW = "Y"
    GREEN = "G"
    FLASH_RED = "F"


class TrafficController:
    """
    Controlador Semafórico Inteligente baseado em Máquina de Estados Finita (FSM).
    Ajusta dinamicamente os tempos de sinal verde com base nas filas das vias
    e dá prioridade à faixa de pedestres quando o boneco for detectado.
    """

    def __init__(
        self,
        t_min_verde: float = 5.0,
        t_max_verde: float = 25.0,
        t_base_verde: float = 10.0,
        t_extensao_por_carro: float = 2.0,
        t_amarelo: float = 3.0,
        t_clearance: float = 1.5,
        t_pedestre_verde: float = 8.0,
        t_pedestre_alerta: float = 3.0,
        limiar_confirmacao_pedestre: float = 1.0,
    ):
        self.t_min_verde = float(t_min_verde)
        self.t_max_verde = float(t_max_verde)
        self.t_base_verde = float(t_base_verde)
        self.t_extensao_por_carro = float(t_extensao_por_carro)
        self.t_amarelo = float(t_amarelo)
        self.t_clearance = float(t_clearance)
        self.t_pedestre_verde = float(t_pedestre_verde)
        self.t_pedestre_alerta = float(t_pedestre_alerta)
        self.limiar_confirmacao_pedestre = float(limiar_confirmacao_pedestre)

        # Estado inicial
        self.estado: State = State.VIA_A_VERDE
        self.tempo_no_estado: float = 0.0

        # Controle de pedestre
        self.tempo_pedestre_presente: float = 0.0
        self.pedido_pedestre_pendente: bool = False
        self.proxima_via_apos_pedestre: State = State.VIA_B_VERDE

        # Telemetria e diagnóstico
        self.motivo_status: str = "Início da operação. Via A aberta."
        self.tempo_alvo_verde_atual: float = self.t_base_verde
        self.total_ciclos: int = 0

    def solicitar_pedestre_manual(self) -> None:
        """Permite acionar o chamado de pedestre via teclado (ex: tecla 'p') para teste."""
        self.pedido_pedestre_pendente = True
        self.tempo_pedestre_presente = self.limiar_confirmacao_pedestre

    @property
    def sinal_via_a(self) -> TrafficSignal:
        if self.estado == State.VIA_A_VERDE:
            return TrafficSignal.GREEN
        elif self.estado == State.VIA_A_AMARELO:
            return TrafficSignal.YELLOW
        return TrafficSignal.RED

    @property
    def sinal_via_b(self) -> TrafficSignal:
        if self.estado == State.VIA_B_VERDE:
            return TrafficSignal.GREEN
        elif self.estado == State.VIA_B_AMARELO:
            return TrafficSignal.YELLOW
        return TrafficSignal.RED

    @property
    def sinal_pedestre(self) -> TrafficSignal:
        if self.estado == State.PEDESTRE_VERDE:
            return TrafficSignal.GREEN
        elif self.estado == State.PEDESTRE_ALERTA:
            return TrafficSignal.FLASH_RED
        return TrafficSignal.RED

    @property
    def tempo_restante(self) -> float:
        """Retorna o tempo restante estimado para a fase atual (em segundos)."""
        if self.estado == State.VIA_A_VERDE:
            duracao = max(self.t_min_verde, self.tempo_alvo_verde_atual)
        elif self.estado == State.VIA_A_AMARELO:
            duracao = self.t_amarelo
        elif self.estado == State.CLEARANCE_A:
            duracao = self.t_clearance
        elif self.estado == State.VIA_B_VERDE:
            duracao = max(self.t_min_verde, self.tempo_alvo_verde_atual)
        elif self.estado == State.VIA_B_AMARELO:
            duracao = self.t_amarelo
        elif self.estado == State.CLEARANCE_B:
            duracao = self.t_clearance
        elif self.estado == State.PEDESTRE_VERDE:
            duracao = self.t_pedestre_verde
        elif self.estado == State.PEDESTRE_ALERTA:
            duracao = self.t_pedestre_alerta
        elif self.estado == State.CLEARANCE_P:
            duracao = self.t_clearance
        else:
            duracao = 0.0

        return max(0.0, duracao - self.tempo_no_estado)

    def _calcular_tempo_alvo_verde(self, carros_propria_via: int, carros_concorrente: int) -> float:
        """Calcula o tempo de verde ideal com base na fila atual."""
        if carros_propria_via <= 0:
            return self.t_min_verde

        # Se houver mais carros na concorrente, modera a extensão
        tempo = self.t_base_verde + max(0, carros_propria_via - 1) * self.t_extensao_por_carro
        return min(self.t_max_verde, max(self.t_min_verde, tempo))

    def update(
        self,
        dt: float,
        carros_via_a: int,
        carros_via_b: int,
        pedestre_detectado: bool,
    ) -> State:
        """
        Executa um passo de simulação/tempo no controlador.

        Args:
            dt: Intervalo de tempo decorrido desde o último update (segundos).
            carros_via_a: Número de veículos detectados na ROI da Via A.
            carros_via_b: Número de veículos detectados na ROI da Via B.
            pedestre_detectado: Se há boneco detectado na zona do pedestre.

        Returns:
            Novo estado do controlador.
        """
        if dt < 0:
            dt = 0.0

        self.tempo_no_estado += dt

        # Filtro de persistência do pedestre para evitar falsos positivos
        if pedestre_detectado:
            self.tempo_pedestre_presente += dt
            if self.tempo_pedestre_presente >= self.limiar_confirmacao_pedestre:
                if not self.pedido_pedestre_pendente:
                    self.motivo_status = "Pedestre confirmado na faixa. Prioridade agendada."
                self.pedido_pedestre_pendente = True
        else:
            # Se sumir da faixa antes de confirmar, reduz o tempo acumulado
            if not self.pedido_pedestre_pendente:
                self.tempo_pedestre_presente = max(0.0, self.tempo_pedestre_presente - dt * 1.5)

        # Máquina de Estados Finita (FSM)
        if self.estado == State.VIA_A_VERDE:
            self.tempo_alvo_verde_atual = self._calcular_tempo_alvo_verde(carros_via_a, carros_via_b)

            # 1. Respeito ao tempo mínimo obrigatório de verde
            if self.tempo_no_estado < self.t_min_verde:
                self.motivo_status = (
                    f"Via A em verde seguro ({self.tempo_no_estado:.1f}s / {self.t_min_verde:.1f}s min). "
                    f"Carros: A={carros_via_a}, B={carros_via_b}"
                )
            else:
                # 2. Antecipação: Via A esvaziou e há carros na Via B ou chamado de pedestre
                if carros_via_a == 0 and (carros_via_b > 0 or self.pedido_pedestre_pendente):
                    self.motivo_status = "Via A vazia; antecipando transição para atender fila/pedestre."
                    self._mudar_estado(State.VIA_A_AMARELO)

                # 3. Prioridade de Pedestre após verde base
                elif self.pedido_pedestre_pendente and self.tempo_no_estado >= self.t_base_verde:
                    self.motivo_status = "Prioridade de travessia do pedestre acionada."
                    self._mudar_estado(State.VIA_A_AMARELO)

                # 4. Fila pesada na Via B demandando alternância justa
                elif carros_via_b >= 3 and self.tempo_no_estado >= self.t_base_verde:
                    self.motivo_status = f"Fila na Via B ({carros_via_b} carros); alternando sinal."
                    self._mudar_estado(State.VIA_A_AMARELO)

                # 5. Esgotamento do tempo alvo calculado ou estouro do t_max
                elif self.tempo_no_estado >= self.tempo_alvo_verde_atual or self.tempo_no_estado >= self.t_max_verde:
                    self.motivo_status = f"Tempo de verde da Via A esgotado ({self.tempo_no_estado:.1f}s)."
                    self._mudar_estado(State.VIA_A_AMARELO)

                else:
                    self.motivo_status = (
                        f"Via A estendida por demanda ({carros_via_a} carros, "
                        f"alvo {self.tempo_alvo_verde_atual:.1f}s)."
                    )

        elif self.estado == State.VIA_A_AMARELO:
            self.motivo_status = f"Via A em atenção (amarelo: {self.tempo_restante:.1f}s restantes)."
            if self.tempo_no_estado >= self.t_amarelo:
                self._mudar_estado(State.CLEARANCE_A)

        elif self.estado == State.CLEARANCE_A:
            self.motivo_status = f"Intervalo de segurança (todos vermelhos: {self.tempo_restante:.1f}s restantes)."
            if self.tempo_no_estado >= self.t_clearance:
                if self.pedido_pedestre_pendente:
                    self.pedido_pedestre_pendente = False
                    self.tempo_pedestre_presente = 0.0
                    self.proxima_via_apos_pedestre = State.VIA_B_VERDE
                    self.motivo_status = "Liberando travessia de pedestre com prioridade."
                    self._mudar_estado(State.PEDESTRE_VERDE)
                else:
                    self.motivo_status = "Abrindo Via B."
                    self._mudar_estado(State.VIA_B_VERDE)

        elif self.estado == State.VIA_B_VERDE:
            self.tempo_alvo_verde_atual = self._calcular_tempo_alvo_verde(carros_via_b, carros_via_a)

            # 1. Respeito ao tempo mínimo obrigatório de verde
            if self.tempo_no_estado < self.t_min_verde:
                self.motivo_status = (
                    f"Via B em verde seguro ({self.tempo_no_estado:.1f}s / {self.t_min_verde:.1f}s min). "
                    f"Carros: A={carros_via_a}, B={carros_via_b}"
                )
            else:
                # 2. Antecipação: Via B esvaziou e há carros na Via A ou pedestre
                if carros_via_b == 0 and (carros_via_a > 0 or self.pedido_pedestre_pendente):
                    self.motivo_status = "Via B vazia; antecipando transição para atender fila/pedestre."
                    self._mudar_estado(State.VIA_B_AMARELO)

                # 3. Prioridade de Pedestre após verde base
                elif self.pedido_pedestre_pendente and self.tempo_no_estado >= self.t_base_verde:
                    self.motivo_status = "Prioridade de travessia do pedestre acionada."
                    self._mudar_estado(State.VIA_B_AMARELO)

                # 4. Fila pesada na Via A demandando alternância justa
                elif carros_via_a >= 3 and self.tempo_no_estado >= self.t_base_verde:
                    self.motivo_status = f"Fila na Via A ({carros_via_a} carros); alternando sinal."
                    self._mudar_estado(State.VIA_B_AMARELO)

                # 5. Esgotamento do tempo alvo calculado ou estouro do t_max
                elif self.tempo_no_estado >= self.tempo_alvo_verde_atual or self.tempo_no_estado >= self.t_max_verde:
                    self.motivo_status = f"Tempo de verde da Via B esgotado ({self.tempo_no_estado:.1f}s)."
                    self._mudar_estado(State.VIA_B_AMARELO)

                else:
                    self.motivo_status = (
                        f"Via B estendida por demanda ({carros_via_b} carros, "
                        f"alvo {self.tempo_alvo_verde_atual:.1f}s)."
                    )

        elif self.estado == State.VIA_B_AMARELO:
            self.motivo_status = f"Via B em atenção (amarelo: {self.tempo_restante:.1f}s restantes)."
            if self.tempo_no_estado >= self.t_amarelo:
                self._mudar_estado(State.CLEARANCE_B)

        elif self.estado == State.CLEARANCE_B:
            self.motivo_status = f"Intervalo de segurança (todos vermelhos: {self.tempo_restante:.1f}s restantes)."
            if self.tempo_no_estado >= self.t_clearance:
                if self.pedido_pedestre_pendente:
                    self.pedido_pedestre_pendente = False
                    self.tempo_pedestre_presente = 0.0
                    self.proxima_via_apos_pedestre = State.VIA_A_VERDE
                    self.motivo_status = "Liberando travessia de pedestre com prioridade."
                    self._mudar_estado(State.PEDESTRE_VERDE)
                else:
                    self.total_ciclos += 1
                    self.motivo_status = "Abrindo Via A."
                    self._mudar_estado(State.VIA_A_VERDE)

        elif self.estado == State.PEDESTRE_VERDE:
            self.motivo_status = f"Faixa de pedestres aberta ({self.tempo_restante:.1f}s restantes)."
            if self.tempo_no_estado >= self.t_pedestre_verde:
                self.motivo_status = "Alerta: tempo de pedestre finalizando."
                self._mudar_estado(State.PEDESTRE_ALERTA)

        elif self.estado == State.PEDESTRE_ALERTA:
            self.motivo_status = f"Faixa em alerta piscante ({self.tempo_restante:.1f}s restantes)."
            if self.tempo_no_estado >= self.t_pedestre_alerta:
                self._mudar_estado(State.CLEARANCE_P)

        elif self.estado == State.CLEARANCE_P:
            self.motivo_status = "Intervalo de segurança pós-pedestre."
            if self.tempo_no_estado >= self.t_clearance:
                # Se uma das vias tiver significativamente mais carros acumulados, abre ela
                if carros_via_b > carros_via_a and carros_via_b >= 2:
                    self.motivo_status = f"Reabrindo Via B (maior demanda pós-pedestre: {carros_via_b} carros)."
                    self._mudar_estado(State.VIA_B_VERDE)
                elif carros_via_a > carros_via_b and carros_via_a >= 2:
                    self.motivo_status = f"Reabrindo Via A (maior demanda pós-pedestre: {carros_via_a} carros)."
                    self._mudar_estado(State.VIA_A_VERDE)
                else:
                    self.motivo_status = f"Reabrindo {self.proxima_via_apos_pedestre.value} após pedestre."
                    self._mudar_estado(self.proxima_via_apos_pedestre)

        return self.estado

    def _mudar_estado(self, novo_estado: State) -> None:
        self.estado = novo_estado
        self.tempo_no_estado = 0.0

    def obter_resumo(self) -> Dict[str, Any]:
        """Retorna dicionário completo com a telemetria atual para HUD e logs."""
        return {
            "estado": self.estado.value,
            "tempo_no_estado": round(self.tempo_no_estado, 2),
            "tempo_restante": round(self.tempo_restante, 1),
            "sinal_via_a": self.sinal_via_a.value,
            "sinal_via_b": self.sinal_via_b.value,
            "sinal_pedestre": self.sinal_pedestre.value,
            "pedido_pedestre_pendente": self.pedido_pedestre_pendente,
            "motivo_status": self.motivo_status,
            "total_ciclos": self.total_ciclos,
        }
