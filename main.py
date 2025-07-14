import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import socket
import threading
import os
import time

# --- Main Application Class ---
class VortexTunnelApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        print("[DEBUG] Initializing Vortex Tunnel application...")

        # --- Window Setup ---
        self.title("Vortex Tunnel")
        self.geometry("600x700")
        self.attributes("-topmost", 0)

        # --- Theme and Styling ---
        self.theme = "dark"
        ctk.set_appearance_mode(self.theme)
        ctk.set_default_color_theme("blue")

        # --- Pre-configured Profiles ---
        self.NATHAN_NAME = "Nathan"
        self.MAJID_NAME = "Majid"
        self.NATHAN_IP = "100.122.120.65"
        self.MAJID_IP = "100.93.161.73"
        
        self.my_name = None
        self.peer_name = None
        self.target_ip = None

        # --- Networking ---
        self.host_ip_listen = "0.0.0.0"
        self.port = 12345
        self.connection = None
        self.connected = threading.Event()

        # --- UI Initialization ---
        self._create_widgets()

        # --- Start Networking ---
        self.start_server()

    def _create_widgets(self):
        print("[DEBUG] Creating UI widgets...")
        # --- Top Bar for Controls ---
        top_frame = ctk.CTkFrame(self, height=50)
        top_frame.pack(side="top", fill="x", padx=10, pady=5)

        # --- Profile Selection Dropdown ---
        profile_options = ["Select Who You Are", f"I am {self.NATHAN_NAME} (Host)", f"I am {self.MAJID_NAME} (Friend)"]
        self.profile_menu = ctk.CTkOptionMenu(top_frame, values=profile_options, command=self.profile_selected)
        self.profile_menu.pack(side="left", padx=5, pady=10)

        self.connect_button = ctk.CTkButton(top_frame, text="Connect", command=self.connect_to_peer)
        self.connect_button.pack(side="left", padx=5, pady=10)

        self.status_label = ctk.CTkLabel(top_frame, text="Status: Disconnected", text_color="red")
        self.status_label.pack(side="left", padx=5, pady=10)

        # --- Tabbed Interface ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(side="bottom", expand=True, fill="both", padx=10, pady=5)
        self.tab_view.add("Draw")
        self.tab_view.add("Chat")
        self.tab_view.add("Files")

        self._create_drawing_tab()
        self._create_chat_tab()
        self._create_files_tab()

        # --- Settings ---
        self.theme_button = ctk.CTkButton(top_frame, text="🌙", width=30, command=self.toggle_theme)
        self.theme_button.pack(side="right", padx=5)
        self.topmost_check = ctk.CTkCheckBox(top_frame, text="Always on Top", command=self.toggle_topmost)
        self.topmost_check.pack(side="right", padx=5)
        print("[DEBUG] Widgets created successfully.")

    def _create_drawing_tab(self):
        draw_tab = self.tab_view.tab("Draw")
        controls_frame = ctk.CTkFrame(draw_tab, height=40)
        controls_frame.pack(fill="x", pady=5)
        self.color, self.brush_size = "white", 3
        def set_color(c): self.color = c
        ctk.CTkButton(controls_frame, text="Red", command=lambda: set_color("red"), fg_color="red", hover_color="#8B0000").pack(side="left", padx=3)
        ctk.CTkButton(controls_frame, text="Blue", command=lambda: set_color("blue"), fg_color="blue", hover_color="#00008B").pack(side="left", padx=3)
        ctk.CTkButton(controls_frame, text="White", command=lambda: set_color("white"), fg_color="white", text_color="black", hover_color="#D3D3D3").pack(side="left", padx=3)
        self.brush_slider = ctk.CTkSlider(controls_frame, from_=1, to=20, command=lambda v: setattr(self, 'brush_size', int(v))); self.brush_slider.set(self.brush_size)
        self.brush_slider.pack(side="left", padx=10, expand=True, fill="x")
        ctk.CTkButton(controls_frame, text="Clear", command=self.clear_canvas).pack(side="right", padx=5)
        self.canvas = tk.Canvas(draw_tab, bg="black", highlightthickness=0); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<B1-Motion>", self.draw); self.old_x, self.old_y = None, None

    def _create_chat_tab(self):
        chat_tab = self.tab_view.tab("Chat")
        self.chat_box = ctk.CTkTextbox(chat_tab, state="disabled"); self.chat_box.pack(expand=True, fill="both", pady=5)
        chat_input_frame = ctk.CTkFrame(chat_tab, height=40); chat_input_frame.pack(fill="x")
        self.chat_entry = ctk.CTkEntry(chat_input_frame, placeholder_text="Type your message..."); self.chat_entry.pack(side="left", expand=True, fill="x", padx=5, pady=5)
        self.chat_entry.bind("<Return>", lambda e: self.send_chat_message())
        ctk.CTkButton(chat_input_frame, text="Send", command=self.send_chat_message).pack(side="right", padx=5, pady=5)

    def _create_files_tab(self):
        files_tab = self.tab_view.tab("Files")
        ctk.CTkButton(files_tab, text="Select and Send File", command=self.select_and_send_file).pack(pady=10)
        self.file_status_label = ctk.CTkLabel(files_tab, text="No file transfers active."); self.file_status_label.pack(pady=10)
        
    def profile_selected(self, selection):
        print(f"[DEBUG] Profile selected: '{selection}'")
        if f"I am {self.NATHAN_NAME}" in selection:
            self.my_name, self.peer_name = self.NATHAN_NAME, self.MAJID_NAME
            self.target_ip = self.MAJID_IP
            self.update_status(f"Ready to connect to {self.peer_name}", "orange")
        elif f"I am {self.MAJID_NAME}" in selection:
            self.my_name, self.peer_name = self.MAJID_NAME, self.NATHAN_NAME
            self.target_ip = self.NATHAN_IP
            self.update_status(f"Ready to connect to {self.peer_name}", "orange")
        else:
            self.my_name, self.peer_name, self.target_ip = None, None, None
            self.update_status("Status: Disconnected", "red")
        print(f"[DEBUG] My Name: {self.my_name}, Peer Name: {self.peer_name}, Target IP: {self.target_ip}")

    def draw(self, event):
        if self.old_x and self.old_y:
            self.canvas.create_line(self.old_x, self.old_y, event.x, event.y, width=self.brush_size, fill=self.color, capstyle=tk.ROUND, smooth=tk.TRUE)
            self.send_data(f"DRAW:{self.old_x},{self.old_y},{event.x},{event.y},{self.color},{self.brush_size}")
        self.old_x, self.old_y = event.x, event.y
    
    def clear_canvas(self):
        print("[DEBUG] Clearing local canvas and sending CLEAR command.")
        self.canvas.delete("all"); self.send_data("CLEAR")

    def send_chat_message(self):
        if not self.my_name: messagebox.showerror("Error", "Please select your profile first!"); return
        msg = self.chat_entry.get()
        if msg:
            self.update_chat_box(f"{self.my_name} (You): {msg}\n")
            self.send_data(f"CHAT:{msg}"); self.chat_entry.delete(0, tk.END)
    
    def update_chat_box(self, message):
        self.chat_box.configure(state="normal"); self.chat_box.insert(tk.END, message)
        self.chat_box.configure(state="disabled"); self.chat_box.yview(tk.END)

    def select_and_send_file(self):
        if not self.connected.is_set(): messagebox.showerror("Error", "Must be connected to send a file."); return
        filepath = filedialog.askopenfilename()
        if not filepath: print("[DEBUG] File selection cancelled."); return
        filename, filesize = os.path.basename(filepath), os.path.getsize(filepath)
        print(f"[DEBUG] Preparing to send file: {filename} ({filesize} bytes)")
        self.send_data(f"FILE_INFO:{filename}:{filesize}")
        threading.Thread(target=self.send_file_data, args=(filepath,), daemon=True).start()

    def send_file_data(self, filepath):
        print(f"[DEBUG] Starting file send thread for {filepath}")
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(4096): self.connection.sendall(chunk)
            print(f"[DEBUG] Finished sending file: {os.path.basename(filepath)}")
            self.file_status_label.configure(text=f"Sent: {os.path.basename(filepath)}")
        except Exception as e:
            print(f"[DEBUG] ERROR sending file: {e}")
            self.file_status_label.configure(text=f"Error sending file: {e}")

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"; ctk.set_appearance_mode(self.theme)
        self.theme_button.configure(text="🌙" if self.theme == "dark" else "☀️")

    def toggle_topmost(self): self.attributes("-topmost", self.topmost_check.get())

    def start_server(self):
        print("[DEBUG] Starting server thread...")
        threading.Thread(target=self._server_thread, daemon=True).start()

    def _server_thread(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((self.host_ip_listen, self.port))
            server.listen(1)
            print(f"[DEBUG] Server is now listening on {self.host_ip_listen}:{self.port}")
        except Exception as e:
            print(f"[DEBUG] SERVER BIND ERROR: {e}"); return
        
        while not self.connected.is_set():
            try:
                conn, addr = server.accept()
                print(f"[DEBUG] Accepted connection from {addr[0]}:{addr[1]}")
                if not self.connected.is_set():
                    self.connection = conn; self.connected.set()
                    self.update_status(f"Connected to {addr[0]}", "green")
                    threading.Thread(target=self.receive_data, daemon=True).start()
                    break
            except OSError: print("[DEBUG] Server socket closed."); break
        print("[DEBUG] Server listening loop has ended.")
        server.close()

    def connect_to_peer(self):
        if not self.target_ip: messagebox.showerror("Error", "Please select your profile first."); return
        print(f"[DEBUG] Attempting to connect to peer at {self.target_ip}:{self.port}")
        def _connect():
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                client_socket.connect((self.target_ip, self.port))
                self.connection = client_socket; self.connected.set()
                print(f"[DEBUG] Connection to {self.target_ip} successful.")
                self.update_status(f"Connected to {self.peer_name} ({self.target_ip})", "green")
                threading.Thread(target=self.receive_data, daemon=True).start()
            except Exception as e:
                print(f"[DEBUG] CONNECTION FAILED to {self.target_ip}: {e}")
                self.update_status(f"Connection failed: {e}", "red")
        threading.Thread(target=_connect, daemon=True).start()

    def send_data(self, data):
        if self.connection and self.connected.is_set():
            try:
                print(f"[DEBUG] SENDING: {data[:100]}") # Log first 100 chars
                self.connection.sendall((data + "\n").encode('utf-8'))
            except Exception as e:
                print(f"[DEBUG] SEND ERROR: {e}"); self.handle_disconnect()
        else: print(f"[DEBUG] SEND FAILED: No active connection.")

    def receive_data(self):
        print("[DEBUG] Receive thread started. Waiting for data...")
        buffer = ""
        while self.connected.is_set():
            try:
                data = self.connection.recv(1024)
                if not data: print("[DEBUG] Receive returned empty bytes. Peer likely closed connection."); self.handle_disconnect(); break
                decoded_data = data.decode('utf-8')
                print(f"[DEBUG] RECEIVED RAW: {decoded_data[:100]}")
                buffer += decoded_data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line: print(f"[DEBUG] PROCESSING LINE: {line[:100]}"); self.process_received_data(line)
            except (ConnectionResetError, OSError) as e: print(f"[DEBUG] Connection error in receive loop: {e}"); self.handle_disconnect(); break
            except Exception as e: print(f"[DEBUG] UNEXPECTED error in receive loop: {e}"); self.handle_disconnect(); break
        print("[DEBUG] Receive thread has ended.")

    def process_received_data(self, data):
        try:
            if data.startswith("DRAW:"):
                _, coords = data.split(":", 1)
                x1, y1, x2, y2, color, size = coords.split(",")
                self.canvas.create_line(int(x1), int(y1), int(x2), int(y2), width=int(size), fill=color, capstyle=tk.ROUND, smooth=tk.TRUE)
            elif data.startswith("CHAT:"):
                _, msg = data.split(":", 1)
                self.update_chat_box(f"{self.peer_name}: {msg}\n")
            elif data.startswith("CLEAR"):
                print("[DEBUG] Received CLEAR command. Clearing canvas.")
                self.canvas.delete("all")
            elif data.startswith("FILE_INFO:"):
                _, filename, filesize_str = data.split(":", 2)
                print(f"[DEBUG] Received FILE_INFO: name={filename}, size={filesize_str}")
                self.receive_file(filename, int(filesize_str))
        except Exception as e:
            print(f"[DEBUG] ERROR processing received data '{data[:100]}': {e}")

    def receive_file(self, filename, filesize):
        save_path = filedialog.asksaveasfilename(initialfile=filename)
        if not save_path:
            print("[DEBUG] User cancelled file save. Consuming file data from socket to clear buffer.")
            bytes_to_read = filesize
            while bytes_to_read > 0:
                chunk = self.connection.recv(min(4096, bytes_to_read))
                if not chunk: break
                bytes_to_read -= len(chunk)
            self.file_status_label.configure(text=f"Cancelled receiving {filename}")
            return
        print(f"[DEBUG] Starting file receive thread to save as {save_path}")
        threading.Thread(target=self._file_receiver_thread, args=(save_path, filesize,), daemon=True).start()

    def _file_receiver_thread(self, save_path, filesize):
        try:
            bytes_received = 0
            with open(save_path, 'wb') as f:
                while bytes_received < filesize:
                    chunk = self.connection.recv(min(4096, filesize - bytes_received))
                    if not chunk: print("[DEBUG] File socket closed prematurely by peer."); break
                    f.write(chunk); bytes_received += len(chunk)
                    progress = (bytes_received / filesize) * 100
                    self.file_status_label.configure(text=f"Receiving {os.path.basename(save_path)}: {progress:.2f}%")
            if bytes_received == filesize:
                print(f"[DEBUG] File received successfully and saved to {save_path}")
                self.file_status_label.configure(text=f"Received and saved: {os.path.basename(save_path)}")
            else:
                 print(f"[DEBUG] File transfer incomplete. Expected {filesize}, got {bytes_received}")
                 self.file_status_label.configure(text=f"File transfer incomplete.")
        except Exception as e:
            print(f"[DEBUG] ERROR receiving file: {e}")
            self.file_status_label.configure(text=f"Error receiving file: {e}")

    def update_status(self, message, color):
        self.status_label.configure(text=message, text_color=color)

    def handle_disconnect(self):
        if not self.connected.is_set(): return # Avoid multiple disconnect calls
        print("[DEBUG] Handling disconnection...")
        self.connected.clear()
        if self.connection:
            self.connection.close(); self.connection = None
        self.update_status("Status: Disconnected", "red")
        self.profile_menu.set("Select Who You Are")
        print("[DEBUG] Disconnection handled. Restarting server to listen for new connections.")
        self.start_server()

    def on_closing(self):
        print("[DEBUG] Close button clicked. Shutting down.")
        if self.connection: self.connection.close()
        self.destroy()

if __name__ == "__main__":
    app = VortexTunnelApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
    print("[DEBUG] Application has been closed.")