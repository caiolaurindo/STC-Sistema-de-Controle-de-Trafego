"""
Testa o modelo YOLO treinado usando a webcam em tempo real.

A inferência roda numa thread separada: o vídeo da câmera é exibido na
velocidade normal e as caixas são atualizadas sempre que o modelo termina
de processar um frame. Assim a imagem não trava mesmo com um modelo pesado.

Uso:
    python testar_camera.py
    python testar_camera.py --modelo my_model/my_model.onnx
    python testar_camera.py --camera 1 --conf 0.4 --imgsz 320

Teclas:
    q / ESC  -> sair
    s        -> salvar print do frame atual em capturas/
"""

import argparse
import sys
import threading
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

PASTA_PROJETO = Path(__file__).resolve().parent
MODELO_PADRAO = PASTA_PROJETO / "my_model" / "my_model.pt"


def parse_args():
    parser = argparse.ArgumentParser(description="Testa o modelo YOLO com a webcam.")
    parser.add_argument("--modelo", type=Path, default=MODELO_PADRAO,
                        help="Arquivo .pt ou .onnx (padrão: my_model/my_model.pt)")
    parser.add_argument("--camera", type=int, default=0,
                        help="Índice da câmera (0 = webcam padrão)")
    parser.add_argument("--conf", type=float, default=0.5,
                        help="Confiança mínima para mostrar uma detecção (0 a 1)")
    parser.add_argument("--imgsz", type=int, default=416,
                        help="Tamanho da imagem na inferência; menor = mais rápido "
                             "(o .onnx exportado aceita apenas 416)")
    parser.add_argument("--largura", type=int, default=640, help="Largura da captura")
    parser.add_argument("--altura", type=int, default=480, help="Altura da captura")
    return parser.parse_args()


def abrir_camera(indice, largura, altura):
    # CAP_DSHOW abre a câmera bem mais rápido no Windows
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    cap = cv2.VideoCapture(indice, backend)
    if not cap.isOpened():
        cap = cv2.VideoCapture(indice)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, largura)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, altura)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # evita acumular frames atrasados
    return cap


class Detector(threading.Thread):
    """Roda o modelo continuamente sobre o frame mais recente da câmera."""

    def __init__(self, model, conf, imgsz):
        super().__init__(daemon=True)
        self.model = model
        self.conf = conf
        self.imgsz = imgsz
        self._frame = None
        self._lock = threading.Lock()
        self._novo_frame = threading.Event()
        self._parar = threading.Event()
        self.deteccoes = []        # lista de (x1, y1, x2, y2, id_classe, confiança)
        self.fps_modelo = 0.0

    def enviar(self, frame):
        with self._lock:
            self._frame = frame
        self._novo_frame.set()

    def parar(self):
        self._parar.set()
        self._novo_frame.set()

    def run(self):
        while not self._parar.is_set():
            self._novo_frame.wait()
            self._novo_frame.clear()
            with self._lock:
                frame = self._frame
            if frame is None or self._parar.is_set():
                continue

            inicio = time.perf_counter()
            resultado = self.model(frame, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
            caixas = resultado.boxes
            self.deteccoes = [
                (*map(int, xyxy), int(c), float(p))
                for xyxy, c, p in zip(caixas.xyxy.tolist(), caixas.cls.tolist(), caixas.conf.tolist())
            ]
            fps = 1.0 / max(time.perf_counter() - inicio, 1e-6)
            self.fps_modelo = fps if self.fps_modelo == 0 else 0.8 * self.fps_modelo + 0.2 * fps


def cor_da_classe(id_classe):
    rng = np.random.default_rng(id_classe + 7)
    return tuple(int(v) for v in rng.integers(60, 255, 3))


def desenhar_deteccoes(frame, deteccoes, nomes):
    for x1, y1, x2, y2, c, p in deteccoes:
        cor = cor_da_classe(c)
        cv2.rectangle(frame, (x1, y1), (x2, y2), cor, 2)
        texto = f"{nomes[c]} {p:.2f}"
        (w, h), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x1, y1 - h - 8), (x1 + w + 6, y1), cor, -1)
        cv2.putText(frame, texto, (x1 + 3, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (0, 0, 0), 1, cv2.LINE_AA)


def desenhar_painel(frame, fps_video, fps_modelo, contagem):
    linhas = [f"Video: {fps_video:.0f} FPS", f"Modelo: {fps_modelo:.1f} FPS"]
    linhas += [f"{nome}: {qtd}" for nome, qtd in sorted(contagem.items())]

    altura_linha = 24
    cv2.rectangle(frame, (5, 5), (230, 15 + altura_linha * len(linhas)), (0, 0, 0), -1)
    for i, texto in enumerate(linhas):
        cv2.putText(frame, texto, (12, 28 + i * altura_linha), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 0), 2, cv2.LINE_AA)


def main():
    args = parse_args()

    if not args.modelo.exists():
        sys.exit(f"Modelo não encontrado: {args.modelo}")

    print(f"Carregando modelo: {args.modelo}")
    model = YOLO(str(args.modelo), task="detect")
    nomes = model.names

    # A primeira inferência é bem mais lenta (inicialização); faz antes de abrir a câmera
    print("Aquecendo o modelo...")
    model(np.zeros((args.altura, args.largura, 3), dtype=np.uint8),
          imgsz=args.imgsz, verbose=False)

    cap = abrir_camera(args.camera, args.largura, args.altura)
    if not cap.isOpened():
        sys.exit(f"Não foi possível abrir a câmera {args.camera}. "
                 "Tente outro índice com --camera 1")

    detector = Detector(model, args.conf, args.imgsz)
    detector.start()

    pasta_capturas = PASTA_PROJETO / "capturas"
    janela = "STC - Teste do modelo (q para sair, s para salvar)"
    fps_video = 0.0
    anterior = time.perf_counter()

    print("Câmera aberta. Pressione 'q' para sair e 's' para salvar um print.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Falha ao ler frame da câmera.")
                break

            detector.enviar(frame.copy())

            deteccoes = detector.deteccoes
            desenhar_deteccoes(frame, deteccoes, nomes)
            contagem = Counter(nomes[d[4]] for d in deteccoes)

            agora = time.perf_counter()
            fps_video = 0.9 * fps_video + 0.1 * (1.0 / max(agora - anterior, 1e-6))
            anterior = agora
            desenhar_painel(frame, fps_video, detector.fps_modelo, contagem)

            cv2.imshow(janela, frame)
            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), 27):
                break
            if tecla == ord("s"):
                pasta_capturas.mkdir(exist_ok=True)
                arquivo = pasta_capturas / f"captura_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                cv2.imwrite(str(arquivo), frame)
                print(f"Print salvo em {arquivo}")
            if cv2.getWindowProperty(janela, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        detector.parar()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
