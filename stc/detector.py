"""
Módulo de Detecção Visual YOLOv8 Assíncrono para o STC.
Executa a inferência em thread separada com transferência de frames em buffer único,
garantindo taxa de quadros fluida no fluxo de vídeo.
"""

import threading
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

try:
    from ultralytics import YOLO
    ULTRALYTICS_DISPONIVEL = True
except ImportError:
    YOLO = None
    ULTRALYTICS_DISPONIVEL = False


class YOLODetector:
    """
    Detector de objetos assíncrono baseado em YOLOv8.
    """

    def __init__(
        self,
        caminho_modelo: Path,
        conf: float = 0.30,
        imgsz: int = 416,
    ):
        self.caminho_modelo = Path(caminho_modelo)
        self.conf = float(conf)
        self.imgsz = int(imgsz)

        self.modelo: Optional[Any] = None
        self.nomes_classes: Dict[int, str] = {}

        # Threading e sincronização
        self._lock = threading.Lock()
        self._rodando = False
        self._thread: Optional[threading.Thread] = None
        self._frame_pendente: Optional[Any] = None
        self._novas_deteccoes: List[Dict[str, Any]] = []
        self._novo_resultado_disponivel = False

        # Métricas
        self.fps_modelo: float = 0.0
        self._contador_frames_ia = 0
        self._ultimo_calculo_fps = time.time()

        self._carregar_modelo()

    def _carregar_modelo(self) -> None:
        if not ULTRALYTICS_DISPONIVEL:
            print("[STC-DETECTOR] Pacote 'ultralytics' não encontrado. Operando em modo de teste/sem IA.")
            return

        if not self.caminho_modelo.exists():
            print(f"[STC-DETECTOR] Arquivo do modelo não encontrado: {self.caminho_modelo}")
            return

        try:
            print(f"[STC-DETECTOR] Carregando modelo YOLO: {self.caminho_modelo}...")
            self.modelo = YOLO(str(self.caminho_modelo))
            self.nomes_classes = getattr(self.modelo, "names", {})
            print(f"[STC-DETECTOR] Modelo carregado com sucesso. Classes: {self.nomes_classes}")
        except Exception as e:
            print(f"[STC-DETECTOR] Erro ao carregar modelo YOLO: {e}")
            self.modelo = None

    def iniciar(self) -> None:
        """Inicia a thread de inferência."""
        if self._rodando:
            return
        self._rodando = True
        self._thread = threading.Thread(target=self._loop_inferencia, daemon=True, name="YOLOInferenceThread")
        self._thread.start()

    def enviar_frame(self, frame: Any) -> None:
        """Envia o frame mais recente para inferência assíncrona (descarta anteriores se a IA estiver ocupada)."""
        if frame is None:
            return
        with self._lock:
            self._frame_pendente = frame.copy()

    def obter_deteccoes(self) -> List[Dict[str, Any]]:
        """Retorna as detecções mais recentes computadas pela IA."""
        with self._lock:
            return list(self._novas_deteccoes)

    def _loop_inferencia(self) -> None:
        """Loop contínuo da thread de processamento da rede neural."""
        while self._rodando:
            frame_atual = None
            with self._lock:
                if self._frame_pendente is not None:
                    frame_atual = self._frame_pendente
                    self._frame_pendente = None

            if frame_atual is None:
                time.sleep(0.005)
                continue

            inicio_inferencia = time.time()
            deteccoes_frame: List[Dict[str, Any]] = []

            if self.modelo is not None:
                try:
                    resultados = self.modelo.predict(
                        source=frame_atual,
                        imgsz=self.imgsz,
                        conf=self.conf,
                        verbose=False,
                    )

                    if resultados and len(resultados) > 0:
                        resultado = resultados[0]
                        boxes = resultado.boxes
                        if boxes is not None and len(boxes) > 0:
                            xyxy = boxes.xyxy.cpu().numpy()
                            confs = boxes.conf.cpu().numpy()
                            cls_ids = boxes.cls.cpu().numpy().astype(int)

                            for i in range(len(xyxy)):
                                x1, y1, x2, y2 = xyxy[i]
                                cid = cls_ids[i]
                                confianca = float(confs[i])
                                nome_classe = self.nomes_classes.get(cid, str(cid))

                                cx = (x1 + x2) / 2.0
                                cy = float(y2)

                                deteccoes_frame.append({
                                    "bbox": (float(x1), float(y1), float(x2), float(y2)),
                                    "cls_id": cid,
                                    "cls_name": nome_classe,
                                    "conf": confianca,
                                    "bottom_center": (cx, cy),
                                })
                except Exception as e:
                    # Não derruba a thread se houver erro transitório em um frame
                    pass

            with self._lock:
                self._novas_deteccoes = deteccoes_frame

            # Cálculo de FPS da IA
            self._contador_frames_ia += 1
            agora = time.time()
            delta = agora - self._ultimo_calculo_fps
            if delta >= 1.0:
                self.fps_modelo = self._contador_frames_ia / delta
                self._contador_frames_ia = 0
                self._ultimo_calculo_fps = agora

    def parar(self) -> None:
        """Para a thread de inferência."""
        self._rodando = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
