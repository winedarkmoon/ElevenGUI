import os
import customtkinter as ctk
from tkinter import ttk, filedialog, StringVar
from dotenv import load_dotenv
from PIL import Image
from utils.gui_functions import *
from threading import Thread
import sys
import numpy as np
import sounddevice as sd
import soundfile as sf
import time
import re
import logging
import sys
try:
    import openai
    # Whisper API is available
except ImportError:
    openai = None
    # Handle Whisper API not being available

try:
    import whisper
    # Whisper Local is available
except ImportError:
    whisper = None
    # Handle Whisper Local not being available


# Modes: "System" (standard), "Dark", "Light"
ctk.set_appearance_mode("Light")
# Themes: "blue" (standard), "green", "dark-blue"
ctk.set_default_color_theme("blue")


load_dotenv()
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


class ElevenGUI:

    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("ElevenGUI")
        self.window_width = 1400
        self.window_height = 800
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        # Calculate the x and y coordinates to center the window
        self.x = (self.screen_width / 2) - (self.window_width / 2)
        self.y = (self.screen_height / 2) - (self.window_height / 2)

        # Set the window position and size
        self.root.geometry('%dx%d+%d+%d' % (self.window_width,
                           self.window_height, self.x, self.y))

        # self.root.geometry("1400x800")
        self.image_path = os.path.join(os.path.dirname(
            os.path.realpath(__file__)), "images")
        self.voices_data = fetch_voices(ELEVENLABS_API_KEY)
        self.chat_image = ctk.CTkImage(light_image=Image.open(os.path.join(self.image_path, "chat_dark.png")),
                                       dark_image=Image.open(os.path.join(self.image_path, "chat_light.png")), size=(20, 20))
        self.play_image = ctk.CTkImage(light_image=Image.open(
            os.path.join(self.image_path, "play.png")), size=(80, 80))
        self.pause_image = ctk.CTkImage(light_image=Image.open(
            os.path.join(self.image_path, "pause.png")), size=(80, 80))
        whisper_api_installed = 'openai' in sys.modules
        whisper_local_installed = 'whisper' in sys.modules

        # Create a list to hold the available Whisper options
        self.whisper_options = []
        if whisper_api_installed:
            self.whisper_options.append("Whisper API")
        if whisper_local_installed:
            self.whisper_options.append("Whisper Local")
        self.current_selected_row = None
        self.history_frame_visible = False
        self.configure_grid()
        self.init_ui()
        self.audio_data_played = 0
        self.temp_audio_file_name = None
        self.audio_playback_finished = False
        self.is_playing = False
        self.is_paused = False
        self.is_recording = False
        self.stream = None
        # Need both of these values to correctly update the audio position in the GUI
        self.audio_length = 0
        self.correct_audio_pos = 0
        # Used by our tkinter gui element named "actual_song_lbl"   > Shows the name of the current song being played.
        self.current_audio = StringVar(value="")
        self.status = StringVar()
        # Used by our tkinter gui element named "status_label"      > Playing | Paused | Stopped
        self.status.set("Stopped")
        self.new_audio_position = 0
        self.current_length = 0

        self.root.mainloop()

    def configure_grid(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(6, weight=0)

    def create_top_frame(self):
        top_frame = ctk.CTkFrame(self.root, height=80, fg_color="transparent")
        top_frame.grid(row=1, column=1, sticky="nsew", padx=15, pady=0)
        return top_frame

    def create_text_box(self):
        text_box = ctk.CTkTextbox(self.root, wrap=ctk.WORD)
        text_box.grid(row=2, column=1, sticky="nsew", padx=10, pady=(10, 0))
        text_box.bind('<Control-v>', lambda event: custom_paste(event,
                      text_box, self.char_count, self.generate_button))
        text_box.bind('<Any-KeyPress>', lambda event: check_character_limit(event,
                      text_box, self.char_count, self.generate_button))
        text_box.bind('<Button-1>', lambda event: check_character_limit(
            event, text_box, self.char_count, self.generate_button))
        return text_box

    def create_text_status_frame(self):
        self.text_status_frame = ctk.CTkFrame(
            self.root, fg_color="transparent")
        self.text_status_frame.grid(row=3, column=1, sticky="new")

        char_count = ctk.CTkLabel(
            self.text_status_frame, text="0/5000", font=("Arial", 12), state="disabled")
        char_count.pack(side=ctk.LEFT, padx=10, pady=0)

        right_button = ctk.CTkLabel(
            self.text_status_frame, text="total quota used: 0 ", font=("Arial", 12), state="disabled")
        right_button.pack(side=ctk.RIGHT, padx=10, pady=0)

        return char_count, right_button

    def create_sample_frame(self):
        self.sample_frame = ctk.CTkFrame(self.root)
        self.sample_frame.grid(row=0, column=1, sticky="new", padx=10)

        settings_label = ctk.CTkLabel(
            self.sample_frame, text="Settings", font=("Arial", 12), state="disabled")
        settings_label.pack(side=ctk.LEFT, padx=10, pady=(5, 0))

        preview_label = ctk.CTkLabel(
            self.sample_frame, text="Preview ", font=("Arial", 12), state="disabled")
        preview_label.pack(side=ctk.RIGHT, padx=10, pady=(5, 0))

        return settings_label, preview_label

    def create_generate_button_frame(self):
        generate_button_frame = ctk.CTkFrame(
            self.root, fg_color="transparent")
        generate_button_frame.grid(row=5, column=1, sticky="ew", pady=10)
        self.progressbar = ctk.CTkProgressBar(generate_button_frame)
        self.progressbar.configure(mode="indeterminate")
        self.generate_button = ctk.CTkButton(generate_button_frame, text="Generate", command=lambda: Thread(target=generate_async, args=(self, ELEVENLABS_API_KEY, self.right_button, self.progressbar, self.generate_button)).start()
                                             )
        self.generate_button.pack(padx=10, pady=10, fill="x")

        return generate_button_frame

    def create_voice_selection_frame(self, top_frame):
        voice_selection_frame = ctk.CTkFrame(
            top_frame, fg_color="transparent")
        voice_selection_frame.pack(
            side="left", padx=0, pady=(0, 0), fill="both", expand=True)
        voice_selection_frame.update_idletasks()

        self.preview_button = ctk.CTkButton(voice_selection_frame, corner_radius=8, width=4, border_spacing=10,
                                            fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                            image=self.chat_image, anchor="e", text="", command=lambda: play_voice_preview(self.voices_data, self.voice_selection_optionmenu, grab_preview))
        self.preview_button.pack(side="right")
        voices = fetch_voices(ELEVENLABS_API_KEY)
        voice_names = ["Select voice:"] + [voice['name'] for voice in voices]
        self.voice_selection_optionmenu = ctk.CTkOptionMenu(
            voice_selection_frame, values=voice_names,
            command=self.on_voice_selection_changed, dynamic_resizing=True)
        self.voice_selection_optionmenu.pack(
            side="left", pady=5, fill="x")

    def on_voice_selection_changed(self, *args):
        if self.history_frame_visible:
            self.populate_table()

    def create_slider_bar_frame(self):
        self.slider_bar_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.slider_bar_frame.grid(row=4, column=1, padx=(
            20, 0), pady=(20, 0), sticky="nsew")

        self.create_stability_slider_frame(self.slider_bar_frame)
        self.create_clarity_slider_frame(self.slider_bar_frame)

    def create_stability_slider_frame(self, slider_bar_frame):
        stability_slider_frame = ctk.CTkFrame(
            slider_bar_frame, fg_color="transparent")
        stability_slider_frame.pack(fill="x")

        stability_label = ctk.CTkLabel(
            stability_slider_frame, text="Stability", anchor="w")
        stability_label.pack(side="top", padx=10, pady=(5, 5), anchor="w")

        slider_1 = ctk.CTkSlider(stability_slider_frame, from_=0, to=1,
                                 number_of_steps=100, command=self.update_stability_value)
        slider_1.pack(side="left", padx=(10, 10),
                      pady=(5, 10), fill="x", expand=True)

        self.stability_val = ctk.CTkLabel(stability_slider_frame, text="")
        self.stability_val.pack(side="left", padx=(0, 20), pady=(10, 10))

        default_slider_value = 0.75
        slider_1.set(default_slider_value)
        self.update_stability_value(default_slider_value)

    def create_clarity_slider_frame(self, slider_bar_frame):
        clarity_slider_frame = ctk.CTkFrame(
            slider_bar_frame, fg_color="transparent")
        clarity_slider_frame.pack(fill="x")

        clarity_label = ctk.CTkLabel(
            clarity_slider_frame, text="Clarity + Similarity Enhancement", anchor="w")
        clarity_label.pack(side="top", padx=10, pady=(5, 5), anchor="w")

        slider_2 = ctk.CTkSlider(clarity_slider_frame, from_=0, to=1,
                                 number_of_steps=100, command=self.update_clarity_value)
        slider_2.pack(side="left", padx=(10, 10),
                      pady=(5, 10), fill="x", expand=True)

        self.clarity_val = ctk.CTkLabel(clarity_slider_frame, text="")
        self.clarity_val.pack(side="left", padx=(0, 20), pady=(10, 10))

        default_slider_value = 0.75
        slider_2.set(default_slider_value)
        self.update_clarity_value(default_slider_value)

    def create_sidebar_logo(self, sidebar_frame):
        logo_label = ctk.CTkLabel(
            sidebar_frame, text="ElevenGUI", font=ctk.CTkFont(size=20, weight="bold"))
        logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

    def create_sidebar_content(self, sidebar_frame):
        sidebar_button_1 = ctk.CTkButton(
            sidebar_frame, text="Synthesize speech", command=lambda: self.sidebar_button_event(1))
        sidebar_button_1.grid(row=1, column=0, padx=20, pady=10)

        sidebar_button_2 = ctk.CTkButton(
            sidebar_frame, text="Voices", command=lambda: self.sidebar_button_event(2))
        sidebar_button_2.grid(row=2, column=0, padx=20, pady=10)

        sidebar_button_3 = ctk.CTkButton(
            sidebar_frame, text="History", command=lambda: self.sidebar_button_event(3))
        sidebar_button_3.grid(row=3, column=0, padx=20, pady=10)

        appearance_mode_label = ctk.CTkLabel(
            sidebar_frame, text="Appearance Mode:", anchor="w")
        appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        appearance_mode_optionmenu = ctk.CTkOptionMenu(sidebar_frame, values=["Light", "Dark", "System"],
                                                       command=self.change_appearance_mode_event)
        appearance_mode_optionmenu.grid(
            row=6, column=0, padx=20, pady=(10, 10))
        scaling_label = ctk.CTkLabel(
            sidebar_frame, text="UI Scaling:", anchor="w")
        scaling_label.grid(row=7, column=0, padx=20, pady=(10, 0))
        scaling_optionmenu = ctk.CTkOptionMenu(sidebar_frame, values=["80%", "90%", "100%", "110%", "120%"],
                                               command=self.change_scaling_event)
        scaling_optionmenu.grid(row=8, column=0, padx=20, pady=(10, 20))
        appearance_mode_optionmenu.set("Light")
        scaling_optionmenu.set("100%")

    def create_sidebar(self):
        sidebar_frame = ctk.CTkFrame(self.root, width=140, corner_radius=0)
        sidebar_frame.grid(row=0, column=0, rowspan=7,
                           sticky=ctk.N + ctk.S + ctk.E + ctk.W)
        sidebar_frame.grid_rowconfigure(4, weight=1)

        self.create_sidebar_logo(sidebar_frame)
        self.create_sidebar_content(sidebar_frame)

    def create_rightbar_content(self, rightbar_frame):
        self.tabview = ctk.CTkTabview(rightbar_frame, width=250)
        self.tabview.grid(row=0, column=2, padx=(
            20, 20), pady=(20, 0), sticky="nsew")
        self.tabview.add("Speech to Text")
        #self.tabview.add("Tab 2")
        #self.tabview.add("Tab 3")
        self.tabview.tab("Speech to Text").grid_columnconfigure(
            0, weight=1)  # configure grid of individual tabs
        self.record_button = ctk.CTkButton(
            self.tabview.tab("Speech to Text"), text="Record audio", command=self.record_audio)
        self.record_button.grid(row=0, column=0, padx=20, pady=10)
        self.upload_button = ctk.CTkButton(
            self.tabview.tab("Speech to Text"), text="Upload audio", command=self.upload_audio)
        self.upload_button.grid(row=1, column=0, padx=20, pady=10)
        # self.quick_button = ctk.CTkButton(
        #    self.tabview.tab("Speech to Text"), text="Gen audio", command=lambda: Thread(target=generate_async, args=(self, ELEVENLABS_API_KEY, self.right_button, self.progressbar, self.generate_button)).start())
        #self.quick_button.grid(row=2, column=0, padx=20, pady=10)
        if len(self.whisper_options) > 0:
            self.tts_menu = ctk.CTkOptionMenu(
                self.tabview.tab("Speech to Text"), values=self.whisper_options)
            self.tts_menu.grid(row=2, column=0, padx=20, pady=10)

    def create_rightbar(self):
        rightbar_frame = ctk.CTkFrame(self.root, width=140, corner_radius=0)
        rightbar_frame.grid(row=0, column=2, rowspan=6,
                            sticky=ctk.N + ctk.S + ctk.E + ctk.W)
        self.create_rightbar_content(rightbar_frame)

    def create_audiobar(self):
        audiobar_frame = ctk.CTkFrame(self.root, height=100, corner_radius=0)
        audiobar_frame.grid(row=6, column=1,
                            sticky='nsew')
        self.play_button = ctk.CTkButton(audiobar_frame, width=4, border_spacing=10,
                                         fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                         image=self.play_image, anchor="e", text="", command=lambda: play_temp_audio(self))
        self.play_button.pack(side="left")
        self.pause_button = ctk.CTkButton(audiobar_frame, width=4, border_spacing=10,
                                          fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
                                          image=self.pause_image, anchor="e", text="", command=lambda: pause_audio(self))
        self.audio_pos_slider = ctk.CTkSlider(
            audiobar_frame, from_=0, to=100, number_of_steps=100)
        self.audio_pos_slider.pack(side="left", padx=(
            10, 10), pady=(5, 10), fill="x", expand=True)
        audio_slider_val = 0
        self.audio_pos_slider.set(audio_slider_val)

        self.audio_curr_pos = ctk.CTkLabel(
            audiobar_frame, text="0:00", font=("Arial", 12), state="disabled")
        self.audio_curr_pos.pack(side=ctk.LEFT, padx=(0, 15), pady=(5, 10))

        self.audio_end_pos = ctk.CTkLabel(
            audiobar_frame, text="0:00", font=("Arial", 12), state="disabled")
        self.audio_end_pos.pack(side=ctk.RIGHT, padx=(0, 15), pady=(5, 10))

        return audiobar_frame

    def record_callback(self, indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)
        if self.is_recording:
            self.recorded_audio.append(indata.copy())

    def record_audio(self):
        if len(self.whisper_options) == 0:
            print("No speech to text options are available. Please install either 'openai' or 'whisper' to enable speech to text functionality.")
            return
        if not self.is_recording:
            self.is_recording = True
            self.record_button.configure(text="Stop recording")
            self.recorded_audio = []
            self.stream = sd.InputStream(
                samplerate=44100, channels=2, callback=self.record_callback)
            self.stream.start()
        else:
            self.is_recording = False
            self.record_button.configure(text="Record Audio")
            self.stream.stop()
            self.stream.close()

            # Process the recorded audio and save it to a temporary file
            try:
                audio_data = np.concatenate(self.recorded_audio, axis=0)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
                    output_file = temp_audio_file.name
                    sf.write(output_file, audio_data, 44100, 'PCM_24')
                    print(f"Audio saved to {output_file}")

                    # Transcribe the recorded audio and paste it into the textbox
                    transcribed_text = self.transcribe_audio(output_file)
                    print(transcribed_text)
                    self.text_box.delete("1.0", "end")
                    self.text_box.insert("1.0", transcribed_text)
                    dummy_event = type("DummyEvent", (object,), {
                        "keysym": None})()
                    check_character_limit(
                        dummy_event, self.text_box, self.char_count, self.generate_button)

                # File is now closed, delete it.
                temp_audio_file.close()
                time.sleep(1)  # wait for 1 second
                os.unlink(output_file)

            except Exception as e:
                logging.exception("Error processing recorded audio: %s", e)

    def upload_audio(self):
        # Open a file dialog and get the selected file's path
        file_path = filedialog.askopenfilename(
            filetypes=[("Audio files", "*.wav *.mp3")])

        if len(self.whisper_options) == 0:
            print("No speech to text  options are available. Please install either 'openai' or 'whisper' to enable speech to text functionality.")
            return

        if file_path:
            # Transcribe the uploaded audio and paste it into the textbox
            transcribed_text = self.transcribe_audio(file_path)
            print(transcribed_text)
            self.text_box.delete("1.0", "end")
            self.text_box.insert("1.0", transcribed_text)
            dummy_event = type("DummyEvent", (object,), {"keysym": None})()
            check_character_limit(dummy_event, self.text_box,
                                  self.char_count, self.generate_button)
        else:
            print("No file selected")

    def transcribe_audio(self, audio_file):
        # Retrieve the selected option from the menu only if both are available

        if len(self.whisper_options) > 1:
            selected_option = self.tts_menu.get()
        else:
            selected_option = self.whisper_options[0]

        if selected_option == "Whisper API":
            with open(audio_file, "rb") as file:
                result = openai.Audio.transcribe(
                    model="whisper-1",
                    file=file,
                    response_format="json"
                )
            text = result["text"]   # Updated according to OpenAI API response
        elif selected_option == "Whisper Local":
            model = whisper.load_model("base.en")
            result = model.transcribe(audio_file, suppress_tokens='')
            text = result["text"]

        # Add spaces before and after punctuation marks, excluding apostrophes
        text = re.sub(r'(?<=\w)([^\w\s\'])(?=\w)', r' \1 ', text)
        # Replace multiple spaces with a single space
        text = re.sub(r'\s+', ' ', text)
        # Remove leading and trailing spaces
        text = text.strip()

        return text

    def update_audio_pos(self):
        # print("update_audio_pos called")  # Add this line
        if self.is_paused or self.is_stopped or self.audio_data_played >= len(self.audio_data):
            pass
        else:
            current_audio_pos_seconds = self.audio_data_played / self.samplerate
            # print(f"current_audio_pos_seconds: {current_audio_pos_seconds}")  # Add this line

            if self.audio_length != 0:
                slider_percentage = (
                    current_audio_pos_seconds / self.audio_length) * 100
            else:
                # Handle the case where audio_length is zero
                slider_percentage = 0

            self.audio_pos_slider.set(slider_percentage)
            converted_to_time = convert(current_audio_pos_seconds)
            self.audio_curr_pos.configure(text=f"{converted_to_time}")
            self.new_audio_position = current_audio_pos_seconds
            if slider_percentage >= 95:
                self.audio_pos_slider.set(100)
                self.play_button.configure(image=self.play_image)

        self.root.after(10, self.update_audio_pos)

    # Function to handle the event when the user clicks the slider
    def start_audio_pos_update_loop(self):
        self.is_paused = False
        self.is_stopped = False
        self.update_audio_pos()

    def audio_callback(self, outdata: np.ndarray, frames: int, time, status) -> None:
        if status:
            print(status, file=sys.stderr)

        if self.audio_playback_finished:
            # fill the buffer with zeros to prevent any residual noise
            outdata.fill(0)

            return

        remaining_frames = len(self.audio_data) - self.audio_data_played

        if remaining_frames >= frames:
            chunk = self.audio_data[self.audio_data_played:self.audio_data_played + frames]
            self.audio_data_played += frames
        else:
            chunk = np.concatenate(
                (self.audio_data[self.audio_data_played:], np.zeros(frames - remaining_frames)))
            self.audio_data_played += len(chunk)

        chunk_stereo = np.repeat(chunk[np.newaxis], 2, axis=0).T
        outdata[:] = chunk_stereo

        if self.audio_data_played >= len(self.audio_data):
            self.audio_playback_finished = True

    def new_audio_callback(self, outdata, frames, time, status):
        if status:
            print(status, file=sys.stderr)

        chunk_size = frames
        start = self.audio_data_played
        stop = start + chunk_size

        if len(self.audio_data.shape) > 1:
            num_channels = self.audio_data.shape[1]
        else:
            num_channels = 1

        if stop > self.audio_data.shape[0]:
            stop = self.audio_data.shape[0]
            chunk_size = stop - start

        if num_channels > 1:
            outdata[:, 0] = self.audio_data[start:stop, 0]
            outdata[:, 1] = self.audio_data[start:stop, 1]
        else:
            outdata[:, 0] = self.audio_data[start:stop]
            outdata[:, 1] = self.audio_data[start:stop]

        self.audio_data_played += chunk_size

    def stop_audio_pos_update_loop(self):
        self.is_stopped = True

    def play_button_check(self):
        if self.is_playing:  # If a song is playing
            # Changes the button from "Play" to "Pause"
            self.play_button.configure(image=self.pause_image)

            self.root.update()
        elif self.is_paused:  # If a song is paused
            # Changes the button from "Pause" to "Resume"
            self.play_button.configure(image=self.play_image)

            self.root.update()
        elif self.is_stopped:  # If a song is stopped
            # Changes the button to "Play"
            self.play_button.configure(image=self.play_image)
            self.root.update()

    # Function that sets the main booleans to True or False depending on the input parameter.
    def boolean_switch(self, input):
        if input == "play":
            self.is_paused = False
            self.is_stopped = False
            self.is_playing = True
        elif input == "pause":
            self.is_playing = False
            self.is_stopped = False
            self.is_paused = True
        elif input == "stop":
            self.is_playing = False
            self.is_paused = False
            self.is_stopped = True
        else:
            print("[DEBUG] Error in boolean_switch function: Invalid input.")

    # --------------------------------------------------------------------------------------------

    def update_table_style(self):
        appearance_mode = ctk.get_appearance_mode()

        if appearance_mode == "System":
            system_theme = ctk.get_system_theme()
            if system_theme == "Light":
                x = 0
            elif system_theme == "Dark":
                x = 1
            else:
                # Default to Light if the system theme is not recognized
                x = 0
        elif appearance_mode == "Light":
            x = 0
        elif appearance_mode == "Dark":
            x = 1

        background_color = ctk.ThemeManager.theme["CTkFrame"]["fg_color"][x]
        text_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"][x]

        self.style.configure("Treeview",
                             background=background_color,
                             foreground=text_color,
                             rowheight=120,
                             fieldbackground=background_color,
                             bordercolor="#343638",
                             borderwidth=10)
        self.table.update_idletasks()

    def on_treeview_select(self, event, root):
        # Check if there is a selected item
        if not self.table.selection():
            return
        selected_item = self.table.selection()[0]
        history_item_id = self.table.item(selected_item, "tags")[0]
        delay = 50

        # Stop and unload the current audio
        stop_and_unload_audio(self)

        # Close the current stream if it's playing
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Load the new audio after a short delay
        self.root.after(delay, lambda: get_history_audio(
            self, history_item_id))

    def populate_table(self):
        print("Populating table...")

        # Clear the current content of the table
        for item in self.table.get_children():
            self.table.delete(item)

        selected_voice_name = self.voice_selection_optionmenu.get()
        data = fetch_history(ELEVENLABS_API_KEY)
        max_line_width = 75

        for item in data:
            # Skip the item if the voice name doesn't match the selected voice
            if selected_voice_name != "Select voice:" and item["voice_name"] != selected_voice_name:
                continue

            wrapped_text = wrap_text(item["text"], max_line_width)
            formatted_date = unix_to_date(item["date_unix"])
            settings = item["settings"]
            stability = settings.get("stability", "N/A")
            similarity_boost = settings.get("similarity_boost", "N/A")
            self.table.insert("", "end", tags=(str(item["history_item_id"]),), values=(
                f"{item['voice_name']}\n{formatted_date}", f"Stability: {stability}\nSimilarity Boost: {similarity_boost}", wrapped_text))
        print("Populated table successfully.")

    def create_table(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview",
                             background=ctk.ThemeManager.theme["CTkFrame"]["fg_color"][1],
                             foreground=ctk.ThemeManager.theme["CTkLabel"]["text_color"][1],
                             rowheight=120,
                             fieldbackground=ctk.ThemeManager.theme["CTkFrame"]["fg_color"][1],
                             bordercolor="#343638",
                             borderwidth=10)
        self.style.map('Treeview', background=[('selected', '#22559b')])

        self.style.configure("Treeview.Heading",
                             background="#565b5e",
                             foreground="white",
                             relief="flat")

        self.style.map("Treeview.Heading",
                       background=[('active', '#3484F0')])

        self.table = ttk.Treeview(self.add_menu_display,
                                  columns=('voice_name', 'settings',
                                           'text'),
                                  selectmode='browse',
                                  show='headings')

        self.table.column("#1", anchor="w", minwidth=5, stretch=False)
        self.table.column("#2", anchor="w", minwidth=5, stretch=False)
        self.table.column("#3", anchor="w", minwidth=200)

        self.table.heading('voice_name', text='Voice', anchor="w")
        self.table.heading('settings', text='Settings', anchor="w")
        self.table.heading('text', text='Text', anchor="w")

        self.table.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

        self.table.bind("<<TreeviewSelect>>",
                        lambda event: self.on_treeview_select(self, event))
    # --------------------------------------------------------------------------------------------

    def init_ui(self):
        self.create_sidebar()
        self.create_main_content()
        self.create_rightbar()
        self.create_audiobar()

    def create_main_content(self):
        self.top_frame = self.create_top_frame()
        self.text_box = self.create_text_box()
        self.char_count, self.right_button = self.create_text_status_frame()
        self.settings_label, self.preview_label = self.create_sample_frame()
        self.generate_button_frame = self.create_generate_button_frame()
        self.create_voice_selection_frame(self.top_frame)
        self.create_slider_bar_frame()

        update_quota(ELEVENLABS_API_KEY, self.right_button)

    def update_stability_value(self, val):
        percentage = float(val) * 100
        self.stability_val.configure(text=f"{percentage:.0f}%")

    def update_clarity_value(self, val):
        percentage = float(val) * 100
        self.clarity_val.configure(text=f"{percentage:.0f}%")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
        if self.history_frame_visible:
            # Delay the call to update_table_style
            self.root.after(30, self.update_table_style)
        # Delay the call to update_idletasks
        self.root.after(30, self.root.update_idletasks)

    def change_scaling_event(self, new_scaling: str):
        new_scaling_float = int(new_scaling.replace("%", "")) / 100
        ctk.set_widget_scaling(new_scaling_float)

    def sidebar_button_event(self, button_id):
        if button_id == 1:
            self.switch_to_synthesize_speech()
        elif button_id == 2:
            print("Voice editing functionality coming soon!")
        elif button_id == 3:
            self.create_history_frame()

    def trigger_dummy_event(self):
        dummy_event = type("DummyEvent", (object,), {"widget": self.table})()
        self.on_treeview_select(dummy_event, self.root)

    def switch_to_synthesize_speech(self):
        print("Switching to Synthesize speech view")
        self.clear_content_frames()
        self.history_frame_visible = False
        self.sample_frame.grid(row=0, column=1, sticky="new", padx=10)
        self.top_frame.grid(row=1, column=1, sticky="nsew", padx=15, pady=0)
        self.text_box.grid(row=2, column=1, sticky="nsew", padx=10, pady=10)
        self.text_status_frame.grid(row=3, column=1, sticky="new")
        self.slider_bar_frame.grid(row=4, column=1, padx=(
            20, 0), pady=(20, 0), sticky="nsew")
        self.generate_button_frame.grid(row=5, column=1, sticky="ew", pady=10)

    def create_history_frame(self):
        self.clear_content_frames()
        ctk.AppearanceModeTracker.add(self.update_table_style)
        self.history_frame_visible = True
        self.sample_frame.grid(row=0, column=1, sticky="new", padx=10)
        self.top_frame.grid(row=1, column=1, sticky="nsew", padx=15, pady=0)
        self.history_frame = ctk.CTkFrame(self.root)
        self.history_frame.grid(
            row=2, column=1, rowspan=3, sticky="nsew", padx=10, pady=10)
        self.add_menu_display = ctk.CTkFrame(self.history_frame,
                                             corner_radius=15)
        self.add_menu_display.grid(pady=15, padx=15, sticky="nwse")
        self.history_frame.grid_rowconfigure(0, weight=1)
        self.history_frame.grid_columnconfigure(0, weight=1)
        self.add_menu_display.grid_rowconfigure(0, weight=1)
        self.add_menu_display.grid_columnconfigure(0, weight=1)
        self.create_table()
        self.update_table_style()
        self.populate_table()

    def clear_content_frames(self):
        for widget in self.root.grid_slaves():
            if widget.grid_info()["column"] == 1 and widget.grid_info()["row"] > 1 and widget.grid_info()["row"] != 6:
                widget.grid_forget()


if __name__ == "__main__":
    ElevenGUI()
