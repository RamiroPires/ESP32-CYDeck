import customtkinter as ctk
from tkinter import messagebox
from PIL import Image
import serial
import serial.tools.list_ports
import threading
import os
import json
import subprocess
import pyautogui
import time

# --- CONFIGURAÇÕES DE CAMINHO ---
CAMINHO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CAMINHO_ATUAL)
PASTA_ICONES = os.path.join(BASE_DIR, "icones")
ARQUIVO_INO = os.path.join(CAMINHO_ATUAL, "streamdeck.ino") 
ARQUIVO_ESTADO = os.path.join(CAMINHO_ATUAL, "estado_programa.json")
PLACA_FQBN = "esp32:esp32:esp32da"

TECLAS_PYAUTOGUI = [
    'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24',
    'playpause', 'prevtrack', 'nexttrack', 'volumemute', 'volumeup', 'volumedown',
    'enter', 'esc', 'space', 'ctrl', 'shift', 'alt'
]

CORES_TFT = ["TFT_GREEN", "TFT_RED", "TFT_BLUE", "TFT_YELLOW", "TFT_ORANGE", "TFT_PURPLE", "TFT_WHITE", "TFT_CYAN"]

ctk.set_appearance_mode("dark")

class StreamDeckPro(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Stream Deck Pro Center v5.1")
        self.geometry("1200x800")
        
        self.conexao_serial = None
        self.monitorando = False
        self.botao_selecionado = 1
        
        # Carrega o estado salvo ou inicia padrão
        self.botoes_config = self.carregar_estado_anterior()

        self.setup_ui()
        self.carregar_galeria()
        self.atualizar_portas()
        
        # Pequeno delay para garantir que a UI carregou antes de aplicar ícones
        self.after(100, self.carregar_visual_botoes)
        self.selecionar_botao(1)

    def setup_ui(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_layout = self.tabview.add("🎨 Layout & Design")
        self.tab_console = self.tabview.add("💻 Console & Flash")

        # --- ABA LAYOUT ---
        self.frame_galeria = ctk.CTkScrollableFrame(self.tab_layout, width=220, label_text="Ícones")
        self.frame_galeria.pack(side="left", fill="both", padx=10, pady=10)

        self.frame_grid = ctk.CTkFrame(self.tab_layout)
        self.frame_grid.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        self.grid_container = ctk.CTkFrame(self.frame_grid, fg_color="transparent")
        self.grid_container.pack(expand=True)
        self.botoes_ui = {}
        for i in range(1, 13):
            r, c = (i-1)//4, (i-1)%4
            btn = ctk.CTkButton(self.grid_container, text=f"{i}", width=100, height=100,
                                fg_color="#1e1e2e", border_width=2, border_color="#45475a",
                                command=lambda id=i: self.selecionar_botao(id))
            btn.grid(row=r, column=c, padx=10, pady=10)
            self.botoes_ui[i] = btn

        self.frame_config = ctk.CTkFrame(self.tab_layout, width=280)
        self.frame_config.pack(side="right", fill="both", padx=10, pady=10)
        
        self.lbl_edit = ctk.CTkLabel(self.frame_config, text="Botão 1", font=("Arial", 20, "bold"))
        self.lbl_edit.pack(pady=20)

        ctk.CTkLabel(self.frame_config, text="Ação (Tecla):").pack(anchor="w", padx=20)
        self.combo_tecla = ctk.CTkComboBox(self.frame_config, values=TECLAS_PYAUTOGUI, command=self.salvar_dados)
        self.combo_tecla.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkLabel(self.frame_config, text="Cor do Clique:").pack(anchor="w", padx=20)
        self.combo_cor = ctk.CTkComboBox(self.frame_config, values=CORES_TFT, command=self.salvar_dados)
        self.combo_cor.pack(fill="x", padx=20, pady=(0, 20))

        self.btn_gerar = ctk.CTkButton(self.frame_config, text="💾 SALVAR & GERAR ARQUIVOS", fg_color="#2ecc71", text_color="black", command=self.gerar_arquivos)
        self.btn_gerar.pack(side="bottom", fill="x", padx=20, pady=20)

        # --- ABA CONSOLE ---
        self.setup_console_tab()

    def setup_console_tab(self):
        self.txt_console = ctk.CTkTextbox(self.tab_console, fg_color="#000", text_color="#00FF00", font=("Consolas", 12))
        self.txt_console.pack(fill="both", expand=True, padx=20, pady=20)

        self.frame_ctrl = ctk.CTkFrame(self.tab_console, fg_color="transparent")
        self.frame_ctrl.pack(fill="x", padx=20, pady=(0, 20))

        self.combo_portas = ctk.CTkComboBox(self.frame_ctrl, values=["COM1"], width=100)
        self.combo_portas.pack(side="left", padx=5)
        self.btn_refresh = ctk.CTkButton(self.frame_ctrl, text="🔄", width=40, command=self.atualizar_portas)
        self.btn_refresh.pack(side="left", padx=5)

        self.btn_serial = ctk.CTkButton(self.frame_ctrl, text="🔌 Ativar Deck (Serial)", command=self.alternar_serial)
        self.btn_serial.pack(side="left", padx=10)

        self.btn_flash = ctk.CTkButton(self.frame_ctrl, text="🚀 FLASH", fg_color="#e67e22", command=self.iniciar_upload)
        self.btn_flash.pack(side="right", padx=10)

    # --- LÓGICA DE DADOS ---
    def carregar_estado_anterior(self):
        if os.path.exists(ARQUIVO_ESTADO):
            try:
                with open(ARQUIVO_ESTADO, "r") as f:
                    dados = json.load(f)
                    return {int(k): v for k, v in dados.items()}
            except: pass
        return {i: {"img": None, "tecla": "f13", "cor": "TFT_GREEN"} for i in range(1, 13)}

    def carregar_visual_botoes(self):
        for i, config in self.botoes_config.items():
            if config["img"] and os.path.exists(config["img"]):
                try:
                    img = ctk.CTkImage(Image.open(config["img"]), size=(80, 80))
                    self.botoes_ui[i].configure(image=img, text="")
                except: pass

    def salvar_estado(self):
        with open(ARQUIVO_ESTADO, "w") as f:
            json.dump(self.botoes_config, f, indent=4)

    def carregar_galeria(self):
        if not os.path.exists(PASTA_ICONES): os.makedirs(PASTA_ICONES)
        for arquivo in os.listdir(PASTA_ICONES):
            if arquivo.lower().endswith(('.png', '.jpg', '.jpeg')):
                caminho = os.path.join(PASTA_ICONES, arquivo)
                try:
                    img = ctk.CTkImage(Image.open(caminho), size=(60, 60))
                    btn = ctk.CTkButton(self.frame_galeria, image=img, text="", width=70, height=70, fg_color="#181825", 
                                        command=lambda p=caminho: self.aplicar_icone(p))
                    btn.pack(pady=5)
                except: pass

    def selecionar_botao(self, id):
        self.botao_selecionado = id
        for i, btn in self.botoes_ui.items():
            btn.configure(border_color="#89b4fa" if i == id else "#45475a")
        config = self.botoes_config[id]
        self.lbl_edit.configure(text=f"Botão {id}")
        self.combo_tecla.set(config["tecla"])
        self.combo_cor.set(config["cor"])

    def salvar_dados(self, _=None):
        id = self.botao_selecionado
        self.botoes_config[id]["tecla"] = self.combo_tecla.get()
        self.botoes_config[id]["cor"] = self.combo_cor.get()
        self.salvar_estado()

    def aplicar_icone(self, caminho):
        id = self.botao_selecionado
        self.botoes_config[id]["img"] = caminho
        img_ctk = ctk.CTkImage(Image.open(caminho), size=(80, 80))
        self.botoes_ui[id].configure(image=img_ctk, text="")
        self.salvar_estado()

    # --- SERIAL & AÇÕES ---
    def escrever_log(self, msg):
        self.txt_console.insert("end", f"> {msg}\n"); self.txt_console.see("end")

    def atualizar_portas(self):
        portas = [p.device for p in serial.tools.list_ports.comports()]
        self.combo_portas.configure(values=portas if portas else ["Nenhuma"])
        if portas: self.combo_portas.set(portas[0])

    def alternar_serial(self):
        if not self.monitorando:
            try:
                self.conexao_serial = serial.Serial(self.combo_portas.get(), 115200, timeout=0.1)
                self.monitorando = True
                self.btn_serial.configure(text="🛑 Desativar Deck", fg_color="red")
                threading.Thread(target=self.ler_serial, daemon=True).start()
                self.escrever_log("Deck ativo e ouvindo...")
            except: messagebox.showerror("Erro", "Porta Ocupada")
        else:
            self.monitorando = False
            if self.conexao_serial: self.conexao_serial.close()
            self.btn_serial.configure(text="🔌 Ativar Deck (Serial)", fg_color="#1f538d")

    def ler_serial(self):
        while self.monitorando:
            if self.conexao_serial and self.conexao_serial.in_waiting > 0:
                try:
                    msg = self.conexao_serial.readline().decode('utf-8').strip()
                    if "BOTAO_" in msg:
                        self.escrever_log(f"RECEBIDO: {msg}")
                        num = int(msg.split("_")[1])
                        caminho_img = self.botoes_config[num]["img"]
                        
                        if caminho_img:
                            nome_icon = os.path.splitext(os.path.basename(caminho_img))[0].lower()
                            
                            if os.path.exists("comandos.json"):
                                with open("comandos.json", "r", encoding="utf-8") as f:
                                    banco = json.load(f)
                                
                                comando = None
                                for categoria in banco.values():
                                    if nome_icon in categoria:
                                        comando = categoria[nome_icon]
                                        break
                                
                                if comando:
                                    # --- CAMINHO INSTANTÂNEO ---
                                    if isinstance(comando, str) and comando.startswith("http"):
                                        self.escrever_log(f"🌐 Abrindo site: {comando}")
                                        os.startfile(comando) # Comando mágico do Windows
                                    
                                    # --- CAMINHO DE TECLAS (MACROS) ---
                                    elif isinstance(comando, list):
                                        self.escrever_log(f"⌨️ Executando macro: {comando}")
                                        if len(comando) > 1:
                                            pyautogui.hotkey(*comando)
                                        else:
                                            pyautogui.press(comando[0])
                except Exception as e:
                    self.escrever_log(f"Erro: {e}")

    # --- GERAR icones.h (IMPORTANTE) ---
    def gerar_arquivos(self):
        self.escrever_log("Gerando icones.h...")
        texto_h = "#include <pgmspace.h>\n\n"
        # Gerar cores
        cores = [self.botoes_config[i]["cor"] for i in range(1, 13)]
        texto_h += "const uint16_t coresBordas[] = { " + ", ".join(cores) + " };\n\n"
        
        # Gerar arrays de pixels (isso demora um pouco)
        for i in range(1, 13):
            self.escrever_log(f"Processando imagem {i}/12...")
            pixels = self.extrair_pixels(self.botoes_config[i]["img"])
            p_str = ",\n  ".join([", ".join(pixels[j:j+10]) for j in range(0, len(pixels), 10)])
            texto_h += f"const uint16_t icone_{i}[] PROGMEM = {{\n  {p_str}\n}};\n\n"
        
        texto_h += "const uint16_t* meusIcones[] = { " + ", ".join([f"icone_{i}" for i in range(1, 13)]) + " };\n"
        
        with open(os.path.join(CAMINHO_ATUAL, "icones.h"), "w") as f:
            f.write(texto_h)
        self.escrever_log("✅ icones.h gerado com sucesso!")
        messagebox.showinfo("Pronto", "Arquivos gerados! Agora clique em FLASH.")

    def extrair_pixels(self, caminho):
        if not caminho or not os.path.exists(caminho):
            return ["0x0000"] * (70*69)
            
        # Abre a imagem
        img = Image.open(caminho)
        
        # --- SOLUÇÃO DO AVISO ---
        # Se a imagem tiver transparência ou paleta de cores, converte para RGBA primeiro
        if img.mode in ("P", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
        
        # Agora converte para RGB (fundo preto para transparência) e redimensiona
        fundo = Image.new('RGBA', img.size, (0, 0, 0, 255))
        img = Image.alpha_composite(fundo, img.convert("RGBA")).convert("RGB").resize((70, 69))
        
        pix = img.load()
        hex_data = []
        
        for y in range(69):
            for x in range(70):
                r, g, b = pix[x, y]
                val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                hex_data.append(f"0x{val:04X}")
        return hex_data

    def iniciar_upload(self):
        if self.monitorando:
            self.alternar_serial() # Fecha o serial
            time.sleep(1.5)        # <--- Dê esse tempo pro Windows liberar a porta!
        threading.Thread(target=self.executar_flash, daemon=True).start()

    def executar_flash(self):
        p = self.combo_portas.get()
        self.escrever_log(f"🚀 Iniciando Flash em {p}...")
        
        # O 'stderr=subprocess.STDOUT' faz o erro aparecer junto com a saída normal
        cmd = f"arduino-cli compile --fqbn {PLACA_FQBN} \"{ARQUIVO_INO}\" && arduino-cli upload -p {p} --fqbn {PLACA_FQBN} \"{ARQUIVO_INO}\""
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if res.returncode == 0:
            self.escrever_log("✅ SUCESSO!")
            self.escrever_log(res.stdout) # Mostra o log de sucesso
        else:
            # Agora ele vai mostrar o motivo real do 'exit status 2'
            self.escrever_log("❌ ERRO DETALHADO:")
            self.escrever_log(res.stdout)
            self.escrever_log(res.stderr)

if __name__ == "__main__":
    app = StreamDeckPro()
    app.mainloop()