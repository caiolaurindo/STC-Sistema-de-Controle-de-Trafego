/*
  =============================================================================
  STC - Sistema de Controle de Tráfego Adaptativo
  Firmware para Arduino / ESP32 para controle dos LEDs dos Semáforos da Maquete.
  =============================================================================

  Protocolo de Comunicação Serial (UART @ 9600 bps):
    Comando recebido: SET:A=<G|Y|R>,B=<G|Y|R>,P=<G|R|F>,T=<tempo>\n
    Exemplo:          SET:A=G,B=R,P=R,T=10\n

    Onde:
      A: Estado do Semáforo da Via A (G = Verde, Y = Amarelo, R = Vermelho)
      B: Estado do Semáforo da Via B (G = Verde, Y = Amarelo, R = Vermelho)
      P: Estado do Semáforo de Pedestre (G = Siga, R = Pare, F = Alerta Piscante)
      T: Tempo restante estimado em segundos (para display de 7 segmentos opcional)

  Mapeamento Padrão de Pinos (Arduino Uno / Nano):
    - Via A:
        Pino 2 -> LED Vermelho
        Pino 3 -> LED Amarelo
        Pino 4 -> LED Verde
    - Via B:
        Pino 5 -> LED Vermelho
        Pino 6 -> LED Amarelo
        Pino 7 -> LED Verde
    - Pedestre:
        Pino 8 -> LED Vermelho
        Pino 9 -> LED Verde
    - Alerta Sonoro (Opcional):
        Pino 10 -> Buzzer Ativo (bipa durante alerta de pedestre)
*/

// ================= Definição dos Pinos =================
const int PIN_A_VERMELHO = 2;
const int PIN_A_AMARELO  = 3;
const int PIN_A_VERDE    = 4;

const int PIN_B_VERMELHO = 5;
const int PIN_B_AMARELO  = 6;
const int PIN_B_VERDE    = 7;

const int PIN_PED_VERMELHO = 8;
const int PIN_PED_VERDE    = 9;

const int PIN_BUZZER       = 10; // Deixe desconectado se não utilizar buzzer

// ================= Variáveis de Estado =================
char estado_via_a    = 'R';
char estado_via_b    = 'R';
char estado_pedestre = 'R';
int  tempo_restante  = 0;

// Watchdog de segurança: se ficar mais de 6 segundos sem comunicação do PC,
// entra em modo de segurança (amarelo piscante de alerta).
unsigned long ultimo_pacote_tempo = 0;
const unsigned long TIMEOUT_COMUNICACAO_MS = 6000;

// Controle de pisca (não-bloqueante via millis)
unsigned long ultimo_pisca_tempo = 0;
bool led_pisca_estado = false;

// Buffer de recepção serial
String bufferSerial = "";

void setup() {
  Serial.begin(9600);

  pinMode(PIN_A_VERMELHO, OUTPUT);
  pinMode(PIN_A_AMARELO, OUTPUT);
  pinMode(PIN_A_VERDE, OUTPUT);

  pinMode(PIN_B_VERMELHO, OUTPUT);
  pinMode(PIN_B_AMARELO, OUTPUT);
  pinMode(PIN_B_VERDE, OUTPUT);

  pinMode(PIN_PED_VERMELHO, OUTPUT);
  pinMode(PIN_PED_VERDE, OUTPUT);

  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  // Inicializa com todos no Vermelho
  atualizarLeds();

  ultimo_pacote_tempo = millis();
  Serial.println("STC_ARDUINO_READY");
}

void loop() {
  // 1. Leitura não-bloqueante da porta Serial
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (bufferSerial.length() > 0) {
        processarComando(bufferSerial);
        bufferSerial = "";
      }
    } else {
      if (bufferSerial.length() < 64) {
        bufferSerial += c;
      }
    }
  }

  // 2. Controle do pisca do alerta de pedestre ou modo de segurança (a cada 300ms)
  unsigned long agora = millis();
  if (agora - ultimo_pisca_tempo >= 300) {
    ultimo_pisca_tempo = agora;
    led_pisca_estado = !led_pisca_estado;
    atualizarLeds();
  }

  // 3. Watchdog: se o script em Python for fechado ou o cabo desconectar
  if (agora - ultimo_pacote_tempo > TIMEOUT_COMUNICACAO_MS) {
    modoFalhaSeguranca();
  }
}

void processarComando(String cmd) {
  cmd.trim();
  if (!cmd.startsWith("SET:")) {
    return;
  }

  ultimo_pacote_tempo = millis();

  // Exemplo de formato: "SET:A=G,B=R,P=R,T=8"
  int idxA = cmd.indexOf("A=");
  int idxB = cmd.indexOf("B=");
  int idxP = cmd.indexOf("P=");
  int idxT = cmd.indexOf("T=");

  if (idxA != -1) estado_via_a    = cmd.charAt(idxA + 2);
  if (idxB != -1) estado_via_b    = cmd.charAt(idxB + 2);
  if (idxP != -1) estado_pedestre = cmd.charAt(idxP + 2);
  if (idxT != -1) {
    int fimT = cmd.indexOf(',', idxT);
    if (fimT == -1) fimT = cmd.length();
    tempo_restante = cmd.substring(idxT + 2, fimT).toInt();
  }

  atualizarLeds();
}

void atualizarLeds() {
  // --- Via A ---
  digitalWrite(PIN_A_VERMELHO, (estado_via_a == 'R') ? HIGH : LOW);
  digitalWrite(PIN_A_AMARELO,  (estado_via_a == 'Y') ? HIGH : LOW);
  digitalWrite(PIN_A_VERDE,    (estado_via_a == 'G') ? HIGH : LOW);

  // --- Via B ---
  digitalWrite(PIN_B_VERMELHO, (estado_via_b == 'R') ? HIGH : LOW);
  digitalWrite(PIN_B_AMARELO,  (estado_via_b == 'Y') ? HIGH : LOW);
  digitalWrite(PIN_B_VERDE,    (estado_via_b == 'G') ? HIGH : LOW);

  // --- Pedestre ---
  if (estado_pedestre == 'G') {
    digitalWrite(PIN_PED_VERMELHO, LOW);
    digitalWrite(PIN_PED_VERDE, HIGH);
    digitalWrite(PIN_BUZZER, LOW);
  } else if (estado_pedestre == 'F') {
    // Alerta de travessia finalizando: vermelho piscante e bips
    digitalWrite(PIN_PED_VERDE, LOW);
    digitalWrite(PIN_PED_VERMELHO, led_pisca_estado ? HIGH : LOW);
    digitalWrite(PIN_BUZZER, led_pisca_estado ? HIGH : LOW);
  } else {
    // Vermelho fixo (Pare)
    digitalWrite(PIN_PED_VERDE, LOW);
    digitalWrite(PIN_PED_VERMELHO, HIGH);
    digitalWrite(PIN_BUZZER, LOW);
  }
}

void modoFalhaSeguranca() {
  // Em caso de perda de comunicação com o PC:
  // Todos os semáforos amarelos piscando como alerta preventivo
  digitalWrite(PIN_A_VERMELHO, LOW);
  digitalWrite(PIN_A_VERDE, LOW);
  digitalWrite(PIN_A_AMARELO, led_pisca_estado ? HIGH : LOW);

  digitalWrite(PIN_B_VERMELHO, LOW);
  digitalWrite(PIN_B_VERDE, LOW);
  digitalWrite(PIN_B_AMARELO, led_pisca_estado ? HIGH : LOW);

  digitalWrite(PIN_PED_VERDE, LOW);
  digitalWrite(PIN_PED_VERMELHO, HIGH);
  digitalWrite(PIN_BUZZER, LOW);
}
