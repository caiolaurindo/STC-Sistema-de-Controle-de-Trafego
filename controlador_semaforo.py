#!/usr/bin/env python3
"""
STC - Sistema de Controle de Tráfego Adaptativo
Script principal que integra:
- Detecção em tempo real com YOLOv8
- Análise de filas e pedestres por Regiões de Interesse (ROIs)
- Lógica de decisão semafórica adaptativa (FSM)
- Interface visual HUD com semáforos virtuais
- Comunicação Serial UART (Arduino / ESP32) com fallback simulado

Uso:
    # Usar com webcam:
    python controlador_semaforo.py --camera 0

    # Usar com arquivo de vídeo:
    python controlador_semaforo.py --video maquete.mp4

    # Calibrar as regiões de interesse (cliques com mouse):
    python controlador_semaforo.py --calibrar

    # Conectar com Arduino/ESP32 via porta Serial:
    python controlador_semaforo.py --serial /dev/ttyUSB0 --baud 9600
"""

import argparse
import sys
import time
from pathlib import Path

try:
    import cv2
    CV2_DISPONIVEL = True
except ImportError:
    cv2 = None
    CV2_DISPONIVEL = False

from stc.controller import TrafficController
from stc.roi import ROIManager
from stc.serial_comm import TrafficSerialCommunicator
from stc.detector import YOLODetector
from stc.visualizer import TrafficVisualizer, ROICalibrator

PASTA_PROJETO = Path(__file__).resolve().parent
MODELO_PADRAO = PASTA_PROJETO / "my_model" / "my_model.pt"
ROIS_PADRAO = PASTA_PROJETO / "rois.json"
PASTA_CAPTURAS = PASTA_PROJETO / "capturas"


def parse_args():
    parser = argparse.ArgumentParser(
        description="STC - Sistema de Controle Semafórico Adaptativo com YOLO e Arduino."
    )
    # Entrada de vídeo
    parser.add_argument("--camera", type=int, default=0,
                        help="Índice da webcam (padrão: 0)")
    parser.add_argument("--video", type=Path, default=None,
                        help="Caminho para arquivo de vídeo gravado (.mp4, .avi)")
    parser.add_argument("--largura", type=int, default=640,
                        help="Largura da captura da câmera (padrão: 640)")
    parser.add_argument("--altura", type=int, default=480,
                        help="Altura da captura da câmera (padrão: 480)")

    # Modelo e Visão
    parser.add_argument("--modelo", type=Path, default=MODELO_PADRAO,
                        help="Caminho para o modelo YOLO (.pt) (padrão: my_model/my_model.pt)")
    parser.add_argument("--conf", type=float, default=0.30,
                        help="Confiança mínima para detecção (0 a 1, padrão: 0.30)")
    parser.add_argument("--imgsz", type=int, default=416,
                        help="Resolução da imagem na inferência da IA (padrão: 416)")
    parser.add_argument("--rois", type=Path, default=ROIS_PADRAO,
                        help="Caminho do arquivo JSON de ROIs (padrão: rois.json)")
    parser.add_argument("--calibrar", action="store_true",
                        help="Abre o calibrador interativo de ROIs no início")

    # Comunicação Serial
    parser.add_argument("--serial", type=str, default="none",
                        help="Porta serial para Arduino/ESP32 (ex: /dev/ttyUSB0 ou COM3). Padrão: none")
    parser.add_argument("--baud", type=int, default=9600,
                        help="Baudrate da comunicação serial (padrão: 9600)")

    # Parâmetros do Semáforo Adaptativo
    parser.add_argument("--t-min-verde", type=float, default=5.0,
                        help="Tempo mínimo de verde veicular em segundos (padrão: 5.0)")
    parser.add_argument("--t-max-verde", type=float, default=25.0,
                        help="Tempo máximo de verde veicular em segundos (padrão: 25.0)")
    parser.add_argument("--t-base-verde", type=float, default=10.0,
                        help="Tempo base de verde veicular em segundos (padrão: 10.0)")
    parser.add_argument("--t-pedestre", type=float, default=8.0,
                        help="Tempo de travessia verde do pedestre em segundos (padrão: 8.0)")

    return parser.parse_args()


def abrir_captura(args):
    """Inicializa a captura da webcam ou arquivo de vídeo."""
    if not CV2_DISPONIVEL:
        print("[ERRO] OpenCV (cv2) não está instalado no ambiente Python atual.")
        print("Ative o ambiente virtual correto (ex: conda activate YOLO_env) antes de rodar.")
        sys.exit(1)

    if args.video is not None:
        caminho_video = Path(args.video).resolve()
        if not caminho_video.exists():
            print(f"[ERRO] Arquivo de vídeo não encontrado: {caminho_video}")
            sys.exit(1)
        print(f"[STC] Abrindo arquivo de vídeo: {caminho_video}")
        cap = cv2.VideoCapture(str(caminho_video))
    else:
        print(f"[STC] Abrindo webcam índice {args.camera}...")
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        cap = cv2.VideoCapture(args.camera, backend)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.largura)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.altura)

    if not cap.isOpened():
        fonte = f"vídeo '{args.video}'" if args.video else f"câmera {args.camera}"
        print(f"[ERRO] Falha ao abrir a fonte de {fonte}.")
        sys.exit(1)

    return cap


def main():
    args = parse_args()

    print("=" * 65)
    print("STC - SISTEMA DE CONTROLE DE TRÁFEGO ADAPTATIVO")
    print("=" * 65)
    print(f"Modelo YOLO:       {args.modelo}")
    print(f"Arquivo ROIs:      {args.rois}")
    print(f"Porta Serial:      {args.serial} ({args.baud} bps)")
    print(f"Tempos Semáforo:   Min Verde={args.t_min_verde}s, Base={args.t_base_verde}s, Max={args.t_max_verde}s, Pedestre={args.t_pedestre}s")
    print("-" * 65)

    # 1. Inicializa fonte de vídeo
    cap = abrir_captura(args)

    # 2. Inicializa Gerenciador de ROIs
    roi_manager = ROIManager(arquivo_json=str(args.rois))

    # Calibração inicial se solicitada via flag
    if args.calibrar:
        print("[STC] Iniciando Calibrador Interativo de ROIs...")
        calibrador = ROICalibrator(roi_manager)
        calibrador.executar(cap)

    # 3. Inicializa Controlador Semafórico FSM
    controlador = TrafficController(
        t_min_verde=args.t_min_verde,
        t_max_verde=args.t_max_verde,
        t_base_verde=args.t_base_verde,
        t_pedestre_verde=args.t_pedestre,
    )

    # 4. Inicializa Comunicação Serial
    serial_comm = TrafficSerialCommunicator(
        porta=args.serial,
        baudrate=args.baud,
    )

    # 5. Inicializa Detector YOLO Assíncrono
    detector = YOLODetector(
        caminho_modelo=args.modelo,
        conf=args.conf,
        imgsz=args.imgsz,
    )
    detector.iniciar()

    # 6. Visualizador HUD
    visualizador = TrafficVisualizer()

    # Variáveis de controle de taxa e FPS
    ultimo_tempo_loop = time.time()
    ultimo_calculo_fps_video = time.time()
    contador_frames_video = 0
    fps_video = 0.0
    pausado = False

    NOME_JANELA = "STC - Sistema de Controle de Trafego Adaptativo"
    cv2.namedWindow(NOME_JANELA, cv2.WINDOW_NORMAL)

    print("\n[STC] Sistema operacional. Controles:")
    print("  [p]     -> Solicitar pedestre manualmente (prioridade)")
    print("  [c]     -> Abrir calibração interativa de ROIs")
    print("  [s]     -> Salvar captura da tela em capturas/")
    print("  [ESPACO]-> Pausar / Despausar vídeo")
    print("  [q/ESC] -> Encerrar sistema\n")

    try:
        while True:
            if not pausado:
                ret, frame = cap.read()
                if not ret:
                    if args.video is not None:
                        # Reinicia o vídeo em loop contínuo
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        print("[STC] Falha na leitura do frame da câmera.")
                        break

                # Envia o frame para a thread de inferência
                detector.enviar_frame(frame)
            else:
                time.sleep(0.03)

            agora = time.time()
            dt = agora - ultimo_tempo_loop
            ultimo_tempo_loop = agora

            # Limita dt para evitar saltos anômalos em caso de lag no sistema operacional
            dt = min(0.2, max(0.0, dt))

            # Obtém detecções mais recentes da IA
            deteccoes = detector.obter_deteccoes()
            h_frame, w_frame = frame.shape[:2]

            # Processa quais carros e pedestres estão dentro de cada ROI
            info_rois = roi_manager.processar_deteccoes(deteccoes, w_frame, h_frame)
            carros_a = info_rois["carros_via_a"]
            carros_b = info_rois["carros_via_b"]
            pedestre_detectado = info_rois["pedestre_detectado"]

            # Atualiza o controlador semafórico adaptativo
            if not pausado:
                controlador.update(
                    dt=dt,
                    carros_via_a=carros_a,
                    carros_via_b=carros_b,
                    pedestre_detectado=pedestre_detectado,
                )

            # Transmite para o Arduino / ESP32 via UART
            serial_comm.enviar_estado(
                via_a=controlador.sinal_via_a.value,
                via_b=controlador.sinal_via_b.value,
                pedestre=controlador.sinal_pedestre.value,
                tempo_restante=controlador.tempo_restante,
            )

            # Calcula FPS do vídeo
            contador_frames_video += 1
            if agora - ultimo_calculo_fps_video >= 1.0:
                fps_video = contador_frames_video / (agora - ultimo_calculo_fps_video)
                contador_frames_video = 0
                ultimo_calculo_fps_video = agora

            status_serial = "SIMULADO" if serial_comm.modo_simulado else f"CONECTADO ({serial_comm.porta})"

            # Renderiza interface HUD sobre o frame
            resumo = controlador.obter_resumo()
            frame_renderizado = visualizador.desenhar(
                frame=frame,
                resumo_controlador=resumo,
                roi_manager=roi_manager,
                deteccoes=deteccoes,
                fps_video=fps_video,
                fps_modelo=detector.fps_modelo,
                status_serial=status_serial,
            )

            cv2.imshow(NOME_JANELA, frame_renderizado)

            # Tratamento de teclas de atalho
            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), 27):  # 'q' ou ESC
                print("[STC] Encerrando por solicitação do usuário.")
                break

            elif tecla == ord("p"):
                print("[STC] Solicitando travessia de pedestre manualmente...")
                controlador.solicitar_pedestre_manual()

            elif tecla == ord("c"):
                print("[STC] Abrindo calibração de ROIs...")
                calibrador = ROICalibrator(roi_manager)
                calibrador.executar(cap)

            elif tecla == ord("s"):
                PASTA_CAPTURAS.mkdir(exist_ok=True)
                nome_foto = PASTA_CAPTURAS / f"captura_stc_{time.strftime('%Y%m%d_%H%M%S')}.png"
                cv2.imwrite(str(nome_foto), frame_renderizado)
                print(f"[STC] Frame com telemetria salvo em: {nome_foto}")

            elif tecla == ord(" "):
                pausado = not pausado
                print(f"[STC] {'PAUSADO' if pausado else 'RETOMADO'}")

    except KeyboardInterrupt:
        print("\n[STC] Interrompido pelo teclado.")

    finally:
        print("[STC] Finalizando componentes...")
        detector.parar()
        serial_comm.fechar()
        cap.release()
        cv2.destroyAllWindows()
        print("[STC] Sistema finalizado com sucesso.")


if __name__ == "__main__":
    main()
