import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageDraw, ImageEnhance, ImageColor, ImageFilter
import numpy as np
import os
import json
from datetime import datetime
import colorsys
from dataclasses import dataclass
from typing import List, Tuple, Optional
import threading


@dataclass
class PixelArtConfig:
    """Configuration class for pixel art generation"""
    pixel_width: int = 30
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    color_mode: str = "Color"
    palette_size: int = 16
    pixel_size: int = 20
    dithering: bool = False
    edge_enhancement: bool = False


class ImageProcessor:
    """Handles all image processing operations"""

    @staticmethod
    def apply_adjustments(img: Image.Image, config: PixelArtConfig) -> Image.Image:
        """Apply brightness, contrast, and saturation adjustments"""
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Apply brightness
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(config.brightness)

        # Apply contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(config.contrast)

        # Apply saturation
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(config.saturation)

        # Apply edge enhancement if enabled
        if config.edge_enhancement:
            img = img.filter(ImageFilter.EDGE_ENHANCE)

        return img

    @staticmethod
    def generate_pixel_grid(img_path: str, config: PixelArtConfig) -> Tuple[List[List[str]], int]:
        """Generate pixel grid from image"""
        img = Image.open(img_path)
        width = config.pixel_width
        aspect_ratio = img.height / img.width
        height = max(1, round(width * aspect_ratio))
        total_pixels = width * height

        # Apply adjustments
        img = ImageProcessor.apply_adjustments(img, config)

        # Resize to desired grid size
        img = img.resize((width, height), Image.LANCZOS if not config.dithering else Image.NEAREST)

        # Apply color mode
        if config.color_mode == "Grayscale":
            img = img.convert('L').convert('RGB')
        elif config.color_mode == "Limited Palette":
            if config.dithering:
                img = img.quantize(colors=config.palette_size, dither=Image.FLOYDSTEINBERG).convert('RGB')
            else:
                img = img.quantize(colors=config.palette_size).convert('RGB')

        # Create pixel grid
        pixel_grid = []
        pixels = img.load()
        for y in range(height):
            row = []
            for x in range(width):
                r, g, b = pixels[x, y][:3]
                color_hex = f"#{r:02x}{g:02x}{b:02x}"
                row.append(color_hex)
            pixel_grid.append(row)

        return pixel_grid, total_pixels

    @staticmethod
    def create_preview_image(pixel_grid: List[List[str]], pixel_size: int, show_grid: bool = True) -> Image.Image:
        """Create a preview image from pixel grid"""
        height = len(pixel_grid)
        width = len(pixel_grid[0])

        preview_img = Image.new("RGB", (width * pixel_size, height * pixel_size), "#34495e")
        draw = ImageDraw.Draw(preview_img)

        for y in range(height):
            for x in range(width):
                color = pixel_grid[y][x]
                r, g, b = ImageColor.getrgb(color)

                if show_grid:
                    draw.rectangle(
                        [x * pixel_size, y * pixel_size,
                         (x + 1) * pixel_size - 1, (y + 1) * pixel_size - 1],
                        fill=(r, g, b),
                        outline="#95a5a6" if pixel_size > 5 else None
                    )
                else:
                    draw.rectangle(
                        [x * pixel_size, y * pixel_size,
                         (x + 1) * pixel_size, (y + 1) * pixel_size],
                        fill=(r, g, b)
                    )

        return preview_img


class ColorPalette:
    """Manages color palette operations"""

    @staticmethod
    def extract_colors(pixel_grid: List[List[str]]) -> List[str]:
        """Extract unique colors from pixel grid"""
        unique_colors = set()
        for row in pixel_grid:
            for color in row:
                unique_colors.add(color)

        # Sort by brightness
        return sorted(unique_colors, key=lambda c: colorsys.rgb_to_hsv(
            int(c[1:3], 16) / 255,
            int(c[3:5], 16) / 255,
            int(c[5:7], 16) / 255
        )[2])

    @staticmethod
    def create_palette_image(colors: List[str], width: int = 300) -> Image.Image:
        """Create a visual representation of the color palette"""
        if not colors:
            return Image.new("RGB", (width, 50), "#34495e")

        color_width = width // len(colors)
        height = 30

        palette_img = Image.new("RGB", (width, height), "#34495e")
        draw = ImageDraw.Draw(palette_img)

        for i, color in enumerate(colors):
            x1 = i * color_width
            x2 = min((i + 1) * color_width, width)
            draw.rectangle([x1, 0, x2, height], fill=color)

        return palette_img


class PixelArtGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Pixel Art Generator v2.0")
        self.root.geometry("1400x900")
        self.root.configure(bg="#2c3e50")

        # Initialize variables
        self.image_path = ""
        self.pixel_grid = None
        self.config = PixelArtConfig()
        self.current_project = None
        self.preview_size = 350
        self.show_grid = tk.BooleanVar(value=True)
        self.auto_preview = tk.BooleanVar(value=True)

        # Setup styles
        self._setup_styles()

        # Create UI
        self._create_ui()

        # Initialize palette window reference
        self.palette_window = None

    def _setup_styles(self):
        """Configure UI styles"""
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Configure styles
        style_configs = {
            "TFrame": {"background": "#2c3e50"},
            "TLabel": {"background": "#2c3e50", "foreground": "#ecf0f1"},
            "TButton": {"background": "#3498db", "foreground": "white", "padding": (10, 5)},
            "Accent.TButton": {"background": "#e74c3c", "foreground": "white"},
            "TScale": {"background": "#2c3e50", "troughcolor": "#34495e"},
            "TEntry": {"fieldbackground": "#34495e", "foreground": "#ecf0f1"},
            "TCombobox": {"fieldbackground": "#34495e", "foreground": "#ecf0f1"},
            "TCheckbutton": {"background": "#2c3e50", "foreground": "#ecf0f1"}
        }

        for style_name, config in style_configs.items():
            self.style.configure(style_name, **config)

        # Map active states
        self.style.map("TButton", background=[('active', '#2980b9')])
        self.style.map("Accent.TButton", background=[('active', '#c0392b')])

    def _create_ui(self):
        """Create the main user interface"""
        # Main container
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Control panel
        self.control_frame = ttk.Frame(main_container, width=400)
        main_container.add(self.control_frame, weight=0)

        # Preview panel
        self.preview_frame = ttk.Frame(main_container)
        main_container.add(self.preview_frame, weight=1)

        self._create_control_panel()
        self._create_preview_panel()
        self._create_status_bar()

    def _create_control_panel(self):
        """Create the control panel with all settings"""
        # Scrollable frame for controls
        canvas = tk.Canvas(self.control_frame, bg="#2c3e50", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.control_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Title
        title_label = ttk.Label(scrollable_frame, text="PIXEL ART GENERATOR",
                                font=("Arial", 16, "bold"))
        title_label.pack(pady=(10, 20))

        # Project management
        self._create_project_section(scrollable_frame)

        # Image loading
        self._create_image_section(scrollable_frame)

        # Pixel settings
        self._create_pixel_section(scrollable_frame)

        # Image adjustments
        self._create_adjustments_section(scrollable_frame)

        # Advanced options
        self._create_advanced_section(scrollable_frame)

        # Generation and export
        self._create_action_section(scrollable_frame)

    def _create_project_section(self, parent):
        """Create project management section"""
        project_frame = ttk.LabelFrame(parent, text="Project Management", padding=10)
        project_frame.pack(fill=tk.X, pady=10)

        button_frame = ttk.Frame(project_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="New", command=self.new_project).pack(
            side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)
        ttk.Button(button_frame, text="Save", command=self.save_project).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(button_frame, text="Load", command=self.load_project).pack(
            side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)

    def _create_image_section(self, parent):
        """Create image loading section"""
        img_frame = ttk.LabelFrame(parent, text="Source Image", padding=10)
        img_frame.pack(fill=tk.X, pady=10)

        load_frame = ttk.Frame(img_frame)
        load_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(load_frame, text="Load Image", command=self.load_image).pack(
            side=tk.LEFT, padx=(0, 10))

        self.img_path_label = ttk.Label(load_frame, text="No image selected",
                                        wraplength=250, font=("Arial", 9))
        self.img_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _create_pixel_section(self, parent):
        """Create pixel settings section"""
        pixel_frame = ttk.LabelFrame(parent, text="Pixel Settings", padding=10)
        pixel_frame.pack(fill=tk.X, pady=10)

        # Grid width
        ttk.Label(pixel_frame, text="Pixel Grid Width:").pack(anchor="w")
        self.width_var = tk.IntVar(value=self.config.pixel_width)
        width_frame = ttk.Frame(pixel_frame)
        width_frame.pack(fill=tk.X, pady=5)

        self.width_slider = ttk.Scale(width_frame, from_=10, to=150,
                                      variable=self.width_var, command=self._on_width_change)
        self.width_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.width_value_label = ttk.Label(width_frame, text="30")
        self.width_value_label.pack(side=tk.RIGHT, padx=(10, 0))

        self.size_label = ttk.Label(pixel_frame, text="Grid Size: 30 x ?",
                                    font=("Arial", 9, "italic"))
        self.size_label.pack(anchor="w")

        # Color mode
        ttk.Label(pixel_frame, text="Color Mode:").pack(anchor="w", pady=(10, 0))
        self.color_mode_var = tk.StringVar(value=self.config.color_mode)
        mode_combo = ttk.Combobox(pixel_frame, textvariable=self.color_mode_var,
                                  state="readonly", width=20)
        mode_combo['values'] = ("Color", "Grayscale", "Limited Palette")
        mode_combo.pack(fill=tk.X, pady=5)
        mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        # Palette size
        self.palette_frame = ttk.Frame(pixel_frame)
        self.palette_frame.pack(fill=tk.X, pady=5)

        ttk.Label(self.palette_frame, text="Palette Size:").pack(anchor="w")
        palette_control_frame = ttk.Frame(self.palette_frame)
        palette_control_frame.pack(fill=tk.X, pady=5)

        self.palette_var = tk.IntVar(value=self.config.palette_size)
        self.palette_slider = ttk.Scale(palette_control_frame, from_=2, to=64,
                                        variable=self.palette_var, command=self._on_palette_change)
        self.palette_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.palette_value_label = ttk.Label(palette_control_frame, text="16")
        self.palette_value_label.pack(side=tk.RIGHT, padx=(10, 0))

    def _create_adjustments_section(self, parent):
        """Create image adjustments section"""
        adj_frame = ttk.LabelFrame(parent, text="Image Adjustments", padding=10)
        adj_frame.pack(fill=tk.X, pady=10)

        adjustments = [
            ("Brightness:", "brightness", 0.5, 2.0, self.config.brightness),
            ("Contrast:", "contrast", 0.5, 2.0, self.config.contrast),
            ("Saturation:", "saturation", 0.0, 2.0, self.config.saturation)
        ]

        self.adjustment_vars = {}
        for label, key, min_val, max_val, default in adjustments:
            ttk.Label(adj_frame, text=label).pack(anchor="w", pady=(5, 0))

            control_frame = ttk.Frame(adj_frame)
            control_frame.pack(fill=tk.X, pady=2)

            var = tk.DoubleVar(value=default)
            self.adjustment_vars[key] = var

            scale = ttk.Scale(control_frame, from_=min_val, to=max_val, variable=var,
                              command=lambda v, k=key: self._on_adjustment_change(k, v))
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

            value_label = ttk.Label(control_frame, text=f"{default:.1f}")
            value_label.pack(side=tk.RIGHT, padx=(10, 0))
            setattr(self, f"{key}_value_label", value_label)

    def _create_advanced_section(self, parent):
        """Create advanced options section"""
        adv_frame = ttk.LabelFrame(parent, text="Advanced Options", padding=10)
        adv_frame.pack(fill=tk.X, pady=10)

        # Checkboxes for advanced options
        self.dithering_var = tk.BooleanVar(value=self.config.dithering)
        ttk.Checkbutton(adv_frame, text="Enable Dithering",
                        variable=self.dithering_var, command=self._on_option_change).pack(anchor="w")

        self.edge_var = tk.BooleanVar(value=self.config.edge_enhancement)
        ttk.Checkbutton(adv_frame, text="Edge Enhancement",
                        variable=self.edge_var, command=self._on_option_change).pack(anchor="w")

        ttk.Checkbutton(adv_frame, text="Show Grid Lines",
                        variable=self.show_grid, command=self._update_preview).pack(anchor="w")

        ttk.Checkbutton(adv_frame, text="Auto Preview",
                        variable=self.auto_preview).pack(anchor="w")

        # Preview pixel size
        ttk.Label(adv_frame, text="Preview Pixel Size:").pack(anchor="w", pady=(10, 0))

        pixel_size_frame = ttk.Frame(adv_frame)
        pixel_size_frame.pack(fill=tk.X, pady=5)

        self.pixel_size_var = tk.IntVar(value=self.config.pixel_size)
        ttk.Scale(pixel_size_frame, from_=5, to=50, variable=self.pixel_size_var,
                  command=self._on_pixel_size_change).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.pixel_size_value_label = ttk.Label(pixel_size_frame, text="20px")
        self.pixel_size_value_label.pack(side=tk.RIGHT, padx=(10, 0))

    def _create_action_section(self, parent):
        """Create action buttons section"""
        action_frame = ttk.LabelFrame(parent, text="Actions", padding=10)
        action_frame.pack(fill=tk.X, pady=10)

        # Generation
        ttk.Button(action_frame, text="Generate Pixel Art",
                   command=self.generate_pixel_art, style="Accent.TButton").pack(
            fill=tk.X, pady=5)

        # Info display
        self.pixel_count_label = ttk.Label(action_frame, text="Total Pixels: 0",
                                           font=("Arial", 11, "bold"))
        self.pixel_count_label.pack(pady=5)

        # Export options
        export_frame = ttk.Frame(action_frame)
        export_frame.pack(fill=tk.X, pady=5)

        ttk.Button(export_frame, text="Export Image",
                   command=self.export_image).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(export_frame, text="Export Grid",
                   command=self.export_pixel_grid).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        # Color palette
        ttk.Button(action_frame, text="Show Color Palette",
                   command=self.show_color_palette).pack(fill=tk.X, pady=5)

    def _create_preview_panel(self):
        """Create the preview panel"""
        # Title
        title_frame = ttk.Frame(self.preview_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(title_frame, text="Original Image",
                  font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        ttk.Label(title_frame, text="Pixel Art Preview",
                  font=("Arial", 12, "bold")).pack(side=tk.RIGHT)

        # Preview containers
        preview_container = ttk.Frame(self.preview_frame)
        preview_container.pack(fill=tk.BOTH, expand=True)

        # Original image preview
        self.orig_frame = ttk.Frame(preview_container)
        self.orig_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.orig_canvas = tk.Canvas(self.orig_frame, bg="#34495e", highlightthickness=1,
                                     highlightbackground="#7f8c8d")
        self.orig_canvas.pack(fill=tk.BOTH, expand=True)

        # Pixel art preview
        self.pixel_frame = ttk.Frame(preview_container)
        self.pixel_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.pixel_canvas = tk.Canvas(self.pixel_frame, bg="#34495e", highlightthickness=1,
                                      highlightbackground="#7f8c8d")
        self.pixel_canvas.pack(fill=tk.BOTH, expand=True)

        # Add placeholder text
        self.orig_canvas.create_text(self.preview_size // 2, self.preview_size // 2,
                                     text="No image loaded", fill="#bdc3c7", font=("Arial", 12))
        self.pixel_canvas.create_text(self.preview_size // 2, self.preview_size // 2,
                                      text="Generate pixel art\nto see preview",
                                      fill="#bdc3c7", font=("Arial", 12), justify=tk.CENTER)

    def _create_status_bar(self):
        """Create status bar"""
        self.status_var = tk.StringVar(value="Ready - Load an image to get started")
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                               relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # Event handlers
    def _on_width_change(self, value):
        """Handle pixel width change"""
        width = int(float(value))
        self.width_value_label.config(text=str(width))
        self.config.pixel_width = width
        self._update_size_label()
        if self.auto_preview.get():
            self._auto_generate()

    def _on_mode_change(self, event=None):
        """Handle color mode change"""
        self.config.color_mode = self.color_mode_var.get()
        # Show/hide palette controls
        if self.config.color_mode == "Limited Palette":
            self.palette_frame.pack(fill=tk.X, pady=5)
        else:
            self.palette_frame.pack_forget()

        if self.auto_preview.get():
            self._auto_generate()

    def _on_palette_change(self, value):
        """Handle palette size change"""
        size = int(float(value))
        self.palette_value_label.config(text=str(size))
        self.config.palette_size = size
        if self.auto_preview.get():
            self._auto_generate()

    def _on_adjustment_change(self, key, value):
        """Handle image adjustment changes"""
        val = float(value)
        setattr(self.config, key, val)
        getattr(self, f"{key}_value_label").config(text=f"{val:.1f}")

        if self.image_path:
            self._display_original()

        if self.auto_preview.get():
            self._auto_generate()

    def _on_option_change(self):
        """Handle advanced option changes"""
        self.config.dithering = self.dithering_var.get()
        self.config.edge_enhancement = self.edge_var.get()
        if self.auto_preview.get():
            self._auto_generate()

    def _on_pixel_size_change(self, value):
        """Handle preview pixel size change"""
        size = int(float(value))
        self.pixel_size_value_label.config(text=f"{size}px")
        self.config.pixel_size = size
        self._update_preview()

    def _update_size_label(self):
        """Update the size label with current dimensions"""
        if not self.image_path:
            self.size_label.config(text="Grid Size: ? x ?")
            return

        try:
            with Image.open(self.image_path) as img:
                width = self.config.pixel_width
                aspect_ratio = img.height / img.width
                height = max(1, round(width * aspect_ratio))
                self.size_label.config(text=f"Grid Size: {width} x {height}")
        except Exception:
            self.size_label.config(text="Grid Size: ? x ?")

    def _auto_generate(self):
        """Auto-generate pixel art if enabled and image is loaded"""
        if self.image_path and self.pixel_grid is not None:
            self.root.after(500, self.generate_pixel_art)  # Debounce updates

    def _update_preview(self):
        """Update the pixel art preview"""
        if self.pixel_grid:
            self._display_pixel_art()

    def _set_status(self, message: str):
        """Update status bar"""
        self.status_var.set(message)
        self.root.update_idletasks()

    # Main functionality methods
    def new_project(self):
        """Create a new project"""
        self.image_path = ""
        self.pixel_grid = None
        self.current_project = None

        # Reset UI
        self.img_path_label.config(text="No image selected")
        self.pixel_count_label.config(text="Total Pixels: 0")

        # Clear canvases
        self.orig_canvas.delete("all")
        self.pixel_canvas.delete("all")

        # Add placeholder text
        self.orig_canvas.create_text(self.preview_size // 2, self.preview_size // 2,
                                     text="No image loaded", fill="#bdc3c7", font=("Arial", 12))
        self.pixel_canvas.create_text(self.preview_size // 2, self.preview_size // 2,
                                      text="Generate pixel art\nto see preview",
                                      fill="#bdc3c7", font=("Arial", 12), justify=tk.CENTER)

        self._set_status("New project created")

    def save_project(self):
        """Save current project"""
        if not self.image_path or not self.pixel_grid:
            messagebox.showwarning("No Data", "No pixel art to save")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pixelproj",
            filetypes=[("Pixel Art Project", "*.pixelproj"), ("All Files", "*.*")]
        )

        if file_path:
            try:
                project_data = {
                    "image_path": self.image_path,
                    "config": {
                        "pixel_width": self.config.pixel_width,
                        "brightness": self.config.brightness,
                        "contrast": self.config.contrast,
                        "saturation": self.config.saturation,
                        "color_mode": self.config.color_mode,
                        "palette_size": self.config.palette_size,
                        "pixel_size": self.config.pixel_size,
                        "dithering": self.config.dithering,
                        "edge_enhancement": self.config.edge_enhancement
                    },
                    "pixel_grid": self.pixel_grid,
                    "created": datetime.now().isoformat()
                }

                with open(file_path, "w") as f:
                    json.dump(project_data, f, indent=2)

                self.current_project = file_path
                self._set_status(f"Project saved: {os.path.basename(file_path)}")
                messagebox.showinfo("Success", f"Project saved successfully!")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to save project: {str(e)}")

    def load_project(self):
        """Load a project from file"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Pixel Art Project", "*.pixelproj"), ("All Files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, "r") as f:
                    project_data = json.load(f)

                # Load configuration
                config_data = project_data["config"]
                for key, value in config_data.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)

                # Update UI variables
                self.width_var.set(self.config.pixel_width)
                self.color_mode_var.set(self.config.color_mode)
                self.palette_var.set(self.config.palette_size)
                self.pixel_size_var.set(self.config.pixel_size)

                for key in ["brightness", "contrast", "saturation"]:
                    if key in self.adjustment_vars:
                        self.adjustment_vars[key].set(getattr(self.config, key))

                self.dithering_var.set(self.config.dithering)
                self.edge_var.set(self.config.edge_enhancement)

                # Load data
                self.image_path = project_data["image_path"]
                self.pixel_grid = project_data["pixel_grid"]

                # Update UI
                self._update_ui_labels()
                if os.path.exists(self.image_path):
                    self.img_path_label.config(text=os.path.basename(self.image_path))
                    self._display_original()
                else:
                    self.img_path_label.config(text=f"Missing: {os.path.basename(self.image_path)}")

                self._display_pixel_art()
                self.current_project = file_path
                self._set_status(f"Project loaded: {os.path.basename(file_path)}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load project: {str(e)}")

    def load_image(self):
        """Load an image file"""
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Image Files", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff"),
                ("JPEG Files", "*.jpg *.jpeg"),
                ("PNG Files", "*.png"),
                ("All Files", "*.*")
            ]
        )

        if file_path:
            self.image_path = file_path
            self.img_path_label.config(text=os.path.basename(file_path))
            self._display_original()
            self._update_size_label()
            self._set_status(f"Loaded: {os.path.basename(file_path)}")

    def _display_original(self):
        """Display the original image with adjustments"""
        if not self.image_path:
            return

        try:
            img = Image.open(self.image_path)
            img = ImageProcessor.apply_adjustments(img, self.config)

            # Get canvas dimensions
            self.orig_canvas.update()
            canvas_width = self.orig_canvas.winfo_width()
            canvas_height = self.orig_canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:  # Canvas is ready
                # Resize image to fit canvas while maintaining aspect ratio
                img.thumbnail((canvas_width - 20, canvas_height - 20), Image.LANCZOS)
                self.orig_tk_img = ImageTk.PhotoImage(img)

                # Clear canvas and display image
                self.orig_canvas.delete("all")
                self.orig_canvas.create_image(
                    canvas_width // 2,
                    canvas_height // 2,
                    image=self.orig_tk_img,
                    anchor="center"
                )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to display image: {str(e)}")
            self._set_status("Error displaying image")

    def _display_pixel_art(self):
        """Display the pixel art preview"""
        if not self.pixel_grid:
            return

        try:
            # Create preview image
            preview_img = ImageProcessor.create_preview_image(
                self.pixel_grid,
                self.config.pixel_size,
                self.show_grid.get()
            )

            # Get canvas dimensions
            self.pixel_canvas.update()
            canvas_width = self.pixel_canvas.winfo_width()
            canvas_height = self.pixel_canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:  # Canvas is ready
                # Resize for display while maintaining aspect ratio
                preview_img.thumbnail((canvas_width - 20, canvas_height - 20), Image.NEAREST)
                self.pixel_tk_img = ImageTk.PhotoImage(preview_img)

                # Clear canvas and display image
                self.pixel_canvas.delete("all")
                self.pixel_canvas.create_image(
                    canvas_width // 2,
                    canvas_height // 2,
                    image=self.pixel_tk_img,
                    anchor="center"
                )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to display pixel art: {str(e)}")

    def _update_ui_labels(self):
        """Update all UI labels with current values"""
        self.width_value_label.config(text=str(self.config.pixel_width))
        self.palette_value_label.config(text=str(self.config.palette_size))
        self.pixel_size_value_label.config(text=f"{self.config.pixel_size}px")

        for key in ["brightness", "contrast", "saturation"]:
            if hasattr(self, f"{key}_value_label"):
                getattr(self, f"{key}_value_label").config(text=f"{getattr(self.config, key):.1f}")

        self._update_size_label()

        # Show/hide palette controls based on mode
        if self.config.color_mode == "Limited Palette":
            self.palette_frame.pack(fill=tk.X, pady=5)
        else:
            self.palette_frame.pack_forget()

    def generate_pixel_art(self):
        """Generate pixel art from the loaded image"""
        if not self.image_path:
            messagebox.showwarning("No Image", "Please load an image first")
            return

        if not os.path.exists(self.image_path):
            messagebox.showerror("File Not Found", "The selected image file no longer exists")
            return

        try:
            self._set_status("Generating pixel art...")
            self.root.update()

            # Generate pixel art in separate thread for responsiveness
            def generate():
                try:
                    self.pixel_grid, total_pixels = ImageProcessor.generate_pixel_grid(
                        self.image_path, self.config
                    )

                    # Update UI in main thread
                    self.root.after(0, lambda: self._finish_generation(total_pixels))

                except Exception as e:
                    self.root.after(0, lambda: self._generation_error(str(e)))

            # Use threading for large images
            if self.config.pixel_width > 100:
                threading.Thread(target=generate, daemon=True).start()
            else:
                generate()

        except Exception as e:
            self._generation_error(str(e))

    def _finish_generation(self, total_pixels):
        """Finish the pixel art generation process"""
        self.pixel_count_label.config(text=f"Total Pixels: {total_pixels:,}")
        self._display_pixel_art()

        # Update palette window if open
        if self.palette_window and self.palette_window.winfo_exists():
            self._update_palette_window()

        self._set_status(f"Pixel art generated! {total_pixels:,} pixels")

    def _generation_error(self, error_msg):
        """Handle pixel art generation errors"""
        messagebox.showerror("Error", f"Failed to generate pixel art: {error_msg}")
        self._set_status("Error generating pixel art")

    def show_color_palette(self):
        """Show the color palette in a separate window"""
        if not self.pixel_grid:
            messagebox.showwarning("No Data", "Generate pixel art first")
            return

        # Close existing palette window
        if self.palette_window and self.palette_window.winfo_exists():
            self.palette_window.destroy()

        # Create new palette window
        self.palette_window = tk.Toplevel(self.root)
        self.palette_window.title("Color Palette")
        self.palette_window.geometry("400x300")
        self.palette_window.configure(bg="#2c3e50")

        # Make window stay on top
        self.palette_window.attributes('-topmost', True)

        self._update_palette_window()

    def _update_palette_window(self):
        """Update the color palette window content"""
        if not self.palette_window or not self.palette_window.winfo_exists():
            return

        # Clear existing content
        for widget in self.palette_window.winfo_children():
            widget.destroy()

        # Extract colors
        colors = ColorPalette.extract_colors(self.pixel_grid)

        # Create palette display
        title_label = tk.Label(self.palette_window, text=f"Color Palette ({len(colors)} colors)",
                               font=("Arial", 14, "bold"), bg="#2c3e50", fg="#ecf0f1")
        title_label.pack(pady=10)

        # Create scrollable frame for colors
        canvas = tk.Canvas(self.palette_window, bg="#2c3e50", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.palette_window, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#2c3e50")

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Display colors in a grid
        colors_per_row = 8
        color_size = 40

        for i, color in enumerate(colors):
            row = i // colors_per_row
            col = i % colors_per_row

            # Create color frame
            color_frame = tk.Frame(scrollable_frame, bg=color, width=color_size, height=color_size,
                                   relief="raised", bd=2)
            color_frame.grid(row=row * 2, column=col, padx=2, pady=2)
            color_frame.grid_propagate(False)

            # Add color label
            tk.Label(scrollable_frame, text=color, font=("Arial", 8),
                     bg="#2c3e50", fg="#ecf0f1").grid(row=row * 2 + 1, column=col, pady=(0, 5))

        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def export_image(self):
        """Export the pixel art as an image file"""
        if not self.pixel_grid:
            messagebox.showwarning("No Data", "Generate pixel art first")
            return

        # Export options dialog
        export_dialog = tk.Toplevel(self.root)
        export_dialog.title("Export Options")
        export_dialog.geometry("300x200")
        export_dialog.configure(bg="#2c3e50")
        export_dialog.resizable(False, False)

        # Center the dialog
        export_dialog.transient(self.root)
        export_dialog.grab_set()

        # Export size
        ttk.Label(export_dialog, text="Export Pixel Size:").pack(pady=10)
        export_size_var = tk.IntVar(value=20)
        ttk.Scale(export_dialog, from_=5, to=100, variable=export_size_var,
                  orient="horizontal").pack(pady=5)

        size_label = ttk.Label(export_dialog, text="20px")
        size_label.pack()

        def update_size_label(val):
            size_label.config(text=f"{int(float(val))}px")

        export_size_var.trace('w', lambda *args: update_size_label(export_size_var.get()))

        # Grid option
        show_grid_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(export_dialog, text="Show grid lines",
                        variable=show_grid_var).pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(export_dialog)
        button_frame.pack(pady=20)

        def do_export():
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[
                    ("PNG Files", "*.png"),
                    ("JPEG Files", "*.jpg"),
                    ("BMP Files", "*.bmp"),
                    ("All Files", "*.*")
                ]
            )

            if file_path:
                try:
                    export_dialog.destroy()
                    self._set_status("Exporting image...")

                    # Create export image
                    export_img = ImageProcessor.create_preview_image(
                        self.pixel_grid,
                        export_size_var.get(),
                        show_grid_var.get()
                    )

                    # Save image
                    if file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
                        # Convert to RGB for JPEG
                        export_img = export_img.convert('RGB')

                    export_img.save(file_path, quality=95)

                    messagebox.showinfo("Success", f"Image exported successfully!\nSaved to: {file_path}")
                    self._set_status(f"Image exported: {os.path.basename(file_path)}")

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export image: {str(e)}")
                    self._set_status("Export failed")

        ttk.Button(button_frame, text="Export", command=do_export).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel",
                   command=export_dialog.destroy).pack(side=tk.LEFT, padx=5)

    def export_pixel_grid(self):
        """Export the pixel grid data"""
        if not self.pixel_grid:
            messagebox.showwarning("No Data", "Generate pixel art first")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("Text Files", "*.txt"),
                ("CSV Files", "*.csv"),
                ("JSON Files", "*.json"),
                ("All Files", "*.*")
            ]
        )

        if file_path:
            try:
                self._set_status("Exporting pixel grid...")

                if file_path.lower().endswith('.json'):
                    # Export as JSON
                    data = {
                        "width": len(self.pixel_grid[0]),
                        "height": len(self.pixel_grid),
                        "colors": ColorPalette.extract_colors(self.pixel_grid),
                        "grid": self.pixel_grid,
                        "config": {
                            "pixel_width": self.config.pixel_width,
                            "color_mode": self.config.color_mode,
                            "palette_size": self.config.palette_size
                        },
                        "exported": datetime.now().isoformat()
                    }

                    with open(file_path, "w") as f:
                        json.dump(data, f, indent=2)

                elif file_path.lower().endswith('.csv'):
                    # Export as CSV
                    with open(file_path, "w") as f:
                        for row in self.pixel_grid:
                            f.write(",".join(row) + "\n")
                else:
                    # Export as plain text
                    with open(file_path, "w") as f:
                        f.write(f"Pixel Art Grid Export\n")
                        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"Dimensions: {len(self.pixel_grid[0])} x {len(self.pixel_grid)}\n")
                        f.write(f"Total Colors: {len(ColorPalette.extract_colors(self.pixel_grid))}\n")
                        f.write("=" * 50 + "\n\n")

                        for row in self.pixel_grid:
                            f.write(" ".join(row) + "\n")

                messagebox.showinfo("Success", f"Pixel grid exported successfully!\nSaved to: {file_path}")
                self._set_status(f"Grid exported: {os.path.basename(file_path)}")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to export grid: {str(e)}")
                self._set_status("Export failed")


def main():
    """Main function to run the application"""
    root = tk.Tk()

    # Set minimum window size
    root.minsize(1200, 800)

    # Create application
    app = PixelArtGenerator(root)

    # Handle window closing
    def on_closing():
        if app.palette_window and app.palette_window.winfo_exists():
            app.palette_window.destroy()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Start the application
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
        messagebox.showerror("Fatal Error", f"Application encountered a fatal error:\n{e}")


if __name__ == "__main__":
    main()