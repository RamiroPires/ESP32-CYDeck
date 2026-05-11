#include <TFT_eSPI.h>
#include <XPT2046_Touchscreen.h>
#include <SPI.h>

// Importa o arquivo de imagens que você gerou no HTML
#include "icones.h"

// --- PINOS CORRETOS DO TOUCH NO ESP32 CYD ---
#define XPT2046_IRQ 36
#define XPT2046_CS 33
#define XPT2046_MOSI 32
#define XPT2046_MISO 39
#define XPT2046_CLK 25

SPIClass touchSPI(VSPI);
XPT2046_Touchscreen ts(XPT2046_CS, XPT2046_IRQ);
TFT_eSPI tft = TFT_eSPI();

// Calibração do Touch (Ajuste se o clique ficar torto)
#define TOUCH_MIN_X 300
#define TOUCH_MAX_X 3800
#define TOUCH_MIN_Y 300
#define TOUCH_MAX_Y 3800

// ==========================================
// 🎨 CONFIGURAÇÃO DE VISUAL E GRID
// ==========================================
#define ESPACAMENTO 8
#define RAIO_BORDA 12  // O mesmo raio usado no recorte da imagem

#if TELA_ORIENTACAO == 0 || TELA_ORIENTACAO == 2
  #define TELA_LARGURA 240
  #define TELA_ALTURA 320
#else
  #define TELA_LARGURA 320
  #define TELA_ALTURA 240
#endif

int celulaTouchX;
int celulaTouchY;

// Controle de estado para não travar o loop e evitar múltiplos toques seguidos
bool aguardandoSoltar = false;
int botaoAtivo = -1;
unsigned long instanteToque = 0;

void setup() {
  Serial.begin(115200);

  tft.init();
  tft.invertDisplay(true);    //inverte as cores
  tft.setRotation(TELA_ORIENTACAO);
  tft.fillScreen(COR_FUNDO);  // Usa a cor de fundo definida no icones.h

  touchSPI.begin(XPT2046_CLK, XPT2046_MISO, XPT2046_MOSI, XPT2046_CS);
  ts.begin(touchSPI);
  ts.setRotation(TELA_ORIENTACAO);

  celulaTouchX = TELA_LARGURA / GRID_COLUNAS;
  celulaTouchY = TELA_ALTURA / GRID_LINHAS;

  // --- DESENHA OS ÍCONES E AS BORDAS ---
  tft.setSwapBytes(true);  // OBRIGATÓRIO PARA AS CORES FICAREM CERTAS

  for (int linha = 0; linha < GRID_LINHAS; linha++) {
    for (int coluna = 0; coluna < GRID_COLUNAS; coluna++) {

      int x = MARGEM_X + (coluna * (ICONE_TAMANHO + ESPACAMENTO));
      int y = MARGEM_Y + (linha * (ICONE_TAMANHO + ESPACAMENTO));
      int indiceBotao = (linha * GRID_COLUNAS) + coluna;

      // 1. Desenha a foto convertida
      tft.pushImage(x, y, ICONE_TAMANHO, ICONE_TAMANHO, meusIcones[indiceBotao]);

      // 2. Desenha a borda perfeita ao redor da foto para disfarçar o corte
      tft.drawRoundRect(x, y, ICONE_TAMANHO, ICONE_TAMANHO, RAIO_BORDA, COR_BORDA_INATIVA);
    }
  }
}

void loop() {
  if (ts.touched()) {
    TS_Point p = ts.getPoint();

    // Ponto Z é a pressão, filtrando toques fantasmas (< 300)
    if (p.z > 300) {
      // O 'constrain' evita que os pixels vazem a tela caso o mapa desça de 0 ou suba de 320/240
      int pixel_x = constrain(map(p.x, TOUCH_MIN_X, TOUCH_MAX_X, 0, TELA_LARGURA), 0, TELA_LARGURA - 1);
      int pixel_y = constrain(map(p.y, TOUCH_MIN_Y, TOUCH_MAX_Y, 0, TELA_ALTURA), 0, TELA_ALTURA - 1);

      if (!aguardandoSoltar) {
        int colunaTocada = pixel_x / celulaTouchX;
        int linhaTocada = pixel_y / celulaTouchY;
        botaoAtivo = (linhaTocada * GRID_COLUNAS) + colunaTocada;  // Índice 0 a 11

        Serial.print("BOTAO_");
        Serial.println(botaoAtivo + 1);

        // Acende a borda colorida
        int x = MARGEM_X + (colunaTocada * (ICONE_TAMANHO + ESPACAMENTO));
        int y = MARGEM_Y + (linhaTocada * (ICONE_TAMANHO + ESPACAMENTO));
        tft.drawRoundRect(x, y, ICONE_TAMANHO, ICONE_TAMANHO, RAIO_BORDA, coresBordas[botaoAtivo]);

        aguardandoSoltar = true;
      }
      
      instanteToque = millis(); // Reseta o tempo enquanto ainda estiver com o dedo na tela
    }
  } else {
    // Se o dedo foi retirado da tela, aguardamos 50ms (debounce) antes de apagar
    if (aguardandoSoltar && (millis() - instanteToque > 50)) {
      int x = MARGEM_X + ((botaoAtivo % GRID_COLUNAS) * (ICONE_TAMANHO + ESPACAMENTO));
      int y = MARGEM_Y + ((botaoAtivo / GRID_COLUNAS) * (ICONE_TAMANHO + ESPACAMENTO));
      tft.drawRoundRect(x, y, ICONE_TAMANHO, ICONE_TAMANHO, RAIO_BORDA, COR_BORDA_INATIVA); // Volta pra cor neutra
      
      Serial.print("SOLTO_");
      Serial.println(botaoAtivo + 1);

      aguardandoSoltar = false;
      botaoAtivo = -1;
    }
  }
}