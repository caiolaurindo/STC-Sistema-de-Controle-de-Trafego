# STC - Sistema de Controle de Tráfego Adaptativo

O **STC (Sistema de Controle de Tráfego)** é um sistema inteligente de controle semafórico adaptativo que utiliza **Visão Computacional (YOLOv8)** para monitorar cruzamentos viários e pedestres em tempo real, ajustando dinamicamente os tempos de sinal verde e acionando prioridade para travessia de pedestres.

> 📖 **Guia Completo e Detalhado:** Veja o [TUTORIAL_EXECUCAO_E_ARDUINO.md](TUTORIAL_EXECUCAO_E_ARDUINO.md) para o passo a passo completo com fotos da ligação, circuito na protoboard, gravação com a Arduino IDE e calibração por mouse.

O projeto inclui simulação gráfica completa na tela (HUD com semáforos virtuais, cronômetro e zonas de interesse) e integração física com microcontroladores (**Arduino / ESP32**) via porta Serial (UART) para controle de LEDs na maquete.

---

## 🌟 Principais Recursos

- **Visão Computacional em Tempo Real (YOLOv8s):**
  - Modelo treinado especificamente para a maquete com as classes: `carro_de_brinquedo` e `boneco_de_brinquedo`.
  - Processamento assíncrono em thread separada (mantém alta taxa de FPS no vídeo sem travamentos).
- **Zonas de Interesse Configuráveis (ROIs):**
  - Mapeamento espacial da **Via A (Norte-Sul)**, **Via B (Leste-Oeste)** e **Faixa de Pedestre**.
  - Detecção baseada no ponto de contato com o solo (centro inferior da bounding box).
  - Coordenadas normalizadas salvas em `rois.json`.
  - **Calibrador Interativo via Mouse:** marque os 4 cantos de cada via diretamente na imagem (`--calibrar`).
- **Controle Semafórico Adaptativo (FSM):**
  - **Tempo Mínimo de Verde ($T_{min}$):** Garante a segurança viária sem alternâncias bruscas.
  - **Extensão Dinâmica:** Estende o sinal verde de acordo com a fila de carros na via aberta até o limite de $T_{max}$.
  - **Troca Antecipada:** Se a via com sinal verde esvaziar e houver demanda concorrente, o sinal transiciona antecipadamente para amarelo.
  - **Prioridade de Pedestre:** Ao confirmar a presença do pedestre na faixa (com filtro temporal anti-ruído), agenda a fase de pedestre imediatamente após o verde veicular seguro.
  - **Intervalo de Segurança (Clearance):** Todas as vias ficam em vermelho por 1,5s na transição entre fases.
  - **Alerta de Travessia:** Pedestre recebe sinal verde com contagem regressiva e fase final de alerta piscante.
- **HUD / Interface Visual no OpenCV:**
  - Semáforos virtuais luminosos na tela para Via A, Via B e Pedestre.
  - Cronômetro digital regressivo em tempo real.
  - Áreas das vias destacadas com preenchimento translúcido e cores de acordo com o sinal.
  - Barra superior de telemetria com motivo da decisão tomada pelo algoritmo.
- **Integração Física com Arduino / ESP32:**
  - Protocolo serial leve e legível: `SET:A=<G|Y|R>,B=<G|Y|R>,P=<G|R|F>,T=<segundos>\n`.
  - Watchdog de segurança no Arduino (entra em amarelo piscante se perder comunicação com o computador).
  - **Modo Simulado Automático:** se não houver placa física conectada, o sistema opera normalmente sem erros.

---

## 📁 Estrutura do Projeto

```
STC-Sistema-de-Controle-de-Trafego/
├── stc/
│   ├── __init__.py           # Exportação dos componentes do pacote
│   ├── controller.py         # Máquina de estados finita (FSM) do semáforo adaptativo
│   ├── roi.py                # Gerenciador de ROIs, cálculo geométrico e calibrador
│   ├── detector.py           # Thread assíncrona de inferência YOLOv8
│   ├── visualizer.py         # HUD com semáforos, timer, telemetria e calibrador
│   └── serial_comm.py        # Driver serial assíncrono com fallback simulado
├── arduino/
│   └── stc_semaforo.ino      # Firmware C++ completo para Arduino / ESP32
├── my_model/
│   ├── my_model.pt           # Pesos do modelo YOLOv8s treinado
│   └── train/                # Métricas, curvas PR, matriz de confusão do treino
├── tests/
│   ├── test_controller.py    # Testes unitários da máquina de estados
│   ├── test_roi.py           # Testes unitários geométricos e de ROIs
│   ├── test_serial.py        # Testes do protocolo serial
│   └── test_cli.py           # Testes de integração da CLI
├── controlador_semaforo.py   # Script principal executável
├── rois.json                 # Coordenadas calibradas das zonas
├── requirements.txt          # Dependências do projeto
├── README.md                 # Este documento
└── README_TREINAMENTO_YOLOV8.md # Guia original de anotação e treino no Colab
```

---

## 🚀 Instalação e Pré-requisitos

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/moises-araujo/STC-Sistema-de-Controle-de-Trafego.git
   cd STC-Sistema-de-Controle-de-Trafego
   ```

2. **Crie e ative um ambiente virtual:**
   ```bash
   # Com Conda:
   conda create -n YOLO_env python=3.12 -y
   conda activate YOLO_env

   # Ou com venv:
   python3 -m venv .venv
   source .venv/bin/activate  # No Windows: .venv\Scripts\activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🎮 Como Executar

### 1. Rodar com a Webcam (Tempo Real)
```bash
python controlador_semaforo.py --camera 0
```

### 2. Rodar com Arquivo de Vídeo Gravado
Ideal para testar o sistema sem precisar montar a maquete:
```bash
python controlador_semaforo.py --video maquete.mp4
```

### 3. Calibrar as Regiões de Interesse (ROIs)
Abre o assistente gráfico para marcar os 4 cantos da Via A, Via B e Faixa de Pedestre usando o botão esquerdo do mouse:
```bash
python controlador_semaforo.py --calibrar
```
*Dica:* Durante a execução normal do programa, você também pode pressionar a tecla `c` a qualquer momento para recalibrar.

### 4. Conectar com o Arduino / ESP32 Físico
```bash
# No Linux:
python controlador_semaforo.py --camera 0 --serial /dev/ttyUSB0 --baud 9600

# No Windows:
python controlador_semaforo.py --camera 0 --serial COM3 --baud 9600
```
*Se a flag `--serial` for omitida ou a porta não estiver disponível, o sistema opera automaticamente em **Modo Simulado**.*

### 5. Ajustar Tempos e Parâmetros
```bash
python controlador_semaforo.py --t-min-verde 6.0 --t-base-verde 12.0 --t-max-verde 30.0 --t-pedestre 10.0
```

---

## ⌨️ Teclas de Atalho (Durante a Execução)

| Tecla | Ação |
| :---: | :--- |
| `p` | **Solicitar Pedestre:** Aciona imediatamente o chamado de pedestre para teste. |
| `c` | **Calibrar ROIs:** Abre a janela de calibração interativa de zonas via mouse. |
| `s` | **Salvar Captura:** Salva um print do frame atual com todo o HUD na pasta `capturas/`. |
| `ESPAÇO` | **Pausar/Retomar:** Pausa ou despausa a execução do vídeo. |
| `q` ou `ESC` | **Sair:** Encerra todos os processos e conexões de forma segura. |

---

## 🔌 Hardware e Conexão com Arduino

Grave o arquivo `arduino/stc_semaforo.ino` no seu Arduino Uno/Nano via Arduino IDE.

### Pinagem Padrão

| Semáforo | Luz / Função | Pino Arduino |
| :--- | :--- | :---: |
| **Via A (Norte-Sul)** | LED Vermelho | **D2** |
| | LED Amarelo | **D3** |
| | LED Verde | **D4** |
| **Via B (Leste-Oeste)** | LED Vermelho | **D5** |
| | LED Amarelo | **D6** |
| | LED Verde | **D7** |
| **Pedestre** | LED Vermelho (Pare) | **D8** |
| | LED Verde (Siga) | **D9** |
| **Sonoro (Opcional)**| Buzzer Ativo (Alerta) | **D10** |

*Observação: Conecte resistores de 220Ω a 330Ω em série com cada LED.*

---

## 🧪 Testes Automatizados

Para rodar a suite de testes unitários:
```bash
pytest
```
São validados:
- Ciclos e transições da Máquina de Estados Finita (FSM).
- Respeito irrestrito a tempos mínimos e máximos de segurança.
- Lógica de antecipação e de extensão dinâmica de verde.
- Prioridade e interrupção segura para travessia de pedestre.
- Testes geométricos de ponto em polígono (Ray-Casting) e persistência de ROIs.
- Formatação e transmissão do protocolo serial UART.
