# Tutorial Passo a Passo: Execução e Conexão com Arduino (STC)

Este guia prático ensina, do zero ao funcionamento completo, como montar o circuito eletrônico, gravar o firmware no Arduino, calibrar as áreas da maquete pela câmera e executar o **Sistema de Controle de Tráfego Adaptativo (STC)**.

---

## 📑 Índice
1. [Visão Geral da Integração](#1-visão-geral-da-integração)
2. [Lista de Materiais Necessários](#2-lista-de-materiais-necessários)
3. [Esquema Elétrico e Montagem do Arduino](#3-esquema-elétrico-e-montagem-do-arduino)
4. [Gravação do Firmware no Arduino (Arduino IDE)](#4-gravação-do-firmware-no-arduino)
5. [Preparação do Ambiente Python no Computador](#5-preparação-do-ambiente-python-no-computador)
6. [Calibração das Zonas de Interesse (ROIs)](#6-calibração-das-zonas-de-interesse-rois)
7. [Executando o Sistema (Webcam, Vídeo ou Arduino)](#7-executando-o-sistema)
8. [Controles e Interpretação da Interface (HUD)](#8-controles-e-interpretação-da-interface-hud)
9. [Resolução de Problemas Comuns (Troubleshooting)](#9-resolução-de-problemas-comuns)

---

## 1. Visão Geral da Integração

O sistema funciona em loop fechado entre o computador e o microcontrolador:

```
[ Câmera / Vídeo ] 
        │ (quadros de vídeo)
        ▼
[ YOLOv8s (IA) ] ────► Detecta miniatura de carros e pedestres
        │
        ▼
[ Gerenciador de ROIs ] ──► Conta veículos nas filas da Via A, Via B e Pedestres
        │
        ▼
[ Controlador FSM ] ──────► Decide tempos de verde/vermelho por demanda e prioridade
        │
   ┌────┴──────────────────────────┐
   ▼                               ▼
[ HUD na Tela (OpenCV) ]     [ Cabo Serial USB (UART) ]
- Semáforos virtuais               │ Mensagens: "SET:A=G,B=R,P=R,T=10\n"
- Temporizador digital             ▼
- Telemetria de decisões     [ Arduino / ESP32 ]
                                   │
                                   ▼
                             [ LEDs Físicos na Maquete ]
```

---

## 2. Lista de Materiais Necessários

### Hardware
| Item | Quantidade | Observações |
| :--- | :---: | :--- |
| **Placa Microcontroladora** | 1 | Arduino Uno, Nano, Mega ou ESP32 |
| **LED Difuso Vermelho 5mm** | 3 | 1 para Via A, 1 para Via B, 1 para Pedestre |
| **LED Difuso Amarelo 5mm** | 2 | 1 para Via A, 1 para Via B |
| **LED Difuso Verde 5mm** | 3 | 1 para Via A, 1 para Via B, 1 para Pedestre |
| **Resistores 220Ω ou 330Ω** | 8 | 1 resistor em série para cada LED |
| **Buzzer Ativo 5V** *(Opcional)* | 1 | Para alerta sonoro de pedestre |
| **Protoboard (Matriz de Contatos)** | 1 ou 2 | Para montar os semáforos da maquete |
| **Cabos Jumper** | ~15 | Macho-Macho ou Macho-Fêmea |
| **Cabo USB da Placa** | 1 | Para ligar o Arduino ao PC |
| **Webcam USB** | 1 | Ou a câmera integrada do notebook |

---

## 3. Esquema Elétrico e Montagem do Arduino

### Mapeamento dos Pinos Digitais (Arduino Uno / Nano)

| Semáforo | Luz / Função | Pino Digital | Ligação |
| :--- | :--- | :---: | :--- |
| **Via A (Norte-Sul)** | LED Vermelho | **D2** | D2 ➔ Resistor 220Ω ➔ Anodo (+) LED ➔ Catodo (-) ➔ GND |
| | LED Amarelo | **D3** | D3 ➔ Resistor 220Ω ➔ Anodo (+) LED ➔ Catodo (-) ➔ GND |
| | LED Verde | **D4** | D4 ➔ Resistor 220Ω ➔ Anodo (+) LED ➔ Catodo (-) ➔ GND |
| **Via B (Leste-Oeste)** | LED Vermelho | **D5** | D5 ➔ Resistor 220Ω ➔ Anodo (+) LED ➔ Catodo (-) ➔ GND |
| | LED Amarelo | **D6** | D6 ➔ Resistor 220Ω ➔ Anodo (+) LED ➔ Catodo (-) ➔ GND |
| | LED Verde | **D7** | D7 ➔ Resistor 220Ω ➔ Anodo (+) LED ➔ Catodo (-) ➔ GND |
| **Pedestre** | LED Vermelho (Pare) | **D8** | D8 ➔ Resistor 220Ω ➔ Anodo (+) LED ➔ Catodo (-) ➔ GND |
| | LED Verde (Siga) | **D9** | D9 ➔ Resistor 220Ω ➔ Anodo (+) LED ➔ Catodo (-) ➔ GND |
| **Sonoro (Opcional)** | Buzzer Ativo | **D10** | D10 ➔ Terminal (+) Buzzer ➔ Terminal (-) ➔ GND |

> ⚠️ **Atenção aos terminais do LED:**
> - **Anodo (+):** Perna mais longa do LED. Conecte ao pino do Arduino através do resistor de 220Ω.
> - **Catodo (-):** Perna mais curta e com lado chanfrado na cápsula. Conecte à linha azul de terra (**GND**) da protoboard.
> - Conecte a linha azul de terra da protoboard a qualquer pino **GND** do Arduino.

---

## 4. Gravação do Firmware no Arduino

### Passo 4.1: Instalar e Abrir a Arduino IDE
1. Se ainda não possui, baixe e instale a [Arduino IDE](https://www.arduino.cc/en/software).
2. Abra a Arduino IDE no seu computador.

### Passo 4.2: Abrir o Código do Firmware
1. Na Arduino IDE, clique em **Arquivo ➔ Abrir...**
2. Navegue até a pasta do projeto e abra o arquivo:
   `STC-Sistema-de-Controle-de-Trafego/arduino/stc_semaforo.ino`

### Passo 4.3: Conectar a Placa e Selecionar a Porta
1. Conecte o cabo USB do Arduino ao seu computador.
2. Na barra superior da Arduino IDE, selecione a sua placa:
   - **Placa:** *Arduino Uno* (ou *Arduino Nano*).
   - **Porta:**
     - No **Windows:** selecione `COM3`, `COM4`, etc.
     - No **Linux:** selecione `/dev/ttyUSB0` ou `/dev/ttyACM0`.

### Passo 4.4: Enviar o Código (Upload)
1. Clique no botão com ícone de seta **Carregar** (Upload / `Ctrl + U`).
2. Aguarde a compilação. Ao final, a barra inferior exibirá **"Carregado com sucesso"**.
3. Imediatamente todos os LEDs vermelhos deverão acender (estado inicial de segurança).

### Passo 4.5: Teste Manual pelo Monitor Serial (Opcional, mas Recomendado)
1. Na Arduino IDE, abra o **Monitor Serial** (`Ctrl + Shift + M`).
2. No canto inferior do Monitor Serial, configure:
   - Velocidade: **9600 baud**.
   - Fim de linha: **Nova linha** (`Newline` / `\n`).
3. Digite e envie o comando:
   ```
   SET:A=G,B=R,P=R,T=10
   ```
   *Resultado esperado:* O LED verde da Via A e os vermelhos da Via B e Pedestre devem acender.
4. Digite e envie o comando de pedestre:
   ```
   SET:A=R,B=R,P=G,T=8
   ```
   *Resultado esperado:* O LED verde de pedestre deve acender e os carros ficam em vermelho.
5. Digite e envie o comando de alerta de pedestre:
   ```
   SET:A=R,B=R,P=F,T=3
   ```
   *Resultado esperado:* O LED vermelho de pedestre deve piscar e o buzzer (se instalado) começará a apitar.

> 🛑 **MUITO IMPORTANTE:** **FECHE o Monitor Serial da Arduino IDE antes de avançar!**
> Se o Monitor Serial continuar aberto, a porta serial ficará travada/ocupada e o Python não conseguirá se conectar a ela.

---

## 5. Preparação do Ambiente Python no Computador

Abra o terminal (ou Anaconda Prompt no Windows) na pasta do projeto:

```bash
cd /caminho/para/STC-Sistema-de-Controle-de-Trafego
```

### 5.1 Ativar o Ambiente Virtual
Se você seguiu o guia de treinamento do projeto:
```bash
conda activate YOLO_env
```
Ou se utiliza `venv`:
```bash
# Linux/macOS:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### 5.2 Instalar as Dependências
Garanta que todas as bibliotecas necessárias estão instaladas:
```bash
pip install -r requirements.txt
```
*(O `requirements.txt` já inclui `ultralytics`, `opencv-python`, `numpy`, `torch` e `pyserial`).*

### 5.3 Validar com os Testes Automatizados
Antes de ligar a câmera, certifique-se de que a lógica interna está 100% íntegra rodando a suíte de testes:
```bash
pytest
```
*Deverá exibir `15 passed` sem nenhum erro.*

---

## 6. Calibração das Zonas de Interesse (ROIs)

Como a câmera pode ser posicionada em ângulos ou alturas diferentes em relação à maquete, o sistema possui um **calibrador interativo via mouse**.

Execute o comando:
```bash
python controlador_semaforo.py --calibrar
```

Uma janela do OpenCV se abrirá exibindo a imagem ao vivo:

1. **Definir Via A (Norte-Sul):**
   - Dê **4 cliques** com o botão esquerdo do mouse delimitando a área onde os veículos da Via A se aproximam do cruzamento.
   - Pressione **ENTER** ou **ESPAÇO** para confirmar a zona.
2. **Definir Via B (Leste-Oeste):**
   - Dê **4 cliques** delimitando a área da fila de veículos da Via B.
   - Pressione **ENTER** ou **ESPAÇO** para confirmar.
3. **Definir Faixa de Pedestre:**
   - Dê **4 cliques** cobrindo a faixa de travessia onde o boneco de brinquedo é posicionado.
   - Pressione **ENTER** ou **ESPAÇO** para confirmar.

*Teclas úteis durante a calibração:*
- `r`: Limpa os pontos da zona atual para você clicar novamente.
- `ESC`: Cancela a calibração e mantém a anterior.

Ao concluir o 3º passo, o arquivo `rois.json` é automaticamente atualizado com as novas coordenadas normalizadas. Você não precisará recalibrar novamente nas próximas execuções, a menos que mude a posição da câmera.

---

## 7. Executando o Sistema

### Cenário 1: Execução Completa (Webcam + Arduino Conectado)

Substitua a porta serial pela porta da sua placa:

**No Linux:**
```bash
python controlador_semaforo.py --camera 0 --serial /dev/ttyUSB0 --baud 9600
```
*(Ou `/dev/ttyACM0`, verifique com `ls /dev/tty*`)*

**No Windows:**
```bash
python controlador_semaforo.py --camera 0 --serial COM3 --baud 9600
```

---

### Cenário 2: Modo Simulado (Sem Placa Física Conectada)
Se você estiver desenvolvendo ou testando no notebook longe da maquete:
```bash
python controlador_semaforo.py --camera 0
```
O sistema detecta que nenhuma porta foi passada e exibe no topo `Serial: SIMULADO`. Tudo funciona na tela perfeitamente!

---

### Cenário 3: Rodar com Arquivo de Vídeo Gravado
Se você gravou um vídeo da maquete (`.mp4`) e quer testar a detecção e o semáforo em loop contínuo:
```bash
python controlador_semaforo.py --video videos/teste_maquete.mp4 --serial COM3
```

---

### Cenário 4: Personalizar os Tempos do Semáforo
Você pode customizar todos os parâmetros de temporização via linha de comando:
```bash
python controlador_semaforo.py \
  --camera 0 \
  --t-min-verde 5.0 \
  --t-base-verde 10.0 \
  --t-max-verde 20.0 \
  --t-pedestre 8.0 \
  --conf 0.35
```

---

## 8. Controles e Interpretação da Interface (HUD)

### O que você vê na tela:

1. **Barra de Telemetria Superior (Preta):**
   - **FSM:** Estado atual da máquina de estados (ex: `VIA_A_VERDE`, `VIA_B_AMARELO`, `PEDESTRE_VERDE`).
   - **Motivo da Decisão:** Explica em linguagem natural por que o semáforo tomou aquela atitude (ex.: *"Via A vazia; antecipando transição para atender fila concorrente"*, *"Prioridade de pedestre acionada"* ou *"Via estendida por demanda"*).
   - **Métricas:** FPS da captura de vídeo, FPS da rede neural YOLO e status da porta Serial.
2. **Painel de Semáforos Virtuais (Canto Superior Direito):**
   - Três módulos verticais realistas mostrando as luzes acesas com efeito de brilho e as luzes apagadas escuras.
   - **Cronômetro Digital:** Contagem regressiva em segundos do tempo que resta para a luz mudar.
3. **Zonas Coloridas na Pista:**
   - As ROIs ficam preenchidas de forma translúcida com a cor do semáforo da respectiva via (Verde, Amarelo ou Vermelho).
4. **Caixas de Detecção da IA:**
   - Veículos contornados em amarelo com pontuação de confiança.
   - Pedestres contornados em magenta.
   - Ponto vermelho/verde na base inferior indicando exatamente onde o objeto está tocando o solo.

### Teclas de Atalho:

| Tecla | Função | Como usar |
| :---: | :--- | :--- |
| `p` | **Chamado Manual de Pedestre** | Simula instantaneamente que um pedestre apertou o botão ou foi detectado na faixa. O semáforo agendará a travessia assim que a via atual terminar seu verde seguro. |
| `c` | **Calibrar ROIs** | Abre o calibrador do mouse imediatamente para ajustar as zonas sem precisar reiniciar o script. |
| `s` | **Salvar Captura** | Tira uma foto instantânea do frame atual com todos os semáforos e bounding boxes e salva na pasta `capturas/`. |
| `ESPAÇO` | **Pausar / Retomar** | Congela o frame para analisar detalhadamente as detecções da IA. |
| `q` ou `ESC`| **Encerrar** | Finaliza as threads, fecha a porta serial e desliga as janelas com segurança. |

---

## 9. Resolução de Problemas Comuns (Troubleshooting)

### 🔴 Erro: "Permission denied: '/dev/ttyUSB0'" (Linux)
Se o Linux negar acesso à porta serial do Arduino:
1. Adicione seu usuário ao grupo `dialout`:
   ```bash
   sudo usermod -a -G dialout $USER
   ```
2. Ou dê permissão temporária de leitura/escrita na porta:
   ```bash
   sudo chmod 666 /dev/ttyUSB0
   ```

### 🔴 Erro: "Port is busy" / "Access is denied" (Windows)
- Certifique-se de que o **Monitor Serial da Arduino IDE está FECHADO**. O Windows não permite que dois programas leiam a mesma porta COM ao mesmo tempo.
- Feche outros softwares que possam estar usando a serial (ex: Cura, Pronterface, VS Code serial monitor).

### 🔴 Os LEDs físicos estão acesos de forma invertida ou não acendem
- Verifique se a perna mais longa do LED (Anodo) está conectada ao resistor e ao pino digital correto.
- Verifique se a linha de terra (**GND**) do Arduino está conectada ao Catodo de todos os LEDs na protoboard.
- Confira se a pinagem do Arduino confere com o arquivo `stc_semaforo.ino` (D2 a D4 para Via A, D5 a D7 para Via B, D8 e D9 para Pedestre).

### 🔴 A taxa de FPS da IA está baixa no PC
- Use um tamanho de imagem menor para inferência:
  ```bash
  python controlador_semaforo.py --camera 0 --imgsz 320
  ```
- Se você possui placa de vídeo NVIDIA, certifique-se de instalar o PyTorch com suporte a CUDA para usar a GPU em vez da CPU.

### 🔴 Detecções piscando ou sumindo rapidamente
- Ajuste a confiança mínima da detecção:
  ```bash
  python controlador_semaforo.py --camera 0 --conf 0.25
  ```
- O algoritmo do STC já possui um filtro temporal interno de 1 segundo para pedestres: o pedestre precisa permanecer visível por 1 segundo consecutivo na faixa para disparar o sinal, evitando falsos disparos com ruídos de câmera.

---

🎉 **Pronto! Seu cruzamento inteligente com controle adaptativo e visão computacional está totalmente operacional!**
