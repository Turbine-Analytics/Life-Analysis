import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from nptdms import TdmsFile
import pandas as pd

def data_channel_in_file_from_tdms(tdms_file,m_grup,m_channel):
    data = None
    for group in tdms_file.groups():
        if m_grup in group.name:
            for channel in group.channels():
                if m_channel in channel.name:
                    data=channel[:]
    return data  

class AnalytikaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Analýza životnosti TG3 - Expert Edition")
        self.root.geometry("1400x900")

        # --- Stavové proměnné ---
        self.tdms_file = None
        self.data = {}  
        self.current_file_path = tk.StringVar(value="Soubor nenačten")
        self.x_unit = tk.StringVar(value="Vzorky")
        
        self.var_m = tk.DoubleVar(value=3.0)
        self.var_ziv_roky = tk.DoubleVar(value=20.0)
        self.var_mez = tk.DoubleVar(value=1.0)
        self.var_range_from = tk.StringVar(value="0")
        self.var_range_to = tk.StringVar(value="end")

        # --- Proměnné pro histogram ---
        self.var_show_hist = tk.BooleanVar(value=False)
        self.var_bins = tk.IntVar(value=50)
        
        self.sel_group = tk.StringVar()
        self.sel_channel = tk.StringVar()

        self.sel_group_view = tk.StringVar()
        self.sel_channel_view = tk.StringVar()
        
        self.default_dir = r'd:\user\nce\Slapy\cutd\data RS\2410-2505\sec_f\\'

        self.setup_ui()

    def setup_ui(self):
        menubar = tk.Menu(self.root)
        
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Načti data", command=self.load_file)
        filemenu.add_command(label="Uložit výsledky jako...", command=self.save_results_csv)
        filemenu.add_separator()
        filemenu.add_command(label="Konec", command=self.root.quit)
        menubar.add_cascade(label="Soubor", menu=filemenu)

        # NOVÉ MENU: Analýza
        analýzamenu = tk.Menu(menubar, tearoff=0)
        analýzamenu.add_command(label="Kanál info", command=self.show_channel_info)
        menubar.add_cascade(label="Analýza", menu=analýzamenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        for u in ["Vzorky", "Sekundy", "Minuty", "Hodiny", "Dny", "Datum a Čas"]:
            viewmenu.add_radiobutton(label=u, variable=self.x_unit, command=self.update_plot)
        menubar.add_cascade(label="Jednotky osy X", menu=viewmenu)
        
        self.root.config(menu=menubar)

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 2. LEVÝ PANEL
        ctrl_panel = ttk.Frame(main_frame, width=320)
        ctrl_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # --- Sekce 1: Kanály ---
        chan_frame = ttk.LabelFrame(ctrl_panel, text="Prohlížeč DAT, tdms, csv")
        chan_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        tree_scroll = ttk.Scrollbar(chan_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(chan_frame, show="tree", selectmode="browse", yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)
        self.tree.bind('<<TreeviewSelect>>', self.on_channel_select)

        # --- Sekce 2: VÝBĚR PRO VÝPOČET ---
        calc_chan_frame = ttk.LabelFrame(ctrl_panel, text="Zvolený kanál pro VÝPOČET životnosti")
        calc_chan_frame.pack(fill=tk.X, pady=5)

        ttk.Label(calc_chan_frame, text="Skupina:").grid(row=0, column=0, sticky="w", padx=5)
        self.combo_group = ttk.Combobox(calc_chan_frame, textvariable=self.sel_group, state="readonly")
        self.combo_group.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        # ZDE PŘIDEJTE LAMBDU, ABY LISTOVÁNÍ FUNGOVALO SPRÁVNĚ:
        self.combo_group.bind("<<ComboboxSelected>>", lambda e: self.update_channel_list("calc"))

        ttk.Label(calc_chan_frame, text="Kanál:").grid(row=1, column=0, sticky="w", padx=5)
        self.combo_chan = ttk.Combobox(calc_chan_frame, textvariable=self.sel_channel, state="readonly")
        self.combo_chan.grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        # --- Sekce 3: VÝBĚR PRO ZOBRAZENÍ (Teď je hned pod Výpočtem) ---
        view_chan_frame = ttk.LabelFrame(ctrl_panel, text="Zvolený kanál pro ZOBRAZENÍ")
        view_chan_frame.pack(fill=tk.X, pady=5)

        ttk.Label(view_chan_frame, text="Skupina:").grid(row=0, column=0, sticky="w", padx=5)
        self.combo_group_view = ttk.Combobox(view_chan_frame, textvariable=self.sel_group_view, state="readonly")
        self.combo_group_view.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.combo_group_view.bind("<<ComboboxSelected>>", lambda e: self.update_channel_list("view"))

        ttk.Label(view_chan_frame, text="Kanál:").grid(row=1, column=0, sticky="w", padx=5)
        self.combo_chan_view = ttk.Combobox(view_chan_frame, textvariable=self.sel_channel_view, state="readonly")
        self.combo_chan_view.grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        # --- Sekce 4: PARAMETRY (Samostatný rámeček pod výběry) ---
        param_frame = ttk.LabelFrame(ctrl_panel, text="Parametry algoritmu")
        param_frame.pack(fill=tk.X, pady=5)

        ttk.Label(param_frame, text="Mocnina m:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Entry(param_frame, textvariable=self.var_m, width=10).grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(param_frame, text="Životnost [roky]:").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Entry(param_frame, textvariable=self.var_ziv_roky, width=10).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(param_frame, text="Mez citlivosti:").grid(row=2, column=0, sticky="w", padx=5)
        ttk.Entry(param_frame, textvariable=self.var_mez, width=10).grid(row=2, column=1, padx=5, pady=2)

        ttk.Label(param_frame, text="Rozsah od/do:").grid(row=3, column=0, sticky="w", padx=5)
        range_f = ttk.Frame(param_frame)
        range_f.grid(row=3, column=1, sticky="w")
        ttk.Entry(range_f, textvariable=self.var_range_from, width=7).pack(side=tk.LEFT, padx=2)
        ttk.Entry(range_f, textvariable=self.var_range_to, width=7).pack(side=tk.LEFT, padx=2)
        
       
        # --- NASTAVENÍ HISTOGRAMU ---
        hist_frame = ttk.LabelFrame(ctrl_panel, text="Režim zobrazení")
        hist_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(hist_frame, text="Zobrazit jako HISTOGRAM", variable=self.var_show_hist, command=self.update_plot).pack(anchor="w", padx=5)
        
        bin_f = ttk.Frame(hist_frame)
        bin_f.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(bin_f, text="Počet binů:").pack(side=tk.LEFT)
        ttk.Entry(bin_f, textvariable=self.var_bins, width=10).pack(side=tk.LEFT, padx=5)

        # --- Sekce 3: Analytické výpočty ---
        calc_frame = ttk.LabelFrame(ctrl_panel, text="Analytické grafy")
        calc_frame.pack(fill=tk.X, pady=5)
        
        self.calc_list = tk.Listbox(calc_frame, height=6)
        calcs = ["Zvolený kanál pro VÝPOČET", 
                 "Zvolený kanál pro ZOBRAZENÍ",  
                 "Kumulativní spotřeba", 
                 "Spotřeba životnoti", 
                 "Histogram spotřeby vs kanal pro zobrazení"]
        for c in calcs: self.calc_list.insert(tk.END, c)
        self.calc_list.pack(fill=tk.X, padx=5, pady=2)
        self.calc_list.bind('<<ListboxSelect>>', lambda e: self.update_plot())

        ttk.Button(ctrl_panel, text="AKTUALIZOVAT GRAF", command=self.update_plot).pack(fill=tk.X, pady=10)

        # 3. PRAVÝ PANEL (GRAF)
        self.plot_frame = ttk.Frame(main_frame)
        self.plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.fig, self.ax = plt.subplots(figsize=(8, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def show_channel_info(self):
        """Vyskakovací okno se statistikou kanálu."""
        if not self.sel_channel.get():
            messagebox.showwarning("Varování", "Není vybrán žádný kanál.")
            return

        try:
            data = self.get_data_universal(self.sel_group.get(), self.sel_channel.get())
        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo se získat data: {e}")
            return

        info_win = tk.Toplevel(self.root)
        info_win.title(f"Info: {self.sel_channel.get()}")

        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        info_win.geometry(f"400x450+{root_x + 30}+{root_y + 30}")
        info_win.transient(self.root)

        # Základní statistika
        stats_frame = ttk.LabelFrame(info_win, text="Statistické parametry")
        stats_frame.pack(fill="both", expand=True, padx=10, pady=10)

        stats = {
            "Počet vzorků": len(data),
            "Minimum": np.nanmin(data),
            "Maximum": np.nanmax(data),
            "Průměr": np.nanmean(data),
            "Medián": np.nanmedian(data),
            "Směrodatná odchylka": np.nanstd(data)
        }

        for i, (k, v) in enumerate(stats.items()):
            ttk.Label(stats_frame, text=f"{k}:").grid(row=i, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(stats_frame, text=f"{v:.4f}" if isinstance(v, float) else v, font=('Helvetica', 9, 'bold')).grid(row=i, column=1, sticky="e", padx=5, pady=2)

        # Volitelný práh
        thresh_frame = ttk.LabelFrame(info_win, text="Analýza překročení prahu")
        thresh_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(thresh_frame, text="Zadej prahovou hodnotu:").pack(side="top", anchor="w", padx=5)
        var_threshold = tk.DoubleVar(value=self.var_mez.get())
        entry_thresh = ttk.Entry(thresh_frame, textvariable=var_threshold)
        entry_thresh.pack(fill="x", padx=5, pady=5)

        lbl_result = ttk.Label(thresh_frame, text="Počet nad mezí: -", font=('Helvetica', 10, 'bold'))
        lbl_result.pack(pady=5)

        def update_threshold_count():
            try:
                val = var_threshold.get()
                count = np.sum(data > val)
                perc = (count / len(data)) * 100
                lbl_result.config(text=f"Počet nad mezí: {count} ({perc:.2f} %)")
            except:
                lbl_result.config(text="Chyba v zadání hodnoty")

        ttk.Button(thresh_frame, text="Spočítat výskyt", command=update_threshold_count).pack(pady=5)
        update_threshold_count() # Prvotní výpočet

    def load_file(self):
        path = filedialog.askopenfilename(
            initialdir=self.default_dir, 
            filetypes=[("Podporované soubory", "*.tdms *.csv"), ("TDMS files", "*.tdms"), ("CSV files", "*.csv")]
        )
        if not path: return

        try:
            for i in self.tree.get_children(): self.tree.delete(i)
            if path.lower().endswith('.tdms'): self._load_tdms(path)
            elif path.lower().endswith('.csv'): self._load_csv(path)
            self.current_file_path.set(path.split("/")[-1])
            messagebox.showinfo("Hotovo", "Soubor načten.")
        except Exception as e:
            messagebox.showerror("Chyba při načítání", f"Nepodařilo se načíst soubor:\n{str(e)}")

    def _load_tdms(self, path):
        self.tdms_file = TdmsFile.read(path)
        groups = []
        for group in self.tdms_file.groups():
            groups.append(group.name)
            g_node = self.tree.insert("", "end", text=group.name, open=False)
            for chan in group.channels():
                self.tree.insert(g_node, "end", text=chan.name, values=(group.name, chan.name))
        self.combo_group['values'] = groups
        self.combo_group_view['values'] = groups
        if 'OK' in groups:
            self.sel_group.set('OK')
            self.update_channel_list("calc")
            if 'TG3 VIBRO TXD [µm]' in self.combo_chan['values']:
                self.sel_channel.set('TG3 VIBRO TXD [µm]')
            self.sel_group_view.set('OK')   
            self.update_channel_list("view")   
            if 'TG3 RT GEN Výkon činný [MW]' in self.combo_chan_view['values']:
                self.sel_channel_view.set('TG3 RT GEN Výkon činný [MW]')      
        try:
            self.data['time'] = data_channel_in_file_from_tdms(self.tdms_file, 'Time_info', 'Time')
            self.data['pc'] = data_channel_in_file_from_tdms(self.tdms_file, 'OK', 'TG3 RT GEN Výkon činný [MW]')
            self.data['rk'] = data_channel_in_file_from_tdms(self.tdms_file, 'OK', 'TG3 RT RK Poloha [%]')
            self.data['ok'] = data_channel_in_file_from_tdms(self.tdms_file, 'OK', 'TG3 RT OK Poloha [%]')
        except: pass

    def _load_csv(self, path):
        # Načtení souboru s automatickou detekcí oddělovače
        df = pd.read_csv(path, sep=None, engine='python')
        self.csv_data_storage = df
        
        group_name = "CSV_Data"
        self.combo_group['values'] = [group_name]
        self.combo_group_view['values'] = [group_name]
        self.sel_group.set(group_name)
        self.sel_group_view.set(group_name)
        
        # Vyčištění a naplnění stromové struktury (Treeview)
        for i in self.tree.get_children(): 
            self.tree.delete(i)
        
        g_node = self.tree.insert("", "end", text=group_name, open=True)
        
        # Jeden průchod přes sloupce pro všechna nastavení
        for col in df.columns:
            # Přidání do stromu
            self.tree.insert(g_node, "end", text=col, values=(group_name, col))
            
            c_low = col.lower()
            
            # 1. Nastavení výchozího kanálu pro VÝPOČET (Vibrace)
            if 'tg3 vibro txd' in c_low or 'vibr' in c_low:
                self.sel_channel.set(col)
                
            # 2. Nastavení výchozího kanálu pro ZOBRAZENÍ (Výkon)
            if 'výkon' in c_low or 'pc' in c_low or 'mw' in c_low:
                self.sel_channel_view.set(col)
                self.data['pc'] = df[col].values
            
            # 3. Mapování systémových dat (Čas, RK, OK)
            if 'time' in c_low or 'čas' in c_low:
                self.data['time'] = pd.to_datetime(df[col]).values
            
            if 'rk' in c_low:
                self.data['rk'] = df[col].values
                
            if 'ok' in c_low:
                self.data['ok'] = df[col].values

        # Aktualizace seznamů v comboboxech
        self.update_channel_list("calc")
        self.update_channel_list("view")
        
        # Pokud se nepodařilo najít časový sloupec, vytvoříme umělý index
        if 'time' not in self.data or self.data['time'] is None:
            self.data['time'] = np.arange(len(df))
    
    def save_results_csv(self):
        # Kontrola, zda máme co ukládat
        if not self.sel_channel.get():
            messagebox.showwarning("Varování", "Nejsou vybrána žádná data k uložení.")
            return

        # Zeptáme se na cestu k souboru
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV soubor", "*.csv")],
            initialfile="vysledky_analyzy.csv"
        )
        
        if not path:
            return

        try:
            # Získání dat (stejná logika jako v update_plot)
            d_calc = self.get_data_universal(self.sel_group.get(), self.sel_channel.get())
            
            # Aplikace ořezu (slice)
            try:
                start = int(self.var_range_from.get())
                end = len(d_calc) if self.var_range_to.get() == "end" else int(self.var_range_to.get())
                s = slice(start, end)
            except:
                s = slice(0, len(d_calc))

            # Příprava DataFrame pro export
            export_df = pd.DataFrame()
            
            # Přidání času (pokud existuje a sedí délka)
            if 'time' in self.data and len(self.data['time']) == len(d_calc):
                export_df['Cas'] = self.data['time'][s]
            
            # Hlavní data
            export_df[self.sel_channel.get()] = d_calc[s]
            
            # Výpočet spotřeby (aby byla v CSV taky)
            spotreba = self.calculate_fatigue(d_calc[s])
            export_df['Spotreba_zivotnosti_lokalni'] = spotreba
            export_df['Spotreba_zivotnosti_kumulativni'] = np.cumsum(spotreba)

            # Uložení
            export_df.to_csv(path, index=False, sep=';', decimal=',')
            messagebox.showinfo("Export dokončen", f"Data byla úspěšně uložena do:\n{path}")

        except Exception as e:
            messagebox.showerror("Chyba exportu", f"Nepodařilo se uložit CSV:\n{str(e)}")

    def update_channel_list(self, target="calc"):
        if target == "view":
            skupina = self.sel_group_view.get()
            combo_to_fill = self.combo_chan_view
            current_chan_var = self.sel_channel_view
        else:
            skupina = self.sel_group.get()
            combo_to_fill = self.combo_chan
            current_chan_var = self.sel_channel

        if not skupina:
            return

        if skupina == "CSV_Data":
            cols = list(self.csv_data_storage.columns)
            combo_to_fill['values'] = cols
            if current_chan_var.get() not in cols: 
                current_chan_var.set("")
        elif self.tdms_file:
            try:
                group = self.tdms_file[skupina]
                chans = [c.name for c in group.channels()]
                combo_to_fill['values'] = chans
                # Pokud aktuálně vybraný kanál není v nové skupině, vymažeme ho
                if current_chan_var.get() not in chans:
                    current_chan_var.set("")
            except:
                combo_to_fill['values'] = []


    def get_data_universal(self, group, channel):
        if group == "CSV_Data": return self.csv_data_storage[channel].values
        else: return data_channel_in_file_from_tdms(self.tdms_file, group, channel)

    def on_channel_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        item = self.tree.item(selected[0])
        if not item['values']: return
        g, c = item['values']
        
        # Nastavení aktuálního výběru do GUI prvků
        self.sel_group.set(g)
        self.update_channel_list()
        self.sel_channel.set(c)
        
        data = self.get_data_universal(g, c)
        self.calc_list.selection_clear(0, tk.END)
        self.plot_raw(c, data)

    def get_time_axis(self):
        unit = self.x_unit.get()
        current_time = self.data['time']
        if unit == "Datum a Čas": return current_time, "Datum a čas"
        if unit == "Vzorky": return np.arange(len(current_time)),"Vzorky [-]"    
        diff_seconds = (current_time - current_time[0]) / np.timedelta64(1, 's')
        if unit == "Sekundy": return diff_seconds, "Čas [s]"
        if unit == "Minuty": return diff_seconds / 60, "Čas [min]"
        if unit == "Hodiny": return diff_seconds / 3600, "Čas [h]"
        if unit == "Dny": return diff_seconds / 86400, "Čas [den]"
        return np.arange(len(current_time)), "Osa X"

    def plot_raw(self, name, data):
        self.ax.clear()
        if self.var_show_hist.get():
            # Histogram pro data vybraná z prohlížeče
            self.ax.hist(data, bins=self.var_bins.get(), color='skyblue', edgecolor='black', alpha=0.7)
            self.ax.set_title(f"Histogram rozložení: {name}")
            self.ax.set_xlabel("Amplituda")
            self.ax.set_ylabel("Četnost (vzorky) [-]")
        else:
            x, lab = self.get_time_axis()
            # Ošetření pokud délka vybraného kanálu nesouhlasí s Time osou
            if len(x) != len(data):
                x = np.arange(len(data))
                lab = "Vzorky [-]"
            self.ax.plot(x, data)
            self.ax.set_title(f"Náhled: {name}", pad=20)
            self.ax.set_xlabel(lab)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.fig.tight_layout()
        self.canvas.draw()

    def calculate_fatigue(self, data_cut):
        m = self.var_m.get()
        ziv_s = self.var_ziv_roky.get() * 365 * 24 * 3600
        mez = self.var_mez.get()
        v_suma = np.sum(data_cut[data_cut > mez]**m)
        zivotnost_c = len(data_cut) / (v_suma * ziv_s) if v_suma > 0 else 0
        spotreba = np.where(data_cut <= mez, 0.0, (data_cut**m) * zivotnost_c)
        return spotreba

    def update_plot(self):
        if self.tdms_file is None and not hasattr(self, 'csv_data_storage'): return
        selection = self.calc_list.curselection()
        
        # Pokud není nic vybráno v listboxu, ale je vybrán kanál v tree, aktualizujeme plot_raw
        if not selection:
            if self.sel_channel.get():
                d = self.get_data_universal(self.sel_group.get(), self.sel_channel.get())
                self.plot_raw(self.sel_channel.get(), d)
            return

        idx = selection[0]
        try:
            d_calc = self.get_data_universal(self.sel_group.get(), self.sel_channel.get())
            d_view = self.get_data_universal(self.sel_group_view.get(), self.sel_channel_view.get())    
        except:
            messagebox.showwarning("Varování", "Vyberte platnou skupinu a kanál!")
            return

        try:
            start = int(self.var_range_from.get())
            end = len(d_calc) if self.var_range_to.get() == "end" else int(self.var_range_to.get())
            s = slice(start, end)
            data_cut = d_calc[s]
        except:
            s = slice(0, len(d_calc))
            data_cut = d_calc

        self.ax.clear()
        
        if self.var_show_hist.get():
            self.ax.hist(data_cut, bins=self.var_bins.get(), color='skyblue', edgecolor='black', alpha=0.7)
            self.ax.set_xlabel(self.sel_channel.get())
            self.ax.set_ylabel("Četnost [-]")
            self.ax.set_title(f"Histogram (Biny: {self.var_bins.get()})")
        else:
            x, lab = self.get_time_axis()
            x = x[s]
            if idx == 0:
                self.ax.plot(x, d_calc[s])
                self.ax.set_ylabel(self.sel_channel.get())
                self.ax.set_title("Průběh kanálu pro VÝPOČET")
                self.ax.set_xlabel(lab)

            elif idx == 1:
                self.ax.plot(x, d_view[s])
                self.ax.set_ylabel(self.sel_channel_view.get())
                self.ax.set_title("Průběh kanálu pro ZOBRAZENÍ")
                self.ax.set_xlabel(lab)


            elif idx in [2, 3, 4]:
                spotreba = self.calculate_fatigue(data_cut)

                if idx == 2:
                    self.ax.plot(x, np.cumsum(spotreba))
                    self.ax.set_ylabel("Kumulativní spotřeba životnosti")
                    self.ax.set_xlabel(lab)
                
                elif idx == 3:
                    self.ax.plot(x, spotreba)
                    self.ax.set_ylabel("Spotřeba životnosti")
                    self.ax.set_xlabel(lab)

                elif idx == 4:
                    counts, bins = np.histogram(d_view[s], bins=self.var_bins.get(), weights=spotreba)
                    total = np.sum(spotreba) if np.sum(spotreba) > 0 else 1
                    self.ax.bar(bins[:-1], (counts/total)*100, width=np.diff(bins)*0.9, align='edge')
                    self.ax.set_xlabel(self.sel_channel_view.get())
                    self.ax.set_ylabel("Podíl na spotřebě [%]")


        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.fig.tight_layout()
        self.canvas.draw() 

if __name__ == "__main__":
    root = tk.Tk()
    app = AnalytikaGUI(root)
    root.mainloop()