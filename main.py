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
import base64
import time
import requests
import webbrowser
import sys

# --- Custom Tooltip Class ---
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        if self.tooltip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip_window, text=self.text, justify='left',
                         background="#2b2b2b", relief='solid', borderwidth=1,
                         font=("Arial", "10", "normal"), fg="white")
        label.pack(ipadx=1)

    def hide_tooltip(self, event):
        if self.tooltip_window: self.tooltip_window.destroy()
        self.tooltip_window = None

# --- Custom Dialogs ---
class FileAcceptDialog(ctk.CTkToplevel):
    def __init__(self, master, filename, filesize, callback):
        super().__init__(master)
        self.callback = callback
        self.title("Incoming File")
        self.geometry("400x200")
        self.transient(master); self.grab_set()
        file_type = os.path.splitext(filename)[1].upper()[1:] or "Unknown"
        size_mb = filesize / (1024 * 1024)
        info_text = f"Name: {filename}\nType: {file_type}\nSize: {size_mb:.2f} MB"
        ctk.CTkLabel(self, text="Incoming File Transfer Request", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        ctk.CTkLabel(self, text=info_text, justify="left").pack(pady=10)
        button_frame = ctk.CTkFrame(self, fg_color="transparent"); button_frame.pack(pady=10)
        ctk.CTkButton(button_frame, text="Accept", command=self.accept).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="Decline", command=self.decline, fg_color="#D32F2F", hover_color="#B71C1C").pack(side="left", padx=10)

    def accept(self): self.destroy(); self.callback(True)
    def decline(self): self.destroy(); self.callback(False)

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, app_instance):
        super().__init__(master)
        self.app = app_instance
        self.title("Settings")
        self.geometry("400x300")
        self.transient(master); self.grab_set()
        ctk.CTkLabel(self, text="Vortex Tunnel Settings", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)
        info_frame = ctk.CTkFrame(self); info_frame.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(info_frame, text=f"Version: {self.app.CURRENT_VERSION}").pack(anchor="w", padx=10)
        ctk.CTkLabel(info_frame, text=f"My Name: {self.app.my_name or 'Not Selected'}").pack(anchor="w", padx=10)
        ctk.CTkLabel(info_frame, text=f"Peer Name: {self.app.peer_name or 'Not Connected'}").pack(anchor="w", padx=10)
        self.update_button = ctk.CTkButton(self, text="Check for Updates", command=self.check_for_updates)
        self.update_button.pack(pady=10)
        ctk.CTkButton(self, text="Close", command=self.destroy).pack(pady=10)

    def check_for_updates(self):
        self.update_button.configure(text="Checking...", state="disabled")
        threading.Thread(target=self._update_thread, daemon=True).start()

    def _update_thread(self):
        try:
            version_url = "https://raw.githubusercontent.com/Starbug10/Vortex-Tunnel-V2/main/version.json"
            response = requests.get(version_url, timeout=10)
            response.raise_for_status()
            latest_info = response.json()
            latest_version = latest_info["latest_version"]

            if latest_version > self.app.CURRENT_VERSION:
                if messagebox.askyesno("Update Available", f"A new version ({latest_version}) is available. Would you like to download it?"):
                    self.download_and_run_update(latest_info)
            else:
                messagebox.showinfo("No Update", "You are on the latest version of Vortex Tunnel.")
        except Exception as e:
            messagebox.showerror("Update Error", f"Could not check for updates. Please check your internet connection.\n\nError: {e}")
        finally:
            self.update_button.configure(text="Check for Updates", state="normal")

    def download_and_run_update(self, latest_info):
        try:
            release_tag = latest_info["release_tag"]
            asset_name = latest_info["asset_name"]
            download_url = f"https://github.com/Starbug10/Vortex-Tunnel-V2/releases/download/{release_tag}/{asset_name}"
            download_path = os.path.join(os.path.expanduser("~"), "Downloads", asset_name)
            
            self.update_button.configure(text="Downloading...")
            with requests.get(download_url, stream=True) as r:
                r.raise_for_status()
                with open(download_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            
            if messagebox.askyesno("Download Complete", f"Update downloaded to:\n{download_path}\n\nWould you like to run it now? (This will close the current app)"):
                os.startfile(download_path)
                self.app.on_closing(force_close=True)
        except Exception as e:
            messagebox.showerror("Download Error", f"Failed to download the update.\n\nError: {e}")

# --- Main Application ---
class VortexTunnelApp(ctk.CTkFrame):
    CURRENT_VERSION = "0.0.1"
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.master = master
        app_data_dir = os.path.join(os.getenv('APPDATA'), 'Vortex Tunnel V3')
        os.makedirs(app_data_dir, exist_ok=True)
        self.NATHAN_NAME, self.MAJID_NAME = "Nathan", "Majid"
        self.NATHAN_IP, self.MAJID_IP = "100.122.120.65", "100.93.161.73"
        self.my_name, self.peer_name = None, None
        self.config_file = os.path.join(app_data_dir, "config.json")
        self.chat_history_file = os.path.join(app_data_dir, "chat_history.log")
        self.downloads_folder = os.path.join(app_data_dir, "Vortex_Downloads")
        os.makedirs(self.downloads_folder, exist_ok=True)
        self.host_ip_listen, self.port = "0.0.0.0", 12345
        self.connection, self.connected = None, threading.Event()
        self.pending_transfers, self.chat_messages, self.file_gallery_items = {}, {}, {}
        self._create_widgets()
        self.load_config_and_history()
        self.start_server()

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        top_frame = ctk.CTkFrame(self); top_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.ip_entry = ctk.CTkEntry(top_frame, placeholder_text="Enter IP to connect..."); self.ip_entry.pack(side="left", padx=5, pady=5, expand=True, fill="x")
        self.connect_button = ctk.CTkButton(top_frame, text="Connect", command=self.connect_to_peer); self.connect_button.pack(side="left", padx=5, pady=5)
        self.settings_button = ctk.CTkButton(top_frame, text="⚙️", width=30, command=self.open_settings); self.settings_button.pack(side="left", padx=5, pady=5)
        self.pin_button = ctk.CTkButton(top_frame, text="📌", width=30, command=self.toggle_topmost); self.pin_button.pack(side="left", padx=5, pady=5); self.is_pinned = False
        self.tab_view = ctk.CTkTabview(self); self.tab_view.grid(row=1, column=0, padx=10, pady=(0,10), sticky="nsew")
        self.tab_view.add("Chat"); self.tab_view.add("Drawing"); self.tab_view.add("Files")
        self._create_chat_tab(); self._create_drawing_tab(); self._create_files_tab()
        bottom_frame = ctk.CTkFrame(self); bottom_frame.grid(row=2, column=0, padx=10, pady=(0,10), sticky="ew")
        profile_options = ["Select Profile", f"I am {self.NATHAN_NAME}", f"I am {self.MAJID_NAME}"]
        self.profile_menu = ctk.CTkOptionMenu(bottom_frame, values=profile_options, command=self.profile_selected); self.profile_menu.pack(side="left", padx=5, pady=5)
        self.status_label = ctk.CTkLabel(bottom_frame, text="Status: Disconnected", text_color="red"); self.status_label.pack(side="left", padx=10, pady=5)

    def _create_chat_tab(self):
        chat_tab = self.tab_view.tab("Chat")
        chat_tab.grid_columnconfigure(0, weight=1); chat_tab.grid_rowconfigure(0, weight=1)
        self.chat_frame = ctk.CTkScrollableFrame(chat_tab); self.chat_frame.grid(row=0, column=0, sticky="nsew")
        input_frame = ctk.CTkFrame(chat_tab, fg_color="transparent"); input_frame.grid(row=1, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        self.chat_entry = ctk.CTkEntry(input_frame, placeholder_text="Type a message or drag a file here..."); self.chat_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.chat_entry.bind("<Return>", lambda e: self.send_chat_message())
        self.send_button = ctk.CTkButton(input_frame, text="Send", command=self.send_chat_message); self.send_button.grid(row=0, column=1, padx=5, pady=5)

    def _create_drawing_tab(self):
        draw_tab = self.tab_view.tab("Drawing")
        draw_tab.grid_columnconfigure(0, weight=1); draw_tab.grid_rowconfigure(1, weight=1)
        controls = ctk.CTkFrame(draw_tab); controls.grid(row=0, column=0, sticky="ew")
        self.color, self.brush_size = "#FFFFFF", 3
        ctk.CTkButton(controls, text="Color", command=self.choose_color).pack(side="left", padx=5, pady=5)
        ctk.CTkSlider(controls, from_=1, to=50, command=lambda v: setattr(self, 'brush_size', int(v))).pack(side="left", expand=True, fill="x")
        ctk.CTkButton(controls, text="Clear Canvas", command=self.clear_canvas).pack(side="right", padx=5, pady=5)
        self.canvas = tk.Canvas(draw_tab, bg="#1a1a1a", highlightthickness=0); self.canvas.grid(row=1, column=0, sticky="nsew")
        self.old_x, self.old_y = None, None
        self.canvas.bind("<B1-Motion>", self.draw); self.canvas.bind("<ButtonRelease-1>", self.reset_drawing_state)

    def _create_files_tab(self):
        files_tab = self.tab_view.tab("Files")
        files_tab.grid_columnconfigure(0, weight=1); files_tab.grid_rowconfigure(0, weight=1)
        self.gallery_frame = ctk.CTkScrollableFrame(files_tab, label_text="Shared File Gallery")
        self.gallery_frame.grid(row=0, column=0, sticky="nsew")

    def open_settings(self): SettingsDialog(self.master, self)
    def choose_color(self): color_code = colorchooser.askcolor(title="Choose color"); self.color = color_code[1] if color_code else self.color
    def toggle_topmost(self): self.is_pinned = not self.is_pinned; self.master.attributes("-topmost", self.is_pinned); self.pin_button.configure(fg_color=("#3b8ed0", "#1f6aa5") if self.is_pinned else ctk.ThemeManager.theme["CTkButton"]["fg_color"])
    def handle_drop(self, event): filepath = self.master.tk.splitlist(event.data)[0]; self.send_file(filepath)
    
    def add_chat_message(self, msg_id, sender, message, is_own, is_file=False, file_info=None):
        if msg_id in self.chat_messages: return
        row_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent"); row_frame.pack(fill="x", padx=5, pady=2)
        row_frame.grid_columnconfigure(1 if is_own else 0, weight=1)
        msg_frame = ctk.CTkFrame(row_frame); msg_frame.grid(row=0, column=1 if is_own else 0, sticky="e" if is_own else "w")
        ctk.CTkLabel(msg_frame, text=f"{sender}:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 5), pady=5)
        if is_file:
            file_frame = ctk.CTkFrame(msg_frame, fg_color="gray20"); file_frame.pack(side="left", padx=5, pady=5)
            ctk.CTkLabel(file_frame, text=f"📄 {file_info['name']}").pack(anchor="w")
            ctk.CTkLabel(file_frame, text=f"Size: {file_info['size']:.2f} MB", font=("Arial", 9)).pack(anchor="w")
        else:
            msg_label = ctk.CTkLabel(msg_frame, text=message, wraplength=self.winfo_width() - 250, justify="left"); msg_label.pack(side="left", padx=5, pady=5, expand=True, fill="x")
        if is_own and not is_file:
            btn_frame = ctk.CTkFrame(msg_frame, fg_color="transparent"); btn_frame.pack(side="right", padx=5, pady=5)
            ctk.CTkButton(btn_frame, text="✏️", width=20, command=lambda id=msg_id: self.edit_chat_prompt(id)).pack()
            ctk.CTkButton(btn_frame, text="🗑️", width=20, command=lambda id=msg_id: self.send_command(f"DELETE_MSG:{id}")).pack(pady=(2,0))
        self.chat_messages[msg_id] = row_frame
        self.after(100, self.chat_frame._parent_canvas.yview_moveto, 1.0)

    def send_chat_message(self, msg_id_to_edit=None):
        msg = self.chat_entry.get();
        if not msg or not self.my_name: return
        cmd = "EDIT_MSG" if msg_id_to_edit else "CHAT_MSG"
        msg_id = msg_id_to_edit if msg_id_to_edit else str(uuid.uuid4())
        full_command = f"{cmd}:{msg_id}:{self.my_name}:{msg}"
        self.send_command(full_command); self.process_command(full_command)
        self.chat_entry.delete(0, tk.END)
        if msg_id_to_edit: self.send_button.configure(text="Send", command=self.send_chat_message)

    def edit_chat_prompt(self, msg_id):
        frame = self.chat_messages[msg_id].winfo_children()[0]
        original_text = frame.winfo_children()[1].cget("text")
        self.chat_entry.delete(0, tk.END); self.chat_entry.insert(0, original_text)
        self.send_button.configure(text="Save", command=lambda: self.send_chat_message(msg_id_to_edit=msg_id))

    def confirm_clear_chat(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to clear the chat history for everyone?"): self.send_command("CLEAR_CHAT")

    def add_file_to_gallery(self, file_id, filename, filepath):
        if file_id in self.file_gallery_items: return
        frame = ctk.CTkFrame(self.gallery_frame); frame.pack(fill="x", padx=5, pady=5, anchor="w")
        try:
            img = Image.open(filepath); img.thumbnail((64,64)); thumb_img = ImageTk.PhotoImage(img)
            img_label = ctk.CTkLabel(frame, image=thumb_img, text=""); img_label.image = thumb_img; img_label.pack(side="left", padx=5, pady=5)
        except: ctk.CTkLabel(frame, text="FILE", width=64, height=64, fg_color="gray25", corner_radius=6).pack(side="left", padx=5, pady=5)
        info_text = f"{filename}\nType: {os.path.splitext(filename)[1].upper()[1:] or 'Unknown'}\nSize: {os.path.getsize(filepath) / (1024*1024):.2f} MB"
        Tooltip(frame, info_text)
        ctk.CTkLabel(frame, text=filename, wraplength=self.winfo_width() - 200).pack(side="left", expand=True, fill="x", padx=5)
        ctk.CTkButton(frame, text="Download", command=lambda id=file_id, name=filename: self.request_file_download(id, name)).pack(side="right", padx=5)
        self.file_gallery_items[file_id] = frame

    def send_file(self, filepath):
        if not filepath or not os.path.exists(filepath): return
        self.update_status(f"Requesting to send {os.path.basename(filepath)}...", "orange")
        filename, filesize = os.path.basename(filepath), os.path.getsize(filepath)
        file_id = str(uuid.uuid4())
        
        self.pending_transfers[file_id] = {"filepath": filepath}
        self.send_command(f"FILE_REQUEST:{file_id}:{filename}:{filesize}")

    def _send_file_data(self, file_id):
        if file_id not in self.pending_transfers: return
        filepath = self.pending_transfers[file_id]['filepath']
        try:
            self.send_command(f"FILE_START_TRANSFER:{file_id}:{os.path.basename(filepath)}:{os.path.getsize(filepath)}")
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192): self.connection.sendall(chunk)
            self.update_status(f"Successfully sent {os.path.basename(filepath)}", "green")
        except Exception as e: print(f"Error sending file data: {e}"); self.update_status(f"Failed to send file", "red")
        finally: 
            if file_id in self.pending_transfers:
                del self.pending_transfers[file_id]

    def request_file_download(self, file_id, filename):
        save_path = filedialog.asksaveasfilename(initialfile=filename, title="Save File As")
        if save_path:
            self.pending_transfers[file_id] = {"save_path": save_path}
            self.send_command(f"REQUEST_DOWNLOAD:{file_id}")

    def load_config_and_history(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f: config = json.load(f)
                last_profile = config.get("last_profile")
                if last_profile and last_profile != "Select Profile":
                    self.profile_menu.set(last_profile); self.profile_selected(last_profile)
                    if messagebox.askyesno("Vortex Tunnel", f"Connect to {self.peer_name} at {self.ip_entry.get()}?"): self.connect_to_peer()
            if os.path.exists(self.chat_history_file):
                with open(self.chat_history_file, 'r') as f:
                    for line in f: self.process_command(line.strip(), from_history=True)
        except Exception as e: print(f"Error loading config: {e}")

    def on_closing(self, force_close=False):
        if not force_close:
            config = {"last_profile": self.profile_menu.get() if self.my_name else "Select Profile"}
            with open(self.config_file, 'w') as f: json.dump(config, f)
        if self.connection: self.connection.close()
        self.master.destroy()
        sys.exit()

    def process_command(self, command_str, from_history=False):
        try:
            cmd = command_str.split(":", 1)[0]
            if cmd == "CHAT_MSG": _, msg_id, sender, message = command_str.split(":", 3); self.add_chat_message(msg_id, sender, message, is_own=(sender == self.my_name))
            elif cmd == "EDIT_MSG": _, msg_id, _, new_message = command_str.split(":", 3); self.chat_messages[msg_id].winfo_children()[0].winfo_children()[1].configure(text=new_message)
            elif cmd == "DELETE_MSG": _, msg_id = command_str.split(":", 1); self.chat_messages[msg_id].destroy(); del self.chat_messages[msg_id]
            elif cmd == "CLEAR_CHAT": [w.destroy() for w in self.chat_messages.values()]; self.chat_messages.clear()
            elif cmd == "DRAW": _, coords = command_str.split(":", 1); x1, y1, x2, y2, color, size = coords.split(","); self.canvas.create_line(int(x1), int(y1), int(x2), int(y2), width=float(size), fill=color, capstyle=tk.ROUND, smooth=tk.TRUE)
            elif cmd == "CLEAR": self.canvas.delete("all")
            elif cmd == "FILE_REQUEST": _, file_id, filename, filesize = command_str.split(":", 3); FileAcceptDialog(self, filename, int(filesize), lambda accept: self.handle_file_decision(accept, file_id, filename, int(filesize)))
            elif cmd == "FILE_ACCEPT": _, file_id = command_str.split(":", 1); threading.Thread(target=self._send_file_data, args=(file_id,), daemon=True).start()
            elif cmd == "FILE_REJECT": self.update_status("File transfer rejected by peer.", "orange")
            elif cmd == "ADD_TO_GALLERY": _, file_id, filename = command_str.split(":", 2); local_path = os.path.join(self.downloads_folder, f"{file_id}_{filename}"); self.add_file_to_gallery(file_id, filename, local_path)
            elif cmd == "REQUEST_DOWNLOAD": _, file_id = command_str.split(":", 1); self._send_file_data(file_id)
            elif cmd == "DELETE_FILE": _, file_id = command_str.split(":", 1); self.file_gallery_items[file_id].destroy(); del self.file_gallery_items[file_id]
            elif cmd == "CLEAR_GALLERY": [w.destroy() for w in self.file_gallery_items.values()]; self.file_gallery_items.clear()
            
            if not from_history: self.notify_user()
            if not from_history and cmd in ["CHAT_MSG", "EDIT_MSG", "DELETE_MSG", "CLEAR_CHAT", "ADD_TO_GALLERY"]:
                with open(self.chat_history_file, 'a' if cmd != "CLEAR_CHAT" else 'w') as f:
                    if cmd != "CLEAR_CHAT": f.write(command_str + '\n')
        except Exception as e: print(f"Error processing command: {e} -> '{command_str}'")

    def handle_file_decision(self, accepted, file_id, filename, filesize):
        if accepted: self.send_command(f"FILE_ACCEPT:{file_id}")
        else: self.send_command(f"FILE_REJECT:{file_id}")

    def receive_data(self):
        buffer = b""
        separator = b"\n"

        while self.connected.is_set():
            try:
                # Read data from the socket
                chunk = self.connection.recv(8192)
                if not chunk:
                    self.handle_disconnect()
                    break
                
                buffer += chunk

                # Process all newline-separated commands in the buffer
                while separator in buffer:
                    command_bytes, buffer = buffer.split(separator, 1)
                    command_str = command_bytes.decode('utf-8', errors='ignore').strip()

                    if not command_str:
                        continue

                    # Check if a file transfer is starting
                    if command_str.startswith("FILE_START_TRANSFER"):
                        try:
                            # --- DEDICATED FILE RECEIVING LOGIC ---
                            _, file_id, filename, filesize_str = command_str.split(":", 3)
                            filesize = int(filesize_str)
                            self.update_status(f"Receiving {filename}...", "orange")
                            
                            # Ask user where to save the file
                            save_path = filedialog.asksaveasfilename(
                                initialfile=filename,
                                title=f"Save Received File: {filename}"
                            )

                            if not save_path:
                                # User cancelled. We must discard the incoming file data to keep the connection synced.
                                self.update_status(f"Cancelled receiving {filename}", "orange")
                                bytes_to_discard = filesize
                                # Discard any data already in the buffer
                                if len(buffer) > 0:
                                    discarded_now = min(len(buffer), bytes_to_discard)
                                    buffer = buffer[discarded_now:]
                                    bytes_to_discard -= discarded_now
                                # Discard the rest from the socket
                                while bytes_to_discard > 0:
                                    discard_chunk = self.connection.recv(min(8192, bytes_to_discard))
                                    if not discard_chunk:
                                        self.handle_disconnect()
                                        return
                                    bytes_to_discard -= len(discard_chunk)
                                continue # Go back to processing commands

                            # User accepted, receive the file in a dedicated loop
                            bytes_received = 0
                            with open(save_path, 'wb') as f:
                                # First, write any file data that was already in our buffer
                                if len(buffer) > 0:
                                    data_to_write = buffer[:filesize]
                                    f.write(data_to_write)
                                    bytes_received += len(data_to_write)
                                    buffer = buffer[filesize:] # Keep any data that came after the file

                                # Now, receive the rest of the file from the socket
                                while bytes_received < filesize:
                                    remaining = filesize - bytes_received
                                    file_chunk = self.connection.recv(min(8192, remaining))
                                    if not file_chunk:
                                        self.handle_disconnect()
                                        return
                                    f.write(file_chunk)
                                    bytes_received += len(file_chunk)
                            
                            # --- FILE TRANSFER COMPLETE ---
                            self.update_status(f"Successfully received {filename}", "green")
                            self.send_command(f"ADD_TO_GALLERY:{file_id}:{filename}")
                            self.add_file_to_gallery(file_id, filename, save_path)

                        except Exception as e:
                            print(f"Error during file transfer: {e}")
                            self.update_status("File transfer failed.", "red")
                            # If something went wrong, the connection state is unknown, so it's safest to disconnect
                            self.handle_disconnect()
                            break
                    
                    else:
                        # It's a regular command, process it
                        self.process_command(command_str)

            except Exception as e:
                print(f"Receive loop error: {e}")
                self.handle_disconnect()
                break

    def send_command(self, data_str):
        if self.connection and self.connected.is_set():
            try: self.connection.sendall((data_str + "\n").encode('utf-8'))
            except Exception: self.handle_disconnect()

    def draw(self, event):
        if self.old_x is not None:
            full_command = f"DRAW:{self.old_x},{self.old_y},{event.x},{event.y},{self.color},{self.brush_size}"
            self.send_command(full_command); self.process_command(full_command)
        self.old_x, self.old_y = event.x, event.y

    def reset_drawing_state(self, event): self.old_x, self.old_y = None, None
    def clear_canvas(self): self.send_command("CLEAR"); self.process_command("CLEAR")
    def profile_selected(self, selection):
        if f"I am {self.NATHAN_NAME}" in selection: self.my_name, self.peer_name, target_ip = self.NATHAN_NAME, self.MAJID_NAME, self.MAJID_IP
        elif f"I am {self.MAJID_NAME}" in selection: self.my_name, self.peer_name, target_ip = self.MAJID_NAME, self.NATHAN_NAME, self.NATHAN_IP
        else: self.my_name, self.peer_name = None, None; return
        self.ip_entry.delete(0, tk.END); self.ip_entry.insert(0, target_ip)

    def connect_to_peer(self):
        peer_ip = self.ip_entry.get()
        if not peer_ip: messagebox.showerror("Error", "IP address is required."); return
        if not self.my_name: messagebox.showerror("Error", "Please select your profile first."); return
        threading.Thread(target=self._connect_thread, args=(peer_ip,), daemon=True).start()

    def _connect_thread(self, peer_ip):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM); client_socket.connect((peer_ip, self.port))
            self.connection = client_socket; self.connected.set()
            self.update_status(f"Connected to {self.peer_name} ({peer_ip})", "green")
            threading.Thread(target=self.receive_data, daemon=True).start()
        except Exception as e: self.update_status(f"Connection failed: {e}", "red")

    def start_server(self): threading.Thread(target=self._server_thread, daemon=True).start()
    def _server_thread(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM); server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try: server.bind((self.host_ip_listen, self.port)); server.listen(1)
        except Exception: return
        if not self.connected.is_set():
            try:
                conn, addr = server.accept(); self.connection = conn; self.connected.set()
                self.update_status(f"Connected by {addr[0]}", "green"); threading.Thread(target=self.receive_data, daemon=True).start()
            except OSError: pass

    def update_status(self, message, color): self.status_label.configure(text=message, text_color=color)
    def handle_disconnect(self):
        if not self.connected.is_set(): return
        self.connected.clear();
        if self.connection: self.connection.close(); self.connection = None
        self.update_status("Status: Disconnected", "red"); self.start_server()

    def notify_user(self):
        if self.master.state() == 'iconic' or not self.master.focus_get():
            self.master.deiconify()
            self.master.attributes('-topmost', 1)
            self.after(100, lambda: self.master.attributes('-topmost', self.is_pinned))
            self.master.bell()

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    root.withdraw()
    ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Github", "VortexTunnelLogo.png")
    try:
        icon_photo = tk.PhotoImage(file=ICON_PATH)
        root.iconphoto(True, icon_photo)
    except tk.TclError:
        print(f"Could not load custom icon from {ICON_PATH}.")
    root.title("Vortex Tunnel")
    root.geometry("800x600")
    ctk.set_appearance_mode("dark")
    app = VortexTunnelApp(master=root)
    app.pack(side="top", fill="both", expand=True)
    root.drop_target_register(DND_FILES)
    root.dnd_bind('<<Drop>>', app.handle_drop)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.deiconify()
    root.mainloop()
