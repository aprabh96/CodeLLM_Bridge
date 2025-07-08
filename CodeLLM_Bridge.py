import os
import json
import time
import fnmatch
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
import datetime
import shutil
import threading
from global_hotkeys import register_hotkey, start_checking_hotkeys, stop_checking_hotkeys
import pyperclip
import keyboard
import tempfile
import signal
import queue

class LoadingDialog:
    """A dialog that shows loading progress with the ability to cancel."""
    
    def __init__(self, parent, title="Loading Profile"):
        self.parent = parent
        self.cancelled = False
        self.current_operation = ""
        
        # Create the dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x200")
        self.dialog.resizable(False, False)
        
        # Center the dialog on parent
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Create the UI
        self.setup_ui()
        
        # Make dialog modal
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
    def setup_ui(self):
        """Set up the loading dialog UI."""
        main_frame = tk.Frame(self.dialog, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(main_frame, text="Loading Profile...", 
                              font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=400)
        self.progress.pack(pady=(0, 10))
        self.progress.start(10)  # Start animation
        
        # Current operation label
        self.operation_label = tk.Label(main_frame, text="Initializing...", 
                                       wraplength=450, justify=tk.LEFT)
        self.operation_label.pack(pady=(0, 10))
        
        # Current folder/file label
        self.detail_label = tk.Label(main_frame, text="", 
                                    wraplength=450, justify=tk.LEFT,
                                    font=("Arial", 9), fg="gray")
        self.detail_label.pack(pady=(0, 15))
        
        # Buttons frame
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Skip button
        self.skip_button = tk.Button(button_frame, text="Skip This Profile", 
                                    command=self.on_skip,
                                    bg="#ff9800", fg="white")
        self.skip_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Cancel button
        self.cancel_button = tk.Button(button_frame, text="Cancel & Use Default", 
                                      command=self.on_cancel,
                                      bg="#f44336", fg="white")
        self.cancel_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Disable timeouts button
        self.disable_timeout_button = tk.Button(button_frame, text="Disable Timeouts", 
                                               command=self.on_disable_timeouts,
                                               bg="#2196f3", fg="white")
        self.disable_timeout_button.pack(side=tk.LEFT)
        
        # Status label
        self.status_label = tk.Label(main_frame, text="", fg="red", font=("Arial", 8))
        self.status_label.pack(pady=(10, 0))
        
    def update_operation(self, operation_text):
        """Update the main operation text."""
        self.current_operation = operation_text
        if hasattr(self, 'operation_label'):
            self.operation_label.config(text=operation_text)
            self.dialog.update()
            
    def update_detail(self, detail_text):
        """Update the detailed progress text."""
        if hasattr(self, 'detail_label'):
            # Truncate very long paths
            if len(detail_text) > 60:
                detail_text = "..." + detail_text[-57:]
            self.detail_label.config(text=detail_text)
            self.dialog.update()
            
    def update_status(self, status_text, color="red"):
        """Update the status message."""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=status_text, fg=color)
            self.dialog.update()
            
    def on_skip(self):
        """Handle skip button click."""
        self.cancelled = "skip"
        self.update_status("Skipping current profile...", "orange")
        
    def on_cancel(self):
        """Handle cancel button click."""
        self.cancelled = "cancel"
        self.update_status("Cancelling and using default profile...", "red")
        
    def on_disable_timeouts(self):
        """Handle disable timeouts button click."""
        self.cancelled = "disable_timeouts"
        self.update_status("Timeouts disabled - loading will continue without time limits...", "blue")
        # Hide the disable timeouts button and update the other buttons
        self.disable_timeout_button.pack_forget()
        self.skip_button.config(text="Continue in Background")
        self.cancel_button.config(text="Cancel & Use Default")
        
    def is_cancelled(self):
        """Check if operation was cancelled."""
        return self.cancelled != False
        
    def get_cancel_type(self):
        """Get the type of cancellation (skip, cancel, or disable_timeouts)."""
        return self.cancelled
        
    def close(self):
        """Close the dialog."""
        if hasattr(self, 'progress'):
            self.progress.stop()
        if hasattr(self, 'dialog'):
            self.dialog.grab_release()
            self.dialog.destroy()

CONFIG_FILE = "app_settings.json"
PROFILES_DIR = "profiles"
HISTORY_DIR = "history"  # New directory for history
LAST_PROFILE_FILE = "last_profile.txt"  # File to store the last selected profile
DEFAULT_PREPEND_STRING = "Apply ALL these changes one by one -"  # Default string for prepending

# Theme colors
LIGHT_THEME = {
    "bg": "#f0f0f0",
    "fg": "#000000",
    "button_bg": "#e0e0e0",
    "button_fg": "#000000",
    "text_bg": "#ffffff",
    "text_fg": "#000000",
    "listbox_bg": "#ffffff",
    "listbox_fg": "#000000",
    "tree_bg": "#ffffff",
    "tree_fg": "#000000",
    "frame_bg": "#f0f0f0",
    "status_bg": "#f0f0f0",
    "status_fg": "#333333",
    "highlight_bg": "#0078d7",
    "highlight_fg": "#ffffff"
}

DARK_THEME = {
    "bg": "#1e1e1e",
    "fg": "#ffffff",
    "button_bg": "#333333",
    "button_fg": "#ffffff",
    "text_bg": "#121212",
    "text_fg": "#e0e0e0",
    "listbox_bg": "#121212",
    "listbox_fg": "#e0e0e0",
    "tree_bg": "#121212",
    "tree_fg": "#e0e0e0",
    "frame_bg": "#1e1e1e",
    "status_bg": "#007acc",
    "status_fg": "#ffffff",
    "highlight_bg": "#0078d7",
    "highlight_fg": "#ffffff",
    "content_bg": "#080808",  # Even darker for content areas
    "content_fg": "#e0e0e0"   # Bright text for contrast
}

# Timeout settings for folder loading (configurable)
FOLDER_LOADING_TIMEOUT = 60  # seconds - total time to load a profile (increased from 10)
FOLDER_ACCESS_TIMEOUT = 10   # seconds per folder access check (increased from 3)

# Note: The monitor also provides an additional 30-second grace period for loading
# For local folders, access checks are optimized to be much faster
# You can adjust these values:
# - Increase FOLDER_LOADING_TIMEOUT if you have very large projects
# - Increase FOLDER_ACCESS_TIMEOUT if you have slow network connections
# - Decrease them if you want faster fallback for unresponsive servers

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

class FolderLoadingTimeout:
    """Context manager for handling folder loading timeouts"""
    def __init__(self, timeout_seconds):
        self.timeout_seconds = timeout_seconds
        self.old_handler = None
        
    def __enter__(self):
        # For Unix-like systems, use signal
        if os.name != 'nt':
            self.old_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(self.timeout_seconds)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cancel the alarm and restore old handler (Unix only)
        if os.name != 'nt':
            signal.alarm(0)
            if self.old_handler is not None:
                signal.signal(signal.SIGALRM, self.old_handler)
            
    def _timeout_handler(self, signum, frame):
        raise TimeoutError(f"Folder loading timed out after {self.timeout_seconds} seconds")

def read_file_with_fallback(path):
    """
    Try reading a file with UTF-8, then fallback to CP-1252,
    and finally CP-1252 with errors='replace' if needed.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='cp1252') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='cp1252', errors='replace') as f:
                return f.read()

def remove_comments_from_code(code, ext):
    """Remove comments from code based on file extension."""
    patterns = {
        'py': [r'(?m)#.*$', r'""".*?"""', r"'''(?:.|\n)*?'''"],
        'js': [r'(?m)//.*$', r'/\*.*?\*/'],
        'ts': [r'(?m)//.*$', r'/\*.*?\*/'],
        'java': [r'(?m)//.*$', r'/\*.*?\*/'],
        'c': [r'(?m)//.*$', r'/\*.*?\*/'],
        'cpp': [r'(?m)//.*$', r'/\*.*?\*/'],
        'h': [r'(?m)//.*$', r'/\*.*?\*/'],
        'cs': [r'(?m)//.*$', r'/\*.*?\*/'],
        'go': [r'(?m)//.*$', r'/\*.*?\*/'],
        'rb': [r'(?m)#.*$', r'=begin(?:.|\n)*?=end'],
        'php': [r'(?m)//.*$', r'(?m)#.*$', r'/\*.*?\*/'],
        'sh': [r'(?m)#.*$'],
        'bash': [r'(?m)#.*$'],
        'rs': [r'(?m)//.*$', r'/\*.*?\*/'],
        'html': [r'<!--.*?-->'],
        'xml': [r'<!--.*?-->'],
    }

    if ext not in patterns:
        return code

    new_code = code
    for pat in patterns[ext]:
        new_code = re.sub(pat, '', new_code, flags=re.DOTALL)
    return new_code

class FolderMonitorApp:
    def __init__(self, master):
        self.master = master
        self.master.title("CodeLLM Bridge by Psynect Corp - psynect.ai")

        # Create profiles directory if it doesn't exist
        if not os.path.exists(PROFILES_DIR):
            os.makedirs(PROFILES_DIR)
            
        # Create history directory if it doesn't exist
        if not os.path.exists(HISTORY_DIR):
            os.makedirs(HISTORY_DIR)

        # Theme setting
        self.dark_mode = tk.BooleanVar(value=False)
        self.current_theme = LIGHT_THEME

        # Profile management
        self.current_profile = self.load_last_profile_with_fallback()
        self.profiles = self.get_available_profiles()
        
        # Flag to track if we're loading with a fallback profile
        self.is_fallback_profile = False
        
        # Loading dialog reference
        self.loading_dialog = None
        
        # History management
        self.history_items = []  # List to store history items
        self.selected_history_item = None  # Currently selected history item
        
        # Status message (replaces message boxes)
        self.status_message = ""
        self.status_timer = None

        # We store multiple top-level folders
        self.root_folders = []

        # folder_tree_data: path -> {'checked': bool, 'is_dir': bool}
        self.folder_tree_data = {}
        # path -> tree item ID
        self.tree_ids_map = {}

        self.poll_interval_ms = 3000

        # Meta prompts
        self.meta_prompts = []
        self.user_instructions = ""

        # Default ignore patterns for common system folders
        self.default_ignore_patterns = [
            "*/.git/*",
            "*/.venv/*", 
            "*/__pycache__/*",
            "*/.vs/*",
            "*/.vscode/*",
            "*/.idea/*",
            "*/node_modules/*",
            "*/build/*",
            "*/dist/*",
            "*/.svn/*",
            "*/.DS_Store"
        ]
        
        # Ignore patterns
        self.ignore_patterns = []
        
        # Default ignore patterns for initial setup (will be populated on first launch)
        self.default_initial_ignore_patterns = [
            "**/node_modules/",
            "**/.npm/",
            "**/__pycache__/",
            "**/.pytest_cache/",
            "**/.mypy_cache/",
            "# Build caches",
            "**/.gradle/",
            "**/.nuget/",
            "**/.cargo/",
            "**/.stack-work/",
            "**/.ccache/",
            "# IDE and Editor caches",
            "**/.idea/",
            "**/.vscode/",
            "**/*.swp",
            "**/*~",
            "# Temp files",
            "**/*.tmp",
            "**/*.temp",
            "**/*.bak",
            "**/*.meta",
            "**/package-lock.json",
            "# Media files",
            "**/*.jpg",
            "**/*.jpeg",
            "**/*.png",
            "**/*.gif",
            "**/*.bmp",
            "**/*.ico",
            "**/*.svg",
            "**/*.webp",
            "**/*.mp4",
            "**/*.avi",
            "**/*.mov",
            "**/*.wmv",
            "**/*.flv",
            "**/*.mkv",
            "**/*.webm",
            "**/*.mp3",
            "**/*.wav",
            "**/*.ogg",
            "**/*.m4a",
            "**/*.flac",
            "# Certificate files",
            "**/*.pem",
            "**/*.crt",
            "**/*.cer",
            "**/*.key",
            "**/*.pfx",
            "**/*.p12",
            "**/*.csr"
        ]
        
        # Flag to control whether to filter system folders
        self.filter_system_folders = tk.BooleanVar(value=True)

        # We keep the saved check states from config
        self.saved_folder_checks = {}
        
        # Selection presets for saving/loading different selection combinations
        self.selection_presets = {}

        # Checkbox for copying entire file tree
        self.copy_entire_tree_var = tk.BooleanVar(value=False)

        # Option to strip comments from copied code
        self.strip_comments_var = tk.BooleanVar(value=False)

        # Instructions expanded state
        self.instructions_expanded = tk.BooleanVar(value=False)

        # A set of directories we've already visited to avoid re-adding them
        self.visited_dirs = set()

        # Initialize prepend string and hotkey variables
        self.prepend_string = DEFAULT_PREPEND_STRING
        self.prepend_hotkey_enabled = tk.BooleanVar(value=False)
        self.hotkey_thread = None
        self.hotkey_registered = False
        # Default hotkey combination
        self.hotkey_combination = "ctrl+alt+v"
        
        # Timeout control
        self.enable_timeouts = tk.BooleanVar(value=True)  # Default: timeouts enabled

        # First create widgets
        self.create_widgets()
        
        # Ensure the current profile exists in the profiles list
        if self.current_profile not in self.profiles:
            self.current_profile = "default"
            self.save_last_profile("default")
        
        # Set the profile dropdown to the loaded profile
        self.profile_var.set(self.current_profile)
        
        # Load settings - try simple load first, only use timeout system if needed
        self.load_settings_smart()
        self.refresh_prompts_listbox()
        
        # NOW update current theme based on the loaded settings
        if self.dark_mode.get():
            self.current_theme = DARK_THEME
        else:
            self.current_theme = LIGHT_THEME
            
        # Apply theme after theme is correctly determined
        self.apply_theme()
        
        # Show status based on whether we loaded successfully or used fallback
        if self.is_fallback_profile:
            self.set_status(f"⚠️ Failed to load '{self.current_profile}' due to timeout - using fallback profile. Check network connections for FTP folders.", 10000)
            # Show the retry button
            self.btn_retry_profile.pack(side=tk.RIGHT, padx=5)
        elif self.current_profile != "default":
            self.set_status(f"Loaded profile: {self.current_profile}")
        else:
            self.set_status("Ready")
        
        # Set some defaults for text widgets (will be overridden if needed)
        text_bg = self.current_theme["text_bg"]
        text_fg = self.current_theme["text_fg"]
        self.master.option_add("*Text.Background", text_bg)
        self.master.option_add("*Text.Foreground", text_fg)
        
        # Start polling
        self.schedule_folder_poll()

        self.setup_global_hotkey()
        
        # Set up window close handler to save current state
        self.master.protocol("WM_DELETE_WINDOW", self.on_window_close)

    # -----------------------------------------------------------------------
    #  GUI
    # -----------------------------------------------------------------------
    def create_widgets(self):
        # Main container
        main_container = tk.Frame(self.master)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Profile Management Frame
        profile_frame = tk.Frame(main_container)
        profile_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        tk.Label(profile_frame, text="Profile:").pack(side=tk.LEFT, padx=5)
        self.profile_var = tk.StringVar(value=self.current_profile)
        self.profile_combo = ttk.Combobox(profile_frame, textvariable=self.profile_var, values=self.profiles)
        self.profile_combo.pack(side=tk.LEFT, padx=5)
        self.profile_combo.bind('<<ComboboxSelected>>', self.on_profile_selected)

        btn_new_profile = tk.Button(profile_frame, text="New Profile", command=self.on_new_profile)
        btn_new_profile.pack(side=tk.LEFT, padx=5)

        btn_update_profile = tk.Button(profile_frame, text="Update Profile", command=self.on_update_profile)
        btn_update_profile.pack(side=tk.LEFT, padx=5)

        btn_delete_profile = tk.Button(profile_frame, text="Delete Profile", command=self.on_delete_profile)
        btn_delete_profile.pack(side=tk.LEFT, padx=5)
        
        # Dark mode toggle
        self.dark_mode_check = tk.Checkbutton(profile_frame, text="Dark Mode", 
                                             variable=self.dark_mode, 
                                             command=self.on_dark_mode_toggle)
        self.dark_mode_check.pack(side=tk.RIGHT, padx=5)

        # Selection Presets Frame
        presets_frame = tk.Frame(main_container)
        presets_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        tk.Label(presets_frame, text="Selection Presets:").pack(side=tk.LEFT, padx=5)
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(presets_frame, textvariable=self.preset_var, width=20)
        self.preset_combo.pack(side=tk.LEFT, padx=5)

        btn_save_preset = tk.Button(presets_frame, text="Save Selection", command=self.on_save_selection_preset)
        btn_save_preset.pack(side=tk.LEFT, padx=5)

        btn_load_preset = tk.Button(presets_frame, text="Load Selection", command=self.on_load_selection_preset)
        btn_load_preset.pack(side=tk.LEFT, padx=5)

        btn_delete_preset = tk.Button(presets_frame, text="Delete Preset", command=self.on_delete_selection_preset)
        btn_delete_preset.pack(side=tk.LEFT, padx=5)

        # Refresh Button Frame
        refresh_frame = tk.Frame(main_container)
        refresh_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        btn_refresh = tk.Button(refresh_frame, text="Refresh Folders", command=self.on_refresh_folders)
        btn_refresh.pack(side=tk.LEFT, padx=5)

        btn_reduce_tokens = tk.Button(refresh_frame, text="Reduce Tokens", command=self.on_reduce_tokens, bg="#4CAF50", fg="white")
        btn_reduce_tokens.pack(side=tk.LEFT, padx=5)

        # System Folder Filter Checkbox
        chk_system_filter = tk.Checkbutton(
            refresh_frame, 
            text="Hide system folders (.git, .venv, etc.)",
            variable=self.filter_system_folders,
            command=self.on_toggle_system_filter
        )
        chk_system_filter.pack(side=tk.LEFT, padx=5)
        
        # Timeout Control Checkbox
        chk_timeout_control = tk.Checkbutton(
            refresh_frame, 
            text="Enable timeouts (uncheck to wait indefinitely)",
            variable=self.enable_timeouts,
            command=self.on_toggle_timeout_control
        )
        chk_timeout_control.pack(side=tk.LEFT, padx=5)

        top_frame = tk.Frame(main_container)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Add Folder
        btn_add_folder = tk.Button(top_frame, text="Add Folder", command=self.on_add_folder)
        btn_add_folder.pack(side=tk.LEFT, padx=5)

        # Remove Folder
        btn_remove_folder = tk.Button(top_frame, text="Remove Folder", command=self.on_remove_folder)
        btn_remove_folder.pack(side=tk.LEFT, padx=5)

        # Checkbox: copy entire file tree
        chk_full_tree = tk.Checkbutton(
            top_frame,
            text="Copy entire file tree (ignore checks)",
            variable=self.copy_entire_tree_var
        )
        chk_full_tree.pack(side=tk.LEFT, padx=5)

        # Checkbox: strip comments from copied code
        chk_strip_comments = tk.Checkbutton(
            top_frame,
            text="Remove comments from copied code",
            variable=self.strip_comments_var
        )
        chk_strip_comments.pack(side=tk.LEFT, padx=5)

        # Add Meta Prompt
        btn_add_prompt = tk.Button(top_frame, text="Add New Meta Prompt", command=self.on_add_prompt)
        btn_add_prompt.pack(side=tk.LEFT, padx=5)

        # Show Selected Files button
        self.btn_show_selected = tk.Button(top_frame, text="Show All Selected Files", command=self.on_show_selected_files)
        self.btn_show_selected.pack(side=tk.LEFT, padx=5)

        # Copy buttons
        btn_copy_file = tk.Button(top_frame, text="Save to Temp File & Copy", command=self.on_copy_to_temp_file)
        btn_copy_file.pack(side=tk.RIGHT, padx=2)
        
        btn_copy = tk.Button(top_frame, text="Copy to Clipboard", command=self.on_copy_to_clipboard)
        btn_copy.pack(side=tk.RIGHT, padx=5)

        # Add retry button for failed profile loads (initially hidden)
        self.btn_retry_profile = tk.Button(top_frame, text="🔄 Retry Original Profile", 
                                          command=self.on_retry_original_profile,
                                          bg="#ffeb3b", fg="#000000")
        # Don't pack it initially - we'll show it only when needed

        # MAIN area
        main_frame = tk.Frame(main_container)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left side: Tree and History
        left_side_frame = tk.Frame(main_frame)
        left_side_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tree area
        tree_frame = tk.LabelFrame(left_side_frame, text="Folder Tree")
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(tree_frame, columns=["Name"], show='tree')
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_tree_item_double_click)

        # History section
        history_frame = tk.LabelFrame(left_side_frame, text="Copy History")
        history_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, padx=5, pady=5)

        # Split the history frame into list and viewer
        history_split_frame = tk.PanedWindow(history_frame, orient=tk.HORIZONTAL)
        history_split_frame.pack(fill=tk.BOTH, expand=True)
        
        # History list panel
        history_list_panel = tk.Frame(history_split_frame)
        history_split_frame.add(history_list_panel, width=200)
        
        # History list with scrollbar
        history_list_frame = tk.Frame(history_list_panel)
        history_list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.history_listbox = tk.Listbox(history_list_frame, height=6)
        self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.history_listbox.bind('<<ListboxSelect>>', self.on_history_item_selected)

        # Scrollbar for history list
        history_scrollbar = ttk.Scrollbar(history_list_frame, orient="vertical", command=self.history_listbox.yview)
        history_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_listbox.configure(yscrollcommand=history_scrollbar.set)

        # History buttons
        history_btn_frame = tk.Frame(history_list_panel)
        history_btn_frame.pack(side=tk.BOTTOM, fill=tk.X)

        btn_copy_history_content = tk.Button(history_btn_frame, text="Copy Content", command=self.on_copy_history_content)
        btn_copy_history_content.pack(side=tk.LEFT, padx=5, pady=2)

        btn_copy_history_prompt = tk.Button(history_btn_frame, text="Copy Prompt", command=self.on_copy_history_prompt)
        btn_copy_history_prompt.pack(side=tk.LEFT, padx=5, pady=2)

        btn_delete_history = tk.Button(history_btn_frame, text="Delete Item", command=self.on_delete_history_item)
        btn_delete_history.pack(side=tk.RIGHT, padx=5, pady=2)
        
        # History content viewer panel
        history_viewer_panel = tk.Frame(history_split_frame)
        history_split_frame.add(history_viewer_panel, width=400)
        
        # Add notebook for content and instructions - use our custom method
        self.create_history_content_tabs(history_viewer_panel)
        
        # Right side: prompts, instructions, filters
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Meta prompts
        prompts_frame = tk.LabelFrame(right_frame, text="Meta Prompts")
        prompts_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=5, pady=5)

        self.prompts_listbox = tk.Listbox(prompts_frame, height=8, selectmode=tk.SINGLE)
        self.prompts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        prompt_btn_frame = tk.Frame(prompts_frame)
        prompt_btn_frame.pack(side=tk.LEFT, fill=tk.Y)

        btn_toggle_prompt = tk.Button(prompt_btn_frame, text="Toggle Selected", command=self.on_toggle_prompt)
        btn_toggle_prompt.pack(fill=tk.X, pady=2)

        btn_edit_prompt = tk.Button(prompt_btn_frame, text="Edit Prompt", command=self.on_edit_prompt)
        btn_edit_prompt.pack(fill=tk.X, pady=2)

        btn_remove_prompt = tk.Button(prompt_btn_frame, text="Remove Prompt", command=self.on_remove_prompt)
        btn_remove_prompt.pack(fill=tk.X, pady=2)

        # User Instructions
        instr_frame = tk.LabelFrame(right_frame, text="User Instructions (always copied)")
        instr_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False, padx=5, pady=5)

        instr_controls = tk.Frame(instr_frame)
        instr_controls.pack(fill=tk.X)

        # Add undo/redo buttons to instructions
        undo_btn = tk.Button(instr_controls, text="Undo", command=lambda: self.do_undo(self.instructions_text))
        undo_btn.pack(side=tk.LEFT, padx=2, pady=2)
        
        redo_btn = tk.Button(instr_controls, text="Redo", command=lambda: self.do_redo(self.instructions_text))
        redo_btn.pack(side=tk.LEFT, padx=2, pady=2)

        self.expand_btn = tk.Button(instr_controls, text="Expand", command=self.toggle_instructions_size)
        self.expand_btn.pack(side=tk.RIGHT, padx=5, pady=2)

        self.instructions_text = ScrolledText(instr_frame, height=4, undo=True, maxundo=-1)  # Unlimited undo
        self.instructions_text.pack(fill=tk.BOTH, expand=True)
        if self.user_instructions:
            self.instructions_text.insert("1.0", self.user_instructions)
        self.instructions_text.bind("<<Modified>>", self.on_instructions_modified)
        
        # Bind keyboard shortcuts
        self.instructions_text.bind("<Control-z>", lambda e: self.handle_undo(e, self.instructions_text))
        self.instructions_text.bind("<Control-y>", lambda e: self.handle_redo(e, self.instructions_text))

        # Filters
        filters_frame = tk.LabelFrame(right_frame, text="Ignore Patterns")
        filters_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add filter controls frame
        filter_controls = tk.Frame(filters_frame)
        filter_controls.pack(fill=tk.X)
        
        # Add undo/redo buttons to filters
        undo_filter_btn = tk.Button(filter_controls, text="Undo", command=lambda: self.do_undo(self.filters_text))
        undo_filter_btn.pack(side=tk.LEFT, padx=2, pady=2)
        
        redo_filter_btn = tk.Button(filter_controls, text="Redo", command=lambda: self.do_redo(self.filters_text))
        redo_filter_btn.pack(side=tk.LEFT, padx=2, pady=2)

        self.filters_text = ScrolledText(filters_frame, height=6, undo=True, maxundo=-1)  # Unlimited undo
        self.filters_text.pack(fill=tk.BOTH, expand=True)
        if self.ignore_patterns:
            filters_content = "\n".join(self.ignore_patterns)
            self.filters_text.insert("1.0", filters_content)
            
        # Bind keyboard shortcuts for filters text
        self.filters_text.bind("<Control-z>", lambda e: self.handle_undo(e, self.filters_text))
        self.filters_text.bind("<Control-y>", lambda e: self.handle_redo(e, self.filters_text))

        btn_save_filters = tk.Button(filters_frame, text="Save Filters", command=self.on_save_filters)
        btn_save_filters.pack(side=tk.BOTTOM, anchor=tk.E, padx=5, pady=5)
        
        # Enhanced status bar at the bottom of the window
        status_frame = tk.Frame(main_container, height=30)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_bar = tk.Label(status_frame, text="Status messages will appear here", 
                               bd=1, relief=tk.SUNKEN, anchor=tk.W,
                               font=('Arial', 10, 'bold'),
                               bg='#f0f0f0', fg='#333333',
                               height=2)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Add Prepend String UI
        prepend_frame = tk.LabelFrame(self.master, text="Clipboard Prepend Hotkey")
        prepend_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Top row: prepend string entry and reset button
        prepend_entry_frame = tk.Frame(prepend_frame)
        prepend_entry_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
        
        tk.Label(prepend_entry_frame, text="Prepend Text:").pack(side=tk.LEFT, padx=5)
        self.prepend_entry = tk.Entry(prepend_entry_frame, width=40)
        self.prepend_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.prepend_entry.insert(0, self.prepend_string)
        # Bind multiple events to ensure the prepend text is saved
        self.prepend_entry.bind("<FocusOut>", self.on_prepend_string_changed)
        self.prepend_entry.bind("<Return>", self.on_prepend_string_changed)
        self.prepend_entry.bind("<KeyRelease>", self.on_prepend_string_changed_delayed)
        
        btn_save_prepend = tk.Button(prepend_entry_frame, text="Save", command=self.on_save_prepend_text)
        btn_save_prepend.pack(side=tk.LEFT, padx=2)
        
        btn_reset_prepend = tk.Button(prepend_entry_frame, text="Reset Default", command=self.reset_prepend_string)
        btn_reset_prepend.pack(side=tk.LEFT, padx=2)
        
        btn_debug_prepend = tk.Button(prepend_entry_frame, text="Debug", command=self.debug_prepend_settings)
        btn_debug_prepend.pack(side=tk.LEFT, padx=2)
        
        # Bottom row: hotkey settings
        hotkey_control_frame = tk.Frame(prepend_frame)
        hotkey_control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
        
        self.prepend_hotkey_check = tk.Checkbutton(hotkey_control_frame, text="Enable Hotkey:", 
                                                  variable=self.prepend_hotkey_enabled, 
                                                  command=self.on_toggle_prepend_hotkey)
        self.prepend_hotkey_check.pack(side=tk.LEFT, padx=5)
        
        # Hotkey display and change button
        self.hotkey_display = tk.Label(hotkey_control_frame, text=self.hotkey_combination.upper(), 
                                      relief=tk.SUNKEN, padx=10, pady=2)
        self.hotkey_display.pack(side=tk.LEFT, padx=5)
        
        btn_change_hotkey = tk.Button(hotkey_control_frame, text="Change Hotkey", command=self.on_change_hotkey)
        btn_change_hotkey.pack(side=tk.LEFT, padx=5)
        
        # Hotkey status label
        self.hotkey_status_label = tk.Label(hotkey_control_frame, text="", fg="green")
        self.hotkey_status_label.pack(side=tk.LEFT, padx=10)
        
    def on_dark_mode_toggle(self):
        """Handle dark mode toggle from checkbox"""
        # Get the latest value
        is_dark = self.dark_mode.get()
        # Update the theme
        self.current_theme = DARK_THEME if is_dark else LIGHT_THEME
        
        # Apply new colors to content viewers
        self.update_content_viewer_colors()
        
        # Apply theme to all widgets
        self.apply_theme()
        self.save_settings()
        theme_name = "dark" if is_dark else "light"
        self.set_status(f"Switched to {theme_name} mode")
        
        # Force a complete refresh of the main window
        self.master.update_idletasks()
        self.master.update()

    def toggle_theme(self):
        """Toggle between light and dark themes programmatically"""
        # Explicitly toggle the variable
        new_value = not self.dark_mode.get()
        self.dark_mode.set(new_value)
        
        # Call the same handler the checkbox uses
        self.on_dark_mode_toggle()

    def update_content_viewer_colors(self):
        """Update text colors for content viewers based on current theme"""
        content_bg = self.current_theme.get("content_bg", self.current_theme["text_bg"])
        content_fg = self.current_theme.get("content_fg", self.current_theme["text_fg"])
        
        if hasattr(self, 'content_viewer'):
            self.content_viewer.config(
                bg=content_bg,
                fg=content_fg,
                insertbackground=self.current_theme["fg"],
                selectbackground=self.current_theme["highlight_bg"],
                selectforeground=self.current_theme["highlight_fg"]
            )
            
        if hasattr(self, 'code_viewer'):
            self.code_viewer.config(
                bg=content_bg,
                fg=content_fg,
                insertbackground=self.current_theme["fg"],
                selectbackground=self.current_theme["highlight_bg"],
                selectforeground=self.current_theme["highlight_fg"]
            )
            
        if hasattr(self, 'instructions_viewer'):
            self.instructions_viewer.config(
                bg=content_bg,
                fg=content_fg, 
                insertbackground=self.current_theme["fg"],
                selectbackground=self.current_theme["highlight_bg"],
                selectforeground=self.current_theme["highlight_fg"]
            )
            
        # Apply to all ScrolledText widgets in the application
        def update_text_widgets(widget):
            if isinstance(widget, ScrolledText):
                widget.config(
                    bg=content_bg,
                    fg=content_fg
                )
            for child in widget.winfo_children():
                update_text_widgets(child)
                
        update_text_widgets(self.master)

    def apply_theme(self):
        """Apply the current theme to all widgets"""
        theme = self.current_theme
        
        # Configure root window
        self.master.configure(bg=theme["bg"])
        
        # Configure all frames
        for widget in self.master.winfo_children():
            if isinstance(widget, tk.Frame):
                self.configure_frame_recursive(widget, theme)
                
        # Configure the status bar specifically
        self.status_bar.configure(bg=theme["status_bg"], fg=theme["status_fg"])
        
        # Configure treeview
        style = ttk.Style()
        style.theme_use('default')  # Reset to default theme first
        
        # Configure general ttk elements
        style.configure(".", 
                      background=theme["bg"],
                      foreground=theme["fg"],
                      fieldbackground=theme["bg"])
        
        # Configure Treeview specifically               
        style.configure("Treeview", 
                      background=theme["tree_bg"],
                      foreground=theme["tree_fg"],
                      fieldbackground=theme["tree_bg"])
        style.map('Treeview', 
                background=[('selected', theme["highlight_bg"])],
                foreground=[('selected', theme["highlight_fg"])])
        
        # Configure the notebook
        style.configure("TNotebook", background=theme["bg"], borderwidth=0)
        style.configure("TFrame", background=theme["bg"], foreground=theme["fg"])
        style.configure("TNotebook.Tab", 
                      background=theme["button_bg"], 
                      foreground=theme["button_fg"],
                      padding=[10, 2])
        style.map("TNotebook.Tab",
                background=[("selected", theme["highlight_bg"]), 
                           ("active", theme["highlight_bg"])],
                foreground=[("selected", theme["highlight_fg"]),
                           ("active", theme["highlight_fg"])])
        
        # More aggressive notebook tab styling
        self.master.option_add("*TNotebook*Foreground", theme["fg"])
        self.master.option_add("*TNotebook*Background", theme["bg"])
        self.master.option_add("*TNotebook.Tab*Background", theme["button_bg"])
        self.master.option_add("*TNotebook.Tab*Foreground", theme["button_fg"])
        
        # Configure scrollbars
        style.configure("TScrollbar", 
                       background=theme["button_bg"], 
                       troughcolor=theme["bg"],
                       bordercolor=theme["bg"],
                       arrowcolor=theme["fg"])
        
        # Configure combobox
        style.configure("TCombobox", 
                       selectbackground=theme["highlight_bg"],
                       selectforeground=theme["highlight_fg"],
                       fieldbackground=theme["text_bg"],
                       background=theme["button_bg"],
                       foreground=theme["text_fg"])
        style.map('TCombobox',
                fieldbackground=[('readonly', theme["text_bg"])],
                background=[('readonly', theme["button_bg"])],
                foreground=[('readonly', theme["text_fg"])])
                
        # Update content viewer colors
        self.update_content_viewer_colors()
                
        # Force all widgets to update immediately
        self.master.update_idletasks()
        
        # Apply theme to notebook contents
        if hasattr(self, 'content_viewer'):
            content_bg = theme.get("content_bg", theme["text_bg"])
            content_fg = theme.get("content_fg", theme["text_fg"])
            self.content_viewer.configure(
                bg=content_bg, 
                fg=content_fg,
                insertbackground=theme["fg"],
                selectbackground=theme["highlight_bg"],
                selectforeground=theme["highlight_fg"]
            )
            
        if hasattr(self, 'instructions_viewer'):
            content_bg = theme.get("content_bg", theme["text_bg"])
            content_fg = theme.get("content_fg", theme["text_fg"])
            self.instructions_viewer.configure(
                bg=content_bg, 
                fg=content_fg,
                insertbackground=theme["fg"],
                selectbackground=theme["highlight_bg"],
                selectforeground=theme["highlight_fg"]
            )
            
        # Apply theme to the content and instructions tabs specifically
        if hasattr(self, 'history_notebook'):
            for tab_id in self.history_notebook.tabs():
                tab = self.history_notebook.nametowidget(tab_id)
                if isinstance(tab, tk.Frame):
                    tab.configure(background=theme["bg"])
                    for child in tab.winfo_children():
                        if isinstance(child, ScrolledText):
                            content_bg = theme.get("content_bg", theme["text_bg"])
                            content_fg = theme.get("content_fg", theme["text_fg"])
                            child.configure(
                                bg=content_bg, 
                                fg=content_fg,
                                insertbackground=theme["fg"],
                                selectbackground=theme["highlight_bg"],
                                selectforeground=theme["highlight_fg"]
                            )
                            
        # Ensure text in the notebook tabs is properly themed
        if hasattr(self, 'history_notebook'):
            notebook = self.history_notebook
            # Force update the notebook tab colors
            notebook.update()
            notebook.update_idletasks()

    def configure_frame_recursive(self, frame, theme):
        """Recursively configure a frame and all its children with theme colors"""
        frame.configure(bg=theme["frame_bg"])
        
        for widget in frame.winfo_children():
            widget_type = widget.winfo_class()
            
            if widget_type == "Frame" or widget_type == "Labelframe":
                self.configure_frame_recursive(widget, theme)
                if widget_type == "Labelframe":
                    widget.configure(fg=theme["fg"], bg=theme["frame_bg"])
                    
            elif widget_type == "Label":
                widget.configure(bg=theme["bg"], fg=theme["fg"])
                # Special handling for hotkey display label
                if hasattr(self, 'hotkey_display') and widget == self.hotkey_display:
                    widget.configure(bg=theme["button_bg"], fg=theme["button_fg"])
                
            elif widget_type == "Button":
                widget.configure(bg=theme["button_bg"], fg=theme["button_fg"],
                               activebackground=theme["highlight_bg"],
                               activeforeground=theme["highlight_fg"],
                               highlightbackground=theme["frame_bg"])
                
            elif widget_type == "Checkbutton":
                widget.configure(bg=theme["bg"], fg=theme["fg"],
                               activebackground=theme["bg"],
                               activeforeground=theme["highlight_fg"],
                               selectcolor=theme["button_bg"],
                               highlightbackground=theme["frame_bg"])
                
            elif widget_type == "Listbox":
                widget.configure(bg=theme["listbox_bg"], fg=theme["listbox_fg"],
                               selectbackground=theme["highlight_bg"],
                               selectforeground=theme["highlight_fg"],
                               highlightbackground=theme["frame_bg"])
                
            elif widget_type == "Text" or widget_type == "ScrolledText":
                widget.configure(bg=theme["text_bg"], fg=theme["text_fg"],
                               insertbackground=theme["fg"],
                               selectbackground=theme["highlight_bg"],
                               selectforeground=theme["highlight_fg"],
                               highlightbackground=theme["frame_bg"])
                
            elif widget_type == "PanedWindow":
                widget.configure(bg=theme["frame_bg"])
                for child in widget.panes():
                    self.configure_frame_recursive(child, theme)

    def handle_undo(self, event, widget):
        """Handle undo event manually"""
        try:
            widget.edit_undo()
        except tk.TclError:
            # No more undo operations available
            pass
        return "break"  # Prevent default handling
    
    def handle_redo(self, event, widget):
        """Handle redo event manually"""
        try:
            widget.edit_redo()
        except tk.TclError:
            # No more redo operations available
            pass
        return "break"  # Prevent default handling
    
    def do_undo(self, widget):
        """Perform undo on the widget"""
        try:
            widget.edit_undo()
            self.set_status("Undo performed")
        except tk.TclError:
            self.set_status("Nothing to undo")
    
    def do_redo(self, widget):
        """Perform redo on the widget"""
        try:
            widget.edit_redo()
            self.set_status("Redo performed")
        except tk.TclError:
            self.set_status("Nothing to redo")
        
    def set_status(self, message, duration=5000):
        """Display a status message that disappears after a duration"""
        # Cancel any existing timer
        if self.status_timer is not None:
            self.master.after_cancel(self.status_timer)
            self.status_timer = None
            
        # Set the message with appropriate styling based on content
        if "error" in message.lower():
            self.status_bar.config(text=message, bg='#ffcccc', fg='#990000')  # Light red background, dark red text
        elif "duplicate" in message.lower():
            self.status_bar.config(text=message, bg='#ffffcc', fg='#666600')  # Light yellow background, dark yellow text
        elif "copied" in message.lower():
            self.status_bar.config(text=message, bg='#ccffcc', fg='#006600')  # Light green background, dark green text
        else:
            self.status_bar.config(text=message, bg='#f0f0f0', fg='#333333')  # Default styling
            
        # Schedule removal
        self.status_timer = self.master.after(duration, self.clear_status)
        
    def clear_status(self):
        """Clear the status message"""
        self.status_bar.config(text="Ready", bg='#f0f0f0', fg='#333333')
        self.status_timer = None

    # -----------------------------------------------------------------------
    #  ADD/REMOVE FOLDER
    # -----------------------------------------------------------------------
    def on_add_folder(self):
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            if folder not in self.root_folders:
                self.root_folders.append(folder)
                self.build_tree_for(folder)
                self.save_settings()
                self.set_status(f"Added folder: {folder}")
            else:
                self.set_status("That folder is already in the list.")

    def on_remove_folder(self):
        if not self.root_folders:
            self.set_status("There are no root folders to remove.")
            return

        remove_win = tk.Toplevel(self.master)
        remove_win.title("Remove Folder")

        tk.Label(remove_win, text="Select a root folder to remove:").pack(anchor=tk.W, padx=5, pady=5)

        listbox = tk.Listbox(remove_win, height=6)
        listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        for rf in self.root_folders:
            listbox.insert(tk.END, rf)

        def do_remove():
            sel = listbox.curselection()
            if sel:
                idx = sel[0]
                folder_to_remove = self.root_folders[idx]
                self.root_folders.pop(idx)
                self.remove_subtree(folder_to_remove)
                remove_win.destroy()
                self.save_settings()
                self.set_status(f"Removed folder: {folder_to_remove}")

        btn_remove = tk.Button(remove_win, text="Remove Selected", command=do_remove)
        btn_remove.pack(side=tk.RIGHT, padx=5, pady=5)

    def remove_subtree(self, folder_path):
        """Remove the given folder_path (and all descendants) from folder_tree_data + TreeView."""
        stack = [folder_path]
        to_delete_tree_ids = []
        while stack:
            current = stack.pop()
            if current in self.tree_ids_map:
                to_delete_tree_ids.append(self.tree_ids_map[current])
            if current in self.folder_tree_data:
                del self.folder_tree_data[current]
            if current in self.tree_ids_map:
                del self.tree_ids_map[current]

            # find children
            for p in list(self.folder_tree_data.keys()):
                if os.path.dirname(p) == current:
                    stack.append(p)

        for tid in to_delete_tree_ids:
            if self.tree.exists(tid):
                self.tree.delete(tid)

    # -----------------------------------------------------------------------
    #  BUILDING/REFRESHING TREE
    # -----------------------------------------------------------------------
    def build_all_trees(self):
        """
        Clear everything, then build a tree for each folder in self.root_folders.
        Reset self.visited_dirs each time we do a full rebuild.
        """
        self.folder_tree_data.clear()
        self.tree_ids_map.clear()
        self.tree.delete(*self.tree.get_children())
        self.visited_dirs = set()

        for folder in self.root_folders:
            if not os.path.exists(folder):
                continue
            self.build_tree_for(folder)

        # apply saved checks
        self.apply_saved_checks()
    
    def build_all_trees_with_dialog_threaded(self, cancel_flag):
        """
        Build trees with progress updates to the loading dialog, designed for threading.
        """
        def update_dialog_safe(operation_text, detail_text=None):
            """Safely update dialog from thread."""
            try:
                if self.loading_dialog:
                    self.master.after_idle(lambda: self.loading_dialog.update_operation(operation_text))
                    if detail_text:
                        self.master.after_idle(lambda: self.loading_dialog.update_detail(detail_text))
            except:
                pass
        
        # Clear data structures from main thread
        def clear_data():
            self.folder_tree_data.clear()
            self.tree_ids_map.clear()
            self.tree.delete(*self.tree.get_children())
            self.visited_dirs = set()
        self.master.after_idle(clear_data)
        
        # Wait for clearing to complete
        time.sleep(0.1)

        total_folders = len(self.root_folders)
        
        for i, folder in enumerate(self.root_folders):
            # Check if user cancelled
            if cancel_flag.is_set():
                return
                
            update_dialog_safe(f"Processing folder {i+1} of {total_folders}...", folder)
            
            if not os.path.exists(folder):
                continue
                
            self.build_tree_for_with_dialog_threaded(folder, cancel_flag)
            
            # Check for cancellation after each folder
            if cancel_flag.is_set():
                return

        # apply saved checks
        update_dialog_safe("Restoring selections...")
        self.master.after_idle(self.apply_saved_checks)

    def build_all_trees_with_dialog(self):
        """
        Build trees with progress updates to the loading dialog.
        """
        self.folder_tree_data.clear()
        self.tree_ids_map.clear()
        self.tree.delete(*self.tree.get_children())
        self.visited_dirs = set()

        total_folders = len(self.root_folders)
        
        for i, folder in enumerate(self.root_folders):
            # Check if user cancelled
            if self.loading_dialog and self.loading_dialog.is_cancelled():
                break
                
            if self.loading_dialog:
                self.loading_dialog.update_operation(f"Processing folder {i+1} of {total_folders}...")
                self.loading_dialog.update_detail(folder)
            
            if not os.path.exists(folder):
                continue
                
            self.build_tree_for_with_dialog(folder)

        # apply saved checks
        if self.loading_dialog:
            self.loading_dialog.update_operation("Restoring selections...")
        self.apply_saved_checks()

    def build_tree_for(self, folder):
        """
        Recursively add 'folder' and all its sub-items to the TreeView,
        skipping directories we've visited or that match ignore patterns.
        Now with timeout handling for network/FTP folders.
        """
        try:
            # Check if folder exists with a timeout
            if not self.check_folder_access_with_timeout(folder):
                print(f"Skipping inaccessible folder: {folder}")
                return
                
            realp = os.path.realpath(folder)
            if realp in self.visited_dirs:
                return
            self.visited_dirs.add(realp)

            if folder not in self.folder_tree_data:
                self.folder_tree_data[folder] = {'checked': False, 'is_dir': True}

            root_text = os.path.basename(folder) or folder
            root_id = self.tree.insert("", tk.END, text=root_text, open=False)
            self.tree_ids_map[folder] = root_id

            self.add_directory_contents(folder, root_id)
            # Don't automatically open root folders - let expand_to_show_selected handle this
            
        except Exception as e:
            print(f"Error building tree for {folder}: {e}")
            # Add a placeholder node to show the folder exists but had issues
            if folder not in self.folder_tree_data:
                self.folder_tree_data[folder] = {'checked': False, 'is_dir': True}
                root_text = f"{os.path.basename(folder) or folder} (⚠️ Access Error)"
                root_id = self.tree.insert("", tk.END, text=root_text, open=False)
                self.tree_ids_map[folder] = root_id

    def check_folder_access_with_timeout(self, folder_path):
        """Check if a folder is accessible within a timeout period."""
        try:
            # For local paths, do a quicker check
            if not self.is_potentially_problematic_path(folder_path):
                # Simple existence check for local paths
                try:
                    return os.path.exists(folder_path) and os.path.isdir(folder_path)
                except:
                    return False
            
            # For potentially problematic paths, use the timeout approach
            if os.name == 'nt':  # Windows
                result_queue = queue.Queue()
                
                def check_access():
                    try:
                        exists = os.path.exists(folder_path)
                        if exists:
                            # Try to list directory to ensure it's actually accessible
                            # But limit the listing to avoid hanging on huge directories
                            try:
                                items = os.listdir(folder_path)
                                # Just check if we can get at least one item, don't load all
                                if len(items) > 100:
                                    # For large directories, just check the first few items
                                    for i, item in enumerate(items):
                                        if i >= 5:  # Only check first 5 items
                                            break
                                        os.path.join(folder_path, item)  # Quick access test
                            except:
                                pass  # If listing fails, still return True if folder exists
                        result_queue.put(exists)
                    except Exception as e:
                        result_queue.put(False)
                
                thread = threading.Thread(target=check_access, daemon=True)
                thread.start()
                thread.join(timeout=FOLDER_ACCESS_TIMEOUT)
                
                if thread.is_alive():
                    print(f"Folder access timed out: {folder_path}")
                    return False
                    
                return result_queue.get() if not result_queue.empty() else False
                
            else:  # Unix-like systems
                with FolderLoadingTimeout(FOLDER_ACCESS_TIMEOUT):
                    if os.path.exists(folder_path):
                        # Light access test - don't fully enumerate large directories
                        try:
                            items = os.listdir(folder_path)
                            # Quick test on just a few items
                            for i, item in enumerate(items):
                                if i >= 5:
                                    break
                                os.path.join(folder_path, item)
                        except:
                            pass  # Still return True if basic existence check passed
                        return True
                    return False
                    
        except (TimeoutError, OSError, IOError) as e:
            print(f"Folder access failed for {folder_path}: {e}")
            return False

    def add_directory_contents(self, directory_path, parent_id):
        """Add directory contents with timeout handling."""
        try:
            # For local paths, do a lightweight check, for network paths use full timeout check
            if self.is_potentially_problematic_path(directory_path):
                if not self.check_folder_access_with_timeout(directory_path):
                    return
            else:
                # Quick check for local paths - just verify it exists and is accessible
                if not (os.path.exists(directory_path) and os.path.isdir(directory_path)):
                    return
                
            items = sorted(os.listdir(directory_path))
        except (PermissionError, OSError, IOError) as e:
            print(f"Cannot access directory {directory_path}: {e}")
            return

        for item in items:
            path = os.path.join(directory_path, item)

            # If ignore, skip
            if self.filters_match(path):
                continue

            # If physically the same as parent, skip (avoid repeated folder name)
            try:
                parent_real = os.path.realpath(directory_path)
                child_real = os.path.realpath(path)
                if os.path.samefile(directory_path, path):
                    # This means child is literally the same as the parent
                    continue
            except (OSError, IOError):
                # If we can't determine samefile, skip to be safe
                continue

            if child_real in self.visited_dirs and os.path.isdir(path):
                # Already processed this directory
                continue

            try:
                is_dir = os.path.isdir(path)
            except (OSError, IOError):
                # If we can't determine if it's a directory, skip it
                continue
                
            self.folder_tree_data[path] = {'checked': False, 'is_dir': is_dir}

            # Add item name with indicator if it might be problematic
            item_text = item
            if is_dir and self.is_potentially_problematic_path(path):
                item_text = f"{item} ⚠️"

            node_id = self.tree.insert(parent_id, tk.END, text=item_text, open=False)
            self.tree_ids_map[path] = node_id

            if is_dir:
                self.visited_dirs.add(child_real)
                # For subdirectories, use a reduced timeout or skip if it seems problematic
                if not self.is_potentially_problematic_path(path):
                    self.add_directory_contents(path, node_id)
                else:
                    print(f"Skipping potentially problematic subdirectory: {path}")
    
    def build_tree_for_with_dialog(self, folder):
        """
        Build tree for a folder with dialog progress updates.
        """
        try:
            if self.loading_dialog:
                self.loading_dialog.update_detail(f"Checking access: {folder}")
            
            # Check if folder exists with a timeout
            if not self.check_folder_access_with_timeout(folder):
                print(f"Skipping inaccessible folder: {folder}")
                if self.loading_dialog:
                    self.loading_dialog.update_detail(f"⚠️ Skipped (inaccessible): {folder}")
                return
                
            realp = os.path.realpath(folder)
            if realp in self.visited_dirs:
                return
            self.visited_dirs.add(realp)

            if folder not in self.folder_tree_data:
                self.folder_tree_data[folder] = {'checked': False, 'is_dir': True}

            root_text = os.path.basename(folder) or folder
            root_id = self.tree.insert("", tk.END, text=root_text, open=False)
            self.tree_ids_map[folder] = root_id

            if self.loading_dialog:
                self.loading_dialog.update_detail(f"Scanning: {folder}")
            
            self.add_directory_contents_with_dialog(folder, root_id)
            # Don't automatically open root folders - let expand_to_show_selected handle this
            
        except Exception as e:
            print(f"Error building tree for {folder}: {e}")
            if self.loading_dialog:
                self.loading_dialog.update_detail(f"⚠️ Error with: {folder}")
            # Add a placeholder node to show the folder exists but had issues
            if folder not in self.folder_tree_data:
                self.folder_tree_data[folder] = {'checked': False, 'is_dir': True}
                root_text = f"{os.path.basename(folder) or folder} (⚠️ Access Error)"
                root_id = self.tree.insert("", tk.END, text=root_text, open=False)
                self.tree_ids_map[folder] = root_id
    
    def build_tree_for_with_dialog_threaded(self, folder, cancel_flag):
        """
        Build tree for a folder with dialog progress updates, designed for threading.
        """
        def update_dialog_safe(detail_text):
            """Safely update dialog from thread."""
            try:
                if self.loading_dialog:
                    self.master.after_idle(lambda: self.loading_dialog.update_detail(detail_text))
            except:
                pass
        
        try:
            update_dialog_safe(f"Checking access: {folder}")
            
            # Check for cancellation
            if cancel_flag.is_set():
                return
            
            # Check if folder exists with a timeout
            if not self.check_folder_access_with_timeout(folder):
                print(f"Skipping inaccessible folder: {folder}")
                update_dialog_safe(f"⚠️ Skipped (inaccessible): {folder}")
                return
                
            realp = os.path.realpath(folder)
            if realp in self.visited_dirs:
                return
            self.visited_dirs.add(realp)

            if folder not in self.folder_tree_data:
                self.folder_tree_data[folder] = {'checked': False, 'is_dir': True}

            root_text = os.path.basename(folder) or folder
            
            # Add tree item from main thread
            def add_tree_item():
                root_id = self.tree.insert("", tk.END, text=root_text, open=False)
                self.tree_ids_map[folder] = root_id
                return root_id
            
            # We need to get the root_id synchronously
            root_id_result = queue.Queue()
            def get_root_id():
                root_id = add_tree_item()
                root_id_result.put(root_id)
            
            self.master.after_idle(get_root_id)
            
            # Wait for the tree item to be created
            start_wait = time.time()
            while root_id_result.empty() and time.time() - start_wait < 5:
                if cancel_flag.is_set():
                    return
                time.sleep(0.05)
            
            if root_id_result.empty():
                print(f"Timeout waiting for tree item creation for {folder}")
                return
                
            root_id = root_id_result.get()

            update_dialog_safe(f"Scanning: {folder}")
            
            self.add_directory_contents_with_dialog_threaded(folder, root_id, cancel_flag)
            
        except Exception as e:
            print(f"Error building tree for {folder}: {e}")
            update_dialog_safe(f"⚠️ Error with: {folder}")
            # Add a placeholder node to show the folder exists but had issues
            if folder not in self.folder_tree_data:
                self.folder_tree_data[folder] = {'checked': False, 'is_dir': True}
                root_text = f"{os.path.basename(folder) or folder} (⚠️ Access Error)"
                def add_error_node():
                    root_id = self.tree.insert("", tk.END, text=root_text, open=False)
                    self.tree_ids_map[folder] = root_id
                self.master.after_idle(add_error_node)

    def add_directory_contents_with_dialog(self, directory_path, parent_id):
        """Add directory contents with dialog progress updates."""
        try:
            # Check if user cancelled
            if self.loading_dialog and self.loading_dialog.is_cancelled():
                return
                
            # For local paths, do a lightweight check, for network paths use full timeout check
            if self.is_potentially_problematic_path(directory_path):
                if not self.check_folder_access_with_timeout(directory_path):
                    return
            else:
                # Quick check for local paths - just verify it exists and is accessible
                if not (os.path.exists(directory_path) and os.path.isdir(directory_path)):
                    return
                
            items = sorted(os.listdir(directory_path))
        except (PermissionError, OSError, IOError) as e:
            print(f"Cannot access directory {directory_path}: {e}")
            return

        for item in items:
            # Check if user cancelled during iteration
            if self.loading_dialog and self.loading_dialog.is_cancelled():
                break
                
            path = os.path.join(directory_path, item)

            # If ignore, skip
            if self.filters_match(path):
                continue

            # If physically the same as parent, skip (avoid repeated folder name)
            try:
                parent_real = os.path.realpath(directory_path)
                child_real = os.path.realpath(path)
                if os.path.samefile(directory_path, path):
                    # This means child is literally the same as the parent
                    continue
            except (OSError, IOError):
                # If we can't determine samefile, skip to be safe
                continue

            if child_real in self.visited_dirs and os.path.isdir(path):
                # Already processed this directory
                continue

            try:
                is_dir = os.path.isdir(path)
            except (OSError, IOError):
                # If we can't determine if it's a directory, skip it
                continue
                
            self.folder_tree_data[path] = {'checked': False, 'is_dir': is_dir}

            # Add item name with indicator if it might be problematic
            item_text = item
            if is_dir and self.is_potentially_problematic_path(path):
                item_text = f"{item} ⚠️"

            node_id = self.tree.insert(parent_id, tk.END, text=item_text, open=False)
            self.tree_ids_map[path] = node_id

            if is_dir:
                self.visited_dirs.add(child_real)
                # For subdirectories, use a reduced timeout or skip if it seems problematic
                if not self.is_potentially_problematic_path(path):
                    # Update dialog with current subdirectory being processed
                    if self.loading_dialog:
                        self.loading_dialog.update_detail(f"Scanning: {path}")
                    self.add_directory_contents_with_dialog(path, node_id)
                else:
                    print(f"Skipping potentially problematic subdirectory: {path}")

    def add_directory_contents_with_dialog_threaded(self, directory_path, parent_id, cancel_flag):
        """Add directory contents with dialog progress updates, designed for threading."""
        def update_dialog_safe(detail_text):
            """Safely update dialog from thread."""
            try:
                if self.loading_dialog:
                    self.master.after_idle(lambda: self.loading_dialog.update_detail(detail_text))
            except:
                pass
        
        try:
            # Check for cancellation
            if cancel_flag.is_set():
                return
                
            # For local paths, do a lightweight check, for network paths use full timeout check
            if self.is_potentially_problematic_path(directory_path):
                if not self.check_folder_access_with_timeout(directory_path):
                    return
            else:
                # Quick check for local paths - just verify it exists and is accessible
                if not (os.path.exists(directory_path) and os.path.isdir(directory_path)):
                    return
                
            items = sorted(os.listdir(directory_path))
        except (PermissionError, OSError, IOError) as e:
            print(f"Cannot access directory {directory_path}: {e}")
            return

        for item in items:
            # Check for cancellation during iteration
            if cancel_flag.is_set():
                break
                
            path = os.path.join(directory_path, item)

            # If ignore, skip
            if self.filters_match(path):
                continue

            # If physically the same as parent, skip (avoid repeated folder name)
            try:
                parent_real = os.path.realpath(directory_path)
                child_real = os.path.realpath(path)
                if os.path.samefile(directory_path, path):
                    # This means child is literally the same as the parent
                    continue
            except (OSError, IOError):
                # If we can't determine samefile, skip to be safe
                continue

            if child_real in self.visited_dirs and os.path.isdir(path):
                # Already processed this directory
                continue

            try:
                is_dir = os.path.isdir(path)
            except (OSError, IOError):
                # If we can't determine if it's a directory, skip it
                continue
                
            self.folder_tree_data[path] = {'checked': False, 'is_dir': is_dir}

            # Add item name with indicator if it might be problematic
            item_text = item
            if is_dir and self.is_potentially_problematic_path(path):
                item_text = f"{item} ⚠️"

            # Add tree item from main thread
            def add_tree_item():
                node_id = self.tree.insert(parent_id, tk.END, text=item_text, open=False)
                self.tree_ids_map[path] = node_id
                return node_id
            
            # We need to get the node_id synchronously
            node_id_result = queue.Queue()
            def get_node_id():
                node_id = add_tree_item()
                node_id_result.put(node_id)
            
            self.master.after_idle(get_node_id)
            
            # Wait for the tree item to be created
            start_wait = time.time()
            while node_id_result.empty() and time.time() - start_wait < 5:
                if cancel_flag.is_set():
                    return
                time.sleep(0.05)
            
            if node_id_result.empty():
                print(f"Timeout waiting for tree item creation for {path}")
                continue
                
            node_id = node_id_result.get()

            if is_dir:
                self.visited_dirs.add(child_real)
                # For subdirectories, use a reduced timeout or skip if it seems problematic
                if not self.is_potentially_problematic_path(path):
                    # Update dialog with current subdirectory being processed
                    update_dialog_safe(f"Scanning: {path}")
                    self.add_directory_contents_with_dialog_threaded(path, node_id, cancel_flag)
                else:
                    print(f"Skipping potentially problematic subdirectory: {path}")

    def apply_saved_checks(self):
        """Apply saved check states from config, respecting filters."""
        # Keep track of applied checks for verification
        applied_checks = {}
        
        for path, checked in self.saved_folder_checks.items():
            # Only apply checks to paths that:
            # 1. Exist in the folder tree data
            # 2. Are not filtered out by ignore patterns
            if path in self.folder_tree_data and not self.filters_match(path):
                self.folder_tree_data[path]['checked'] = checked
                applied_checks[path] = checked
                item_id = self.tree_ids_map.get(path)
                if item_id:
                    text = self.tree.item(item_id, 'text')
                    if checked and not text.startswith("[x] "):
                        self.tree.item(item_id, text="[x] " + text)
                    elif not checked and text.startswith("[x] "):
                        self.tree.item(item_id, text=text.replace("[x] ", "", 1))
        
        # Don't clear saved_folder_checks immediately - keep them for potential re-application
        # as the tree continues to build. We'll schedule a delayed clear instead.
        
        # Update button count and automatically expand tree to show selected items
        self.update_show_selected_button()
        
        # Schedule delayed expansion and cleanup
        self.master.after(100, self.expand_to_show_selected)
        self.master.after(500, self._delayed_apply_remaining_checks)  # Check again after 500ms
        self.master.after(2000, self._clear_saved_checks)  # Clear after 2 seconds
    
    def _delayed_apply_remaining_checks(self):
        """Apply any remaining saved checks that weren't applied initially."""
        remaining_checks = {}
        for path, checked in self.saved_folder_checks.items():
            if path not in self.folder_tree_data:
                remaining_checks[path] = checked
            elif path in self.folder_tree_data and self.folder_tree_data[path].get('checked', False) != checked:
                # Re-apply the check if it doesn't match
                if not self.filters_match(path):
                    self.folder_tree_data[path]['checked'] = checked
                    item_id = self.tree_ids_map.get(path)
                    if item_id:
                        text = self.tree.item(item_id, 'text')
                        if checked and not text.startswith("[x] "):
                            self.tree.item(item_id, text="[x] " + text)
                        elif not checked and text.startswith("[x] "):
                            self.tree.item(item_id, text=text.replace("[x] ", "", 1))
        
        if remaining_checks:
            print(f"Applied {len(remaining_checks)} additional saved checks")
            self.update_show_selected_button()
    
    def _clear_saved_checks(self):
        """Clear the saved folder checks after giving enough time for tree building."""
        if self.saved_folder_checks:
            print(f"Clearing {len(self.saved_folder_checks)} saved checks")
        self.saved_folder_checks = {}

    # -----------------------------------------------------------------------
    #  IGNORE PATTERNS
    # -----------------------------------------------------------------------
    def filters_match(self, path):
        """
        Check if a path matches any of the ignore patterns.
        Returns True if the path should be ignored.
        """
        fpath = path.replace("\\", "/")
        
        # Check user-defined ignore patterns
        for pat in self.ignore_patterns:
            pclean = pat.strip()
            if pclean and fnmatch.fnmatch(fpath, pclean):
                return True
                
        # Only check default ignore patterns if the filter is enabled
        if self.filter_system_folders.get():
            # Also check default ignore patterns
            for pat in self.default_ignore_patterns:
                pclean = pat.strip()
                if pclean and fnmatch.fnmatch(fpath, pclean):
                    return True
            
            # Check if file/folder is hidden (starts with dot)
            basename = os.path.basename(path)
            if basename.startswith('.') and len(basename) > 1:  # Skip '.' and '..' directories
                return True
            
        return False

    def on_save_filters(self):
        raw = self.filters_text.get("1.0", tk.END)
        lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
        self.ignore_patterns = lines
        # Rebuild everything
        self.build_all_trees()
        self.save_settings()
        self.set_status("Ignore patterns saved & tree refreshed.")

    # -----------------------------------------------------------------------
    #  POLLING
    # -----------------------------------------------------------------------
    def schedule_folder_poll(self):
        self.poll_folder()
        self.master.after(self.poll_interval_ms, self.schedule_folder_poll)

    def poll_folder(self):
        """
        Check for new items in each root folder using os.walk,
        skip if ignore or visited, also skip if child is samefile() as parent.
        """
        for folder in self.root_folders:
            if not os.path.exists(folder):
                continue
            for root, dirs, files in os.walk(folder):
                root_real = os.path.realpath(root)
                # skip if root is ignored or visited
                if self.filters_match(root) or (root_real in self.visited_dirs):
                    continue

                # If not in data => new subfolder
                if root not in self.folder_tree_data:
                    self.folder_tree_data[root] = {'checked': False, 'is_dir': True}
                    parent = os.path.dirname(root)
                    if parent in self.tree_ids_map:
                        node_id = self.tree.insert(self.tree_ids_map[parent], tk.END,
                                                   text=os.path.basename(root), open=False)
                        self.tree_ids_map[root] = node_id
                    self.visited_dirs.add(root_real)

                for d in dirs:
                    dpath = os.path.join(root, d)
                    dreal = os.path.realpath(dpath)
                    if self.filters_match(dpath) or (dreal in self.visited_dirs):
                        continue
                    if os.path.samefile(root, dpath):
                        continue
                    if dpath not in self.folder_tree_data:
                        self.folder_tree_data[dpath] = {'checked': False, 'is_dir': True}
                        if root in self.tree_ids_map:
                            node_id = self.tree.insert(self.tree_ids_map[root], tk.END, text=d, open=False)
                            self.tree_ids_map[dpath] = node_id
                        self.visited_dirs.add(dreal)

                for f in files:
                    fpath = os.path.join(root, f)
                    freal = os.path.realpath(fpath)
                    if self.filters_match(fpath) or (freal in self.visited_dirs):
                        continue
                    if os.path.samefile(root, fpath):
                        continue
                    if fpath not in self.folder_tree_data:
                        self.folder_tree_data[fpath] = {'checked': False, 'is_dir': False}
                        if root in self.tree_ids_map:
                            node_id = self.tree.insert(self.tree_ids_map[root], tk.END, text=f, open=False)
                            self.tree_ids_map[fpath] = node_id
                        self.visited_dirs.add(freal)

    # -----------------------------------------------------------------------
    #  CHECK / UNCHECK
    # -----------------------------------------------------------------------
    def on_tree_item_double_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        path = self.find_path_by_tree_id(item_id)
        if not path:
            return
        current = self.folder_tree_data[path]['checked']
        new_state = not current
        self.set_subtree_checked(path, new_state)
        self.save_settings()

    def set_subtree_checked(self, path, checked):
        """Mark path and all its children as checked/unchecked."""
        # Update internal data structure
        self.folder_tree_data[path]['checked'] = checked
        
        # Update UI
        item_id = self.tree_ids_map.get(path)
        if item_id:
            text = self.tree.item(item_id, 'text')
            text_without_check = text.replace("[x] ", "", 1) if text.startswith("[x] ") else text
            
            if checked:
                self.tree.item(item_id, text=f"[x] {text_without_check}")
            else:
                self.tree.item(item_id, text=text_without_check)

        # Recursively update children if this is a directory
        if self.folder_tree_data[path]['is_dir']:
            for p in list(self.folder_tree_data.keys()):
                if os.path.dirname(p) == path:
                    self.set_subtree_checked(p, checked)
        
        # Update the show selected button count
        self.update_show_selected_button()

    def find_path_by_tree_id(self, tree_id):
        for p, tid in self.tree_ids_map.items():
            if tid == tree_id:
                return p
        return None

    def on_show_selected_files(self):
        """Expand the tree to show all selected files and folders."""
        self._manual_expand_call = True
        self.expand_to_show_selected()
        
    def expand_to_show_selected(self):
        """Expand tree nodes to make all selected items visible."""
        selected_paths = [path for path, info in self.folder_tree_data.items() if info['checked']]
        
        if not selected_paths:
            # Only show this message if called manually (not during auto-expansion)
            if hasattr(self, '_manual_expand_call'):
                self.set_status("No files are currently selected.")
                delattr(self, '_manual_expand_call')
            return
        
        # Collect all parent directories that need to be expanded
        paths_to_expand = set()
        
        for selected_path in selected_paths:
            # Add the selected path itself if it's a directory
            if self.folder_tree_data[selected_path]['is_dir']:
                paths_to_expand.add(selected_path)
            
            # Add all parent directories of this selected path
            current_path = selected_path
            while current_path:
                parent_path = os.path.dirname(current_path)
                if parent_path and parent_path != current_path and parent_path in self.folder_tree_data:
                    paths_to_expand.add(parent_path)
                    current_path = parent_path
                else:
                    break
        
        # Also add the root folders themselves
        for root_folder in self.root_folders:
            if root_folder in self.folder_tree_data:
                paths_to_expand.add(root_folder)
        
        # Expand all necessary nodes
        expanded_count = 0
        for path in sorted(paths_to_expand):  # Sort to expand from root to leaves
            if path in self.tree_ids_map:
                tree_id = self.tree_ids_map[path]
                if self.tree.exists(tree_id):
                    # Check if it's currently collapsed
                    if not self.tree.item(tree_id, 'open'):
                        self.tree.item(tree_id, open=True)
                        expanded_count += 1
        
        # Scroll to the first selected item to make it visible
        if selected_paths:
            # Sort selected paths to find the "first" one (alphabetically)
            first_selected = sorted(selected_paths)[0]
            if first_selected in self.tree_ids_map:
                tree_id = self.tree_ids_map[first_selected]
                if self.tree.exists(tree_id):
                    self.tree.see(tree_id)
                    # Also select it to highlight it
                    self.tree.selection_set(tree_id)
        
        selected_count = len(selected_paths)
        # Only show status message if called manually
        if hasattr(self, '_manual_expand_call'):
            self.set_status(f"Expanded tree to show {selected_count} selected items (expanded {expanded_count} folders).")
            delattr(self, '_manual_expand_call')
        
        # Update the button text to show count
        self.update_show_selected_button()

    def update_show_selected_button(self):
        """Update the 'Show All Selected Files' button text to show count."""
        if hasattr(self, 'btn_show_selected'):
            selected_count = len([path for path, info in self.folder_tree_data.items() if info['checked']])
            if selected_count > 0:
                self.btn_show_selected.config(text=f"Show All Selected Files ({selected_count})")
            else:
                self.btn_show_selected.config(text="Show All Selected Files")

    # -----------------------------------------------------------------------
    #  META PROMPTS
    # -----------------------------------------------------------------------
    def on_add_prompt(self):
        def save_prompt():
            title = entry_title.get().strip()
            content = text_content.get("1.0", tk.END).strip()
            if title:
                self.meta_prompts.append({"title": title, "content": content, "checked": True})
                prompt_win.destroy()
                self.refresh_prompts_listbox()
                self.save_settings()

        prompt_win = tk.Toplevel(self.master)
        prompt_win.title("New Meta Prompt")

        tk.Label(prompt_win, text="Title:").pack(anchor=tk.W, padx=5, pady=2)
        entry_title = tk.Entry(prompt_win, width=40)
        entry_title.pack(fill=tk.X, padx=5, pady=2)

        tk.Label(prompt_win, text="Content:").pack(anchor=tk.W, padx=5, pady=2)
        text_content = ScrolledText(prompt_win, height=6, width=40)
        text_content.pack(fill=tk.BOTH, padx=5, pady=2)

        btn_save = tk.Button(prompt_win, text="Save Prompt", command=save_prompt)
        btn_save.pack(side=tk.RIGHT, padx=5, pady=5)

    def refresh_prompts_listbox(self):
        self.prompts_listbox.delete(0, tk.END)
        for prompt in self.meta_prompts:
            prefix = "[x]" if prompt['checked'] else "[ ]"
            self.prompts_listbox.insert(tk.END, f"{prefix} {prompt['title']}")

    def on_toggle_prompt(self):
        idxs = self.prompts_listbox.curselection()
        if not idxs:
            return
        idx = idxs[0]
        self.meta_prompts[idx]['checked'] = not self.meta_prompts[idx]['checked']
        self.refresh_prompts_listbox()
        self.save_settings()
        prompt_status = "enabled" if self.meta_prompts[idx]['checked'] else "disabled"
        self.set_status(f"Meta prompt {self.meta_prompts[idx]['title']} {prompt_status}.")

    def on_remove_prompt(self):
        idxs = self.prompts_listbox.curselection()
        if not idxs:
            return
        idx = idxs[0]
        del self.meta_prompts[idx]
        self.refresh_prompts_listbox()
        self.save_settings()

    def on_edit_prompt(self):
        idxs = self.prompts_listbox.curselection()
        if not idxs:
            return
        idx = idxs[0]
        prompt = self.meta_prompts[idx]

        def save_edited_prompt():
            title = entry_title.get().strip()
            content = text_content.get("1.0", tk.END).strip()
            if title:
                prompt["title"] = title
                prompt["content"] = content
                edit_win.destroy()
                self.refresh_prompts_listbox()
                self.save_settings()

        edit_win = tk.Toplevel(self.master)
        edit_win.title("Edit Meta Prompt")

        tk.Label(edit_win, text="Title:").pack(anchor=tk.W, padx=5, pady=2)
        entry_title = tk.Entry(edit_win, width=40)
        entry_title.pack(fill=tk.X, padx=5, pady=2)
        entry_title.insert(0, prompt["title"])

        tk.Label(edit_win, text="Content:").pack(anchor=tk.W, padx=5, pady=2)
        text_content = ScrolledText(edit_win, height=6, width=40)
        text_content.pack(fill=tk.BOTH, padx=5, pady=2)
        text_content.insert("1.0", prompt["content"])

        btn_save = tk.Button(edit_win, text="Save Changes", command=save_edited_prompt)
        btn_save.pack(side=tk.RIGHT, padx=5, pady=5)

    # -----------------------------------------------------------------------
    #  USER INSTRUCTIONS
    # -----------------------------------------------------------------------
    def on_instructions_modified(self, event):
        if self.instructions_text.edit_modified():
            self.instructions_text.edit_modified(False)
            self.user_instructions = self.instructions_text.get("1.0", tk.END).strip()
            self.save_settings()

    def toggle_instructions_size(self):
        """Toggle between compact and expanded instructions view."""
        is_expanded = self.instructions_expanded.get()
        if is_expanded:
            self.instructions_text.configure(height=4)
            self.expand_btn.configure(text="Expand")
        else:
            self.instructions_text.configure(height=20)
            self.expand_btn.configure(text="Collapse")
        self.instructions_expanded.set(not is_expanded)

    # -----------------------------------------------------------------------
    #  COPY TO CLIPBOARD
    # -----------------------------------------------------------------------
    def on_copy_to_clipboard(self):
        self.user_instructions = self.instructions_text.get("1.0", tk.END).strip()
        
        # Verify that checked items still exist and are accessible
        # This prevents filter-hidden items from being selected
        self.validate_checked_items()
        
        if self.copy_entire_tree_var.get():
            file_tree_block = self.build_full_file_tree_text()
        else:
            file_tree_block = self.build_checked_file_tree_text()

        file_contents_block = self.build_file_contents_text()
        meta_prompts_block = self.build_meta_prompts_text()
        user_instructions_block = f"<user_instructions>\n{self.user_instructions}\n</user_instructions>"

        final_clip = (
            f"<file_tree>\n{file_tree_block}\n</file_tree>\n\n"
            f"<file_contents>\n{file_contents_block}\n</file_contents>\n\n"
            f"{meta_prompts_block}\n"
            f"{user_instructions_block}\n"
        )

        # Check if this content is identical to the most recent history item
        is_duplicate = False
        if self.history_items:
            latest_history_path = os.path.join(self.history_items[0]['path'], "content.txt")
            try:
                if os.path.exists(latest_history_path):
                    with open(latest_history_path, 'r', encoding='utf-8') as f:
                        last_content = f.read()
                    if last_content == final_clip:
                        is_duplicate = True
            except Exception:
                # If there's any error reading the file, assume it's not a duplicate
                pass

        # Only save to history if it's not a duplicate
        if not is_duplicate:
            self.save_history_item(final_clip, self.user_instructions)
            self.set_status("Data copied to clipboard and saved to history.")
        else:
            self.set_status("Data copied to clipboard (duplicate not saved to history).")

        self.master.clipboard_clear()
        self.master.clipboard_append(final_clip)
        self.save_settings()

    def on_copy_to_temp_file(self):
        """Save content to a temporary file and copy the file path to clipboard."""
        self.user_instructions = self.instructions_text.get("1.0", tk.END).strip()
        
        # Verify that checked items still exist and are accessible
        self.validate_checked_items()
        
        if self.copy_entire_tree_var.get():
            file_tree_block = self.build_full_file_tree_text()
        else:
            file_tree_block = self.build_checked_file_tree_text()

        file_contents_block = self.build_file_contents_text()
        meta_prompts_block = self.build_meta_prompts_text()
        user_instructions_block = f"<user_instructions>\n{self.user_instructions}\n</user_instructions>"

        final_content = (
            f"<file_tree>\n{file_tree_block}\n</file_tree>\n\n"
            f"<file_contents>\n{file_contents_block}\n</file_contents>\n\n"
            f"{meta_prompts_block}\n"
            f"{user_instructions_block}\n"
        )

        try:
            # Create a temporary file with a descriptive name
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_file = tempfile.NamedTemporaryFile(
                mode='w', 
                encoding='utf-8', 
                suffix=f'_codellm_bridge_{timestamp}.txt',
                delete=False  # Don't delete automatically so LLMs can read it
            )
            
            # Write the content to the temporary file
            temp_file.write(final_content)
            temp_file.close()
            
            # Copy the actual file to clipboard (like right-click copy in Windows Explorer)
            import subprocess
            import os
            
            # Use Windows PowerShell to copy the file to clipboard
            try:
                # Convert path to Windows format if needed
                windows_path = temp_file.name.replace('/', '\\')
                
                # Determine which PowerShell executable is available
                # Try "powershell" first (Windows PowerShell), then "pwsh" (PowerShell Core)
                ps_executables = [
                    "powershell",  # Windows PowerShell if already in PATH
                    "powershell.exe",
                    r"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",  # Default Win PS path
                    "pwsh",  # PowerShell Core (as last resort)
                    "pwsh.exe"
                ]
                ps_exe = None
                for exe in ps_executables:
                    if shutil.which(exe):
                        ps_exe = exe
                        break

                if ps_exe:
                    # Use -LiteralPath to avoid wildcard expansion
                    ps_command = f'Set-Clipboard -LiteralPath \"{windows_path}\"'

                    # Use -NoProfile for faster startup and to avoid user profile side effects
                    subprocess.run([ps_exe, '-NoProfile', '-Command', ps_command], 
                                   check=True, capture_output=True, text=True)
                    print(f"Copied file to clipboard using {ps_exe}")
                else:
                    raise FileNotFoundError("No compatible Windows PowerShell executable found for Set-Clipboard")

            except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
                print(f"PowerShell file copy failed: {e} - falling back to copying path as text")
                # Fallback: copy file path as plain text if PowerShell method fails
                try:
                    self.master.clipboard_clear()
                    self.master.clipboard_append(temp_file.name)
                except Exception as clip_e:
                    print(f"Clipboard fallback failed: {clip_e}")
            
            # Check if this content is identical to the most recent history item
            is_duplicate = False
            if self.history_items:
                latest_history_path = os.path.join(self.history_items[0]['path'], "content.txt")
                try:
                    if os.path.exists(latest_history_path):
                        with open(latest_history_path, 'r', encoding='utf-8') as f:
                            last_content = f.read()
                        if last_content == final_content:
                            is_duplicate = True
                except Exception:
                    # If there's any error reading the file, assume it's not a duplicate
                    pass

            # Only save to history if it's not a duplicate
            if not is_duplicate:
                self.save_history_item(final_content, self.user_instructions)
                self.set_status(f"Content saved to temporary file: {temp_file.name}\nFile copied to clipboard and saved to history.")
            else:
                self.set_status(f"Content saved to temporary file: {temp_file.name}\nFile copied to clipboard (duplicate not saved to history).")
            
            self.save_settings()
            
        except Exception as e:
            self.set_status(f"Error creating temporary file: {str(e)}")
        
    def validate_checked_items(self):
        """
        Ensure that only items that are visible and explicitly checked
        remain marked as checked in the data structure.
        """
        # Create a set of visible paths
        visible_paths = set()
        for path in self.folder_tree_data:
            # Skip items that match filters
            if self.filters_match(path):
                # If this was checked, uncheck it since it's filtered
                if path in self.folder_tree_data and self.folder_tree_data[path]['checked']:
                    print(f"Unchecking filtered item: {path}")
                    self.folder_tree_data[path]['checked'] = False
                continue
                
            # Item is visible
            visible_paths.add(path)
        
        # Now go through and ensure only visible items can be checked
        for path in list(self.folder_tree_data.keys()):
            # If the path isn't visible but is checked, uncheck it
            if path not in visible_paths and self.folder_tree_data[path]['checked']:
                print(f"Unchecking non-visible item: {path}")
                self.folder_tree_data[path]['checked'] = False

    # -----------------------------------------------------------------------
    #  BUILD FILE TREE: FULL vs CHECKED
    # -----------------------------------------------------------------------
    def build_checked_file_tree_text(self):
        """
        Build a text representation of ONLY checked items in the tree.
        Unchecked parent folders won't be shown.
        """
        if not self.root_folders:
            return "No folders selected."

        # Get all explicitly checked paths
        checked_paths = [path for path, info in self.folder_tree_data.items() 
                        if info['checked']]
        
        if not checked_paths:
            return "(No items selected)"

        # Sort paths for consistent output
        checked_paths.sort()
        
        # Debug what we're including in the tree
        print(f"Including {len(checked_paths)} checked items in file tree:")
        for path in checked_paths:
            is_dir = self.folder_tree_data[path]['is_dir']
            print(f"  - {'[DIR] ' if is_dir else ''}{path}")
        
        # Organize by directories for a cleaner view
        # First, separate directories and files
        checked_dirs = [path for path in checked_paths if self.folder_tree_data[path]['is_dir']]
        checked_files = [path for path in checked_paths if not self.folder_tree_data[path]['is_dir']]
        
        # Build lines for the output
        lines = []
        
        # First add any checked directories
        for dir_path in checked_dirs:
            lines.append(dir_path)  # Add the directory path
            
            # Look for any checked files that are direct children of this directory
            child_files = [f for f in checked_files if os.path.dirname(f) == dir_path]
            if child_files:
                # Sort child files for consistent output
                child_files.sort()
                # Add each child file with indentation
                for i, child in enumerate(child_files):
                    is_last = (i == len(child_files) - 1)
                    branch = "└── " if is_last else "├── "
                    lines.append(f"    {branch}{os.path.basename(child)}")
                    # Remove from checked_files so we don't process it again
                    checked_files.remove(child)
                    
        # Now add any remaining checked files that aren't children of checked directories
        for file_path in checked_files:
            lines.append(file_path)
            
        return "\n".join(lines)

    def build_full_file_tree_text(self):
        if not self.root_folders:
            return "No folders selected."

        lines = []

        def recurse(path, prefix=""):
            basename = os.path.basename(path) or path
            if prefix == "":
                lines.append(path)
            else:
                lines.append(f"{prefix}{basename}")

            children = [p for p in self.folder_tree_data if os.path.dirname(p) == path]
            subdirs = [c for c in children if self.folder_tree_data[c]['is_dir']]
            subfiles = [c for c in children if not self.folder_tree_data[c]['is_dir']]
            subdirs.sort()
            subfiles.sort()
            all_items = subdirs + subfiles

            for i, child in enumerate(all_items):
                is_last = (i == len(all_items) - 1)
                branch = "└── " if is_last else "├── "
                deeper_prefix = "    " if is_last else "│   "

                if self.folder_tree_data[child]['is_dir']:
                    recurse(child, prefix + branch)  # Remove extra line for directory
                else:
                    lines.append(prefix + branch + os.path.basename(child))

        for rf in self.root_folders:
            if os.path.exists(rf) and rf in self.folder_tree_data:
                recurse(rf)

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    #  BUILD FILE CONTENTS + META PROMPTS
    # -----------------------------------------------------------------------
    def build_file_contents_text(self):
        """Build a text representation of the contents of checked files."""
        lines = []
        
        # Get a list of all checked files (not directories)
        checked_files = [path for path, info in self.folder_tree_data.items() 
                        if info['checked'] and not info['is_dir']]
        
        # Sort them for consistent output
        checked_files.sort()
        
        # Debug info about what's being copied
        print(f"Copying {len(checked_files)} checked files:")
        for path in checked_files:
            print(f"  - {path}")
        
        # Build the content for each file
        for path in checked_files:
            filename = os.path.basename(path)
            ext = os.path.splitext(filename)[1].lstrip('.') or "txt"
            lines.append(f"File: {path}")
            lines.append(f"```{ext}")
            try:
                content = read_file_with_fallback(path)
                if self.strip_comments_var.get():
                    content = remove_comments_from_code(content, ext)
                lines.append(content)
            except Exception as e:
                lines.append(f"<Error reading file: {e}>")
            lines.append("```")
            lines.append("")
            
        return "\n".join(lines)

    def build_meta_prompts_text(self):
        lines = []
        idx = 1
        for prompt in self.meta_prompts:
            if prompt['checked']:
                lines.append(f"<meta prompt {idx}=\"{prompt['title']}\">")
                lines.append(prompt['content'])
                lines.append(f"</meta prompt {idx}>")
                idx += 1
        return "\n".join(lines)

    # -----------------------------------------------------------------------
    #  SAVE / LOAD
    # -----------------------------------------------------------------------
    def save_settings(self):
        """Save settings to either default or profile."""
        if self.current_profile == "default":
            try:
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    data = {
                        "root_folders": self.root_folders,
                        "user_instructions": self.user_instructions,
                        "meta_prompts": self.meta_prompts,
                        "folder_checks": {},
                        "ignore_patterns": self.ignore_patterns,
                        "copy_entire_tree": self.copy_entire_tree_var.get(),
                        "filter_system_folders": self.filter_system_folders.get(),
                        "dark_mode": self.dark_mode.get(),
                        "prepend_string": self.prepend_string,
                        "prepend_hotkey_enabled": self.prepend_hotkey_enabled.get(),
                        "hotkey_combination": self.hotkey_combination,
                        "enable_timeouts": self.enable_timeouts.get(),
                        "strip_comments": self.strip_comments_var.get(),
                        "selection_presets": getattr(self, 'selection_presets', {}),
                    }
                    for path, info in self.folder_tree_data.items():
                        data["folder_checks"][path] = info['checked']
                    json.dump(data, f, indent=2)
            except Exception as e:
                messagebox.showerror("Error Saving Settings", str(e))
        else:
            self.save_profile(self.current_profile)

    def load_settings(self):
        """Load settings from either default or profile."""
        is_first_launch = False
        
        if self.current_profile == "default":
            if not os.path.exists(CONFIG_FILE):
                # Add default meta prompt and ignore patterns for new installations
                self.add_default_meta_prompts()
                self.ignore_patterns = self.default_initial_ignore_patterns.copy()
                is_first_launch = True
                # We'll skip loading from file but still update the UI
                self.save_settings()  # Create the file for next time
            else:
                config_path = CONFIG_FILE
        else:
            config_path = os.path.join(PROFILES_DIR, f"{self.current_profile}.json")
            if not os.path.exists(config_path):
                # Add defaults for new profile
                self.add_default_meta_prompts()
                self.ignore_patterns = self.default_initial_ignore_patterns.copy()
                is_first_launch = True
                self.save_settings()  # Create the file for next time
        
        if not is_first_launch:  # Only load from file if it's not first launch
            try:
                # Clear existing data
                self.folder_tree_data.clear() 
                self.tree_ids_map.clear()
                self.saved_folder_checks.clear()
                self.visited_dirs.clear()
                
                # Remove all items from tree view
                self.tree.delete(*self.tree.get_children())
                
                # Load new settings
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.root_folders = data.get("root_folders", [])
                self.user_instructions = data.get("user_instructions", "")
                self.meta_prompts = data.get("meta_prompts", [])
                # Check if we need to add the default meta prompt
                if not self.meta_prompts:
                    self.add_default_meta_prompts()
                
                self.saved_folder_checks = data.get("folder_checks", {})
                self.ignore_patterns = data.get("ignore_patterns", [])
                self.copy_entire_tree_var.set(data.get("copy_entire_tree", False))
                self.filter_system_folders.set(data.get("filter_system_folders", True))
                self.dark_mode.set(data.get("dark_mode", False))
                self.prepend_string = data.get("prepend_string", DEFAULT_PREPEND_STRING)
                self.prepend_hotkey_enabled.set(data.get("prepend_hotkey_enabled", False))
                self.hotkey_combination = data.get("hotkey_combination", "ctrl+alt+v")
                self.enable_timeouts.set(data.get("enable_timeouts", True))
                self.strip_comments_var.set(data.get("strip_comments", False))
                self.selection_presets = data.get("selection_presets", {})
            except Exception as e:
                messagebox.showerror("Error Loading Settings", str(e))
        
        # Always update the UI, whether it's first launch or not
        
        # Build the tree with current settings
        self.build_all_trees()
        
        # Update UI
        if hasattr(self, 'instructions_text'):
            self.instructions_text.delete("1.0", tk.END)
            self.instructions_text.insert("1.0", self.user_instructions)
        
        if hasattr(self, 'filters_text'):
            self.filters_text.delete("1.0", tk.END)
            self.filters_text.insert("1.0", "\n".join(self.ignore_patterns))
        
        self.refresh_prompts_listbox()
        
        # Load history for this profile
        self.load_history()
        
        # Update preset combo box
        self.update_preset_combo()

        if hasattr(self, 'prepend_entry'):
            self.prepend_entry.delete(0, tk.END)
            self.prepend_entry.insert(0, self.prepend_string)
            # Ensure the entry shows the full text by moving to the beginning
            self.prepend_entry.icursor(0)
        if hasattr(self, 'prepend_hotkey_check'):
            self.prepend_hotkey_check.select() if self.prepend_hotkey_enabled.get() else self.prepend_hotkey_check.deselect()
        if hasattr(self, 'hotkey_display'):
            self.hotkey_display.config(text=self.hotkey_combination.upper())
        
        # Update dark mode checkbox to reflect loaded setting
        if hasattr(self, 'dark_mode_check'):
            if self.dark_mode.get():
                self.dark_mode_check.select()
            else:
                self.dark_mode_check.deselect()
        
        # Note: setup_global_hotkey() is called after theme is applied in __init__

    def add_default_meta_prompts(self):
        """Add default meta prompts for new installations or empty profiles."""
        # Check if we already have a meta prompt with this title
        existing_titles = [p["title"] for p in self.meta_prompts]
        
        if "Please Provide Code in Chat" not in existing_titles:
            self.meta_prompts.append({
                "title": "Please Provide Code in Chat",
                "content": "Please provide all code and edits directly in the chat interface, not in a code editor or canvas. This makes it easier for me to copy and implement your suggestions in my development environment.\n\nWhen suggesting code edits, please:\n- Clearly indicate which files to modify\n- Specify the locations for changes (line numbers, function names, etc.)\n- Show complete code blocks with enough context to locate the edit points\n- Format your response in a way that's easy to copy from chat",
                "checked": True
            })
            self.save_settings()

    def get_available_profiles(self):
        """Get list of available profile names."""
        profiles = ["default"]
        if os.path.exists(PROFILES_DIR):
            for f in os.listdir(PROFILES_DIR):
                if f.endswith('.json'):
                    profiles.append(os.path.splitext(f)[0])
        return sorted(profiles)
    
    def load_last_profile(self):
        """Load the last selected profile from file."""
        try:
            if os.path.exists(LAST_PROFILE_FILE):
                with open(LAST_PROFILE_FILE, 'r', encoding='utf-8') as f:
                    last_profile = f.read().strip()
                    # Verify the profile still exists
                    if last_profile == "default" or (os.path.exists(PROFILES_DIR) and 
                        os.path.exists(os.path.join(PROFILES_DIR, f"{last_profile}.json"))):
                        return last_profile
        except Exception as e:
            print(f"Error loading last profile: {e}")
        return "default"
    
    def load_last_profile_with_fallback(self):
        """Load the last selected profile with fallback to a working profile if needed."""
        last_profile = self.load_last_profile()
        
        # If it's the default profile, just return it
        if last_profile == "default":
            return last_profile
            
        # Check if the profile file exists
        profile_path = os.path.join(PROFILES_DIR, f"{last_profile}.json")
        if not os.path.exists(profile_path):
            print(f"Profile file {profile_path} not found, falling back to default")
            return "default"
            
        # Try to quickly validate the profile by checking for problematic paths
        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                root_folders = data.get("root_folders", [])
                
                # Check if any folders might be network/FTP paths
                problematic_folders = []
                for folder in root_folders:
                    if self.is_potentially_problematic_path(folder):
                        problematic_folders.append(folder)
                
                # If we found problematic folders, we'll return this profile but mark it for careful loading
                if problematic_folders:
                    print(f"Found potentially problematic folders in {last_profile}: {problematic_folders}")
                    
                return last_profile
                    
        except Exception as e:
            print(f"Error validating profile {last_profile}: {e}")
            return "default"
    
    def is_potentially_problematic_path(self, path):
        """Check if a path might be problematic (network, FTP, etc.)"""
        # Check for network paths
        if path.startswith('\\\\') or path.startswith('//'):
            return True
        
        # Check for FTP-like URLs  
        if any(path.lower().startswith(protocol) for protocol in ['ftp://', 'sftp://', 'ftps://']):
            return True
            
        # Check for very long paths that might be network mounted
        if len(path) > 200:
            return True
            
        # Check for paths that don't exist locally
        try:
            if not os.path.exists(path):
                return True
        except (OSError, IOError):
            return True
            
        return False
    
    def load_settings_smart(self):
        """Smart loading that tries simple load first for local folders, then falls back to timeout system."""
        original_profile = self.current_profile
        
        # First, try to determine if we have mostly local folders
        try:
            if self.current_profile == "default":
                config_path = CONFIG_FILE
            else:
                config_path = os.path.join(PROFILES_DIR, f"{self.current_profile}.json")
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                root_folders = data.get("root_folders", [])
                
                # Check if most folders are local (not problematic)
                local_folders = []
                problematic_folders = []
                for folder in root_folders:
                    if self.is_potentially_problematic_path(folder):
                        problematic_folders.append(folder)
                    else:
                        local_folders.append(folder)
                
                # If most folders are local, try a direct load first
                if len(local_folders) >= len(problematic_folders):
                    print(f"Profile has {len(local_folders)} local folders vs {len(problematic_folders)} network folders - trying direct load")
                    try:
                        # Try direct load for profiles with mostly local folders
                        self.load_settings()
                        print("Direct load successful!")
                        return
                    except Exception as e:
                        print(f"Direct load failed: {e}, falling back to timeout system")
                
        except Exception as e:
            print(f"Error checking profile: {e}")
        
        # Fall back to timeout system
        print("Using timeout-based loading system")
        self.load_settings_with_timeout()
    
    def load_settings_with_timeout(self):
        """Load settings with timeout handling and fallback mechanisms."""
        original_profile = self.current_profile
        
        # Show loading dialog
        self.loading_dialog = LoadingDialog(self.master, f"Loading Profile: {original_profile}")
        self.loading_dialog.update_operation(f"Loading profile '{original_profile}'...")
        
        try:
            # Try to load with timeout
            if os.name == 'nt':  # Windows - use threading approach
                self.load_settings_windows_timeout_with_dialog()
            else:  # Unix-like systems - use signal approach
                with FolderLoadingTimeout(FOLDER_LOADING_TIMEOUT):
                    self.load_settings_with_dialog()
                    
        except (TimeoutError, Exception) as e:
            print(f"Failed to load profile '{original_profile}': {e}")
            
            # Check if user cancelled
            if self.loading_dialog and self.loading_dialog.is_cancelled():
                cancel_type = self.loading_dialog.get_cancel_type()
                if cancel_type == "cancel":
                    # User wants to use default profile
                    self.current_profile = "default"
                    self.is_fallback_profile = True
                    self.loading_dialog.update_operation("Loading default profile...")
                    try:
                        self.load_minimal_settings()
                    except Exception:
                        self.load_minimal_settings()
                elif cancel_type == "skip":
                    # User wants to skip to a working fallback
                    self.is_fallback_profile = True
                    fallback_profile = self.find_working_fallback_profile()
                    self.current_profile = fallback_profile
                    self.loading_dialog.update_operation(f"Loading fallback profile '{fallback_profile}'...")
                    try:
                        if os.name == 'nt':
                            self.load_settings_windows_timeout_with_dialog()
                        else:
                            with FolderLoadingTimeout(FOLDER_LOADING_TIMEOUT):
                                self.load_settings_with_dialog()
                    except Exception:
                        self.load_minimal_settings()
            else:
                # Automatic fallback due to timeout
                self.is_fallback_profile = True
                
                # Try to find a working fallback profile
                fallback_profile = self.find_working_fallback_profile()
                
                if fallback_profile != original_profile:
                    print(f"Falling back to profile: {fallback_profile}")
                    self.current_profile = fallback_profile
                    # Don't save this as the last profile - we want to remember the user's preference
                    
                    if self.loading_dialog:
                        self.loading_dialog.update_operation(f"Loading fallback profile '{fallback_profile}'...")
                    
                    # Try loading the fallback profile
                    try:
                        if os.name == 'nt':
                            self.load_settings_windows_timeout_with_dialog()
                        else:
                            with FolderLoadingTimeout(FOLDER_LOADING_TIMEOUT):
                                self.load_settings_with_dialog()
                    except Exception as fallback_error:
                        print(f"Even fallback profile failed: {fallback_error}")
                        # Load absolute minimum - clear everything
                        self.load_minimal_settings()
                else:
                    # Load minimal settings as last resort
                    self.load_minimal_settings()
        
        finally:
            # Close loading dialog
            if self.loading_dialog:
                self.loading_dialog.close()
                self.loading_dialog = None
    
    def load_settings_windows_timeout(self):
        """Load settings with timeout on Windows using threading."""
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def load_thread():
            try:
                self.load_settings()
                result_queue.put("success")
            except Exception as e:
                exception_queue.put(e)
        
        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()
        thread.join(timeout=FOLDER_LOADING_TIMEOUT)
        
        if thread.is_alive():
            # Thread is still running - it timed out
            raise TimeoutError(f"Settings loading timed out after {FOLDER_LOADING_TIMEOUT} seconds")
        
        # Check if there were any exceptions
        if not exception_queue.empty():
            raise exception_queue.get()
    
    def load_settings_windows_timeout_with_dialog(self):
        """Load settings with timeout on Windows using threading, with progress dialog."""
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        cancel_flag = threading.Event()
        
        def load_thread():
            try:
                self.load_settings_with_dialog_threaded(cancel_flag)
                result_queue.put("success")
            except Exception as e:
                exception_queue.put(e)
        
        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()
        
        # Monitor the thread with periodic checks for cancellation
        start_time = time.time()
        timeouts_disabled = False
        
        while thread.is_alive():
            # Process GUI events to keep dialog responsive
            try:
                self.master.update()
            except:
                break  # Window closed
                
            # Check if user cancelled or disabled timeouts
            if self.loading_dialog and self.loading_dialog.is_cancelled():
                cancel_type = self.loading_dialog.get_cancel_type()
                if cancel_type == "disable_timeouts":
                    timeouts_disabled = True
                    self.enable_timeouts.set(False)  # Update the checkbox
                    # Continue monitoring but without timeout
                elif cancel_type in ["skip", "cancel"]:
                    # Signal the thread to stop and break out
                    cancel_flag.set()
                    break
                
            # Check for timeout only if timeouts are enabled and not disabled by user
            if not timeouts_disabled and self.enable_timeouts.get():
                if time.time() - start_time > FOLDER_LOADING_TIMEOUT:
                    cancel_flag.set()
                    raise TimeoutError(f"Settings loading timed out after {FOLDER_LOADING_TIMEOUT} seconds")
            
            # Sleep briefly to avoid busy waiting
            time.sleep(0.1)
        
        # Wait a bit more for the thread to complete (or longer if timeouts disabled)
        wait_time = 1.0 if self.enable_timeouts.get() and not timeouts_disabled else None
        thread.join(timeout=wait_time)
        
        # Check if user cancelled (but not if they disabled timeouts)
        if self.loading_dialog and self.loading_dialog.is_cancelled():
            cancel_type = self.loading_dialog.get_cancel_type()
            if cancel_type != "disable_timeouts":
                raise TimeoutError("User cancelled loading")
        
        # Only check for timeout if timeouts are still enabled and thread is still alive
        if thread.is_alive() and self.enable_timeouts.get() and not timeouts_disabled:
            # Thread is still running - it timed out
            cancel_flag.set()
            raise TimeoutError(f"Settings loading timed out after {FOLDER_LOADING_TIMEOUT} seconds")
        
        # Check if there were any exceptions
        if not exception_queue.empty():
            raise exception_queue.get()

    def load_settings_windows_no_timeout_with_dialog(self):
        """Load settings without timeout using threading, but keep UI responsive for cancellation."""
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        cancel_flag = threading.Event()
        
        def load_thread():
            try:
                self.load_settings_with_dialog_threaded(cancel_flag)
                result_queue.put("success")
            except Exception as e:
                exception_queue.put(e)
        
        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()
        
        # Monitor the thread with periodic checks for cancellation (no timeout)
        while thread.is_alive():
            # Process GUI events to keep dialog responsive
            try:
                self.master.update()
            except:
                break  # Window closed
                
            # Check if user cancelled
            if self.loading_dialog and self.loading_dialog.is_cancelled():
                cancel_type = self.loading_dialog.get_cancel_type()
                if cancel_type in ["skip", "cancel"]:
                    # Signal the thread to stop and break out
                    cancel_flag.set()
                    break
            
            # Sleep briefly to avoid busy waiting
            time.sleep(0.1)
        
        # Wait for the thread to complete
        thread.join(timeout=2.0)
        
        # Check if user cancelled
        if self.loading_dialog and self.loading_dialog.is_cancelled():
            cancel_type = self.loading_dialog.get_cancel_type()
            if cancel_type in ["skip", "cancel"]:
                raise TimeoutError("User cancelled loading")
        
        # Check if there were any exceptions
        if not exception_queue.empty():
            raise exception_queue.get()
    
    def load_settings_with_dialog_threaded(self, cancel_flag):
        """Load settings with progress updates to the dialog, designed for threading with cancellation."""
        def update_dialog_safe(operation_text):
            """Safely update dialog from thread."""
            try:
                if self.loading_dialog:
                    self.master.after_idle(lambda: self.loading_dialog.update_operation(operation_text))
            except:
                pass
        
        update_dialog_safe("Reading profile configuration...")
        
        # Check for cancellation
        if cancel_flag.is_set():
            return
            
        is_first_launch = False
        
        if self.current_profile == "default":
            if not os.path.exists(CONFIG_FILE):
                # Add default meta prompt and ignore patterns for new installations
                self.add_default_meta_prompts()
                self.ignore_patterns = self.default_initial_ignore_patterns.copy()
                is_first_launch = True
                # We'll skip loading from file but still update the UI
                self.save_settings()  # Create the file for next time
            else:
                config_path = CONFIG_FILE
        else:
            config_path = os.path.join(PROFILES_DIR, f"{self.current_profile}.json")
            if not os.path.exists(config_path):
                # Add defaults for new profile
                self.add_default_meta_prompts()
                self.ignore_patterns = self.default_initial_ignore_patterns.copy()
                is_first_launch = True
                self.save_settings()  # Create the file for next time
        
        if not is_first_launch:  # Only load from file if it's not first launch
            try:
                update_dialog_safe("Loading profile data...")
                
                # Check for cancellation
                if cancel_flag.is_set():
                    return
                    
                # Clear existing data
                self.folder_tree_data.clear() 
                self.tree_ids_map.clear()
                self.saved_folder_checks.clear()
                self.visited_dirs.clear()
                
                # Remove all items from tree view
                self.master.after_idle(lambda: self.tree.delete(*self.tree.get_children()))
                
                # Load new settings
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.root_folders = data.get("root_folders", [])
                self.user_instructions = data.get("user_instructions", "")
                self.meta_prompts = data.get("meta_prompts", [])
                # Check if we need to add the default meta prompt
                if not self.meta_prompts:
                    self.add_default_meta_prompts()
                
                self.saved_folder_checks = data.get("folder_checks", {})
                self.ignore_patterns = data.get("ignore_patterns", [])
                self.copy_entire_tree_var.set(data.get("copy_entire_tree", False))
                self.filter_system_folders.set(data.get("filter_system_folders", True))
                self.dark_mode.set(data.get("dark_mode", False))
                self.prepend_string = data.get("prepend_string", DEFAULT_PREPEND_STRING)
                self.prepend_hotkey_enabled.set(data.get("prepend_hotkey_enabled", False))
                self.hotkey_combination = data.get("hotkey_combination", "ctrl+alt+v")
                self.enable_timeouts.set(data.get("enable_timeouts", True))
                self.strip_comments_var.set(data.get("strip_comments", False))
                self.selection_presets = data.get("selection_presets", {})
            except Exception as e:
                self.master.after_idle(lambda: messagebox.showerror("Error Loading Settings", str(e)))
        
        # Check for cancellation before building trees
        if cancel_flag.is_set():
            return
            
        # Always update the UI, whether it's first launch or not
        
        update_dialog_safe("Building folder tree...")
        
        # Build the tree with current settings
        self.build_all_trees_with_dialog_threaded(cancel_flag)
        
        # Check for cancellation
        if cancel_flag.is_set():
            return
            
        update_dialog_safe("Updating interface...")
        
        # Update UI - these need to be called from main thread
        def update_ui():
            if hasattr(self, 'instructions_text'):
                self.instructions_text.delete("1.0", tk.END)
                self.instructions_text.insert("1.0", self.user_instructions)
            
            if hasattr(self, 'filters_text'):
                self.filters_text.delete("1.0", tk.END)
                self.filters_text.insert("1.0", "\n".join(self.ignore_patterns))
            
            self.refresh_prompts_listbox()
            
            # Load history for this profile
            self.load_history()
            
            # Update preset combo box
            self.update_preset_combo()

            if hasattr(self, 'prepend_entry'):
                self.prepend_entry.delete(0, tk.END)
                self.prepend_entry.insert(0, self.prepend_string)
                # Ensure the entry shows the full text by moving to the beginning
                self.prepend_entry.icursor(0)
            if hasattr(self, 'prepend_hotkey_check'):
                self.prepend_hotkey_check.select() if self.prepend_hotkey_enabled.get() else self.prepend_hotkey_check.deselect()
            if hasattr(self, 'hotkey_display'):
                self.hotkey_display.config(text=self.hotkey_combination.upper())
            
            # Update dark mode checkbox to reflect loaded setting
            if hasattr(self, 'dark_mode_check'):
                if self.dark_mode.get():
                    self.dark_mode_check.select()
                else:
                    self.dark_mode_check.deselect()
        
        self.master.after_idle(update_ui)

    def load_settings_with_dialog(self):
        """Load settings with progress updates to the dialog."""
        if self.loading_dialog:
            self.loading_dialog.update_operation("Reading profile configuration...")
            
        is_first_launch = False
        
        if self.current_profile == "default":
            if not os.path.exists(CONFIG_FILE):
                # Add default meta prompt and ignore patterns for new installations
                self.add_default_meta_prompts()
                self.ignore_patterns = self.default_initial_ignore_patterns.copy()
                is_first_launch = True
                # We'll skip loading from file but still update the UI
                self.save_settings()  # Create the file for next time
            else:
                config_path = CONFIG_FILE
        else:
            config_path = os.path.join(PROFILES_DIR, f"{self.current_profile}.json")
            if not os.path.exists(config_path):
                # Add defaults for new profile
                self.add_default_meta_prompts()
                self.ignore_patterns = self.default_initial_ignore_patterns.copy()
                is_first_launch = True
                self.save_settings()  # Create the file for next time
        
        if not is_first_launch:  # Only load from file if it's not first launch
            try:
                if self.loading_dialog:
                    self.loading_dialog.update_operation("Loading profile data...")
                    
                # Clear existing data
                self.folder_tree_data.clear() 
                self.tree_ids_map.clear()
                self.saved_folder_checks.clear()
                self.visited_dirs.clear()
                
                # Remove all items from tree view
                self.tree.delete(*self.tree.get_children())
                
                # Load new settings
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.root_folders = data.get("root_folders", [])
                self.user_instructions = data.get("user_instructions", "")
                self.meta_prompts = data.get("meta_prompts", [])
                # Check if we need to add the default meta prompt
                if not self.meta_prompts:
                    self.add_default_meta_prompts()
                
                self.saved_folder_checks = data.get("folder_checks", {})
                self.ignore_patterns = data.get("ignore_patterns", [])
                self.copy_entire_tree_var.set(data.get("copy_entire_tree", False))
                self.filter_system_folders.set(data.get("filter_system_folders", True))
                self.dark_mode.set(data.get("dark_mode", False))
                self.prepend_string = data.get("prepend_string", DEFAULT_PREPEND_STRING)
                self.prepend_hotkey_enabled.set(data.get("prepend_hotkey_enabled", False))
                self.hotkey_combination = data.get("hotkey_combination", "ctrl+alt+v")
                self.enable_timeouts.set(data.get("enable_timeouts", True))
                self.strip_comments_var.set(data.get("strip_comments", False))
                self.selection_presets = data.get("selection_presets", {})
            except Exception as e:
                messagebox.showerror("Error Loading Settings", str(e))
        
        # Always update the UI, whether it's first launch or not
        
        if self.loading_dialog:
            self.loading_dialog.update_operation("Building folder tree...")
        
        # Build the tree with current settings
        self.build_all_trees_with_dialog()
        
        if self.loading_dialog:
            self.loading_dialog.update_operation("Updating interface...")
        
        # Update UI
        if hasattr(self, 'instructions_text'):
            self.instructions_text.delete("1.0", tk.END)
            self.instructions_text.insert("1.0", self.user_instructions)
        
        if hasattr(self, 'filters_text'):
            self.filters_text.delete("1.0", tk.END)
            self.filters_text.insert("1.0", "\n".join(self.ignore_patterns))
        
        self.refresh_prompts_listbox()
        
        # Load history for this profile
        if self.loading_dialog:
            self.loading_dialog.update_operation("Loading history...")
        self.load_history()

        if hasattr(self, 'prepend_entry'):
            self.prepend_entry.delete(0, tk.END)
            self.prepend_entry.insert(0, self.prepend_string)
            # Ensure the entry shows the full text by moving to the beginning
            self.prepend_entry.icursor(0)
        if hasattr(self, 'prepend_hotkey_check'):
            self.prepend_hotkey_check.select() if self.prepend_hotkey_enabled.get() else self.prepend_hotkey_check.deselect()
        if hasattr(self, 'hotkey_display'):
            self.hotkey_display.config(text=self.hotkey_combination.upper())
        
        # Update dark mode checkbox to reflect loaded setting
        if hasattr(self, 'dark_mode_check'):
            if self.dark_mode.get():
                self.dark_mode_check.select()
            else:
                self.dark_mode_check.deselect()
        
        if self.loading_dialog:
            self.loading_dialog.update_operation("Loading complete!")
        
        # Note: setup_global_hotkey() is called after theme is applied in __init__
    
    def find_working_fallback_profile(self):
        """Find a profile that's likely to work (no network paths)."""
        available_profiles = self.get_available_profiles()
        
        # Try profiles in order of preference
        for profile_name in ["default"] + [p for p in available_profiles if p != "default"]:
            if profile_name == self.current_profile:
                continue  # Skip the one that failed
                
            try:
                profile_path = os.path.join(PROFILES_DIR, f"{profile_name}.json") if profile_name != "default" else CONFIG_FILE
                
                if profile_name == "default" and not os.path.exists(CONFIG_FILE):
                    return "default"  # Default will create minimal settings
                    
                if not os.path.exists(profile_path):
                    continue
                    
                with open(profile_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    root_folders = data.get("root_folders", [])
                    
                    # Check if this profile has only safe, local paths
                    has_problematic_paths = False
                    for folder in root_folders:
                        if self.is_potentially_problematic_path(folder):
                            has_problematic_paths = True
                            break
                    
                    if not has_problematic_paths:
                        return profile_name
                        
            except Exception as e:
                print(f"Error checking profile {profile_name}: {e}")
                continue
        
        return "default"
    
    def load_minimal_settings(self):
        """Load minimal settings when everything else fails."""
        print("Loading minimal settings as fallback")
        
        # Clear everything
        self.root_folders = []
        self.user_instructions = ""
        self.meta_prompts = []
        self.saved_folder_checks = {}
        self.ignore_patterns = self.default_initial_ignore_patterns.copy()
        self.copy_entire_tree_var.set(False)
        self.strip_comments_var.set(False)
        self.filter_system_folders.set(True)
        self.dark_mode.set(False)
        self.prepend_string = DEFAULT_PREPEND_STRING
        self.prepend_hotkey_enabled.set(False)
        self.hotkey_combination = "ctrl+alt+v"
        
        # Add default meta prompt
        self.add_default_meta_prompts()
        
        # Clear tree data
        self.folder_tree_data.clear()
        self.tree_ids_map.clear()
        self.visited_dirs.clear()
        
        # Update UI elements if they exist
        if hasattr(self, 'instructions_text'):
            self.instructions_text.delete("1.0", tk.END)
            self.instructions_text.insert("1.0", self.user_instructions)
        
        if hasattr(self, 'filters_text'):
            self.filters_text.delete("1.0", tk.END)
            self.filters_text.insert("1.0", "\n".join(self.ignore_patterns))
            
        # Don't try to load history or build trees - just get the app running
    
    def save_last_profile(self, profile_name):
        """Save the currently selected profile as the last used profile."""
        try:
            with open(LAST_PROFILE_FILE, 'w', encoding='utf-8') as f:
                f.write(profile_name)
        except Exception as e:
            print(f"Error saving last profile: {e}")

    def on_refresh_folders(self):
        """Refresh the folder tree while preserving selections."""
        # Store current selections
        selections = {path: info['checked'] for path, info in self.folder_tree_data.items()}
        
        # Clear visited dirs to allow re-scanning
        self.visited_dirs.clear()
        
        # Rebuild trees
        self.folder_tree_data.clear()
        self.tree_ids_map.clear()
        self.tree.delete(*self.tree.get_children())
        
        # Rebuild all trees
        for folder in self.root_folders:
            if not os.path.exists(folder):
                continue
            self.build_tree_for(folder)
        
        # Restore selections
        for path, was_checked in selections.items():
            if path in self.folder_tree_data:
                self.folder_tree_data[path]['checked'] = was_checked
                item_id = self.tree_ids_map.get(path)
                if item_id and was_checked:
                    text = self.tree.item(item_id, 'text')
                    if not text.startswith("[x] "):
                        self.tree.item(item_id, text="[x] " + text)
        
        # Validate checked items to ensure consistency
        self.validate_checked_items()
        
        # Expand tree to show selected items
        self.master.after(100, self.expand_to_show_selected)

    def on_new_profile(self):
        """Create a new profile."""
        def save_new_profile():
            name = entry_name.get().strip()
            if not name:
                error_label.config(text="Profile name cannot be empty")
                return
            if name == "default":
                error_label.config(text="Cannot use 'default' as profile name")
                return
            if name in self.profiles:
                error_label.config(text="Profile already exists")
                return
            
            self.current_profile = name
            self.profile_var.set(name)
            self.profiles.append(name)
            self.profile_combo['values'] = self.profiles
            
            # Save as last used profile
            self.save_last_profile(name)
            
            # Clear the file list and user instructions for the new profile
            self.root_folders = []
            self.user_instructions = ""
            
            # Clear the folder tree data and tree view
            self.folder_tree_data.clear()
            self.tree_ids_map.clear()
            self.visited_dirs.clear()
            self.tree.delete(*self.tree.get_children())
            
            self.save_settings()
            new_win.destroy()
            self.set_status(f"Created new profile: {name}")
        
        new_win = tk.Toplevel(self.master)
        new_win.title("New Profile")
        
        tk.Label(new_win, text="Profile Name:").pack(padx=5, pady=5)
        entry_name = tk.Entry(new_win)
        entry_name.pack(padx=5, pady=5)
        
        error_label = tk.Label(new_win, text="", fg="red")
        error_label.pack(padx=5, pady=2)
        
        tk.Button(new_win, text="Create", command=save_new_profile).pack(padx=5, pady=5)

    def on_update_profile(self):
        """Update current profile."""
        if self.current_profile == "default":
            self.save_settings()
        else:
            self.save_profile(self.current_profile)
        self.set_status(f"Profile '{self.current_profile}' updated")

    def on_delete_profile(self):
        """Delete current profile."""
        if self.current_profile == "default":
            self.set_status("Cannot delete default profile", 5000)
            return
        
        confirm_win = tk.Toplevel(self.master)
        confirm_win.title("Confirm Delete")
        confirm_win.geometry("300x120")
        confirm_win.resizable(False, False)
        
        msg = f"Delete profile '{self.current_profile}'?"
        tk.Label(confirm_win, text=msg, wraplength=280).pack(padx=10, pady=10)
        
        btn_frame = tk.Frame(confirm_win)
        btn_frame.pack(side=tk.BOTTOM, pady=10)
        
        def do_delete():
            profile_path = os.path.join(PROFILES_DIR, f"{self.current_profile}.json")
            if os.path.exists(profile_path):
                os.remove(profile_path)
            
            self.profiles.remove(self.current_profile)
            self.current_profile = "default"
            self.profile_var.set("default")
            self.profile_combo['values'] = self.profiles
            
            # Save default as last used profile
            self.save_last_profile("default")
            
            self.load_settings()
            
            confirm_win.destroy()
            self.set_status(f"Profile deleted successfully.")
        
        btn_yes = tk.Button(btn_frame, text="Yes", command=do_delete, width=10)
        btn_yes.pack(side=tk.LEFT, padx=5)
        
        btn_no = tk.Button(btn_frame, text="No", command=confirm_win.destroy, width=10)
        btn_no.pack(side=tk.LEFT, padx=5)

    def on_profile_selected(self, event):
        """Handle profile selection change with loading dialog."""
        new_profile = self.profile_var.get()
        if new_profile != self.current_profile:
            # Save current profile before switching
            self.save_settings()
            
            # Switch to new profile
            old_profile = self.current_profile
            self.current_profile = new_profile
            
            # Save as last used profile
            self.save_last_profile(new_profile)
            
            # Show loading dialog for manual profile switch
            self.loading_dialog = LoadingDialog(self.master, f"Switching to Profile: {new_profile}")
            self.loading_dialog.update_operation(f"Switching to profile '{new_profile}'...")
            
            try:
                # Clear all data structures completely
                self.folder_tree_data.clear()
                self.tree_ids_map.clear()
                self.saved_folder_checks.clear()
                self.visited_dirs.clear()
                
                # Remove all items from tree view
                self.tree.delete(*self.tree.get_children())
                
                # Load the new profile with timeout and dialog support
                if self.enable_timeouts.get():
                    # Use timeout-protected loading
                    try:
                        if os.name == 'nt':
                            self.load_settings_windows_timeout_with_dialog()
                        else:
                            with FolderLoadingTimeout(FOLDER_LOADING_TIMEOUT):
                                self.load_settings_with_dialog()
                    except (TimeoutError, Exception) as e:
                        print(f"Failed to load profile '{new_profile}': {e}")
                        
                        # Check if user disabled timeouts during loading
                        if self.loading_dialog and self.loading_dialog.get_cancel_type() == "disable_timeouts":
                            # User wants to continue without timeouts
                            self.loading_dialog.update_operation("Loading without timeouts...")
                            self.load_settings_windows_no_timeout_with_dialog()
                        else:
                            # Handle timeout or other errors
                            self.current_profile = old_profile
                            self.profile_var.set(old_profile)
                            self.set_status(f"❌ Failed to switch to '{new_profile}' - staying with '{old_profile}'", 8000)
                            return
                else:
                    # Load without timeouts but still use threading to keep UI responsive
                    self.load_settings_windows_no_timeout_with_dialog()
                
                # Validate checked items
                self.validate_checked_items()
                
                # Clear history selection
                self.selected_history_item = None
                
                # Expand tree to show selected items after a short delay
                self.master.after(200, self.expand_to_show_selected)
                
                self.set_status(f"✅ Switched to profile: {new_profile}")
                
                # Apply theme in case it changed
                if self.dark_mode.get():
                    self.current_theme = DARK_THEME
                else:
                    self.current_theme = LIGHT_THEME
                self.apply_theme()
                
            except Exception as e:
                print(f"Error switching to profile '{new_profile}': {e}")
                # Revert to old profile
                self.current_profile = old_profile
                self.profile_var.set(old_profile)
                self.set_status(f"❌ Error switching to '{new_profile}' - staying with '{old_profile}'", 8000)
                
            finally:
                # Close loading dialog
                if self.loading_dialog:
                    self.loading_dialog.close()
                    self.loading_dialog = None

    def save_profile(self, profile_name):
        """Save settings to a specific profile."""
        data = {
            "root_folders": self.root_folders,
            "user_instructions": self.user_instructions,
            "meta_prompts": self.meta_prompts,
            "folder_checks": {},
            "ignore_patterns": self.ignore_patterns,
            "copy_entire_tree": self.copy_entire_tree_var.get(),
            "filter_system_folders": self.filter_system_folders.get(),
            "dark_mode": self.dark_mode.get(),
            "prepend_string": self.prepend_string,
            "prepend_hotkey_enabled": self.prepend_hotkey_enabled.get(),
            "hotkey_combination": self.hotkey_combination,
            "enable_timeouts": self.enable_timeouts.get(),
            "strip_comments": self.strip_comments_var.get(),
            "selection_presets": getattr(self, 'selection_presets', {}),
        }
        for path, info in self.folder_tree_data.items():
            data["folder_checks"][path] = info['checked']

        profile_path = os.path.join(PROFILES_DIR, f"{profile_name}.json")
        try:
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error Saving Profile", str(e))

    def save_selection_preset(self, preset_name, description=""):
        """Save current selection state as a preset."""
        current_selections = {}
        for path, info in self.folder_tree_data.items():
            if info['checked']:
                current_selections[path] = True
        
        self.selection_presets[preset_name] = {
            "folder_checks": current_selections,
            "description": description,
            "created_date": datetime.datetime.now().isoformat(),
            "last_used": datetime.datetime.now().isoformat()
        }
        
        # Save to current profile
        self.save_settings()
        self.set_status(f"✓ Selection preset '{preset_name}' saved")

    def load_selection_preset(self, preset_name):
        """Load a selection preset."""
        if preset_name not in self.selection_presets:
            self.set_status(f"❌ Selection preset '{preset_name}' not found")
            return False
        
        preset = self.selection_presets[preset_name]
        
        # Clear all current selections
        for path in self.folder_tree_data:
            self.folder_tree_data[path]['checked'] = False
        
        # Apply preset selections
        for path, checked in preset["folder_checks"].items():
            if path in self.folder_tree_data:
                self.folder_tree_data[path]['checked'] = checked
        
        # Update the tree view to reflect the changes
        self.update_tree_display()
        
        # Expand all parent folders of selected items to make them visible
        self.expand_to_selected_items()
        
        # Update last used timestamp
        self.selection_presets[preset_name]["last_used"] = datetime.datetime.now().isoformat()
        
        # Save to current profile
        self.save_settings()
        self.set_status(f"✓ Selection preset '{preset_name}' loaded")
        return True

    def delete_selection_preset(self, preset_name):
        """Delete a selection preset."""
        if preset_name in self.selection_presets:
            del self.selection_presets[preset_name]
            self.save_settings()
            self.set_status(f"✓ Selection preset '{preset_name}' deleted")
            return True
        return False

    def get_selection_presets(self):
        """Get list of available selection presets."""
        return list(self.selection_presets.keys())

    def update_tree_display(self):
        """Update the tree view to reflect current folder_tree_data checked states."""
        for path, info in self.folder_tree_data.items():
            item_id = self.tree_ids_map.get(path)
            if item_id:
                text = self.tree.item(item_id, 'text')
                if info['checked'] and not text.startswith("[x] "):
                    self.tree.item(item_id, text="[x] " + text)
                elif not info['checked'] and text.startswith("[x] "):
                    self.tree.item(item_id, text=text.replace("[x] ", "", 1))

    def expand_to_selected_items(self):
        """Expand all parent folders of selected items to make them visible."""
        selected_paths = []
        expanded_count = 0
        
        # Collect all selected paths
        for path, info in self.folder_tree_data.items():
            if info['checked']:
                selected_paths.append(path)
        
        # For each selected path, expand all its parent directories
        paths_to_expand = set()
        for path in selected_paths:
            # Add all parent directories to the expansion set
            current_path = path
            while current_path:
                parent_path = os.path.dirname(current_path)
                if parent_path and parent_path != current_path:
                    paths_to_expand.add(parent_path)
                    current_path = parent_path
                else:
                    break
        
        # Also add the selected paths themselves if they are directories
        for path in selected_paths:
            if path in self.folder_tree_data and self.folder_tree_data[path]['is_dir']:
                paths_to_expand.add(path)
        
        # Expand all the collected paths
        for path in paths_to_expand:
            if path in self.tree_ids_map:
                tree_id = self.tree_ids_map[path]
                if self.tree.exists(tree_id):
                    if not self.tree.item(tree_id, 'open'):
                        self.tree.item(tree_id, open=True)
                        expanded_count += 1
        
        # Scroll to the first selected item to make it visible
        if selected_paths:
            # Sort selected paths to find the "first" one (alphabetically)
            first_selected = sorted(selected_paths)[0]
            if first_selected in self.tree_ids_map:
                tree_id = self.tree_ids_map[first_selected]
                if self.tree.exists(tree_id):
                    self.tree.see(tree_id)
        
        if expanded_count > 0:
            self.set_status(f"✓ Expanded {expanded_count} folders to show selected items")

    def on_save_selection_preset(self):
        """Handle saving current selection as a preset."""
        preset_name = tk.simpledialog.askstring("Save Selection Preset", "Enter a name for this selection preset:")
        if preset_name:
            if preset_name in self.selection_presets:
                if not messagebox.askyesno("Overwrite Preset", f"A preset named '{preset_name}' already exists. Overwrite it?"):
                    return
            
            description = tk.simpledialog.askstring("Preset Description", "Enter a description (optional):", initialvalue="")
            self.save_selection_preset(preset_name, description or "")
            self.update_preset_combo()

    def on_load_selection_preset(self):
        """Handle loading a selection preset."""
        preset_name = self.preset_var.get()
        if not preset_name:
            messagebox.showwarning("No Selection", "Please select a preset from the dropdown.")
            return
        
        if preset_name in self.selection_presets:
            self.load_selection_preset(preset_name)
        else:
            messagebox.showerror("Preset Not Found", f"Selection preset '{preset_name}' not found.")

    def on_delete_selection_preset(self):
        """Handle deleting a selection preset."""
        preset_name = self.preset_var.get()
        if not preset_name:
            messagebox.showwarning("No Selection", "Please select a preset from the dropdown.")
            return
        
        if preset_name in self.selection_presets:
            if messagebox.askyesno("Delete Preset", f"Are you sure you want to delete the preset '{preset_name}'?"):
                self.delete_selection_preset(preset_name)
                self.update_preset_combo()
                self.preset_var.set("")
        else:
            messagebox.showerror("Preset Not Found", f"Selection preset '{preset_name}' not found.")

    def update_preset_combo(self):
        """Update the preset combo box with current presets."""
        if hasattr(self, 'preset_combo'):
            presets = self.get_selection_presets()
            self.preset_combo['values'] = presets

    def on_reduce_tokens(self):
        """Open the token reduction helper dialog."""
        self.open_token_reduction_dialog()

    def open_token_reduction_dialog(self):
        """Create and show the token reduction helper dialog."""
        dialog = tk.Toplevel(self.master)
        dialog.title("Token Reduction Helper")
        dialog.geometry("700x500")
        dialog.resizable(True, True)
        
        # Make dialog modal
        dialog.transient(self.master)
        dialog.grab_set()
        
        # Center the dialog on parent
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (dialog.winfo_screenheight() // 2) - (500 // 2)
        dialog.geometry(f"700x500+{x}+{y}")
        
        # Main frame
        main_frame = tk.Frame(dialog, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(main_frame, text="Reduce Tokens with AI File Analysis", 
                              font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Instructions section
        instructions_frame = tk.LabelFrame(main_frame, text="Step 1: Get JSON Format Instructions", padx=10, pady=10)
        instructions_frame.pack(fill=tk.X, pady=(0, 15))
        
        inst_text = tk.Label(instructions_frame, 
                           text="Use Cursor AI, Windsurf AI, or similar tools to analyze your codebase.\nClick below to copy the JSON format instructions:", 
                           justify=tk.LEFT, wraplength=600)
        inst_text.pack(pady=(0, 10))
        
        btn_copy_instructions = tk.Button(instructions_frame, text="📋 Copy JSON Format Instructions", 
                                        command=lambda: self.copy_ai_instructions(dialog),
                                        bg="#2196F3", fg="white", font=("Arial", 11, "bold"))
        btn_copy_instructions.pack(pady=5)
        
        # JSON import section
        import_frame = tk.LabelFrame(main_frame, text="Step 2: Import AI's JSON Response", padx=10, pady=10)
        import_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        import_text = tk.Label(import_frame, 
                             text="After AI analyzes your code and responds with JSON file list, import it below:", 
                             justify=tk.LEFT, wraplength=600)
        import_text.pack(pady=(0, 10))
        
        btn_import_json = tk.Button(import_frame, text="📥 Import JSON from Clipboard", 
                                  command=lambda: self.import_json_selection(dialog),
                                  bg="#FF9800", fg="white", font=("Arial", 11, "bold"))
        btn_import_json.pack(pady=5)
        
        # Text area for manual JSON entry (optional)
        manual_frame = tk.Frame(import_frame)
        manual_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        tk.Label(manual_frame, text="Or paste JSON here manually:", font=("Arial", 10)).pack(anchor=tk.W)
        
        json_text_frame = tk.Frame(manual_frame)
        json_text_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        self.json_text = ScrolledText(json_text_frame, height=8, font=("Consolas", 10))
        self.json_text.pack(fill=tk.BOTH, expand=True)
        
        # Manual import button
        btn_manual_import = tk.Button(manual_frame, text="Import from Text Above", 
                                    command=lambda: self.import_json_from_text(dialog),
                                    bg="#4CAF50", fg="white")
        btn_manual_import.pack(pady=(10, 0))
        
        # Close button
        close_frame = tk.Frame(main_frame)
        close_frame.pack(fill=tk.X, pady=(15, 0))
        
        btn_close = tk.Button(close_frame, text="Close", command=dialog.destroy)
        btn_close.pack(side=tk.RIGHT)

    def copy_ai_instructions(self, dialog):
        """Generate and copy AI analysis instructions to clipboard."""
        # Get user instructions from the main window
        user_request = self.user_instructions.strip() if self.user_instructions.strip() else "[No specific request provided - please describe what you want to implement]"
        
        # Generate complete instructions including user request
        instructions = f"""{user_request}

IMPORTANT: DO NOT make any code changes or modifications. I only need you to analyze the codebase and tell me which specific files I should select for this request.

Please analyze my codebase and determine the minimum essential files needed for the above request. Use tools like Cursor AI or Windsurf AI to examine the project structure.

Respond with ONLY a JSON object in this exact format:
{{
  "files": [
    "src/components/Header.tsx",
    "src/utils/api.js", 
    "package.json",
    "src/styles/main.css"
  ],
  "reasoning": "Brief explanation of why these files are essential for your request"
}}

Include only the files that need to be modified or are critical dependencies. Use file paths relative to the project root (the tool will automatically convert them to absolute paths). Remember: NO CODE CHANGES, just file selection analysis."""

        try:
            pyperclip.copy(instructions)
            messagebox.showinfo("Instructions Copied!", 
                              "Your request + JSON format instructions have been copied!\n\n"
                              "Next steps:\n"
                              "1. Open Cursor AI, Windsurf AI, or any AI coding assistant\n"
                              "2. Paste the copied text (includes your request + format)\n"
                              "3. Let the AI analyze your codebase (NO code changes will be made)\n"
                              "4. Copy the AI's JSON response\n"
                              "5. Come back and click 'Import JSON' below")
        except Exception as e:
            messagebox.showerror("Copy Error", f"Failed to copy to clipboard: {str(e)}")

    def import_json_selection(self, dialog):
        """Import file selection from clipboard JSON."""
        try:
            clipboard_content = pyperclip.paste()
            self.process_json_selection(clipboard_content, dialog)
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to read from clipboard: {str(e)}")

    def import_json_from_text(self, dialog):
        """Import file selection from the text area."""
        json_content = self.json_text.get("1.0", tk.END).strip()
        if not json_content:
            messagebox.showwarning("No Content", "Please paste JSON content in the text area first.")
            return
        self.process_json_selection(json_content, dialog)

    def find_absolute_path(self, relative_path):
        """Convert relative path to absolute path by matching against folder_tree_data."""
        # Clean up the relative path
        relative_path = relative_path.replace('\\', '/').strip('/')
        
        # Try exact matches first
        for abs_path in self.folder_tree_data.keys():
            abs_normalized = abs_path.replace('\\', '/')
            if abs_normalized.endswith('/' + relative_path) or abs_normalized.endswith(relative_path):
                return abs_path
        
        # Try matching by filename and partial path
        relative_parts = [part for part in relative_path.split('/') if part]
        
        for abs_path in self.folder_tree_data.keys():
            abs_parts = [part for part in abs_path.replace('\\', '/').split('/') if part]
            
            # Check if all relative parts appear in order at the end of absolute parts
            if len(relative_parts) <= len(abs_parts):
                if abs_parts[-len(relative_parts):] == relative_parts:
                    return abs_path
        
        return None

    def process_json_selection(self, json_content, dialog):
        """Process the JSON content and apply file selection."""
        try:
            # Try to parse JSON
            data = json.loads(json_content)
            
            # Validate JSON structure
            if "files" not in data or not isinstance(data["files"], list):
                messagebox.showerror("Invalid JSON", 
                                   "JSON must contain a 'files' array.\n\n"
                                   "Expected format:\n"
                                   '{"files": ["path1", "path2"], "reasoning": "..."}')
                return
            
            files_to_select = data["files"]
            reasoning = data.get("reasoning", "No reasoning provided")
            
            # Clear all current selections
            for path in self.folder_tree_data:
                self.folder_tree_data[path]['checked'] = False
            
            # Apply new selections
            selected_count = 0
            missing_files = []
            conversion_log = []
            
            for file_path in files_to_select:
                # First try direct match (in case it's already absolute)
                if file_path in self.folder_tree_data:
                    self.folder_tree_data[file_path]['checked'] = True
                    selected_count += 1
                    conversion_log.append(f"✓ Direct: {file_path}")
                else:
                    # Try to convert relative to absolute
                    absolute_path = self.find_absolute_path(file_path)
                    if absolute_path:
                        self.folder_tree_data[absolute_path]['checked'] = True
                        selected_count += 1
                        conversion_log.append(f"✓ Converted: {file_path} → {absolute_path}")
                    else:
                        missing_files.append(file_path)
                        conversion_log.append(f"✗ Not found: {file_path}")
            
            # Update the tree display
            self.update_tree_display()
            self.expand_to_selected_items()
            
            # Show results
            result_message = f"✅ Successfully selected {selected_count} files!\n\n"
            if reasoning:
                result_message += f"AI Reasoning: {reasoning}\n\n"
            
            # Show conversion details
            if conversion_log:
                result_message += "Path Conversion Log:\n"
                for log_entry in conversion_log[:10]:  # Show first 10 entries
                    result_message += f"{log_entry}\n"
                if len(conversion_log) > 10:
                    result_message += f"... and {len(conversion_log) - 10} more\n"
                result_message += "\n"
            
            if missing_files:
                result_message += f"⚠️ Warning: {len(missing_files)} files not found:\n"
                for missing in missing_files[:5]:  # Show first 5 missing files
                    result_message += f"- {missing}\n"
                if len(missing_files) > 5:
                    result_message += f"... and {len(missing_files) - 5} more"
            
            messagebox.showinfo("Import Successful", result_message)
            
            # Update status
            self.set_status(f"✓ AI selection applied: {selected_count} files selected")
            
            # Close dialog
            dialog.destroy()
            
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Parse Error", 
                               f"Invalid JSON format:\n{str(e)}\n\n"
                               "Please ensure the content is valid JSON.")
        except Exception as e:
            messagebox.showerror("Processing Error", f"Error processing selection: {str(e)}")

    def on_toggle_system_filter(self):
        """Rebuild tree when system filter is toggled."""
        self.build_all_trees()
        self.save_settings()
        if self.filter_system_folders.get():
            self.set_status("System folders are now hidden")
        else:
            self.set_status("System folders are now visible")

    def on_toggle_timeout_control(self):
        """Handle timeout control toggle."""
        self.save_settings()
        if self.enable_timeouts.get():
            self.set_status("⏱️ Timeouts enabled - will timeout after configured time limits")
        else:
            self.set_status("⏳ Timeouts disabled - will wait indefinitely for folder loading")

    def on_retry_original_profile(self):
        """Retry loading the original profile that failed during startup."""
        if not self.is_fallback_profile:
            self.set_status("No failed profile to retry")
            return
            
        # Get the original profile name from the last_profile.txt
        original_profile = self.load_last_profile()
        
        if original_profile == self.current_profile:
            self.set_status("Already using the original profile")
            return
        
        self.set_status("Retrying original profile load...", 2000)
        
        # Try to load the original profile
        old_profile = self.current_profile
        self.current_profile = original_profile
        self.is_fallback_profile = False
        
        try:
            # Update the dropdown
            self.profile_var.set(original_profile)
            
            # Show loading dialog for retry
            self.loading_dialog = LoadingDialog(self.master, f"Retrying Profile: {original_profile}")
            self.loading_dialog.update_operation(f"Retrying profile '{original_profile}'...")
            
            try:
                # Try loading with timeout
                if os.name == 'nt':
                    self.load_settings_windows_timeout_with_dialog()
                else:
                    with FolderLoadingTimeout(FOLDER_LOADING_TIMEOUT):
                        self.load_settings_with_dialog()
                
                # If we get here, it worked!
                self.set_status(f"✅ Successfully loaded original profile: {original_profile}")
                
                # Hide the retry button
                self.btn_retry_profile.pack_forget()
                
                # Apply the new theme
                if self.dark_mode.get():
                    self.current_theme = DARK_THEME
                else:
                    self.current_theme = LIGHT_THEME
                self.apply_theme()
                
            finally:
                # Close loading dialog
                if self.loading_dialog:
                    self.loading_dialog.close()
                    self.loading_dialog = None
            
        except (TimeoutError, Exception) as e:
            print(f"Retry failed for profile '{original_profile}': {e}")
            
            # Revert to the fallback profile
            self.current_profile = old_profile
            self.is_fallback_profile = True
            self.profile_var.set(old_profile)
            
            self.set_status(f"❌ Retry failed - network/FTP folders still inaccessible. Staying with fallback profile.", 8000)

    # -----------------------------------------------------------------------
    #  HISTORY MANAGEMENT
    # -----------------------------------------------------------------------
    def load_history(self):
        """Load history items for the current profile."""
        self.history_items = []
        profile_history_dir = os.path.join(HISTORY_DIR, self.current_profile)
        
        if not os.path.exists(profile_history_dir):
            os.makedirs(profile_history_dir)
            return
            
        # Get all history directories sorted by timestamp (newest first)
        history_dirs = []
        for item in os.listdir(profile_history_dir):
            item_path = os.path.join(profile_history_dir, item)
            if os.path.isdir(item_path):
                try:
                    # Extract timestamp from directory name
                    timestamp = int(item)
                    history_dirs.append((timestamp, item_path))
                except ValueError:
                    continue
                    
        # Sort by timestamp (descending)
        history_dirs.sort(reverse=True)
        
        # Load each history item
        for _, dir_path in history_dirs:
            meta_path = os.path.join(dir_path, "meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                        self.history_items.append({
                            'path': dir_path,
                            'timestamp': meta.get('timestamp', 0),
                            'datetime': meta.get('datetime', ''),
                            'description': meta.get('description', ''),
                            'file_count': meta.get('file_count', 0)
                        })
                except Exception as e:
                    print(f"Error loading history item: {e}")
                    
        # Update history listbox
        self.refresh_history_listbox()
        
    def refresh_history_listbox(self):
        """Update the history listbox with current items."""
        self.history_listbox.delete(0, tk.END)
        for item in self.history_items:
            self.history_listbox.insert(tk.END, f"{item['datetime']} - {item['description']} ({item['file_count']} files)")
            
    def save_history_item(self, full_content, user_instructions):
        """Save a new history item with the given content and instructions."""
        # Create timestamp for unique ID
        timestamp = int(time.time())
        dt_string = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")  # 12-hour time with AM/PM
        
        # Create directory for this history item
        profile_history_dir = os.path.join(HISTORY_DIR, self.current_profile)
        if not os.path.exists(profile_history_dir):
            os.makedirs(profile_history_dir)
            
        history_item_dir = os.path.join(profile_history_dir, str(timestamp))
        os.makedirs(history_item_dir)
        
        # Save content and instructions to files
        content_path = os.path.join(history_item_dir, "content.txt")
        with open(content_path, 'w', encoding='utf-8') as f:
            f.write(full_content)
            
        instructions_path = os.path.join(history_item_dir, "instructions.txt")
        with open(instructions_path, 'w', encoding='utf-8') as f:
            f.write(user_instructions)
            
        # Count files in content
        file_count = full_content.count("<file_contents>")
        
        # Create description
        description = f"Copy from {self.current_profile}"
        
        # Save metadata
        meta = {
            'timestamp': timestamp,
            'datetime': dt_string,
            'description': description,
            'file_count': file_count
        }
        
        meta_path = os.path.join(history_item_dir, "meta.json")
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
            
        # Add to history items and refresh listbox
        self.history_items.insert(0, {
            'path': history_item_dir,
            'timestamp': timestamp,
            'datetime': dt_string,
            'description': description,
            'file_count': file_count
        })
        
        self.refresh_history_listbox()
        
    def on_history_item_selected(self, event):
        """Handle selection of a history item."""
        selection = self.history_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        if 0 <= index < len(self.history_items):
            self.selected_history_item = self.history_items[index]
            
            # Load content and instructions into viewers
            content_path = os.path.join(self.selected_history_item['path'], "content.txt")
            instructions_path = os.path.join(self.selected_history_item['path'], "instructions.txt")
            
            # Update content viewer
            self.content_viewer.config(state=tk.NORMAL)
            self.content_viewer.delete("1.0", tk.END)
            try:
                if os.path.exists(content_path):
                    with open(content_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.content_viewer.insert("1.0", content)
                    
                    # Extract code content for the Code tab (include both tree and contents)
                    self.code_viewer.config(state=tk.NORMAL)
                    self.code_viewer.delete("1.0", tk.END)
                    
                    # Extract both file tree and file contents
                    code_sections = []
                    
                    # Extract file tree
                    if "<file_tree>" in content and "</file_tree>" in content:
                        file_tree = content.split("<file_tree>")[1].split("</file_tree>")[0].strip()
                        code_sections.append("<file_tree>\n" + file_tree + "\n</file_tree>")
                    
                    # Extract file contents
                    if "<file_contents>" in content and "</file_contents>" in content:
                        file_contents = content.split("<file_contents>")[1].split("</file_contents>")[0].strip()
                        code_sections.append("<file_contents>\n" + file_contents + "\n</file_contents>")
                    
                    if code_sections:
                        self.code_viewer.insert("1.0", "\n\n".join(code_sections))
                    else:
                        self.code_viewer.insert("1.0", "No code content found")
                    
                    self.code_viewer.config(state=tk.DISABLED)
            except Exception as e:
                self.content_viewer.insert("1.0", f"Error loading content: {e}")
                self.code_viewer.config(state=tk.NORMAL)
                self.code_viewer.delete("1.0", tk.END)
                self.code_viewer.insert("1.0", f"Error loading content: {e}")
                self.code_viewer.config(state=tk.DISABLED)
            self.content_viewer.config(state=tk.DISABLED)
            
            # Update instructions viewer
            self.instructions_viewer.config(state=tk.NORMAL)
            self.instructions_viewer.delete("1.0", tk.END)
            try:
                if os.path.exists(instructions_path):
                    with open(instructions_path, 'r', encoding='utf-8') as f:
                        instructions = f.read()
                    self.instructions_viewer.insert("1.0", instructions)
            except Exception as e:
                self.instructions_viewer.insert("1.0", f"Error loading instructions: {e}")
            self.instructions_viewer.config(state=tk.DISABLED)
            
            # Show status
            self.set_status(f"Loaded: {self.selected_history_item['datetime']}")
            
    def on_copy_history_content(self):
        """Copy the content of the selected history item to clipboard."""
        if not self.selected_history_item:
            self.set_status("Please select a history item first.")
            return
            
        content_path = os.path.join(self.selected_history_item['path'], "content.txt")
        if os.path.exists(content_path):
            try:
                with open(content_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.master.clipboard_clear()
                self.master.clipboard_append(content)
                self.set_status("History content copied to clipboard.")
            except Exception as e:
                self.set_status(f"Error: Could not load content: {e}", 5000)
                
    def on_copy_history_prompt(self):
        """Copy just the user instructions from the selected history item."""
        if not self.selected_history_item:
            self.set_status("Please select a history item first.")
            return
            
        instructions_path = os.path.join(self.selected_history_item['path'], "instructions.txt")
        if os.path.exists(instructions_path):
            try:
                with open(instructions_path, 'r', encoding='utf-8') as f:
                    instructions = f.read()
                self.master.clipboard_clear()
                self.master.clipboard_append(instructions)
                self.set_status("User instructions copied to clipboard.")
            except Exception as e:
                self.set_status(f"Error: Could not load instructions: {e}", 5000)
                
    def on_delete_history_item(self):
        """Delete the selected history item."""
        if not self.selected_history_item:
            self.set_status("Please select a history item first.")
            return
            
        confirm_win = tk.Toplevel(self.master)
        confirm_win.title("Confirm Delete")
        confirm_win.geometry("300x120")
        confirm_win.resizable(False, False)
        
        msg = f"Are you sure you want to delete this history item?\n\n{self.selected_history_item['datetime']}"
        tk.Label(confirm_win, text=msg, wraplength=280).pack(padx=10, pady=10)
        
        btn_frame = tk.Frame(confirm_win)
        btn_frame.pack(side=tk.BOTTOM, pady=10)
        
        def do_delete():
            try:
                shutil.rmtree(self.selected_history_item['path'])
                
                # Remove from list
                index = self.history_items.index(self.selected_history_item)
                del self.history_items[index]
                
                # Update listbox
                self.refresh_history_listbox()
                
                # Clear selection
                self.selected_history_item = None
                
                # Clear viewers
                self.content_viewer.config(state=tk.NORMAL)
                self.content_viewer.delete("1.0", tk.END)
                self.content_viewer.config(state=tk.DISABLED)
                
                self.instructions_viewer.config(state=tk.NORMAL)
                self.instructions_viewer.delete("1.0", tk.END)
                self.instructions_viewer.config(state=tk.DISABLED)
                
                confirm_win.destroy()
                self.set_status("History item deleted successfully.")
            except Exception as e:
                confirm_win.destroy()
                self.set_status(f"Error: Could not delete history item: {e}", 5000)
        
        btn_yes = tk.Button(btn_frame, text="Yes", command=do_delete, width=10)
        btn_yes.pack(side=tk.LEFT, padx=5)
        
        btn_no = tk.Button(btn_frame, text="No", command=confirm_win.destroy, width=10)
        btn_no.pack(side=tk.LEFT, padx=5)

    def create_history_content_tabs(self, parent):
        """Create the Content and Instructions tabs with proper styling from the start"""
        self.history_notebook = ttk.Notebook(parent)
        self.history_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create content tab with dark styling applied from the beginning
        bg_color = self.current_theme.get("content_bg", self.current_theme["text_bg"])
        fg_color = self.current_theme.get("content_fg", self.current_theme["text_fg"])
        
        # Content tab
        content_frame = tk.Frame(self.history_notebook, bg=bg_color)
        self.history_notebook.add(content_frame, text="Content")
        
        self.content_viewer = ScrolledText(content_frame, wrap=tk.WORD, height=6,
                                          bg=bg_color, fg=fg_color)
        self.content_viewer.pack(fill=tk.BOTH, expand=True)
        self.content_viewer.config(state=tk.DISABLED)  # Read-only
        
        # Code and Tree tab 
        code_frame = tk.Frame(self.history_notebook, bg=bg_color)
        self.history_notebook.add(code_frame, text="Code & Tree")
        
        self.code_viewer = ScrolledText(code_frame, wrap=tk.WORD, height=6,
                                        bg=bg_color, fg=fg_color)
        self.code_viewer.pack(fill=tk.BOTH, expand=True)
        self.code_viewer.config(state=tk.DISABLED)  # Read-only
        
        # Instructions tab
        instructions_frame = tk.Frame(self.history_notebook, bg=bg_color)
        self.history_notebook.add(instructions_frame, text="Instructions")
        
        self.instructions_viewer = ScrolledText(instructions_frame, wrap=tk.WORD, height=6,
                                               bg=bg_color, fg=fg_color)
        self.instructions_viewer.pack(fill=tk.BOTH, expand=True)
        self.instructions_viewer.config(state=tk.DISABLED)  # Read-only

    def on_prepend_string_changed(self, event=None):
        """Handle immediate prepend string changes."""
        new_text = self.prepend_entry.get()
        if new_text != self.prepend_string:
            self.prepend_string = new_text
            self.save_settings()
            self.set_status(f"Prepend text saved: {self.prepend_string[:50]}{'...' if len(self.prepend_string) > 50 else ''}")
    
    def on_prepend_string_changed_delayed(self, event=None):
        """Handle delayed prepend string changes to avoid too frequent saves."""
        # Cancel any existing timer
        if hasattr(self, '_prepend_save_timer'):
            self.master.after_cancel(self._prepend_save_timer)
        
        # Set a new timer to save after 1 second of no typing
        self._prepend_save_timer = self.master.after(1000, self._delayed_prepend_save)
    
    def _delayed_prepend_save(self):
        """Actually save the prepend string after delay."""
        new_text = self.prepend_entry.get()
        if new_text != self.prepend_string:
            self.prepend_string = new_text
            self.save_settings()
            self.set_status(f"Prepend text auto-saved: {self.prepend_string[:50]}{'...' if len(self.prepend_string) > 50 else ''}")
    
    def on_save_prepend_text(self):
        """Manually save the prepend text."""
        new_text = self.prepend_entry.get()
        if new_text != self.prepend_string:
            self.prepend_string = new_text
            self.save_settings()
            self.set_status(f"Prepend text manually saved: {self.prepend_string[:50]}{'...' if len(self.prepend_string) > 50 else ''}")
        else:
            self.set_status("Prepend text unchanged - no save needed.")

    def on_toggle_prepend_hotkey(self):
        if self.prepend_hotkey_enabled.get():
            self.setup_global_hotkey()
            self.set_status("Prepend hotkey enabled.")
        else:
            self.unregister_global_hotkey()
            self.set_status("Prepend hotkey disabled.")
        self.save_settings()

    def setup_global_hotkey(self):
        """Setup or re-setup the global hotkey with improved error handling."""
        # First unregister any existing hotkey
        if self.hotkey_registered:
            self.unregister_global_hotkey()
            # Wait a bit more for complete cleanup
            time.sleep(0.2)
            
        if self.prepend_hotkey_enabled.get():
            def on_hotkey_press():
                try:
                    # Get clipboard content
                    content = self.master.clipboard_get()
                    
                    # More robust check for prepend string - handle various whitespace scenarios
                    content_stripped = content.strip()
                    prepend_stripped = self.prepend_string.strip()
                    
                    # Check if content already starts with the prepend string (with flexible whitespace handling)
                    if content_stripped.startswith(prepend_stripped) or (prepend_stripped in content_stripped[:len(prepend_stripped) + 10]):
                        print("Content already contains prepend string, performing direct paste")
                        # Content already has the prepend string, just simulate paste
                        time.sleep(0.1)
                        # Release all keys from the hotkey combination
                        for key in self.hotkey_combination.split('+'):
                            try:
                                keyboard.release(key.strip())
                            except:
                                pass  # Ignore release errors
                        time.sleep(0.1)
                        keyboard.press('ctrl')
                        keyboard.press('v')
                        time.sleep(0.1)
                        keyboard.release('v')
                        keyboard.release('ctrl')
                        return
                    
                    print(f"Prepending text: '{self.prepend_string[:30]}...' to clipboard content")
                    # Prepend string and two newlines
                    new_content = f"{self.prepend_string}\n\n{content}"
                    
                    # Set clipboard with retry logic
                    for attempt in range(3):
                        try:
                            self.master.clipboard_clear()
                            self.master.clipboard_append(new_content)
                            # Verify clipboard was set correctly
                            test_content = self.master.clipboard_get()
                            if test_content == new_content:
                                break
                        except Exception as clip_e:
                            print(f"Clipboard set attempt {attempt + 1} failed: {clip_e}")
                            if attempt == 2:
                                raise clip_e
                            time.sleep(0.05)
                    
                    # Give a small delay to ensure clipboard is updated
                    time.sleep(0.1)
                    
                    # Release the original hotkey combination to avoid interference
                    for key in self.hotkey_combination.split('+'):
                        try:
                            keyboard.release(key.strip())
                        except:
                            pass  # Ignore release errors
                    
                    # Small delay before paste
                    time.sleep(0.1)
                    
                    # Simulate paste using just Ctrl+V
                    keyboard.press('ctrl')
                    keyboard.press('v')
                    time.sleep(0.1)
                    keyboard.release('v')
                    keyboard.release('ctrl')
                    
                    print("Prepend and paste completed successfully")
                    
                except Exception as e:
                    print(f"Hotkey error: {e}")
                    # Try to release any stuck keys
                    try:
                        for key in ['ctrl', 'alt', 'shift', 'win', 'v']:
                            keyboard.release(key)
                    except:
                        pass
            
            def on_hotkey_release():
                # We don't need to do anything on release
                pass

            # Register hotkey in a thread
            def hotkey_thread_func():
                try:
                    # Convert our format to the library's expected format
                    hotkey_str = self.hotkey_combination.replace('ctrl', 'control').replace('+', ' + ')
                    print(f"Registering hotkey: {hotkey_str}")
                    
                    # Clear any previous registrations that might be stuck
                    try:
                        stop_checking_hotkeys()
                        time.sleep(0.1)
                    except:
                        pass  # Ignore if nothing was registered
                    
                    register_hotkey(hotkey_str, on_hotkey_press, on_hotkey_release)
                    start_checking_hotkeys()
                    self.hotkey_registered = True
                    print(f"Hotkey {hotkey_str} registered successfully")
                    
                    # Test the hotkey registration by checking if the system acknowledges it
                    time.sleep(0.1)
                    
                    # Update status on main thread
                    self.master.after(0, lambda: self.update_hotkey_status("Active", "green"))
                except Exception as e:
                    print(f"Hotkey registration error: {e}")
                    self.hotkey_registered = False
                    # Update status on main thread
                    self.master.after(0, lambda: self.update_hotkey_status(f"Error: {str(e)[:30]}", "red"))
                    
            self.hotkey_thread = threading.Thread(target=hotkey_thread_func, daemon=True)
            self.hotkey_thread.start()
        else:
            self.update_hotkey_status("", "")

    def unregister_global_hotkey(self):
        """Unregister the global hotkey with proper cleanup."""
        if self.hotkey_registered:
            try:
                # Force stop and cleanup
                stop_checking_hotkeys()
                
                # Wait a moment for the library to properly release the hotkeys
                time.sleep(0.1)
                
                # Clear any held keyboard states using the keyboard library
                try:
                    # Release all possible modifier keys that might be stuck
                    for key in ['ctrl', 'alt', 'shift', 'win']:
                        keyboard.release(key)
                except:
                    pass  # Ignore errors when releasing keys that weren't pressed
                
                self.hotkey_registered = False
                self.update_hotkey_status("", "")
                print("Hotkey successfully unregistered and keys released")
            except Exception as e:
                print(f"Error unregistering hotkey: {e}")
                # Force cleanup even if error occurred
                try:
                    for key in ['ctrl', 'alt', 'shift', 'win']:
                        keyboard.release(key)
                except:
                    pass
                self.hotkey_registered = False
                
    def update_hotkey_status(self, text, color):
        """Update the hotkey status label."""
        if hasattr(self, 'hotkey_status_label'):
            # Handle empty color by using default theme color
            if not color:
                # Use current theme if available, otherwise use black as fallback
                if hasattr(self, 'current_theme') and self.current_theme:
                    color = self.current_theme.get("fg", "black")
                else:
                    color = "black"
            self.hotkey_status_label.config(text=text, fg=color)

    def reset_prepend_string(self):
        """Reset the prepend string to its default value."""
        # Confirm with user before resetting
        import tkinter.messagebox as msgbox
        result = msgbox.askyesno("Reset Prepend Text", 
                                f"Reset prepend text to default?\n\nCurrent: {self.prepend_string[:50]}{'...' if len(self.prepend_string) > 50 else ''}\nDefault: {DEFAULT_PREPEND_STRING}")
        if result:
            self.prepend_string = DEFAULT_PREPEND_STRING
            self.prepend_entry.delete(0, tk.END)
            self.prepend_entry.insert(0, self.prepend_string)
            self.prepend_entry.icursor(0)
            self.save_settings()
            self.set_status("Prepend string reset to default.")
    
    def debug_prepend_settings(self):
        """Debug method to show current prepend settings."""
        import tkinter.messagebox as msgbox
        
        # Check what's in memory
        memory_text = f"In Memory: {self.prepend_string}"
        
        # Check what's in the entry widget
        entry_text = f"In Entry: {self.prepend_entry.get()}"
        
        # Check what's in the settings file
        file_text = "File: Not found"
        try:
            if self.current_profile == "default":
                config_path = CONFIG_FILE
            else:
                config_path = os.path.join(PROFILES_DIR, f"{self.current_profile}.json")
                
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                file_prepend = data.get("prepend_string", "NOT FOUND")
                file_text = f"File: {file_prepend}"
        except Exception as e:
            file_text = f"File Error: {e}"
        
        debug_msg = f"Prepend String Debug:\n\n{memory_text}\n\n{entry_text}\n\n{file_text}\n\nProfile: {self.current_profile}"
        msgbox.showinfo("Prepend Debug", debug_msg)
        
    def on_change_hotkey(self):
        """Open a dialog to change the hotkey combination."""
        change_win = tk.Toplevel(self.master)
        change_win.title("Change Hotkey")
        change_win.geometry("550x650")  # Increased from 500x550 to 550x650 for better visibility
        change_win.resizable(True, True)  # Made resizable so users can adjust if needed
        
        # Center the window
        change_win.transient(self.master)
        change_win.grab_set()
        
        # Instructions
        instruction_text = """Choose a new hotkey combination for the clipboard prepend function.

Current hotkey: {}

Click on the buttons below to select modifier keys, then select a main key.
Common combinations like Ctrl+C, Ctrl+V, Ctrl+X are reserved and will be blocked.

Recommended combinations:
• Ctrl+Alt+V (default)
• Ctrl+Shift+V
• Ctrl+Alt+P
• Ctrl+Shift+P
• Win+V""".format(self.hotkey_combination.upper())
        
        instruction_label = tk.Label(change_win, text=instruction_text, justify=tk.LEFT, wraplength=480)
        instruction_label.pack(padx=10, pady=10)
        
        # Current selection display
        current_frame = tk.Frame(change_win)
        current_frame.pack(pady=10)
        
        tk.Label(current_frame, text="New Hotkey: ", font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        hotkey_var = tk.StringVar(value=self.hotkey_combination)
        hotkey_display_label = tk.Label(current_frame, textvariable=hotkey_var, 
                                       font=("Arial", 12), bg="#e0e0e0", 
                                       relief=tk.SUNKEN, padx=10, pady=5)
        hotkey_display_label.pack(side=tk.LEFT, padx=10)
        
        # Modifier keys frame
        mod_frame = tk.LabelFrame(change_win, text="Modifier Keys (choose at least one)")
        mod_frame.pack(pady=10, padx=20, fill=tk.X)
        
        ctrl_var = tk.BooleanVar(value='ctrl' in self.hotkey_combination)
        alt_var = tk.BooleanVar(value='alt' in self.hotkey_combination)
        shift_var = tk.BooleanVar(value='shift' in self.hotkey_combination)
        win_var = tk.BooleanVar(value='win' in self.hotkey_combination)
        
        def update_hotkey_display():
            modifiers = []
            if ctrl_var.get():
                modifiers.append('ctrl')
            if alt_var.get():
                modifiers.append('alt')
            if shift_var.get():
                modifiers.append('shift')
            if win_var.get():
                modifiers.append('win')
            
            # Get current main key
            current_keys = hotkey_var.get().split('+')
            main_key = None
            for key in current_keys:
                if key.strip() not in ['ctrl', 'alt', 'shift', 'win']:
                    main_key = key.strip()
                    break
            
            if modifiers and main_key:
                new_hotkey = '+'.join(modifiers) + '+' + main_key
                hotkey_var.set(new_hotkey)
            elif modifiers:
                hotkey_var.set('+'.join(modifiers) + '+')
            else:
                hotkey_var.set('')
        
        tk.Checkbutton(mod_frame, text="Ctrl", variable=ctrl_var, command=update_hotkey_display).pack(side=tk.LEFT, padx=10)
        tk.Checkbutton(mod_frame, text="Alt", variable=alt_var, command=update_hotkey_display).pack(side=tk.LEFT, padx=10)
        tk.Checkbutton(mod_frame, text="Shift", variable=shift_var, command=update_hotkey_display).pack(side=tk.LEFT, padx=10)
        tk.Checkbutton(mod_frame, text="Win", variable=win_var, command=update_hotkey_display).pack(side=tk.LEFT, padx=10)
        
        # Main key frame - limit expansion to leave room for buttons
        key_frame = tk.LabelFrame(change_win, text="Main Key")
        key_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=False)  # Changed expand=False
        
        # Common keys in a grid
        keys = [
            ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
            ['I', 'J', 'K', 'L', 'M', 'N', 'O', 'P'],
            ['Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X'],
            ['Y', 'Z', '1', '2', '3', '4', '5', '6'],
            ['7', '8', '9', '0', 'F1', 'F2', 'F3', 'F4'],
            ['F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12']
        ]
        
        def set_main_key(key):
            modifiers = []
            if ctrl_var.get():
                modifiers.append('ctrl')
            if alt_var.get():
                modifiers.append('alt')
            if shift_var.get():
                modifiers.append('shift')
            if win_var.get():
                modifiers.append('win')
            
            if modifiers:
                new_hotkey = '+'.join(modifiers) + '+' + key.lower()
                hotkey_var.set(new_hotkey)
        
        for row in keys:
            row_frame = tk.Frame(key_frame)
            row_frame.pack(fill=tk.X, pady=2)
            for key in row:
                btn = tk.Button(row_frame, text=key, width=4, 
                               command=lambda k=key: set_main_key(k))
                btn.pack(side=tk.LEFT, padx=2)
        
        # Warning label for reserved combinations
        warning_label = tk.Label(change_win, text="", fg="red", wraplength=480)
        warning_label.pack(pady=5)
        
        def check_reserved_hotkey():
            current_hotkey = hotkey_var.get().lower()
            reserved_combinations = ['ctrl+c', 'ctrl+v', 'ctrl+x', 'ctrl+z', 'ctrl+y', 
                                   'ctrl+a', 'ctrl+s', 'ctrl+n', 'ctrl+o', 'ctrl+p',
                                   'alt+f4', 'alt+tab']
            
            if current_hotkey in reserved_combinations:
                warning_label.config(text=f"⚠️ Warning: {current_hotkey.upper()} is a reserved system shortcut!")
                return False
            else:
                warning_label.config(text="")
                return True
        
        # Update warning when hotkey changes
        def on_hotkey_change(*args):
            check_reserved_hotkey()
        hotkey_var.trace('w', on_hotkey_change)
        
        # Buttons frame - ensure it's always visible at the bottom
        btn_frame = tk.Frame(change_win)
        btn_frame.pack(side=tk.BOTTOM, pady=15, fill=tk.X)  # Pack at bottom with more padding
        
        def apply_hotkey():
            new_hotkey = hotkey_var.get()
            if not new_hotkey or new_hotkey.endswith('+'):
                messagebox.showwarning("Invalid Hotkey", "Please select both modifier keys and a main key.")
                return
            
            if not check_reserved_hotkey():
                result = messagebox.askyesno("Reserved Hotkey", 
                    "This hotkey combination is normally reserved by the system. "
                    "It may not work properly. Do you want to use it anyway?")
                if not result:
                    return
            
            # Test if modifiers are selected
            modifiers = []
            if ctrl_var.get():
                modifiers.append('ctrl')
            if alt_var.get():
                modifiers.append('alt')
            if shift_var.get():
                modifiers.append('shift')
            if win_var.get():
                modifiers.append('win')
            
            if not modifiers:
                messagebox.showwarning("Invalid Hotkey", "Please select at least one modifier key (Ctrl, Alt, Shift, or Win).")
                return
            
            # Apply the new hotkey
            old_hotkey = self.hotkey_combination
            self.hotkey_combination = new_hotkey
            self.hotkey_display.config(text=new_hotkey.upper())
            
            # Re-register hotkey if it's currently enabled
            if self.prepend_hotkey_enabled.get():
                self.setup_global_hotkey()
            
            self.save_settings()
            change_win.destroy()
            self.set_status(f"Hotkey changed from {old_hotkey.upper()} to {new_hotkey.upper()}")
        
        def cancel_change():
            change_win.destroy()
        
        # Create buttons with better visibility - centered in the frame
        button_container = tk.Frame(btn_frame)
        button_container.pack()
        
        tk.Button(button_container, text="Save", command=apply_hotkey, width=10, 
                 font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Button(button_container, text="Cancel", command=cancel_change, width=10, 
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=10)
        
        # Focus the window
        change_win.focus_set()

    def on_window_close(self):
        """Handle window close event to save current state and cleanup."""
        try:
            # Save current settings
            self.save_settings()
            
            # Save current profile as last used
            self.save_last_profile(self.current_profile)
            
            # Cleanup hotkeys with extra safety
            if hasattr(self, 'hotkey_registered') and self.hotkey_registered:
                print("Cleaning up hotkeys on window close...")
                self.unregister_global_hotkey()
                # Extra safety - force release any potentially stuck keys
                try:
                    for key in ['ctrl', 'alt', 'shift', 'win']:
                        keyboard.release(key)
                except:
                    pass
                # Wait a moment for complete cleanup
                time.sleep(0.1)
                
            # Destroy the window
            self.master.destroy()
        except Exception as e:
            print(f"Error during window close: {e}")
            # Force close even if there's an error - but still try hotkey cleanup
            try:
                if hasattr(self, 'hotkey_registered') and self.hotkey_registered:
                    stop_checking_hotkeys()
                    for key in ['ctrl', 'alt', 'shift', 'win']:
                        keyboard.release(key)
            except:
                pass
            self.master.destroy()

    def _monitor_thread_non_blocking(self, thread, start_time, timeout_seconds, cancel_flag, exception_queue, result_queue, on_success, on_error):
        """Periodically check thread status without blocking Tk mainloop."""
        if thread.is_alive():
            # Check for cancellation
            if self.loading_dialog and self.loading_dialog.is_cancelled():
                cancel_type = self.loading_dialog.get_cancel_type()
                if cancel_type in ["skip", "cancel"]:
                    cancel_flag.set()
                    if on_error:
                        on_error(TimeoutError("User cancelled loading"))
                    return
                elif cancel_type == "disable_timeouts":
                    timeout_seconds = None  # Disable further timeout checks
            
            # Check timeout with more generous handling
            elapsed_time = time.time() - start_time
            if timeout_seconds is not None and elapsed_time > timeout_seconds:
                # Give extra time for local folders (be more generous)
                if elapsed_time < timeout_seconds + 30:  # Extra 30 seconds grace period
                    if self.loading_dialog:
                        remaining = int((timeout_seconds + 30) - elapsed_time)
                        self.loading_dialog.update_status(f"Taking longer than expected... {remaining}s remaining", "orange")
                else:
                    cancel_flag.set()
                    if on_error:
                        on_error(TimeoutError(f"Loading timed out after {timeout_seconds + 30} seconds (with grace period)"))
                    return
            
            # Continue polling
            self.master.after(100, lambda: self._monitor_thread_non_blocking(thread, start_time, timeout_seconds, cancel_flag, exception_queue, result_queue, on_success, on_error))
        else:
            # Thread finished
            if not exception_queue.empty():
                if on_error:
                    on_error(exception_queue.get())
            else:
                if on_success:
                    on_success()

def main():
    root = tk.Tk()
    app = FolderMonitorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
