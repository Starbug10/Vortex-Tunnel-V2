import customtkinter as ctk
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
import socket
import threading
import os
import json
import uuid
from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

class VortexTunnelApp(ctk.CTkFrame):
    """
    The main application frame containing all UI elements and logic.
    This is placed inside a TkinterDnD root window to handle drag-and-drop.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master

        # --- Profiles & Memory ---
        self.NATHAN_NAME = "Nathan"
        self.MAJID_NAME = "Majid"
        self.NATHAN_IP = "100.122.120.65"
        self.MAJID_IP = "100.93.161.73"
        self.my_name = None
        self.peer_name = None
        self.config_file = "config.json"
        self.chat_history_file = "chat_history.log"
        self.downloads_folder = "Vortex_Downloads"
        os.makedirs(self.downloads_folder, exist_ok=True)

        # --- Networking ---
        self.host_ip_listen = "0.0.0.0"
        self.port = 12345
        self.connection = None
        self.connected = threading.Event()
        
        # --- UI Data Storage ---
        self.chat_messages = {}
        self.file_gallery_items = {}

        # --- UI Initialization ---
        self._create_widgets()
        self.load_config_and_history()

        # --- System Handlers ---
        self.start_server()

    def _create_widgets(self):
        # --- Responsive Grid Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Top Control Bar ---
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        top_frame.grid_columnconfigure(0, weight=1)

        self.ip_entry = ctk.CTkEntry(top_frame, placeholder_text="Enter IP or select a profile...")
        self.ip_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        profile_options = ["Select Profile", f"I am {self.NATHAN_NAME}", f"I am {self.MAJID_NAME}"]
        self.profile_menu = ctk.CTkOptionMenu(top_frame, values=profile_options, command=self.profile_selected)
        self.profile_menu.grid(row=0, column=1, padx=5, pady=5)

        self.connect_button = ctk.CTkButton(top_frame, text="Connect", command=self.connect_to_peer)
        self.connect_button.grid(row=0, column=2, padx=5, pady=5)
        
        self.status_label = ctk.CTkLabel(top_frame, text="Status: Disconnected", text_color="red")
        self.status_label.grid(row=1, column=0, columnspan=3, padx=5, pady=(0,5), sticky="w")

        # --- Tabbed Interface ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=1, column=0, padx=10, pady=(0,10), sticky="nsew")
        self.tab_view.add("Chat")
        self.tab_view.add("Drawing")
        self.tab_view.add("Files")
        self._create_chat_tab()
        self._create_drawing_tab()
        self._create_files_tab()

    def _create_chat_tab(self):
        chat_tab = self.tab_view.tab("Chat")
        chat_tab.grid_columnconfigure(0, weight=1)
        chat_tab.grid_rowconfigure(0, weight=1)

        self.chat_frame = ctk.CTkScrollableFrame(chat_tab)
        self.chat_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.chat_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(self.chat_frame, text="Clear Chat", command=self.confirm_clear_chat).pack(anchor="ne", padx=5, pady=5)
        
        input_frame = ctk.CTkFrame(chat_tab, fg_color="transparent")
        input_frame.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.chat_entry = ctk.CTkEntry(input_frame, placeholder_text="Type a message...")
        self.chat_entry.grid(row=0, column=0, padx=(0,5), sticky="ew")
        self.chat_entry.bind("<Return>", lambda e: self.send_chat_message())
        self.send_button = ctk.CTkButton(input_frame, text="Send", command=self.send_chat_message)
        self.send_button.grid(row=0, column=1)

    def _create_drawing_tab(self):
        draw_tab = self.tab_view.tab("Drawing")
        draw_tab.grid_columnconfigure(0, weight=1)
        draw_tab.grid_rowconfigure(1, weight=1)

        controls = ctk.CTkFrame(draw_tab)
        controls.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.color = "#FFFFFF"
        self.brush_size = 3
        
        ctk.CTkButton(controls, text="Color", command=self.choose_color).pack(side="left", padx=5, pady=5)
        ctk.CTkSlider(controls, from_=1, to=50, command=lambda v: setattr(self, 'brush_size', int(v))).pack(side="left", padx=5, pady=5, expand=True, fill="x")
        ctk.CTkButton(controls, text="Clear Canvas", command=self.clear_canvas).pack(side="right", padx=5, pady=5)
        
        self.pin_button = ctk.CTkButton(controls, text="📌", width=30, command=self.toggle_topmost)
        self.pin_button.pack(side="right", padx=5, pady=5)
        self.is_pinned = False

        self.canvas = tk.Canvas(draw_tab, bg="#1a1a1a", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.old_x, self.old_y = None, None
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.reset_drawing_state)

    def _create_files_tab(self):
        files_tab = self.tab_view.tab("Files")
        files_tab.grid_columnconfigure(0, weight=1)
        files_tab.grid_rowconfigure(0, weight=1)
        
        self.gallery_frame = ctk.CTkScrollableFrame(files_tab, label_text="Sent & Received Files (Drag files here to send)")
        self.gallery_frame.grid(row=0, column=0, sticky="nsew")
        self.gallery_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(self.gallery_frame, text="Clear Gallery", command=lambda: self.send_command("CLEAR_GALLERY")).pack(anchor="ne", padx=5, pady=5)

    def choose_color(self):
        color_code = colorchooser.askcolor(title="Choose color")
        if color_code: self.color = color_code[1]

    def toggle_topmost(self):
        self.is_pinned = not self.is_pinned
        self.master.attributes("-topmost", self.is_pinned)
        self.pin_button.configure(fg_color=("#3b8ed0", "#1f6aa5") if self.is_pinned else ctk.ThemeManager.theme["CTkButton"]["fg_color"])

    def handle_drop(self, event):
        filepath = self.master.tk.splitlist(event.data)[0]
        if self.connected.is_set(): self.send_file(filepath)
        else: messagebox.showerror("Error", "Must be connected to send files.")

    def add_chat_message(self, msg_id, sender, message, is_own):
        if msg_id in self.chat_messages: return
        
        row_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        row_frame.pack(fill="x", padx=5, pady=2)
        row_frame.grid_columnconfigure(1 if is_own else 0, weight=1)

        msg_frame = ctk.CTkFrame(row_frame)
        msg_frame.grid(row=0, column=1 if is_own else 0, sticky="e" if is_own else "w")
        
        ctk.CTkLabel(msg_frame, text=f"{sender}:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 5), pady=5)
        msg_label = ctk.CTkLabel(msg_frame, text=message, wraplength=self.winfo_width() - 250, justify="left")
        msg_label.pack(side="left", padx=5, pady=5, expand=True, fill="x")

        if is_own:
            btn_frame = ctk.CTkFrame(msg_frame, fg_color="transparent")
            btn_frame.pack(side="right", padx=5, pady=5)
            ctk.CTkButton(btn_frame, text="E", width=20, command=lambda id=msg_id: self.edit_chat_prompt(id)).pack()
            ctk.CTkButton(btn_frame, text="X", width=20, command=lambda id=msg_id: self.send_command(f"DELETE_MSG:{id}")).pack(pady=(2,0))
        
        self.chat_messages[msg_id] = row_frame
        self.after(100, self.chat_frame._parent_canvas.yview_moveto, 1.0)

    def send_chat_message(self, msg_id_to_edit=None):
        msg = self.chat_entry.get()
        if not msg or not self.my_name: return
        
        cmd = "EDIT_MSG" if msg_id_to_edit else "CHAT_MSG"
        msg_id = msg_id_to_edit if msg_id_to_edit else str(uuid.uuid4())
        
        self.send_command(f"{cmd}:{msg_id}:{self.my_name}:{msg}")
        self.chat_entry.delete(0, tk.END)
        if msg_id_to_edit: self.send_button.configure(text="Send", command=self.send_chat_message)

    def edit_chat_prompt(self, msg_id):
        frame = self.chat_messages[msg_id].winfo_children()[0]
        original_text = frame.winfo_children()[1].cget("text")
        self.chat_entry.delete(0, tk.END)
        self.chat_entry.insert(0, original_text)
        self.send_button.configure(text="Save", command=lambda: self.send_chat_message(msg_id_to_edit=msg_id))

    def confirm_clear_chat(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to clear the chat history for everyone?"):
            self.send_command("CLEAR_CHAT")

    def add_file_to_gallery(self, file_id, filename, filepath):
        if file_id in self.file_gallery_items: return
        
        frame = ctk.CTkFrame(self.gallery_frame)
        frame.pack(fill="x", padx=5, pady=5, anchor="w")
        
        try:
            img = Image.open(filepath)
            img.thumbnail((64,64))
            thumb_img = ImageTk.PhotoImage(img)
            img_label = ctk.CTkLabel(frame, image=thumb_img, text="")
            img_label.image = thumb_img # Keep a reference
            img_label.pack(side="left", padx=5, pady=5)
        except:
            ctk.CTkLabel(frame, text="FILE", width=64, height=64, fg_color="gray25", corner_radius=6).pack(side="left", padx=5, pady=5)

        ctk.CTkLabel(frame, text=filename, wraplength=self.winfo_width() - 200).pack(side="left", expand=True, fill="x", padx=5)
        ctk.CTkButton(frame, text="X", width=25, command=lambda id=file_id: self.send_command(f"DELETE_FILE:{id}")).pack(side="right", padx=5)
        self.file_gallery_items[file_id] = frame

    def send_file(self, filepath):
        if not filepath or not os.path.exists(filepath): return
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        file_id = str(uuid.uuid4())
        self.send_command(f"FILE_INFO:{file_id}:{filename}:{filesize}")
        threading.Thread(target=self._send_file_data, args=(filepath,), daemon=True).start()
        
        local_path = os.path.join(self.downloads_folder, f"{file_id}_{filename}")
        import shutil
        shutil.copy(filepath, local_path)
        self.add_file_to_gallery(file_id, filename, local_path)

    def _send_file_data(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(4096): self.connection.sendall(chunk)
        except Exception as e: print(f"Error sending file data: {e}")

    def load_config_and_history(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    last_profile = config.get("last_profile")
                    if last_profile and last_profile != "Select Profile":
                        self.profile_menu.set(last_profile)
                        self.profile_selected(last_profile)
                        if messagebox.askyesno("Vortex Tunnel", f"Connect to {self.peer_name} at {self.ip_entry.get()}?"):
                            self.connect_to_peer()
            if os.path.exists(self.chat_history_file):
                with open(self.chat_history_file, 'r') as f:
                    for line in f: self.process_command(line.strip(), from_history=True)
        except Exception as e: print(f"Error loading config: {e}")

    def on_closing(self):
        config = {"last_profile": self.profile_menu.get() if self.my_name else "Select Profile"}
        with open(self.config_file, 'w') as f: json.dump(config, f)
        if self.connection: self.connection.close()
        self.master.destroy()

    def process_command(self, command_str, from_history=False):
        try:
            parts = command_str.split(":", 3)
            cmd = parts[0]
            if cmd == "CHAT_MSG":
                msg_id, sender, message = parts[1], parts[2], parts[3]
                self.add_chat_message(msg_id, sender, message, is_own=(sender == self.my_name))
            elif cmd == "EDIT_MSG":
                msg_id, _, _, new_message = parts
                frame = self.chat_messages[msg_id].winfo_children()[0]
                frame.winfo_children()[1].configure(text=new_message)
            elif cmd == "DELETE_MSG":
                msg_id = command_str.split(":")[1]
                if msg_id in self.chat_messages: self.chat_messages[msg_id].destroy(); del self.chat_messages[msg_id]
            elif cmd == "CLEAR_CHAT":
                for widget in self.chat_messages.values(): widget.destroy()
                self.chat_messages.clear()
            elif cmd == "DRAW":
                _, coords = command_str.split(":", 1)
                x1, y1, x2, y2, color, size = coords.split(",")
                self.canvas.create_line(int(x1), int(y1), int(x2), int(y2), width=float(size), fill=color, capstyle=tk.ROUND, smooth=tk.TRUE)
            elif cmd == "CLEAR": self.canvas.delete("all")
            elif cmd == "DELETE_FILE":
                file_id = command_str.split(":")[1]
                if file_id in self.file_gallery_items: self.file_gallery_items[file_id].destroy(); del self.file_gallery_items[file_id]
            elif cmd == "CLEAR_GALLERY":
                for widget in self.file_gallery_items.values(): widget.destroy()
                self.file_gallery_items.clear()
            
            if not from_history:
                if cmd == "CLEAR_CHAT":
                    open(self.chat_history_file, 'w').close()
                elif cmd in ["CHAT_MSG", "DELETE_MSG", "EDIT_MSG"]:
                    # This history saving is simplified. A robust solution would be more complex.
                    with open(self.chat_history_file, 'a') as f:
                        f.write(command_str + '\n')
        except Exception as e: print(f"Error processing command: {e} -> '{command_str}'")

    def _handle_file_reception(self, file_id, filename, filesize, buffer):
        filepath = os.path.join(self.downloads_folder, f"{file_id}_{filename}")
        bytes_received = 0
        try:
            with open(filepath, 'wb') as f:
                if buffer: f.write(buffer); bytes_received += len(buffer)
                while bytes_received < filesize:
                    chunk = self.connection.recv(min(4096, filesize - bytes_received))
                    if not chunk: break
                    f.write(chunk); bytes_received += len(chunk)
            if bytes_received == filesize: self.add_file_to_gallery(file_id, filename, filepath)
        except Exception as e: print(f"Error receiving file: {e}")
        return b""

    def receive_data(self):
        buffer = b""
        separator = b"\n"
        while self.connected.is_set():
            try:
                chunk = self.connection.recv(4096)
                if not chunk: self.handle_disconnect(); break
                buffer += chunk
                while separator in buffer:
                    line_bytes, buffer = buffer.split(separator, 1)
                    line_str = line_bytes.decode('utf-8', errors='ignore')
                    if line_str.startswith("FILE_INFO:"):
                        _, file_id, filename, filesize_str = line_str.split(":", 3)
                        buffer = self._handle_file_reception(file_id, filename, int(filesize_str), buffer)
                    elif line_str:
                        self.process_command(line_str)
            except Exception: self.handle_disconnect(); break
    
    def send_command(self, data_str):
        if self.connection and self.connected.is_set():
            try: self.connection.sendall((data_str + "\n").encode('utf-8'))
            except Exception: self.handle_disconnect()
    def draw(self, event):
        if self.old_x is not None: self.send_command(f"DRAW:{self.old_x},{self.old_y},{event.x},{event.y},{self.color},{self.brush_size}")
        self.old_x, self.old_y = event.x, event.y
    def reset_drawing_state(self, event): self.old_x, self.old_y = None, None
    def clear_canvas(self): self.send_command("CLEAR")
    def profile_selected(self, selection):
        if f"I am {self.NATHAN_NAME}" in selection: self.my_name, self.peer_name, target_ip = self.NATHAN_NAME, self.MAJID_NAME, self.MAJID_IP
        elif f"I am {self.MAJID_NAME}" in selection: self.my_name, self.peer_name, target_ip = self.MAJID_NAME, self.NATHAN_NAME, self.NATHAN_IP
        else: self.my_name = None; self.peer_name = None; return
        self.ip_entry.delete(0, tk.END)
        self.ip_entry.insert(0, target_ip)
    def connect_to_peer(self):
        peer_ip = self.ip_entry.get()
        if not peer_ip: messagebox.showerror("Error", "IP address is required."); return
        if not self.my_name: messagebox.showerror("Error", "Please select your profile first."); return
        threading.Thread(target=self._connect_thread, args=(peer_ip,), daemon=True).start()
    def _connect_thread(self, peer_ip):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((peer_ip, self.port))
            self.connection = client_socket
            self.connected.set()
            self.update_status(f"Connected to {self.peer_name} ({peer_ip})", "green")
            threading.Thread(target=self.receive_data, daemon=True).start()
        except Exception as e: self.update_status(f"Connection failed: {e}", "red")
    def start_server(self): threading.Thread(target=self._server_thread, daemon=True).start()
    def _server_thread(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: server.bind((self.host_ip_listen, self.port)); server.listen(1)
        except Exception: return
        if not self.connected.is_set():
            try:
                conn, addr = server.accept()
                self.connection = conn
                self.connected.set()
                self.update_status(f"Connected by {addr[0]}", "green")
                threading.Thread(target=self.receive_data, daemon=True).start()
            except OSError: pass
    def update_status(self, message, color): self.status_label.configure(text=message, text_color=color)
    def handle_disconnect(self):
        if not self.connected.is_set(): return
        self.connected.clear()
        if self.connection: self.connection.close(); self.connection = None
        self.update_status("Status: Disconnected", "red")
        self.start_server()

if __name__ == "__main__":
    # --- Main window creation is handled here to resolve library conflicts ---
    root = TkinterDnD.Tk()
    root.title("Vortex Tunnel")
    root.geometry("700x800")
    ctk.set_appearance_mode("dark")

    # The main app is now a frame within the TkinterDnD root window
    app = VortexTunnelApp(master=root)
    app.pack(side="top", fill="both", expand=True)
    
    # Bind DND to the root window and forward to the app's handler
    root.drop_target_register(DND_FILES)
    root.dnd_bind('<<Drop>>', app.handle_drop)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    root.mainloop()
