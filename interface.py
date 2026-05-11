import customtkinter as ctk
from tkinter import messagebox, colorchooser, filedialog
from PIL import Image, ImageDraw
import serial
import serial.tools.list_ports
import threading
import os
import json
import subprocess
import pyautogui
import time
import webbrowser
import sys
import winreg
try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

# --- CONFIGURAÇÕES DE CAMINHO ---
CAMINHO_ATUAL = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CAMINHO_ATUAL)
PASTA_ICONES = os.path.join(BASE_DIR, "icones")
ARQUIVO_INO = os.path.join(CAMINHO_ATUAL, "streamdeck.ino") 
ARQUIVO_ESTADO = os.path.join(CAMINHO_ATUAL, "estado_programa.json")
PLACA_FQBN = "esp32:esp32:esp32da"

# --- PALETA DE CORES VIVAS ---
COLORS = {
    "base": "#121212",
    "surface": "#1E1E1E",
    "overlay": "#333333",
    "text": "#FFFFFF",
    "subtext": "#AAAAAA",
    "blue": "#007BFF",
    "red": "#FF3333",
    "green": "#00FF00",
    "yellow": "#FFD700",
}

TECLAS_PYAUTOGUI = [
    'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24',
    'playpause', 'prevtrack', 'nexttrack', 'volumemute', 'volumeup', 'volumedown',
    'enter', 'esc', 'space', 'ctrl', 'shift', 'alt'
]

# Convertendo as cores legadas para dar suporte aos estados antigos já salvos
MAPA_CORES_TFT = {
    "TFT_GREEN": "#00FF00",
    "TFT_RED": "#FF0000",
    "TFT_BLUE": "#0000FF",
    "TFT_YELLOW": "#FFFF00",
    "TFT_ORANGE": "#FFA500",
    "TFT_PURPLE": "#800080",
    "TFT_WHITE": "#FFFFFF",
    "TFT_CYAN": "#00FFFF"
}
ctk.set_appearance_mode("dark")

class ColorPickerPopup(ctk.CTkToplevel):
    def __init__(self, master, current_color, callback):
        super().__init__(master)
        self.title("Paleta de Cores")
        self.geometry("320x280")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.callback = callback
        self.configure(fg_color=COLORS["base"])
        
        self.grid_columnconfigure((0,1,2,3), weight=1)
        
        cores = [
            "#FF0000", "#FF7F00", "#FFFF00", "#00FF00",
            "#00FFFF", "#0000FF", "#8A2BE2", "#FF00FF",
            "#FF1493", "#00FA9A", "#FFFFFF", "#888888"
        ]
        
        ctk.CTkLabel(self, text="Selecione uma cor", font=("Arial", 16, "bold"), text_color=COLORS["text"]).grid(row=0, column=0, columnspan=4, pady=(15, 10))
        
        for i, cor in enumerate(cores):
            r, c = (i // 4) + 1, i % 4
            btn = ctk.CTkButton(self, text="", width=45, height=45, fg_color=cor, hover_color=cor, corner_radius=8,
                                command=lambda c=cor: self.selecionar(c))
            btn.grid(row=r, column=c, padx=5, pady=5)
            
        self.entry_custom = ctk.CTkEntry(self, placeholder_text="Hex (ex: #FFFFFF)", fg_color=COLORS["surface"], border_color=COLORS["overlay"], text_color=COLORS["text"])
        self.entry_custom.grid(row=5, column=0, columnspan=3, padx=(15, 5), pady=(15, 10), sticky="ew")
        
        btn_ok = ctk.CTkButton(self, text="OK", width=50, fg_color=COLORS["blue"], text_color=COLORS["base"], hover_color="#79a1e5", command=self.selecionar_custom)
        btn_ok.grid(row=5, column=3, padx=(0, 15), pady=(15, 10))
        
    def selecionar(self, cor):
        self.callback(cor)
        self.destroy()
        
    def selecionar_custom(self):
        cor = self.entry_custom.get().strip()
        if len(cor) == 7 and cor.startswith("#"):
            self.callback(cor.upper())
            self.destroy()

class StreamDeckPro(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Stream Deck Pro Center")
        self.geometry("1280x800")
        self.configure(fg_color=COLORS["base"])
        
        self.conexao_serial = None
        self.monitorando = False
        self.botao_selecionado = 1
        # Atributos para o Drag and Drop
        self.drag_data = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.teclas_pressionadas = set()
        self.botao_segurado = None
        
        # Carrega o estado de perfis salvo ou inicia padrão
        self.perfil_atual, self.perfis = self.carregar_estado_anterior()

        self.config_geral = self.perfis[self.perfil_atual]["config_geral"]
        self.botoes_config = self.perfis[self.perfil_atual]["botoes"]
        self.carregar_comandos_json()

        self.setup_ui()
        self.carregar_galeria()
        self.atualizar_portas()
        # Atualiza a cor dos botões de configuração global
        self.atualizar_cores_globais_ui()
        
        # Adiciona atalho para deletar um botão com a tecla "Delete"
        self.bind("<Delete>", lambda event: self.remover_botao())
        
        self.reconstruir_botoes_ui()

        # Conecta automaticamente na última porta caso exista uma
        if self.combo_portas.get() != "Nenhuma":
            self.after(1000, self.alternar_serial)

    def setup_ui(self):
        self.tabview = ctk.CTkTabview(self, fg_color=COLORS["surface"],
                                      segmented_button_fg_color=COLORS["surface"],
                                      segmented_button_selected_color=COLORS["blue"],
                                      segmented_button_selected_hover_color="#79a1e5",
                                      segmented_button_unselected_color=COLORS["overlay"],
                                      segmented_button_unselected_hover_color="#5c6075")
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tab_layout = self.tabview.add("🎨 Layout & Design")
        self.tab_console = self.tabview.add("💻 Console & Flash")
        self.tab_config = self.tabview.add("⚙️ Config")
        self.tab_about = self.tabview.add("ℹ️ About")
        
        self.tab_layout.configure(fg_color=COLORS["base"])
        self.tab_console.configure(fg_color=COLORS["base"])
        self.tab_config.configure(fg_color=COLORS["base"])
        self.tab_about.configure(fg_color=COLORS["base"])

        # --- ABA LAYOUT ---
        self.frame_galeria = ctk.CTkScrollableFrame(self.tab_layout, width=270, label_text="Ícones",
                                                    label_fg_color=COLORS["blue"], label_font=("Arial", 14, "bold"),
                                                    fg_color=COLORS["surface"])
        self.frame_galeria.pack(side="left", fill="both", padx=(10, 5), pady=10)

        self.frame_grid = ctk.CTkFrame(self.tab_layout, fg_color=COLORS["surface"])
        self.frame_grid.pack(side="left", fill="both", expand=True, padx=5, pady=10)
        
        self.frame_grid_top = ctk.CTkFrame(self.frame_grid, fg_color="transparent")
        self.frame_grid_top.pack(side="top", fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(self.frame_grid_top, text="Perfil:", font=("Arial", 14, "bold"), text_color=COLORS["subtext"]).pack(side="left", padx=(0, 5))
        self.combo_perfil = ctk.CTkComboBox(self.frame_grid_top, values=list(self.perfis.keys()), command=self.mudar_perfil, width=150, fg_color=COLORS["overlay"], border_color=COLORS["overlay"], button_color=COLORS["blue"])
        self.combo_perfil.pack(side="left", padx=5)
        self.combo_perfil.set(self.perfil_atual)
        
        self.btn_add_perfil = ctk.CTkButton(self.frame_grid_top, text="➕", width=30, fg_color=COLORS["blue"], hover_color="#79a1e5", command=self.adicionar_perfil)
        self.btn_add_perfil.pack(side="left", padx=5)
        self.btn_del_perfil = ctk.CTkButton(self.frame_grid_top, text="🗑️", width=30, fg_color=COLORS["red"], hover_color="#D62828", command=self.remover_perfil)
        self.btn_del_perfil.pack(side="left", padx=5)
        
        ctk.CTkLabel(self.frame_grid_top, text="|", text_color=COLORS["overlay"], font=("Arial", 16)).pack(side="left", padx=10)
        
        ctk.CTkLabel(self.frame_grid_top, text="Grid:", font=("Arial", 14, "bold"), text_color=COLORS["subtext"]).pack(side="left", padx=(0,5))
        self.val_colunas = ctk.StringVar(value=str(self.config_geral.get("colunas", 4)))
        self.val_linhas = ctk.StringVar(value=str(self.config_geral.get("linhas", 3)))
        ctk.CTkLabel(self.frame_grid_top, text="Cols:").pack(side="left", padx=(5,2))
        self.combo_cols = ctk.CTkComboBox(self.frame_grid_top, values=["1", "2", "3", "4", "5"], variable=self.val_colunas, width=60, command=self.mudar_grid)
        self.combo_cols.pack(side="left", padx=2)
        ctk.CTkLabel(self.frame_grid_top, text="Lins:").pack(side="left", padx=(10,2))
        self.combo_lins = ctk.CTkComboBox(self.frame_grid_top, values=["1", "2", "3"], variable=self.val_linhas, width=60, command=self.mudar_grid)
        self.combo_lins.pack(side="left", padx=2)

        self.grid_container = ctk.CTkFrame(self.frame_grid, fg_color="transparent")
        self.grid_container.pack(expand=True)
        self.botoes_ui = {}

        self.frame_config = ctk.CTkFrame(self.tab_layout, width=280, fg_color=COLORS["surface"])
        self.frame_config.pack(side="right", fill="both", padx=(5, 10), pady=10)
        
        self.lbl_edit = ctk.CTkLabel(self.frame_config, text="Botão 1", font=("Arial", 22, "bold"), text_color=COLORS["blue"])
        self.lbl_edit.pack(pady=20)

        self.lbl_acao = ctk.CTkLabel(self.frame_config, text="Ação (Escolha ou Digite):", text_color=COLORS["subtext"])
        self.lbl_acao.pack(anchor="w", padx=20)
        self.combo_tecla = ctk.CTkComboBox(self.frame_config, values=TECLAS_PYAUTOGUI, command=self.salvar_dados,
                                           fg_color=COLORS["overlay"], border_color=COLORS["overlay"], button_color=COLORS["blue"], dropdown_fg_color=COLORS["overlay"])
        self.combo_tecla.pack(fill="x", padx=20, pady=(0, 20))
        
        self.entry_tecla = ctk.CTkEntry(self.frame_config, fg_color=COLORS["overlay"], border_color=COLORS["overlay"], text_color=COLORS["text"])

        # Adiciona a capacidade de atualizar os dados ao digitar um comando livre
        self.combo_tecla.bind("<KeyRelease>", self.salvar_dados_tecla)
        self.combo_tecla.bind("<Button-1>", self.ao_clicar_acao)
        if hasattr(self.combo_tecla, '_entry'):
            self.combo_tecla._entry.bind("<KeyRelease>", self.salvar_dados_tecla)
            self.combo_tecla._entry.bind("<Button-1>", self.ao_clicar_acao)
            
        self.entry_tecla.bind("<KeyRelease>", self.salvar_dados_tecla)
        self.entry_tecla.bind("<KeyPress>", self.capturar_hotkey)
        self.entry_tecla.bind("<Button-1>", self.ao_clicar_acao)

        ctk.CTkLabel(self.frame_config, text="Cor do Clique:", text_color=COLORS["subtext"]).pack(anchor="w", padx=20)
        self.btn_cor = ctk.CTkButton(self.frame_config, text="🎨 Escolher Cor", command=self.escolher_cor, border_width=1, border_color=COLORS["overlay"])
        self.btn_cor.pack(fill="x", padx=20, pady=(0, 20))

        self.btn_remover = ctk.CTkButton(self.frame_config, text="🗑️ Limpar Botão", fg_color=COLORS["red"], hover_color="#D62828", command=self.remover_botao)
        self.btn_remover.pack(fill="x", padx=20, pady=(0, 20))

        self.btn_resetar = ctk.CTkButton(self.frame_config, text="🔄 RESETAR PÁGINA", fg_color=COLORS["yellow"], text_color=COLORS["base"], hover_color="#E5C890", command=self.resetar_pagina)
        self.btn_resetar.pack(fill="x", padx=20, pady=20)

        # --- Frame de Configurações Globais ---
        self.frame_global_config = ctk.CTkFrame(self.frame_config, fg_color="transparent")
        self.frame_global_config.pack(side="bottom", fill="x", padx=20, pady=(0, 20))

        ctk.CTkLabel(self.frame_global_config, text="Tela & Cores", font=("Arial", 16, "bold"), text_color=COLORS["subtext"]).pack(pady=(0,10))

        self.combo_orientacao = ctk.CTkComboBox(self.frame_global_config, values=["Retrato", "Paisagem", "Retrato Invertido", "Paisagem Invertida"], command=self.salvar_orientacao)
        self.combo_orientacao.pack(fill="x", pady=5)
        self.combo_orientacao.set(self.config_geral.get("orientacao", "Paisagem"))

        self.btn_cor_fundo = ctk.CTkButton(self.frame_global_config, text="🎨 Cor de Fundo", command=lambda: self.escolher_cor_global('cor_fundo'))
        self.btn_cor_fundo.pack(fill="x", pady=5)

        self.btn_cor_grid = ctk.CTkButton(self.frame_global_config, text="🎨 Cor da Borda", command=lambda: self.escolher_cor_global('cor_grid'))
        self.btn_cor_grid.pack(fill="x", pady=5)

        self.btn_sync = ctk.CTkButton(self.frame_config, text="🚀 SINCRONIZAR DECK", fg_color=COLORS["green"], text_color="black", hover_color="#00CC00", font=("Arial", 14, "bold"), command=self.sincronizar_deck)
        self.btn_sync.pack(side="bottom", fill="x", padx=20, pady=20)

        # --- ABA CONSOLE ---
        self.setup_console_tab()

        # --- ABA CONFIG ---
        ctk.CTkLabel(self.tab_config, text="⚙️ Configurações do Sistema", font=("Arial", 20, "bold"), text_color=COLORS["blue"]).pack(anchor="w", padx=20, pady=(20, 10))

        self.switch_startup = ctk.CTkSwitch(self.tab_config, text="Iniciar oculto com o Windows", command=self.toggle_startup, progress_color=COLORS["blue"])
        self.switch_startup.pack(pady=10, anchor="w", padx=20)
        
        self.switch_tray = ctk.CTkSwitch(self.tab_config, text="Minimizar para a bandeja ao fechar", command=self.toggle_tray, progress_color=COLORS["blue"])
        self.switch_tray.pack(pady=10, anchor="w", padx=20)
        
        if not HAS_PYSTRAY:
            self.switch_tray.configure(state="disabled", text="Minimizar para a bandeja (Requer no terminal: pip install pystray)")

        if self.config_geral.get("iniciar_windows", False):
            self.switch_startup.select()
            self.set_startup_registry(True)
        else:
            self.switch_startup.deselect()
            self.set_startup_registry(False)

        if self.config_geral.get("minimizar_bandeja", False):
            self.switch_tray.select()
        else:
            self.switch_tray.deselect()
            
        self.protocol("WM_DELETE_WINDOW", self.ao_fechar_janela)

        # --- ABA ABOUT ---
        ctk.CTkLabel(self.tab_about, text="Stream Deck Pro Center\n\nGerenciador de macros e ícones para ESP32.\nVersão 2.0", font=("Arial", 16), text_color=COLORS["subtext"], justify="center").pack(pady=50)

    def setup_console_tab(self):
        self.txt_console = ctk.CTkTextbox(self.tab_console, fg_color=COLORS["base"], text_color=COLORS["green"], font=("Consolas", 13))
        self.txt_console.pack(fill="both", expand=True, padx=20, pady=20)

        self.frame_ctrl = ctk.CTkFrame(self.tab_console, fg_color="transparent")
        self.frame_ctrl.pack(fill="x", padx=20, pady=(0, 20))

        self.combo_portas = ctk.CTkComboBox(self.frame_ctrl, values=["COM1"], width=100)
        self.combo_portas.pack(side="left", padx=5)
        self.btn_refresh = ctk.CTkButton(self.frame_ctrl, text="🔄", width=40, command=self.atualizar_portas)
        self.btn_refresh.pack(side="left", padx=5)

        self.btn_serial = ctk.CTkButton(self.frame_ctrl, text="🔌 Ativar Deck (Serial)", fg_color=COLORS["blue"], hover_color="#79a1e5", command=self.alternar_serial)
        self.btn_serial.pack(side="left", padx=10)

        self.btn_flash = ctk.CTkButton(self.frame_ctrl, text="🚀 SINCRONIZAR DECK", fg_color=COLORS["yellow"], text_color="black", hover_color="#FFC107", command=self.sincronizar_deck)
        self.btn_flash.pack(side="right", padx=10)

    # --- MÉTODOS DE CONFIGURAÇÃO DE SISTEMA ---
    def toggle_startup(self):
        state = self.switch_startup.get() == 1
        self.config_geral["iniciar_windows"] = state
        self.salvar_estado()
        self.set_startup_registry(state)

    def set_startup_registry(self, enable):
        if os.name != 'nt': return
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "StreamDeckPro"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                base_cmd = f'"{sys.executable}"' if getattr(sys, 'frozen', False) else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'{base_cmd} --hidden')
            else:
                try: winreg.DeleteValue(key, app_name)
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception as e:
            self.escrever_log(f"⚠️ Erro ao alterar registro do Windows: {e}")

    def toggle_tray(self):
        self.config_geral["minimizar_bandeja"] = self.switch_tray.get() == 1
        self.salvar_estado()

    def ao_fechar_janela(self):
        if self.config_geral.get("minimizar_bandeja", False) and HAS_PYSTRAY:
            self.withdraw()
            self.mostrar_bandeja()
        else:
            if getattr(self, "monitorando", False): self.alternar_serial() # Libera a porta de forma segura
            self.quit()
            
    def mostrar_bandeja(self):
        image = Image.new('RGB', (64, 64), color=COLORS["blue"])
        d = ImageDraw.Draw(image)
        d.text((22, 25), "SD", fill="white")
        
        menu = pystray.Menu(pystray.MenuItem('Restaurar Painel', self.restaurar_janela), pystray.MenuItem('Encerrar Programa', self.sair_totalmente))
        self.tray_icon = pystray.Icon("StreamDeckPro", image, "Stream Deck", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        
    def restaurar_janela(self, icon, item):
        self.tray_icon.stop()
        self.after(0, self.deiconify)
        
    def sair_totalmente(self, icon, item):
        self.tray_icon.stop()
        if getattr(self, "monitorando", False): self.alternar_serial()
        self.after(0, self.quit)

    # --- LÓGICA DE DADOS ---
    def carregar_estado_anterior(self):
        config_geral_padrao = {"cor_fundo": "#121212", "cor_grid": "#333333", "colunas": 4, "linhas": 3, "orientacao": "Paisagem"}
        botoes_padrao = {i: {"img": None, "tecla": "f13", "cor": "#00FF00"} for i in range(1, 16)}

        perfis = {
            "Padrão": {
                "config_geral": config_geral_padrao.copy(),
                "botoes": botoes_padrao.copy()
            }
        }
        perfil_atual = "Padrão"

        if os.path.exists(ARQUIVO_ESTADO):
            try:
                with open(ARQUIVO_ESTADO, "r") as f:
                    dados = json.load(f)
                    
                    if "perfis" in dados and "perfil_atual" in dados:
                        perfil_atual = dados.get("perfil_atual", "Padrão")
                        perfis.clear()
                        for k, v in dados["perfis"].items():
                            b = {int(bk): bv for bk, bv in v.get("botoes", {}).items()}
                            cg = v.get("config_geral", config_geral_padrao.copy())
                            for bv in b.values():
                                if bv.get("cor") in MAPA_CORES_TFT: bv["cor"] = MAPA_CORES_TFT[bv["cor"]]
                            perfis[k] = {"config_geral": cg, "botoes": b}
                        if perfil_atual not in perfis:
                            perfil_atual = list(perfis.keys())[0]
                    else:
                        if "botoes" in dados and "config_geral" in dados:
                            botoes = {int(k): v for k, v in dados["botoes"].items()}
                            config_geral = dados.get("config_geral", config_geral_padrao.copy())
                        else:
                            botoes = {int(k): v for k, v in dados.items()}
                            config_geral = config_geral_padrao.copy()
                        for v in botoes.values():
                            if v.get("cor") in MAPA_CORES_TFT: v["cor"] = MAPA_CORES_TFT[v["cor"]]
                        perfis["Padrão"] = {"config_geral": config_geral, "botoes": botoes}
                    
                    return perfil_atual, perfis
            except: pass
        
        return perfil_atual, perfis
        
    def carregar_comandos_json(self):
        self.comandos_json = {}
        self.grupos_icones = {}
        if os.path.exists("comandos.json"):
            try:
                with open("comandos.json", "r", encoding="utf-8") as f:
                    banco = json.load(f)
                    for categoria, comandos in banco.items():
                        # Transforma "CONTROLE_DE_MIDIA" em "Controle De Midia"
                        nome_categoria = categoria.replace("_", " ").title()
                        self.grupos_icones[nome_categoria] = list(comandos.keys())
                        for nome_icon, comando in comandos.items():
                            self.comandos_json[nome_icon.lower()] = comando
            except Exception as e:
                print(f"Erro ao carregar comandos.json: {e}")

    def obter_grupo_icone(self, nome_arquivo):
        nome = nome_arquivo.lower()
        for grupo, palavras in getattr(self, "grupos_icones", {}).items():
            for p in palavras:
                if p in nome:
                    return grupo
        return "Outros"
        
    def reconstruir_botoes_ui(self):
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        
        self.botoes_ui = {}
        cols = self.config_geral.get("colunas", 4)
        lins = self.config_geral.get("linhas", 3)
        total = cols * lins

        for i in range(1, total + 1):
            if i not in self.botoes_config:
                self.botoes_config[i] = {"img": None, "tecla": "f13", "cor": "#00FF00"}
        self.salvar_estado()
        
        for i in range(1, total + 1):
            r, c = (i-1) // cols, (i-1) % cols
            btn_size = min(110, 480 // cols, 330 // lins)
            btn = ctk.CTkButton(self.grid_container, text=f"{i}", width=btn_size, height=btn_size,
                                fg_color="#000000", border_width=2, border_color=COLORS["overlay"],
                                hover_color=COLORS["overlay"], text_color=COLORS["subtext"],
                                command=lambda id=i: self.selecionar_botao(id))
            btn.grid(row=r, column=c, padx=5, pady=5)
            
            # Liga o drag and drop também nos botões da placa
            btn.bind("<ButtonPress-1>", lambda e, id=i: self.on_drag_start_grid(e, id))
            btn.bind("<B1-Motion>", self.on_drag_motion)
            btn.bind("<ButtonRelease-1>", self.on_drag_release)
            self.botoes_ui[i] = btn
        
        self.atualizar_cores_globais_ui()
        self.carregar_visual_botoes()
        if self.botao_selecionado > total:
            self.selecionar_botao(1)
        else:
            self.selecionar_botao(self.botao_selecionado)
            
    def mudar_grid(self, _=None):
        self.config_geral["colunas"] = int(self.val_colunas.get())
        self.config_geral["linhas"] = int(self.val_linhas.get())
        self.salvar_estado()
        self.reconstruir_botoes_ui()
        
    def salvar_orientacao(self, _=None):
        self.config_geral["orientacao"] = self.combo_orientacao.get()
        self.salvar_estado()

    def carregar_visual_botoes(self):
        for i, config in self.botoes_config.items():
            if i in self.botoes_ui and config.get("img") and os.path.exists(config["img"]):
                try:
                    btn_w = self.botoes_ui[i].cget("width")
                    btn_h = self.botoes_ui[i].cget("height")
                    img = ctk.CTkImage(Image.open(config["img"]), size=(int(btn_w)-20, int(btn_h)-20))
                    self.botoes_ui[i].configure(image=img, text="")
                except: pass
            elif i in self.botoes_ui:
                self.botoes_ui[i].configure(image=None, text=f"{i}")

    def salvar_estado(self):
        self.perfis[self.perfil_atual]["config_geral"] = self.config_geral
        self.perfis[self.perfil_atual]["botoes"] = self.botoes_config
        
        dados_para_salvar = {
            "perfil_atual": self.perfil_atual,
            "perfis": self.perfis
        }
        with open(ARQUIVO_ESTADO, "w") as f:
            json.dump(dados_para_salvar, f, indent=4)

    def carregar_galeria(self):
        if not os.path.exists(PASTA_ICONES): os.makedirs(PASTA_ICONES)
        
        # Organizar ícones por grupo
        icones_por_grupo = {}
        for arquivo in os.listdir(PASTA_ICONES):
            if arquivo.lower().endswith(('.png', '.jpg', '.jpeg')):
                grupo = self.obter_grupo_icone(arquivo)
                if grupo not in icones_por_grupo:
                    icones_por_grupo[grupo] = []
                icones_por_grupo[grupo].append(arquivo)

        # Criar frame com scroll para cada grupo
        for nome_grupo, arquivos in icones_por_grupo.items():
            # Título do grupo
            lbl_grupo = ctk.CTkLabel(self.frame_galeria, text=nome_grupo, font=("Arial", 14, "bold"), text_color=COLORS["blue"])
            lbl_grupo.pack(anchor="w", padx=5, pady=(15, 5))

            # Container para ícones do grupo - grid com 3 colunas fixas
            frame_grupo = ctk.CTkFrame(self.frame_galeria, fg_color="transparent")
            frame_grupo.pack(fill="x")

            colunas = 3
            for idx, arquivo in enumerate(sorted(arquivos)):
                caminho = os.path.join(PASTA_ICONES, arquivo)
                try:
                    img = ctk.CTkImage(Image.open(caminho), size=(65, 65))
                    btn = ctk.CTkButton(frame_grupo, image=img, text="", width=70, height=70, fg_color=COLORS["base"], hover_color=COLORS["overlay"])
                    btn.grid(row=idx // colunas, column=idx % colunas, padx=3, pady=3)
                    
                    btn.bind("<ButtonPress-1>", lambda e, p=caminho: self.on_drag_start(e, p))
                    btn.bind("<B1-Motion>", self.on_drag_motion)
                    btn.bind("<ButtonRelease-1>", self.on_drag_release)
                except: pass

    # --- SISTEMA DE PERFIS ---
    def mudar_perfil(self, nome_perfil):
        self.perfil_atual = nome_perfil
        self.config_geral = self.perfis[self.perfil_atual]["config_geral"]
        self.botoes_config = self.perfis[self.perfil_atual]["botoes"]
        
        self.val_colunas.set(str(self.config_geral.get("colunas", 4)))
        self.val_linhas.set(str(self.config_geral.get("linhas", 3)))
        self.combo_orientacao.set(self.config_geral.get("orientacao", "Paisagem"))
        
        self.botao_selecionado = 1
        self.reconstruir_botoes_ui()
        self.salvar_estado()

    def adicionar_perfil(self):
        dialog = ctk.CTkInputDialog(text="Digite o nome do novo perfil:", title="Novo Perfil")
        nome = dialog.get_input()
        if nome and nome not in self.perfis:
            self.perfis[nome] = {
                "config_geral": {"cor_fundo": "#121212", "cor_grid": "#333333", "colunas": 4, "linhas": 3, "orientacao": "Paisagem"},
                "botoes": {i: {"img": None, "tecla": "f13", "cor": "#00FF00"} for i in range(1, 16)}
            }
            self.combo_perfil.configure(values=list(self.perfis.keys()))
            self.combo_perfil.set(nome)
            self.mudar_perfil(nome)

    def remover_perfil(self):
        if len(self.perfis) <= 1:
            messagebox.showwarning("Aviso", "Você não pode deletar o único perfil restante.")
            return
        if messagebox.askyesno("Remover Perfil", f"Tem certeza que deseja remover o perfil '{self.perfil_atual}'?"):
            del self.perfis[self.perfil_atual]
            novo_perfil = list(self.perfis.keys())[0]
            self.combo_perfil.configure(values=list(self.perfis.keys()))
            self.combo_perfil.set(novo_perfil)
            self.mudar_perfil(novo_perfil)

    # --- SISTEMA DE DRAG AND DROP ---
    def criar_imagem_arredondada(self, caminho, size, radius):
        try:
            img = Image.open(caminho).convert("RGBA")
            img = img.resize(size)
            mask = Image.new("L", size, 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
            output = Image.new("RGBA", size, (0, 0, 0, 0))
            output.paste(img, (0, 0), mask)
            return output
        except:
            return Image.new("RGBA", size, (0, 0, 0, 0))

    def criar_imagem_cor_arredondada(self, cor_hex, size, radius):
        try:
            r, g, b = int(cor_hex[1:3], 16), int(cor_hex[3:5], 16), int(cor_hex[5:7], 16)
        except:
            r, g, b = 0, 255, 0
        img = Image.new("RGBA", size, (r, g, b, 255))
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
        output = Image.new("RGBA", size, (0, 0, 0, 0))
        output.paste(img, (0, 0), mask)
        return output

    def on_drag_start(self, event, caminho):
        self.drag_data = {"caminho": caminho, "origem_id": None}
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        
        self.drag_window = ctk.CTkToplevel(self)
        self.drag_window.overrideredirect(True)
        self.drag_window.attributes("-topmost", True)
        self.drag_window.wm_attributes("-alpha", 0.8)
        
        # Transparência absoluta fora do contorno
        bg_color = "#010203"
        if os.name == 'nt':
            self.drag_window.wm_attributes("-transparentcolor", bg_color)
        self.drag_window.configure(fg_color=bg_color)
        
        pil_img = self.criar_imagem_arredondada(caminho, (65, 65), 12)
        img = ctk.CTkImage(pil_img, size=(65, 65))
        lbl = ctk.CTkLabel(self.drag_window, image=img, text="", fg_color=bg_color)
        lbl.pack()
        self.drag_window.img_ref = img # Previne o garbage collection limpar a imagem fantasma
        
        self.drag_window.geometry(f"+{event.x_root+10}+{event.y_root+10}")
        
    def on_drag_start_grid(self, event, id):
        config = self.botoes_config.get(id, {})
        caminho = config.get("img")
        self.drag_data = {"caminho": caminho, "origem_id": id}
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        
        self.drag_window = ctk.CTkToplevel(self)
        self.drag_window.overrideredirect(True)
        self.drag_window.attributes("-topmost", True)
        self.drag_window.wm_attributes("-alpha", 0.8)
        
        bg_color = "#010203"
        if os.name == 'nt': self.drag_window.wm_attributes("-transparentcolor", bg_color)
        self.drag_window.configure(fg_color=bg_color)
        
        if caminho and os.path.exists(caminho): pil_img = self.criar_imagem_arredondada(caminho, (65, 65), 12)
        else: pil_img = self.criar_imagem_cor_arredondada(config.get("cor", "#00FF00"), (65, 65), 12)
            
        img = ctk.CTkImage(pil_img, size=(65, 65))
        lbl = ctk.CTkLabel(self.drag_window, image=img, text="", fg_color=bg_color)
        lbl.pack()
        self.drag_window.img_ref = img
        self.drag_window.geometry(f"+{event.x_root+10}+{event.y_root+10}")

    def on_drag_motion(self, event):
        if hasattr(self, "drag_window") and self.drag_window.winfo_exists():
            self.drag_window.geometry(f"+{event.x_root+10}+{event.y_root+10}")

    def on_drag_release(self, event):
        if hasattr(self, "drag_window") and self.drag_window.winfo_exists():
            self.drag_window.destroy()

        # Se não há dados de arrasto (nenhum clique iniciado), ignora o evento
        if not self.drag_data:
            return
        
        target_id = None
        for id, btn in self.botoes_ui.items():
            bx, by = btn.winfo_rootx(), btn.winfo_rooty()
            bw, bh = btn.winfo_width(), btn.winfo_height()
            
            if bx <= event.x_root <= bx + bw and by <= event.y_root <= by + bh:
                target_id = id
                break
                
        origem_id = self.drag_data.get("origem_id")
        caminho = self.drag_data.get("caminho")
        is_click = abs(event.x_root - self.drag_start_x) < 5 and abs(event.y_root - self.drag_start_y) < 5

        if is_click:
            if origem_id is None: self.aplicar_icone(caminho) # Clique na galeria
        else:
            if target_id is not None:
                if origem_id is None: # Galeria para Grid
                    self.selecionar_botao(target_id)
                    self.aplicar_icone(caminho)
                elif origem_id != target_id: # Grid para Grid (Troca!)
                    self.botoes_config[origem_id], self.botoes_config[target_id] = self.botoes_config[target_id], self.botoes_config[origem_id]
                    self.salvar_estado()
                    self.carregar_visual_botoes()
                    self.selecionar_botao(target_id)

        # Limpa os dados de arrasto para o próximo evento
        self.drag_data = None

    def formatar_comando(self, comando):
        if isinstance(comando, list):
            return " + ".join(comando)
        return str(comando)

    def selecionar_botao(self, id):
        self.botao_selecionado = id
        cor_grid = self.config_geral.get("cor_grid", "#333333")
        for i, btn in self.botoes_ui.items():
            btn.configure(border_color=COLORS["blue"] if i == id else cor_grid)
        
        config = self.botoes_config[id]
        self.lbl_edit.configure(text=f"Botão {id}")
        
        cor = config.get("cor", "#00FF00")
        if cor in MAPA_CORES_TFT: cor = MAPA_CORES_TFT[cor]
        try:
            r, g, b = int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16)
            text_c = "black" if (0.299*r + 0.587*g + 0.114*b) > 128 else "white"
        except: text_c = "black"
        self.btn_cor.configure(fg_color=cor, text_color=text_c, hover_color=cor)

        # Lógica para travar ou destravar o ComboBox de tecla
        self.combo_tecla.configure(state="normal", button_color=COLORS["blue"], values=TECLAS_PYAUTOGUI)
        caminho_img = config.get("img")
        
        if caminho_img and os.path.exists(caminho_img):
            nome_icon = os.path.splitext(os.path.basename(caminho_img))[0].lower()
            
            if nome_icon in self.comandos_json:
                cmd = self.comandos_json[nome_icon]
                if cmd in [["open_app"], ["url"], ["open_folder"], ["hotkey"]]:
                    self.combo_tecla.pack_forget()
                    self.entry_tecla.pack(fill="x", padx=20, pady=(0, 20), after=self.lbl_acao)
                    self.entry_tecla.delete(0, "end")
                    self.entry_tecla.insert(0, config.get("tecla", ""))
                elif cmd == ["back"]:
                    self.entry_tecla.pack_forget()
                    self.combo_tecla.pack(fill="x", padx=20, pady=(0, 20), after=self.lbl_acao)
                    self.combo_tecla.set("browserback")
                    self.combo_tecla.configure(state="disabled")
                else:
                    self.entry_tecla.pack_forget()
                    self.combo_tecla.pack(fill="x", padx=20, pady=(0, 20), after=self.lbl_acao)
                    self.combo_tecla.set(self.formatar_comando(cmd))
                    self.combo_tecla.configure(state="disabled")
            else:
                self.entry_tecla.pack_forget()
                self.combo_tecla.pack(fill="x", padx=20, pady=(0, 20), after=self.lbl_acao)
                self.combo_tecla.set(config.get("tecla", "f13"))
        else:
            self.entry_tecla.pack_forget()
            self.combo_tecla.pack(fill="x", padx=20, pady=(0, 20), after=self.lbl_acao)
            self.combo_tecla.set(config.get("tecla", "f13"))
            
    def ao_clicar_acao(self, event=None):
        id = self.botao_selecionado
        config = self.botoes_config.get(id, {})
        caminho_img = config.get("img")
        if not caminho_img: return
        nome_icon = os.path.splitext(os.path.basename(caminho_img))[0].lower()
        if nome_icon in getattr(self, 'comandos_json', {}):
            cmd = self.comandos_json[nome_icon]
            if cmd == ["open_app"]:
                filepath = filedialog.askopenfilename(title="Selecione o programa", filetypes=[("Executáveis", "*.exe"), ("Todos os arquivos", "*.*")])
                if filepath:
                    if self.entry_tecla.winfo_ismapped():
                        self.entry_tecla.delete(0, "end")
                        self.entry_tecla.insert(0, filepath)
                    else:
                        self.combo_tecla.set(filepath)
                    self.salvar_dados()
                return "break"
            elif cmd == ["open_folder"]:
                dirpath = filedialog.askdirectory(title="Selecione a pasta")
                if dirpath:
                    if self.entry_tecla.winfo_ismapped():
                        self.entry_tecla.delete(0, "end")
                        self.entry_tecla.insert(0, dirpath)
                    else:
                        self.combo_tecla.set(dirpath)
                    self.salvar_dados()
                return "break"
            elif cmd == ["hotkey"]:
                if self.entry_tecla.get() == "Pressione o atalho...":
                    self.entry_tecla.delete(0, "end")
                self.limpar_teclas_pressionadas()

    def limpar_teclas_pressionadas(self):
        if hasattr(self, 'teclas_pressionadas'):
            self.teclas_pressionadas.clear()
        self.nova_gravacao = True

    def soltar_hotkey(self, event=None):
        id = self.botao_selecionado
        config = self.botoes_config.get(id, {})
        caminho_img = config.get("img")
        cmd = None
        if caminho_img:
            nome_icon = os.path.splitext(os.path.basename(caminho_img))[0].lower()
            cmd = getattr(self, 'comandos_json', {}).get(nome_icon)
            
        if cmd == ["hotkey"]:
            if not event: return "break"
            key = event.keysym.lower()
            map_keys = {'control_l': 'ctrl', 'control_r': 'ctrl', 'shift_l': 'shift', 'shift_r': 'shift', 'alt_l': 'alt', 'alt_r': 'alt', 'super_l': 'win', 'super_r': 'win', 'return': 'enter', 'escape': 'esc', 'prior': 'pageup', 'next': 'pagedown'}
            key = map_keys.get(key, key)
            
            if hasattr(self, 'teclas_pressionadas'):
                self.teclas_pressionadas.discard(key)
                if len(self.teclas_pressionadas) == 0:
                    self.nova_gravacao = True
            return "break"
        else:
            self.salvar_dados_tecla(event)

    def salvar_dados_tecla(self, event=None):
        id = self.botao_selecionado
        if self.entry_tecla.winfo_ismapped():
            self.botoes_config[id]["tecla"] = self.entry_tecla.get()
            self.salvar_estado()
        elif self.combo_tecla.cget("state") == "normal":
            self.botoes_config[id]["tecla"] = self.combo_tecla.get()
            self.salvar_estado()

    def salvar_dados(self, _=None):
        id = self.botao_selecionado
        # Só salva a tecla se o combobox estiver habilitado
        if self.entry_tecla.winfo_ismapped():
            self.botoes_config[id]["tecla"] = self.entry_tecla.get()
        elif self.combo_tecla.cget("state") == "normal":
            self.botoes_config[id]["tecla"] = self.combo_tecla.get()
        self.salvar_estado()
        self.selecionar_botao(id)
        
    def capturar_hotkey(self, event):
        id = self.botao_selecionado
        config = self.botoes_config.get(id, {})
        caminho_img = config.get("img")
        if not caminho_img: return
        nome_icon = os.path.splitext(os.path.basename(caminho_img))[0].lower()
        cmd = getattr(self, 'comandos_json', {}).get(nome_icon)
        
        if cmd == ["hotkey"]:
            if event.keysym in ['Tab', 'Return']: return
            
            key = event.keysym.lower()
            
            # Limpa o campo caso queira corrigir
            if key == 'backspace' or key == 'delete':
                self.entry_tecla.delete(0, "end")
                self.teclas_pressionadas.clear()
                self.salvar_dados_tecla()
                return "break"
            
            # Padroniza teclas de sistema
            map_keys = {
                'control_l': 'ctrl', 'control_r': 'ctrl',
                'shift_l': 'shift', 'shift_r': 'shift',
                'alt_l': 'alt', 'alt_r': 'alt',
                'super_l': 'win', 'super_r': 'win',
                'return': 'enter', 'escape': 'esc',
                'prior': 'pageup', 'next': 'pagedown'
            }
            key = map_keys.get(key, key)
            
            current_text = self.entry_tecla.get()
            if current_text == "Pressione o atalho...": current_text = ""
            
            if not hasattr(self, 'teclas_pressionadas'):
                self.teclas_pressionadas = set()
                
            if len(self.teclas_pressionadas) == 0:
                current_text = ""
                
            keys = [k.strip() for k in current_text.split("+")] if current_text else []
            
            # Regra de Ouro: Um atalho só pode ter UMA tecla comum (ex: 'F', 'A').
            # Se o usuário pressionar uma nova tecla comum, removemos a antiga para não "somar" (ex: a + b).
            MODIFIERS = {'ctrl', 'shift', 'alt', 'win'}
            
            if key not in MODIFIERS:
                # Filtra a lista mantendo apenas os modificadores
                keys = [k for k in keys if k in MODIFIERS]
                # Remove as teclas não-modificadoras da memória virtual
                to_remove = [k for k in self.teclas_pressionadas if k not in MODIFIERS]
                for k in to_remove:
                    self.teclas_pressionadas.discard(k)
                    
            self.teclas_pressionadas.add(key)
            if key not in keys: keys.append(key)
                
            # Organiza para os modificadores ficarem sempre na frente de forma padronizada
            def sort_key(k):
                order = {'ctrl': 1, 'shift': 2, 'alt': 3, 'win': 4}
                return order.get(k, 5)
                
            keys.sort(key=sort_key)
                
            self.entry_tecla.delete(0, "end")
            self.entry_tecla.insert(0, " + ".join(keys))
            self.salvar_dados_tecla()
            return "break"

    def escolher_cor(self):
        id = self.botao_selecionado
        cor_atual = self.botoes_config[id].get("cor", "#00FF00")
        if cor_atual in MAPA_CORES_TFT: cor_atual = MAPA_CORES_TFT[cor_atual]
        
        _, nova_cor = colorchooser.askcolor(title="Escolher Cor", initialcolor=cor_atual)
        if nova_cor:
            self.botoes_config[id]["cor"] = nova_cor.upper()
            self.salvar_dados()
            self.selecionar_botao(id)
        
    def escolher_cor_global(self, tipo_cor):
        cor_atual = self.config_geral.get(tipo_cor)
        
        _, nova_cor = colorchooser.askcolor(title="Escolher Cor", initialcolor=cor_atual)
        if nova_cor:
            self.config_geral[tipo_cor] = nova_cor.upper()
            self.salvar_estado()
            self.atualizar_cores_globais_ui()
        
    def atualizar_cores_globais_ui(self):
        # Cor de Fundo
        cor_fundo = self.config_geral.get("cor_fundo", "#121212")
        self.btn_cor_fundo.configure(fg_color=cor_fundo, text_color=self.get_text_color_for_bg(cor_fundo))
        self.frame_grid.configure(fg_color=cor_fundo)
        
        # Cor do Grid
        cor_grid = self.config_geral.get("cor_grid", "#333333")
        self.btn_cor_grid.configure(fg_color=cor_grid, text_color=self.get_text_color_for_bg(cor_grid))
        
        # Atualiza a pré-visualização no Grid do programa para refletir a tela real
        for i, btn in self.botoes_ui.items():
            btn.configure(fg_color="#000000", border_color=cor_grid if self.botao_selecionado != i else COLORS["blue"])

    def aplicar_icone(self, caminho):
        id = self.botao_selecionado
        self.botoes_config[id]["img"] = caminho
        img_ctk = ctk.CTkImage(Image.open(caminho), size=(80, 80))
        self.botoes_ui[id].configure(image=img_ctk, text="")

        nome_icon = os.path.splitext(os.path.basename(caminho))[0].lower()

        if nome_icon in self.comandos_json:
            cmd = self.comandos_json[nome_icon]
            if cmd == ["open_app"]:
                self.botoes_config[id]["tecla"] = "Clique para selecionar programa..."
            elif cmd == ["open_folder"]:
                self.botoes_config[id]["tecla"] = "Clique para selecionar pasta..."
            elif cmd == ["hotkey"]:
                self.botoes_config[id]["tecla"] = "Pressione o atalho..."
            elif cmd == ["url"]:
                self.botoes_config[id]["tecla"] = "https://"
            elif cmd == ["back"]:
                self.botoes_config[id]["tecla"] = "browserback"
            else:
                self.botoes_config[id]["tecla"] = self.formatar_comando(cmd)
        
        self.salvar_estado()
        self.selecionar_botao(id)

    def get_text_color_for_bg(self, bg_color):
        try:
            r, g, b = int(bg_color[1:3], 16), int(bg_color[3:5], 16), int(bg_color[5:7], 16)
            return "black" if (0.299*r + 0.587*g + 0.114*b) > 128 else "white"
        except:
            return "black"

    def remover_botao(self):
        id = self.botao_selecionado
        self.botoes_config[id]["img"] = None
        self.botoes_config[id]["tecla"] = "f13"
        self.botoes_config[id]["cor"] = "#00FF00"
        
        self.botoes_ui[id].configure(image=None, text=f"{id}")
        self.salvar_estado()
        self.selecionar_botao(id)
        
    def resetar_pagina(self):
        if messagebox.askyesno("Resetar", "Tem certeza que deseja limpar a configuração de todos os botões?"):
            cols = self.config_geral.get("colunas", 4)
            lins = self.config_geral.get("linhas", 3)
            total = cols * lins
            for i in range(1, total + 1):
                self.botoes_config[i] = {"img": None, "tecla": "f13", "cor": "#00FF00"}
                if i in self.botoes_ui:
                    self.botoes_ui[i].configure(image=None, text=f"{i}")
            self.salvar_estado()
            self.selecionar_botao(1)
            self.escrever_log("Página resetada com sucesso!")

    # --- SERIAL & AÇÕES ---
    def escrever_log(self, msg):
        self.txt_console.insert("end", f"> {msg}\n"); self.txt_console.see("end")

    def atualizar_portas(self):
        portas_encontradas = serial.tools.list_ports.comports()
        lista_portas = [p.device for p in portas_encontradas]
        
        self.combo_portas.configure(values=lista_portas if lista_portas else ["Nenhuma"])
        
        if lista_portas:
            self.combo_portas.set(lista_portas[-1]) # O USB sempre costuma ser a última porta conectada
            self.escrever_log(f"🔍 Portas seriais detectadas: {', '.join(lista_portas)}")
        else:
            self.combo_portas.set("Nenhuma")
            self.escrever_log("⚠️ Nenhuma placa detectada. Verifique o cabo USB (precisa ter dados) e o driver da placa.")

    def alternar_serial(self):
        if not self.monitorando:
            try:
                self.conexao_serial = serial.Serial(self.combo_portas.get(), 115200, timeout=0.1)
                self.monitorando = True
                self.btn_serial.configure(text="🛑 Desativar Deck", fg_color=COLORS["red"], hover_color="#D62828")
                threading.Thread(target=self.ler_serial, daemon=True).start()
                self.escrever_log("Deck ativo e ouvindo...")
            except: messagebox.showerror("Erro", "Porta Ocupada")
        else:
            self.monitorando = False
            if self.conexao_serial: self.conexao_serial.close()
            self.btn_serial.configure(text="🔌 Ativar Deck (Serial)", fg_color=COLORS["blue"], hover_color="#79a1e5")

    def ler_serial(self):
        while self.monitorando:
            if self.conexao_serial and self.conexao_serial.in_waiting > 0:
                try:
                    msg = self.conexao_serial.readline().decode('utf-8').strip()
                    if "BOTAO_" in msg:
                        self.escrever_log(f"RECEBIDO: {msg}")
                        
                        num = int(msg.split("_")[1])
                        self.botao_segurado = num
                        
                        if num not in self.botoes_config:
                            self.escrever_log(f"❌ Erro: Botão {num} não existe no botoes_config")
                            continue
                            
                        config = self.botoes_config[num]
                        tecla = config.get("tecla", "")
                        caminho_img = config.get("img")
                        
                        comando = None
                        if caminho_img:
                            nome_icon = os.path.splitext(os.path.basename(caminho_img))[0].lower()
                            if nome_icon in self.comandos_json:
                                cmd = self.comandos_json[nome_icon]
                                # Ignora atalhos de ações interativas para processá-los na parte customizada
                                if cmd not in [["open_app"], ["url"], ["back"]]:
                                    comando = cmd
                        
                        # 1. Executar comandos originados do JSON (Se o ícone estiver cadastrado lá)
                        if comando:
                            # Verifica se o comando único do JSON tem característica de link (URL)
                            cmd_str = comando[0] if (isinstance(comando, list) and len(comando) == 1) else str(comando)
                            is_json_url = cmd_str.startswith("http") or ("." in cmd_str and " " not in cmd_str and not os.path.exists(cmd_str) and "+" not in cmd_str and isinstance(comando, list) and len(comando) == 1)
                            
                            if is_json_url:
                                url_to_open = cmd_str if cmd_str.startswith("http") else "https://" + cmd_str
                                self.escrever_log(f"🌐 Abrindo site: {url_to_open}")
                                webbrowser.open(url_to_open)
                            elif isinstance(comando, list):
                                self.escrever_log(f"⌨️ Executando Macro JSON: {comando}")
                                if len(comando) > 1: pyautogui.hotkey(*comando)
                                else:
                                    pyautogui.press(comando[0])
                                    # Inicia repetição contínua se for botão de volume
                                    if comando in [["volumeup"], ["volumedown"]]:
                                        threading.Thread(target=self.repetir_acao_continua, args=(num, comando[0]), daemon=True).start()
                        
                        # 2. Se for comando customizado, lido do campo de texto
                        elif tecla:
                            # Heurística para detectar se é uma URL (contém ponto, sem espaços, não é um path existente)
                            is_url = "." in tecla and " " not in tecla and not os.path.exists(tecla) and "+" not in tecla

                            if is_url:
                                url_to_open = tecla if tecla.startswith("http") else "https://" + tecla
                                self.escrever_log(f"🌐 Abrindo site: {url_to_open}")
                                webbrowser.open(url_to_open)
                            elif os.path.exists(tecla):
                                self.escrever_log(f"🚀 Abrindo programa: {tecla}")
                                os.startfile(tecla)
                            elif "+" in tecla:
                                teclas = [t.strip().lower() for t in tecla.split("+")]
                                self.escrever_log(f"⌨️ Executando Macro Customizada: {teclas}")
                                pyautogui.hotkey(*teclas)
                            else:
                                self.escrever_log(f"⌨️ Pressionando tecla: {tecla.lower()}")
                                pyautogui.press(tecla.lower())
                                # Suporte também caso você tenha digitado manualmente o atalho de volume
                                if tecla.lower() in ["volumeup", "volumedown"]:
                                    threading.Thread(target=self.repetir_acao_continua, args=(num, tecla.lower()), daemon=True).start()
                        else:
                            self.escrever_log(f"⚠️ Botão {num} não tem ação configurada.")
                            
                    elif "SOLTO_" in msg:
                        num = int(msg.split("_")[1])
                        if getattr(self, 'botao_segurado', None) == num:
                            self.botao_segurado = None

                except Exception as e:
                    self.escrever_log(f"🔥 Erro Crítico: {e}")
                    
    def repetir_acao_continua(self, num, tecla):
        time.sleep(0.4) # Atraso inicial de 400ms para evitar disparo sem querer num clique rápido
        while getattr(self, 'botao_segurado', None) == num and self.monitorando:
            pyautogui.press(tecla)
            time.sleep(0.05) # Intervalo de 50ms (velocidade turbo para aumentar/abaixar o volume)

    # --- GERAR icones.h (IMPORTANTE) ---
    def gerar_arquivos(self, silent=False):
        def hex_para_rgb565(cor_hex, fallback='0x0000'):
            if not cor_hex or not cor_hex.startswith("#"): return fallback
            try:
                r, g, b = int(cor_hex[1:3], 16), int(cor_hex[3:5], 16), int(cor_hex[5:7], 16)
                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                return f"0x{rgb565:04X}"
            except:
                return fallback

        self.escrever_log("Gerando icones.h...")
        texto_h = "#include <pgmspace.h>\n\n"
        
        # --- Cores Globais ---
        cor_fundo_565 = hex_para_rgb565(self.config_geral.get("cor_fundo"), "0x0000") # Preto em caso de erro
        cor_grid_565 = hex_para_rgb565(self.config_geral.get("cor_grid"), "0x8410") # Cinza em caso de erro
        cols = self.config_geral.get("colunas", 4)
        lins = self.config_geral.get("linhas", 3)
        total_botoes = cols * lins
        
        orientacao_nome = self.config_geral.get("orientacao", "Paisagem")
        orientacao_map = {
            "Retrato": 0,
            "Paisagem": 1,
            "Retrato Invertido": 2,
            "Paisagem Invertida": 3
        }
        orientacao_val = orientacao_map.get(orientacao_nome, 1)
        is_retrato = orientacao_nome in ["Retrato", "Retrato Invertido"]
        tela_w = 240 if is_retrato else 320
        tela_h = 320 if is_retrato else 240
        
        espacamento = 8
        icone_w_max = (tela_w - espacamento * (cols + 1)) // cols
        icone_h_max = (tela_h - espacamento * (lins + 1)) // lins
        icone_tamanho = min(icone_w_max, icone_h_max)
        
        margem_x = (tela_w - (cols * icone_tamanho + (cols - 1) * espacamento)) // 2
        margem_y = (tela_h - (lins * icone_tamanho + (lins - 1) * espacamento)) // 2
        
        texto_h += f"#define COR_FUNDO {cor_fundo_565}\n"
        texto_h += f"#define COR_BORDA_INATIVA {cor_grid_565}\n\n"
        texto_h += f"#define TELA_ORIENTACAO {orientacao_val}\n"
        texto_h += f"#define GRID_COLUNAS {cols}\n"
        texto_h += f"#define GRID_LINHAS {lins}\n"
        texto_h += f"#define ICONE_TAMANHO {icone_tamanho}\n"
        texto_h += f"#define MARGEM_X {margem_x}\n"
        texto_h += f"#define MARGEM_Y {margem_y}\n\n"

        # --- Cores de Borda Ativa (por botão) ---
        cores_hex = []
        for i in range(1, total_botoes + 1):
            cor = self.botoes_config[i].get("cor", "#00FF00")
            if cor in MAPA_CORES_TFT: cor = MAPA_CORES_TFT[cor]
            cores_hex.append(hex_para_rgb565(cor, "0x07E0")) # Verde em caso de erro
            
        texto_h += "const uint16_t coresBordas[] = { " + ", ".join(cores_hex) + " };\n\n"
        
        # Gerar arrays de pixels (isso demora um pouco)
        for i in range(1, total_botoes + 1):
            self.escrever_log(f"Processando imagem {i}/{total_botoes}...")
            pixels = self.extrair_pixels(self.botoes_config[i].get("img"), icone_tamanho, icone_tamanho)
            p_str = ",\n  ".join([", ".join(pixels[j:j+10]) for j in range(0, len(pixels), 10)])
            texto_h += f"const uint16_t icone_{i}[] PROGMEM = {{\n  {p_str}\n}};\n\n"
        
        texto_h += "const uint16_t* meusIcones[] = { " + ", ".join([f"icone_{i}" for i in range(1, total_botoes + 1)]) + " };\n"
        
        with open(os.path.join(CAMINHO_ATUAL, "icones.h"), "w") as f:
            f.write(texto_h)
        self.escrever_log("✅ icones.h gerado com sucesso!")
        if not silent:
            messagebox.showinfo("Pronto", "Arquivos gerados com sucesso!")

    def extrair_pixels(self, caminho, w, h):
        cor_fundo_hex = self.config_geral.get("cor_fundo", "#121212")
        try:
            bg_r, bg_g, bg_b = int(cor_fundo_hex[1:3], 16), int(cor_fundo_hex[3:5], 16), int(cor_fundo_hex[5:7], 16)
        except:
            bg_r, bg_g, bg_b = 18, 18, 18
            
        img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
        
        if caminho and os.path.exists(caminho):
            img_orig = Image.open(caminho).convert("RGBA")
            
            # Aplica uma margem interna (padding de 16px) para o ícone não ser cortado nas bordas
            padding = 16
            img_orig = img_orig.resize((w - padding, h - padding))
            
            temp_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            temp_img.paste(img_orig, (padding // 2, padding // 2))
            img.alpha_composite(temp_img)
        
        # Cria a máscara com cantos arredondados (raio = 12, igual no Arduino)
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, w, h), radius=12, fill=255)
        
        # Fundo exato da tela do LCD
        fundo = Image.new('RGBA', (w, h), (bg_r, bg_g, bg_b, 255))
        fundo.paste(img, (0, 0), mask)
        
        img_rgb = fundo.convert("RGB")
        pix = img_rgb.load()
        hex_data = []
        
        for y in range(h):
            for x in range(w):
                r, g, b = pix[x, y]
                val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                hex_data.append(f"0x{val:04X}")
        return hex_data

    def sincronizar_deck(self):
        if hasattr(self, 'is_compiling') and self.is_compiling:
            self.escrever_log("⏳ Sincronização já em andamento. Aguarde...")
            return
        p = self.combo_portas.get()
        if p == "Nenhuma":
            self.escrever_log("❌ Nenhuma placa conectada para sincronizar.")
            messagebox.showwarning("Aviso", "Nenhuma placa conectada para sincronizar.")
            return
            
        self.is_compiling = True
        
        # --- POPUP DE SINCRONIZAÇÃO ---
        self.sync_popup = ctk.CTkToplevel(self)
        self.sync_popup.title("Aguarde")
        self.sync_popup.geometry("350x150")
        self.sync_popup.resizable(False, False)
        self.sync_popup.attributes("-topmost", True)
        self.sync_popup.configure(fg_color=COLORS["surface"])
        
        self.sync_popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 350) // 2
        y = self.winfo_y() + (self.winfo_height() - 150) // 2
        self.sync_popup.geometry(f"+{x}+{y}")
        self.sync_popup.grab_set()
        
        lbl = ctk.CTkLabel(self.sync_popup, text="Sincronizando Deck...\nIsso pode levar alguns segundos.", font=("Arial", 14), text_color=COLORS["text"])
        lbl.pack(pady=(30, 15))
        
        self.sync_progress = ctk.CTkProgressBar(self.sync_popup, mode="indeterminate", width=250, progress_color=COLORS["blue"])
        self.sync_progress.pack()
        self.sync_progress.start()
        
        self.update()
        
        if self.monitorando:
            self.alternar_serial() # Libera a porta COM para o Flash
            time.sleep(1.5)
            
        threading.Thread(target=self.processo_sincronizacao_completo, daemon=True).start()

    def processo_sincronizacao_completo(self):
        self.escrever_log("⚙️ Compilando imagens e firmware (Isso pode levar alguns segundos)...")
        self.gerar_arquivos(silent=True)
        
        p = self.combo_portas.get()
        self.escrever_log(f"🚀 Iniciando gravação (Flash) em {p}...")
        
        cmd = f"arduino-cli compile --fqbn {PLACA_FQBN} \"{ARQUIVO_INO}\" && arduino-cli upload -p {p} --fqbn {PLACA_FQBN} \"{ARQUIVO_INO}\""
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if res.returncode == 0:
            self.escrever_log("✅ DECK ATUALIZADO COM SUCESSO!")
            
            # Reconectar serial automaticamente de forma segura na thread principal
            self.after(2000, self.iniciar_serial_pos_flash)
            self.after(0, self.fechar_sync_popup, True)
        else:
            self.escrever_log("❌ ERRO DETALHADO:")
            self.escrever_log(res.stdout)
            self.escrever_log(res.stderr)
            self.after(0, self.fechar_sync_popup, False)
            
        self.is_compiling = False

    def fechar_sync_popup(self, sucesso):
        if hasattr(self, 'sync_popup') and self.sync_popup.winfo_exists():
            self.sync_progress.stop()
            self.sync_popup.destroy()
        
        if sucesso:
            messagebox.showinfo("Sucesso", "Deck sincronizado com sucesso!")
        else:
            messagebox.showerror("Erro", "Erro ao compilar/gravar o código!\nVerifique a aba Console para mais detalhes.")
            
    def iniciar_serial_pos_flash(self):
        self.escrever_log("🔄 Reconectando ao Deck automaticamente...")
        self.atualizar_portas()
        if self.combo_portas.get() != "Nenhuma" and not self.monitorando:
            self.alternar_serial()

if __name__ == "__main__":
    app = StreamDeckPro()
    if "--hidden" in sys.argv and HAS_PYSTRAY:
        app.withdraw()
        app.after(100, app.mostrar_bandeja)
    app.mainloop()