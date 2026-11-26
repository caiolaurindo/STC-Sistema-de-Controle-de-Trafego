"""
Módulo de Visualização Gráfica (HUD / OSD) para o STC.
Renderiza os semáforos virtuais, temporizador digital, áreas de interesse (ROIs),
caixas delimitadoras de detecção e telemetria de tráfego na tela.
"""

import time
from typing import Dict, List, Tuple, Any, Optional

try:
    import cv2
    import numpy as np
    CV2_DISPONIVEL = True
except ImportError:
    cv2 = None
    np = None
    CV2_DISPONIVEL = False

from stc.controller import State, TrafficSignal
from stc.roi import ROI, ROIManager


class TrafficVisualizer:
    """
    Renderizador da interface visual sobreposta ao frame de vídeo.
    """

    CORES_LUZ = {
        "vermelho_aceso": (0, 0, 255),
        "vermelho_apagado": (0, 0, 50),
        "amarelo_aceso": (0, 220, 255),
        "amarelo_apagado": (0, 60, 60),
        "verde_aceso": (0, 255, 0),
        "verde_apagado": (0, 50, 0),
        "branco_brilho": (240, 240, 240),
        "fundo_caixa": (20, 20, 20),
        "borda_caixa": (100, 100, 100),
    }

    def __init__(self):
        pass

    def desenhar(
        self,
        frame: Any,
        resumo_controlador: Dict[str, Any],
        roi_manager: ROIManager,
        deteccoes: List[Dict[str, Any]],
        fps_video: float = 0.0,
        fps_modelo: float = 0.0,
        status_serial: str = "Simulado",
    ) -> Any:
        """
        Desenha todos os elementos visuais sobre o frame:
        - Bounding boxes das detecções YOLO
        - Polígonos das ROIs com cores dinâmicas
        - Painel de Semáforos e Cronômetro
        - Barra de Telemetria Superior
        """
        if not CV2_DISPONIVEL or frame is None:
            return frame

        canvas = frame.copy()
        altura, largura = canvas.shape[:2]

        # 1. Desenha as ROIs translúcidas e bordas
        self._desenhar_rois(canvas, roi_manager, resumo_controlador, largura, altura)

        # 2. Desenha caixas de detecção dos veículos e pedestres
        self._desenhar_deteccoes(canvas, deteccoes)

        # 3. Desenha os semáforos virtuais (Via A, Via B, Pedestre) e cronômetro
        self._desenhar_painel_semaforos(canvas, resumo_controlador, largura, altura)

        # 4. Desenha barra de telemetria superior (status, motivo, FPS)
        self._desenhar_telemetria_superior(
            canvas, resumo_controlador, fps_video, fps_modelo, status_serial, largura
        )

        return canvas

    def _desenhar_rois(
        self,
        canvas: Any,
        roi_manager: ROIManager,
        resumo: Dict[str, Any],
        largura: int,
        altura: int,
    ) -> None:
        """Desenha preenchimentos semitransparentes e contornos nas ROIs."""
        overlay = canvas.copy()

        sinal_a = resumo.get("sinal_via_a", "R")
        sinal_b = resumo.get("sinal_via_b", "R")
        sinal_ped = resumo.get("sinal_pedestre", "R")

        def cor_por_sinal(sinal):
            if sinal == "G":
                return (0, 200, 0)
            elif sinal == "Y":
                return (0, 200, 230)
            elif sinal == "F":
                # Alerta piscante
                pisca = (time.time() % 0.6) < 0.3
                return (0, 0, 255) if pisca else (0, 140, 255)
            else:
                return (0, 0, 200)

        cores_roi = {
            "via_a": cor_por_sinal(sinal_a),
            "via_b": cor_por_sinal(sinal_b),
            "pedestre": (220, 120, 0) if sinal_ped != "G" else (0, 240, 100),
        }

        for chave, roi in roi_manager.rois.items():
            pts = np.array(roi.to_pixel_coords(largura, altura), np.int32)
            pts = pts.reshape((-1, 1, 2))
            cor = cores_roi.get(chave, (180, 180, 180))

            # Preenchimento suave
            cv2.fillPoly(overlay, [pts], cor)
            # Borda nítida
            cv2.polylines(canvas, [pts], isClosed=True, color=cor, thickness=2)

            # Rótulo da zona
            if len(roi.pontos) > 0:
                p_inicio = pts[0][0]
                texto_label = f"{roi.nome}"
                cv2.putText(
                    canvas,
                    texto_label,
                    (p_inicio[0] + 5, p_inicio[1] + 18),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )

        # Mescla com transparência suave (alpha 0.22)
        cv2.addWeighted(overlay, 0.22, canvas, 0.78, 0, canvas)

    def _desenhar_deteccoes(self, canvas: Any, deteccoes: List[Dict[str, Any]]) -> None:
        """Desenha as caixas dos objetos e o ponto de contato do solo."""
        for det in deteccoes:
            bbox = det.get("bbox")
            if not bbox:
                continue
            x1, y1, x2, y2 = map(int, bbox)
            nome_classe = det.get("cls_name", "obj")
            conf = det.get("conf", 0.0)

            eh_pedestre = "boneco" in nome_classe.lower() or "pedestre" in nome_classe.lower()
            cor_box = (255, 0, 200) if eh_pedestre else (255, 180, 0)

            # Caixa
            cv2.rectangle(canvas, (x1, y1), (x2, y2), cor_box, 2)

            # Ponto de apoio do chão
            cx = (x1 + x2) // 2
            cy = y2
            cv2.circle(canvas, (cx, cy), 4, (0, 0, 255), -1)

            # Tag com fundo
            label = f"{nome_classe} {conf:.2f}"
            t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
            cv2.rectangle(canvas, (x1, y1 - 18), (x1 + t_size[0] + 4, y1), cor_box, -1)
            cv2.putText(
                canvas,
                label,
                (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

    def _desenhar_painel_semaforos(
        self,
        canvas: Any,
        resumo: Dict[str, Any],
        largura: int,
        altura: int,
    ) -> None:
        """Desenha o módulo com os semáforos das vias e do pedestre no canto lateral direito."""
        sinal_a = resumo.get("sinal_via_a", "R")
        sinal_b = resumo.get("sinal_via_b", "R")
        sinal_ped = resumo.get("sinal_pedestre", "R")
        tempo_restante = resumo.get("tempo_restante", 0.0)

        # Posição do painel no canto superior direito
        painel_w = 210
        painel_h = 160
        painel_x = largura - painel_w - 15
        painel_y = 65

        # Fundo do painel
        overlay = canvas.copy()
        cv2.rectangle(
            overlay,
            (painel_x, painel_y),
            (painel_x + painel_w, painel_y + painel_h),
            (15, 15, 15),
            -1,
        )
        cv2.addWeighted(overlay, 0.75, canvas, 0.25, 0, canvas)
        cv2.rectangle(
            canvas,
            (painel_x, painel_y),
            (painel_x + painel_w, painel_y + painel_h),
            (80, 80, 80),
            1,
        )

        # 1. Semáforo Via A (coluna 1)
        self._desenhar_cabina_semaforo(
            canvas,
            x=painel_x + 15,
            y=painel_y + 10,
            titulo="VIA A",
            sinal=sinal_a,
        )

        # 2. Semáforo Via B (coluna 2)
        self._desenhar_cabina_semaforo(
            canvas,
            x=painel_x + 65,
            y=painel_y + 10,
            titulo="VIA B",
            sinal=sinal_b,
        )

        # 3. Semáforo Pedestre (coluna 3)
        self._desenhar_cabina_pedestre(
            canvas,
            x=painel_x + 115,
            y=painel_y + 10,
            titulo="PED",
            sinal=sinal_ped,
        )

        # 4. Cronômetro digital no rodapé do painel
        timer_box_x = painel_x + 10
        timer_box_y = painel_y + 115
        timer_box_w = painel_w - 20
        timer_box_h = 35

        cv2.rectangle(
            canvas,
            (timer_box_x, timer_box_y),
            (timer_box_x + timer_box_w, timer_box_y + timer_box_h),
            (30, 30, 30),
            -1,
        )

        # Cor do timer de acordo com a fase
        if "AMARELO" in resumo.get("estado", ""):
            cor_timer = (0, 220, 255)
        elif "PEDESTRE" in resumo.get("estado", ""):
            cor_timer = (0, 240, 100)
        else:
            cor_timer = (0, 255, 0)

        timer_txt = f"{tempo_restante:.0f}s"
        cv2.putText(
            canvas,
            "TEMPO:",
            (timer_box_x + 8, timer_box_y + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (180, 180, 180),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            timer_txt,
            (timer_box_x + 85, timer_box_y + 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            cor_timer,
            2,
            cv2.LINE_AA,
        )

    def _desenhar_cabina_semaforo(
        self,
        canvas: Any,
        x: int,
        y: int,
        titulo: str,
        sinal: str,
    ) -> None:
        """Desenha um semáforo veicular vertical com 3 luzes."""
        w, h = 38, 95
        # Caixa
        cv2.rectangle(canvas, (x, y + 14), (x + w, y + 14 + h), (25, 25, 25), -1)
        cv2.rectangle(canvas, (x, y + 14), (x + w, y + 14 + h), (100, 100, 100), 1)

        # Título
        cv2.putText(
            canvas,
            titulo,
            (x + 2, y + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (200, 200, 200),
            1,
            cv2.LINE_AA,
        )

        raio = 10
        centro_x = x + w // 2
        cy_vermelho = y + 32
        cy_amarelo = y + 60
        cy_verde = y + 88

        # Lâmpada Vermelha
        aceso = sinal == "R"
        cor = self.CORES_LUZ["vermelho_aceso"] if aceso else self.CORES_LUZ["vermelho_apagado"]
        cv2.circle(canvas, (centro_x, cy_vermelho), raio, cor, -1)
        if aceso:
            cv2.circle(canvas, (centro_x - 3, cy_vermelho - 3), 3, self.CORES_LUZ["branco_brilho"], -1)

        # Lâmpada Amarela
        aceso = sinal == "Y"
        cor = self.CORES_LUZ["amarelo_aceso"] if aceso else self.CORES_LUZ["amarelo_apagado"]
        cv2.circle(canvas, (centro_x, cy_amarelo), raio, cor, -1)
        if aceso:
            cv2.circle(canvas, (centro_x - 3, cy_amarelo - 3), 3, self.CORES_LUZ["branco_brilho"], -1)

        # Lâmpada Verde
        aceso = sinal == "G"
        cor = self.CORES_LUZ["verde_aceso"] if aceso else self.CORES_LUZ["verde_apagado"]
        cv2.circle(canvas, (centro_x, cy_verde), raio, cor, -1)
        if aceso:
            cv2.circle(canvas, (centro_x - 3, cy_verde - 3), 3, self.CORES_LUZ["branco_brilho"], -1)

    def _desenhar_cabina_pedestre(
        self,
        canvas: Any,
        x: int,
        y: int,
        titulo: str,
        sinal: str,
    ) -> None:
        """Desenha um semáforo de pedestre com 2 luzes (Vermelho / Verde)."""
        w, h = 38, 95
        cv2.rectangle(canvas, (x, y + 14), (x + w, y + 14 + h), (25, 25, 25), -1)
        cv2.rectangle(canvas, (x, y + 14), (x + w, y + 14 + h), (100, 100, 100), 1)

        cv2.putText(
            canvas,
            titulo,
            (x + 5, y + 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            (200, 200, 200),
            1,
            cv2.LINE_AA,
        )

        raio = 12
        centro_x = x + w // 2
        cy_vermelho = y + 42
        cy_verde = y + 80

        # Lâmpada Vermelha (Pare)
        if sinal == "R":
            cor = self.CORES_LUZ["vermelho_aceso"]
            cv2.circle(canvas, (centro_x, cy_vermelho), raio, cor, -1)
            cv2.circle(canvas, (centro_x - 3, cy_vermelho - 3), 3, self.CORES_LUZ["branco_brilho"], -1)
        elif sinal == "F":
            # Piscando no alerta
            pisca = (time.time() % 0.6) < 0.3
            cor = self.CORES_LUZ["vermelho_aceso"] if pisca else self.CORES_LUZ["vermelho_apagado"]
            cv2.circle(canvas, (centro_x, cy_vermelho), raio, cor, -1)
        else:
            cv2.circle(canvas, (centro_x, cy_vermelho), raio, self.CORES_LUZ["vermelho_apagado"], -1)

        # Lâmpada Verde (Caminhe)
        if sinal == "G":
            cor = self.CORES_LUZ["verde_aceso"]
            cv2.circle(canvas, (centro_x, cy_verde), raio, cor, -1)
            cv2.circle(canvas, (centro_x - 3, cy_verde - 3), 3, self.CORES_LUZ["branco_brilho"], -1)
        else:
            cv2.circle(canvas, (centro_x, cy_verde), raio, self.CORES_LUZ["verde_apagado"], -1)

    def _desenhar_telemetria_superior(
        self,
        canvas: Any,
        resumo: Dict[str, Any],
        fps_video: float,
        fps_modelo: float,
        status_serial: str,
        largura: int,
    ) -> None:
        """Barra de telemetria superior preta com status operacional e contadores."""
        h_barra = 55
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (largura, h_barra), (10, 10, 10), -1)
        cv2.addWeighted(overlay, 0.85, canvas, 0.15, 0, canvas)
        cv2.line(canvas, (0, h_barra), (largura, h_barra), (70, 70, 70), 1)

        # Linha 1: Estado atual e Motivo da decisão do algoritmo
        estado = resumo.get("estado", "INDEFINIDO")
        motivo = resumo.get("motivo_status", "")

        txt_linha1 = f"FSM: {estado} | {motivo}"
        cv2.putText(
            canvas,
            txt_linha1,
            (15, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (0, 240, 255),
            1,
            cv2.LINE_AA,
        )

        # Linha 2: FPS da câmera, FPS do YOLO, Status Serial e Teclas de Atalho
        ped_chamado = "SIM" if resumo.get("pedido_pedestre_pendente") else "NAO"
        txt_linha2 = (
            f"FPS Video: {fps_video:4.1f} | FPS IA: {fps_modelo:4.1f} | "
            f"Serial: {status_serial} | Pedestre Chamado: {ped_chamado} | "
            f"Teclas: [p] Pedestre | [c] Calibrar | [q] Sair"
        )
        cv2.putText(
            canvas,
            txt_linha2,
            (15, 44),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (200, 200, 200),
            1,
            cv2.LINE_AA,
        )


class ROICalibrator:
    """
    Calibrador Interativo de ROIs via cliques de mouse.
    Permite clicar 4 pontos para cada uma das zonas e salva diretamente em JSON.
    """

    NOMES_ZONAS = [
        ("via_a", "Via A (Norte-Sul) - Fila de Veiculos"),
        ("via_b", "Via B (Leste-Oeste) - Fila de Veiculos"),
        ("pedestre", "Faixa de Pedestre - Area de Travessia"),
    ]

    def __init__(self, roi_manager: ROIManager, nome_janela: str = "Calibrador de ROIs - STC"):
        self.roi_manager = roi_manager
        self.nome_janela = nome_janela
        self.indice_zona_atual = 0
        self.pontos_atuais: List[Tuple[int, int]] = []
        self.novas_rois: Dict[str, List[Tuple[float, float]]] = {}
        self.largura = 640
        self.altura = 480

    def _mouse_callback(self, event: int, x: int, y: int, flags: int, param: Any) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(self.pontos_atuais) < 4:
                self.pontos_atuais.append((x, y))

    def executar(self, capturador: Any) -> bool:
        """
        Executa o loop interativo de calibração.
        Retorna True se salvou, False se cancelou.
        """
        if not CV2_DISPONIVEL:
            print("[STC-CALIBRADOR] OpenCV não disponível.")
            return False

        cv2.namedWindow(self.nome_janela)
        cv2.setMouseCallback(self.nome_janela, self._mouse_callback)

        self.indice_zona_atual = 0
        self.pontos_atuais = []
        self.novas_rois = {}

        while True:
            ret, frame = capturador.read()
            if not ret or frame is None:
                continue

            self.altura, self.largura = frame.shape[:2]
            canvas = frame.copy()

            chave_atual, descricao_atual = self.NOMES_ZONAS[self.indice_zona_atual]

            # Desenha zonas já concluídas
            for chave, pontos_norm in self.novas_rois.items():
                pts_px = [
                    (int(px * self.largura), int(py * self.altura))
                    for px, py in pontos_norm
                ]
                pts_arr = np.array(pts_px, np.int32).reshape((-1, 1, 2))
                cv2.polylines(canvas, [pts_arr], True, (0, 255, 0), 2)
                cv2.putText(
                    canvas,
                    f"OK: {chave}",
                    (pts_px[0][0], pts_px[0][1] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )

            # Desenha pontos da zona atual
            for i, p in enumerate(self.pontos_atuais):
                cv2.circle(canvas, p, 5, (0, 0, 255), -1)
                cv2.putText(
                    canvas,
                    str(i + 1),
                    (p[0] + 6, p[1] - 6),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    2,
                )

            if len(self.pontos_atuais) > 1:
                pts_atuais_arr = np.array(self.pontos_atuais, np.int32).reshape((-1, 1, 2))
                cv2.polylines(
                    canvas,
                    [pts_atuais_arr],
                    isClosed=(len(self.pontos_atuais) == 4),
                    color=(0, 220, 255),
                    thickness=2,
                )

            # Barra inferior de instrução
            cv2.rectangle(canvas, (0, self.altura - 55), (self.largura, self.altura), (0, 0, 0), -1)
            cv2.putText(
                canvas,
                f"Calibrando [{self.indice_zona_atual + 1}/3]: {descricao_atual}",
                (15, self.altura - 32),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                (0, 255, 255),
                1,
            )
            cv2.putText(
                canvas,
                f"Pontos marcados: {len(self.pontos_atuais)}/4 | [r] Limpar zona | [ENTER/ESPACO] Avancar | [ESC] Cancelar",
                (15, self.altura - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.40,
                (200, 200, 200),
                1,
            )

            cv2.imshow(self.nome_janela, canvas)
            tecla = cv2.waitKey(20) & 0xFF

            if tecla == 27:  # ESC
                print("[STC-CALIBRADOR] Calibração cancelada pelo usuário.")
                cv2.destroyWindow(self.nome_janela)
                return False

            elif tecla == ord("r"):  # Limpar pontos da zona atual
                self.pontos_atuais = []

            elif tecla in (13, 32):  # ENTER ou ESPAÇO para avançar
                if len(self.pontos_atuais) == 4:
                    # Converte pontos para normalizado (0 a 1)
                    norm_pts = [
                        (round(px / self.largura, 4), round(py / self.altura, 4))
                        for px, py in self.pontos_atuais
                    ]
                    self.novas_rois[chave_atual] = norm_pts
                    self.pontos_atuais = []
                    self.indice_zona_atual += 1

                    if self.indice_zona_atual >= len(self.NOMES_ZONAS):
                        # Todas as 3 zonas concluídas!
                        for k, pts in self.novas_rois.items():
                            if k in self.roi_manager.rois:
                                self.roi_manager.rois[k].pontos = pts
                        self.roi_manager.salvar()
                        print(f"[STC-CALIBRADOR] Calibração concluída e salva com sucesso em {self.roi_manager.arquivo_json}!")
                        cv2.destroyWindow(self.nome_janela)
                        return True
                else:
                    print(f"[STC-CALIBRADOR] Marque exatamente 4 pontos com o mouse antes de avançar ({len(self.pontos_atuais)}/4).")
