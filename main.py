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
        # ... (This part is unchanged)
        super().__init__()
        self.title("Vortex Tunnel"); self.geometry("600x700"); self.attributes("-topmost", 0)
        self.theme = "dark"; ctk.set_appearance_mode(self.theme); ctk.set_default_color_theme("blue")
        self.NATHAN_NAME = "Nathan"; self.MAJID_NAME = "Majid"
        self.NATHAN_IP = "100.122.120.65"; self.MAJID_IP = "100.93.161.73"
        self.my_name = None; self.peer_name = None; self.target_ip = None
        self.host_ip_listen = "0.0.0.0"; self.port = 12345
        self.connection = None; self.connected = threading.Event()
        self._create_widgets()
        self.start_server()

    def _create_widgets(self):
        # ... (This part is unchanged)
        top_frame = ctk.CTkFrame(self, height=50); top_frame.pack(side="top", fill="x", padx=10, pady=(10,5))
        self.manual_ip_entry = ctk.CTkEntry(top_frame, placeholder_text="Or enter a manual IP here..."); self.manual_ip_entry.pack(side="left", padx=5, pady=10, expand=True, fill="x")
        profile_options = ["Select Profile", f"Connect to {self.NATHAN_NAME}", f"Connect to {self.MAJID_NAME}", "Local Test (127.0.0.1)"]
        self.profile_menu = ctk.CTkOptionMenu(top_frame, values=profile_options, command=self.profile_selected); self.profile_menu.pack(side="left", padx=5, pady=10)
        self.connect_button = ctk.CTkButton(top_frame, text="Connect", command=self.connect_to_peer); self.connect_button.pack(side="left", padx=5, pady=10)
        status_frame = ctk.CTkFrame(self); status_frame.pack(side="top", fill="x", padx=10, pady=(0,5))
        self.status_label = ctk.CTkLabel(status_frame, text="Status: Disconnected", text_color="red"); self.status_label.pack(side="left", padx=5, pady=5)
        self.theme_button = ctk.CTkButton(status_frame, text="🌙", width=30, command=self.toggle_theme); self.theme_button.pack(side="right", padx=5, pady=5)
        self.topmost_check = ctk.CTkCheckBox(status_frame, text="Always on Top", command=self.toggle_topmost); self.topmost_check.pack(side="right", padx=5, pady=5)
        self.tab_view = ctk.CTkTabview(self); self.tab_view.pack(side="bottom", expand=True, fill="both", padx=10, pady=(0,10))
        self.tab_view.add("Draw"); self.tab_view.add("Chat"); self.tab_view.add("Files")
        self._create_drawing_tab(); self._create_chat_tab(); self._create_files_tab()

    def profile_selected(self, selection):
        # ... (This part is unchanged)
        self.manual_ip_entry.delete(0, tk.END)
        if f"Connect to {self.NATHAN_NAME}" in selection: self.target_ip, self.peer_name = self.NATHAN_IP, self.NATHAN_NAME
        elif f"Connect to {self.MAJID_NAME}" in selection: self.target_ip, self.peer_name = self.MAJID_IP, self.MAJID_NAME
        elif "Local Test" in selection: self.target_ip, self.peer_name = "127.0.0.1", "Localhost"
        else: self.target_ip, self.peer_name = None, None
        if self.target_ip: self.manual_ip_entry.insert(0, self.target_ip); self.update_status(f"Ready to connect to {self.peer_name}", "orange")

    def connect_to_peer(self):
        # ... (This part is unchanged)
        peer_ip = self.manual_ip_entry.get()
        if not peer_ip: messagebox.showerror("Error", "Please select a profile or enter an IP address."); return
        def _connect():
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                client_socket.connect((peer_ip, self.port)); self.connection = client_socket; self.connected.set()
                self.update_status(f"Connected to {peer_ip}", "green"); self.peer_name = "Peer"
                threading.Thread(target=self.receive_data, daemon=True).start()
            except Exception as e: self.update_status(f"Connection failed: {e}", "red")
        threading.Thread(target=_connect, daemon=True).start()

    # --- THE MAIN FIX IS IN THE receive_data FUNCTION BELOW ---

    def receive_data(self):
        buffer = b""  # Use a byte buffer now
        separator = b"\n"
        
        while self.connected.is_set():
            try:
                # Read text commands line-by-line
                chunk = self.connection.recv(1024)
                if not chunk:
                    self.handle_disconnect()
                    break
                buffer += chunk

                while separator in buffer:
                    line_bytes, buffer = buffer.split(separator, 1)
                    line_str = line_bytes.decode('utf-8')

                    # If a file is announced, switch to file receiving mode
                    if line_str.startswith("FILE_INFO:"):
                        _, filename, filesize_str = line_str.split(":", 2)
                        filesize = int(filesize_str)
                        
                        # This function will now handle the ENTIRE file download
                        # It will read the remaining bytes from the buffer and the socket
                        buffer = self._handle_file_reception(filename, filesize, buffer)
                    else:
                        # Otherwise, process as a normal text command
                        self.process_text_command(line_str)

            except (ConnectionResetError, OSError):
                self.handle_disconnect()
                break
            except Exception as e:
                # Catch decoding errors for safety, but the main logic change should prevent them
                print(f"[ERROR] An unexpected error occurred in receive loop: {e}")
                self.handle_disconnect()
                break

    def _handle_file_reception(self, filename, filesize, initial_buffer):
        """
        Handles receiving a file synchronously within the receive_data thread.
        This prevents conflicts over the socket.
        """
        save_path = filedialog.asksaveasfilename(initialfile=filename)
        if not save_path:
            # User cancelled, so we must discard the file data from the socket
            bytes_to_discard = filesize
            # Discard what's already in the buffer
            bytes_to_discard -= len(initial_buffer)
            # Receive and discard the rest from the socket
            while bytes_to_discard > 0:
                chunk = self.connection.recv(min(4096, bytes_to_discard))
                if not chunk: break
                bytes_to_discard -= len(chunk)
            self.file_status_label.configure(text=f"Cancelled receiving {filename}")
            return b"" # Return empty buffer

        bytes_received = 0
        try:
            with open(save_path, 'wb') as f:
                # First, write any file data that was already in our buffer
                if initial_buffer:
                    f.write(initial_buffer)
                    bytes_received += len(initial_buffer)

                # Now, receive the rest of the file from the socket
                while bytes_received < filesize:
                    chunk = self.connection.recv(min(4096, filesize - bytes_received))
                    if not chunk:
                        break # Connection lost
                    f.write(chunk)
                    bytes_received += len(chunk)
                    progress = (bytes_received / filesize) * 100
                    self.file_status_label.configure(text=f"Receiving {os.path.basename(save_path)}: {progress:.2f}%")
            
            if bytes_received == filesize:
                self.file_status_label.configure(text=f"Received and saved: {os.path.basename(save_path)}")
            else:
                self.file_status_label.configure(text="File transfer incomplete.")

        except Exception as e:
            self.file_status_label.configure(text=f"Error receiving file: {e}")
        
        return b"" # Return an empty buffer after handling the file

    def process_text_command(self, data_str):
        """Processes only non-file, text-based commands."""
        try:
            if data_str.startswith("DRAW:"):
                _, coords = data_str.split(":", 1)
                x1, y1, x2, y2, color, size = coords.split(",")
                self.canvas.create_line(int(x1), int(y1), int(x2), int(y2), width=int(size), fill=color, capstyle=tk.ROUND, smooth=tk.TRUE)
            elif data_str.startswith("CHAT:"):
                _, msg = data_str.split(":", 1)
                self.update_chat_box(f"{self.peer_name}: {msg}\n")
            elif data_str.startswith("CLEAR"):
                self.canvas.delete("all")
        except Exception as e:
            print(f"[ERROR] Could not process command '{data_str[:50]}': {e}")
            
    # --- NO OTHER FUNCTIONAL CHANGES BELOW THIS LINE ---
    def send_data(self, data):
        if self.connection and self.connected.is_set():
            try: self.connection.sendall((data + "\n").encode('utf-8'))
            except Exception: self.handle_disconnect()
    def _create_drawing_tab(self):
        draw_tab = self.tab_view.tab("Draw"); controls_frame = ctk.CTkFrame(draw_tab, height=40); controls_frame.pack(fill="x", pady=5); self.color, self.brush_size = "white", 3
        def set_color(c): self.color = c
        ctk.CTkButton(controls_frame, text="Red", command=lambda: set_color("red"), fg_color="red", hover_color="#8B0000").pack(side="left", padx=3); ctk.CTkButton(controls_frame, text="Blue", command=lambda: set_color("blue"), fg_color="blue", hover_color="#00008B").pack(side="left", padx=3); ctk.CTkButton(controls_frame, text="White", command=lambda: set_color("white"), fg_color="white", text_color="black", hover_color="#D3D3D3").pack(side="left", padx=3)
        self.brush_slider = ctk.CTkSlider(controls_frame, from_=1, to=20, command=lambda v: setattr(self, 'brush_size', int(v))); self.brush_slider.set(self.brush_size); self.brush_slider.pack(side="left", padx=10, expand=True, fill="x")
        ctk.CTkButton(controls_frame, text="Clear", command=self.clear_canvas).pack(side="right", padx=5); self.canvas = tk.Canvas(draw_tab, bg="black", highlightthickness=0); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<B1-Motion>", self.draw); self.old_x, self.old_y = None, None
    def _create_chat_tab(self):
        chat_tab = self.tab_view.tab("Chat"); self.chat_box = ctk.CTkTextbox(chat_tab, state="disabled"); self.chat_box.pack(expand=True, fill="both", pady=5); chat_input_frame = ctk.CTkFrame(chat_tab, height=40); chat_input_frame.pack(fill="x")
        self.chat_entry = ctk.CTkEntry(chat_input_frame, placeholder_text="Type your message..."); self.chat_entry.pack(side="left", expand=True, fill="x", padx=5, pady=5); self.chat_entry.bind("<Return>", lambda e: self.send_chat_message())
        ctk.CTkButton(chat_input_frame, text="Send", command=self.send_chat_message).pack(side="right", padx=5, pady=5)
    def _create_files_tab(self):
        files_tab = self.tab_view.tab("Files"); ctk.CTkButton(files_tab, text="Select and Send File", command=self.select_and_send_file).pack(pady=10); self.file_status_label = ctk.CTkLabel(files_tab, text="No file transfers active."); self.file_status_label.pack(pady=10)
    def draw(self, event):
        if self.old_x is not None and self.old_y is not None: self.canvas.create_line(self.old_x, self.old_y, event.x, event.y, width=self.brush_size, fill=self.color, capstyle=tk.ROUND, smooth=tk.TRUE); self.send_data(f"DRAW:{self.old_x},{self.old_y},{event.x},{event.y},{self.color},{self.brush_size}")
        self.old_x, self.old_y = event.x, event.y
    def clear_canvas(self): self.canvas.delete("all"); self.send_data("CLEAR")
    def send_chat_message(self):
        msg = self.chat_entry.get()
        if msg: self.update_chat_box(f"You: {msg}\n"); self.send_data(f"CHAT:{msg}"); self.chat_entry.delete(0, tk.END)
    def update_chat_box(self, message): self.chat_box.configure(state="normal"); self.chat_box.insert(tk.END, message); self.chat_box.configure(state="disabled"); self.chat_box.yview(tk.END)
    def select_and_send_file(self):
        if not self.connected.is_set(): messagebox.showerror("Error", "Must be connected to send a file."); return
        filepath = filedialog.askopenfilename()
        if not filepath: return
        filename, filesize = os.path.basename(filepath), os.path.getsize(filepath); self.send_data(f"FILE_INFO:{filename}:{filesize}"); threading.Thread(target=self.send_file_data, args=(filepath,), daemon=True).start()
    def send_file_data(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(4096): self.connection.sendall(chunk)
            # No status update here, as sender doesn't know if receiver accepted
        except Exception as e: self.file_status_label.configure(text=f"Error sending file: {e}")
    def toggle_theme(self): self.theme = "light" if self.theme == "dark" else "dark"; ctk.set_appearance_mode(self.theme); self.theme_button.configure(text="🌙" if self.theme == "dark" else "☀️")
    def toggle_topmost(self): self.attributes("-topmost", self.topmost_check.get())
    def start_server(self): threading.Thread(target=self._server_thread, daemon=True).start()
    def _server_thread(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM); server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: server.bind((self.host_ip_listen, self.port)); server.listen(1)
        except Exception: return
        if not self.connected.is_set():
            try:
                conn, addr = server.accept(); self.connection = conn; self.connected.set(); self.update_status(f"Connected as Host", "green"); self.peer_name = "Peer"; threading.Thread(target=self.receive_data, daemon=True).start()
            except OSError: pass
        server.close()
    def update_status(self, message, color): self.status_label.configure(text=message, text_color=color)
    def handle_disconnect(self):
        if not self.connected.is_set(): return
        self.connected.clear()
        if self.connection: self.connection.close(); self.connection = None
        self.update_status("Status: Disconnected", "red"); self.profile_menu.set("Select Profile"); self.start_server()
    def on_closing(self):
        if self.connection: self.connection.close()
        self.destroy()

if __name__ == "__main__":
    app = VortexTunnelApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()