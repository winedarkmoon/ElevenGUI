import datetime
import requests
import tempfile
from typing import Callable
import customtkinter as ctk
import os
import threading
from dotenv import load_dotenv
import time
import sounddevice as sd
import soundfile as sf
from io import BytesIO

load_dotenv()
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')


def fetch_history(api_key):
    url = "https://api.elevenlabs.io/v1/history"
    headers = {"xi-api-key": api_key}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # raise exception if the response contains an HTTP error status code
        data = response.json()
        return data["history"]
    except Exception as e:
        print(f"Failed to fetch the history: {e}")
        return []  # return an empty list if fetching the history fails



def wrap_text(text, max_line_width):
    words = text.split()
    lines = []
    current_line = []
    current_line_width = 0

    for word in words:
        word_width = len(word) + 1  # +1 for a space character
        if current_line_width + word_width <= max_line_width:
            current_line.append(word)
            current_line_width += word_width
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
            current_line_width = word_width

    if current_line:
        lines.append(' '.join(current_line))

    return '\n'.join(lines)


def unix_to_date(unix_timestamp):
    dt_object = datetime.datetime.fromtimestamp(unix_timestamp)
    return dt_object.strftime('%m.%d.%y, %H:%M')


def check_character_limit(event, text_box, char_count, generate_button):
    current_length = len(text_box.get("1.0", 'end-1c'))
    # print(current_length)
    char_count.configure(text=f"{current_length}/5000")

    # Disable the button if the limit is reached
    if current_length >= 5000 or current_length == 0:
        generate_button.configure(state="disabled")
    else:
        generate_button.configure(state="normal")

    # If the character limit is exceeded, allow only backspace and delete events
    if current_length >= 5000 and event.keysym not in ['BackSpace', 'Delete']:
        return "break"

    # Update the text box after handling cut and paste events
    if event.keysym in ['Control_L', 'Control_R']:
        text_box.after(50, lambda: check_character_limit(
            event, text_box, char_count, generate_button))


def custom_paste(event, text_box, char_count, generate_button):
    try:
        pasted_text = text_box.clipboard_get()
    except ctk.TclError:
        # There's nothing in the clipboard, or it's not text
        return

    current_length = len(text_box.get("1.0", 'end-1c'))
    remaining_chars = 5000 - current_length

    # Only insert the text if it doesn't exceed the limit
    if len(pasted_text) <= remaining_chars:
        text_box.insert(ctk.INSERT, pasted_text)
    else:
        text_box.insert(ctk.INSERT, pasted_text[:remaining_chars])

    # Prevent the default paste event
    return "break"


def grab_preview(voices_data, selected_voice_name):
    # Get the selected voice name
    print(selected_voice_name)

    # Get the voice_id corresponding to the selected voice name
    preview_url = None
    for voice in voices_data:
        if voice["name"] == selected_voice_name:
            preview_url = voice["preview_url"]
            print(preview_url)
    return preview_url


def fetch_voices(api_key):
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": api_key}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            voices_data = data['voices']
            return voices_data
        else:
            print("Error fetching voices")
            return []
    except requests.RequestException:
        print("Unable to connect to ElevenLabs API. Please check your internet connection.")
        return []


def update_quota(api_key, right_button):
    url = "https://api.elevenlabs.io/v1/user"
    headers = {"xi-api-key": api_key}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            quota_used = data['subscription']['character_count']
            quota_total = data['subscription']['character_limit']

            right_button.configure(
                text=f"total quota used: {quota_used} / {quota_total}")
        else:
            print("Error updating quota.")
    except requests.exceptions.ConnectionError:
        print("Unable to connect to ElevenLabs API. Please check your internet connection.")



# Declare a dictionary for caching audio files
voice_preview_cache = {}


def play_voice_preview(voices_data, voice_selection_optionmenu, grab_preview: Callable):
    selected_voice_name = voice_selection_optionmenu.get()

    def play_audio_callback(audio_data, samplerate):
        sd.play(audio_data, samplerate)

    def download_and_cache_preview(voice_name, preview_url, callback):
        response = requests.get(preview_url)

        if response.status_code == 200:
            audio_data = response.content
            audio_file = BytesIO(audio_data)
            data, samplerate = sf.read(audio_file, dtype='float32')

            voice_preview_cache[voice_name] = (data, samplerate)
            # Call the callback function to play the audio
            callback(data, samplerate)

    if selected_voice_name in voice_preview_cache:
        audio_data, samplerate = voice_preview_cache[selected_voice_name]
        play_audio_callback(audio_data, samplerate)
    else:
        preview_url = grab_preview(voices_data, selected_voice_name)
        if preview_url is not None:
            # Create a new thread to download and cache the preview
            download_thread = threading.Thread(target=download_and_cache_preview, args=(
                selected_voice_name, preview_url, play_audio_callback))
            download_thread.start()


def generate_event(self, ELEVENLABS_API_KEY, right_button, progressbar, generate_button):
    print("Generate button clicked")

    # Extract the text from the textbox
    text = self.text_box.get("1.0", "end-1c")
    progressbar.pack(padx=10, pady=10, fill="x", before=generate_button)
    progressbar.start()
    # Get the selected voice name
    selected_voice_name = self.voice_selection_optionmenu.get()
    print(selected_voice_name)

    # Get the voice_id corresponding to the selected voice name
    voice_id = None
    for voice in self.voices_data:
        if voice["name"] == selected_voice_name:
            voice_id = voice["voice_id"]
            print(voice_id)
            break

    # Extract the stability and clarity values from the slider settings
    stability = float(self.stability_val.cget("text").replace("%", "")) / 100
    similarity_boost = float(
        self.clarity_val.cget("text").replace("%", "")) / 100

    # Create the request body
    request_body = {
        "text": text,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost
        }
    }

    # Send the API request
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY,
               "Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=request_body)

    if response.status_code == 200:
        # Handle the response (e.g., play the audio, display a message, etc.)
        update_quota(ELEVENLABS_API_KEY, right_button)
        print("Text-to-speech generation successful")
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(response.content)
            temp_file_path = f.name
        audio_data, samplerate = sf.read(temp_file_path)
        sd.play(audio_data, samplerate)
        sd.wait()  # Wait for the audio to finish playing
    else:
        print("Error generating text-to-speech")
    progressbar.stop()
    progressbar.pack_forget()


def generate_async(self, ELEVENLABS_API_KEY, right_button, progressbar, generate_button):
    threading.Thread(target=generate_event, args=(self,
                                                  ELEVENLABS_API_KEY, right_button, progressbar, generate_button)).start()

# Function that converts an input (in seconds) to "hours : minutes : seconds"


def convert(seconds):
    minutes = seconds // 60
    seconds %= 60

    return "%d:%02d" % (minutes, seconds)


def get_history_audio(self, history_item_id):
    url = f"https://api.elevenlabs.io/v1/history/{history_item_id}/audio"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print("good response")
        audio_data = response.content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_file:
            temp_audio_file.write(audio_data)
            self.temp_audio_file_name = temp_audio_file.name

        self.audio_file = sf.SoundFile(self.temp_audio_file_name)
        self.samplerate = self.audio_file.samplerate
        self.audio_length = len(self.audio_file) / self.samplerate
        self.audio_end_pos.configure(text=convert(self.audio_length))

    else:
        print("Error with history audio")

def play_temp_audio(self):
    if not self.temp_audio_file_name:
        print("No audio file selected!")
        return

    if self.stream and self.stream.active:
        stop_audio(self)
    elif self.temp_audio_file_name:
        # Reset flags
        self.audio_data_played = 0
        self.audio_playback_finished = False

        data, samplerate = sf.read(self.temp_audio_file_name)
        self.audio_data = data.T.copy(order='C')
        self.samplerate = samplerate

        # Create and start a new output stream
        self.stream = sd.OutputStream(
            samplerate=samplerate, channels=2, callback=self.audio_callback, blocksize=2048)
        self.stream.start()

        self.status.set("Playing")
        self.boolean_switch("play")
        self.play_button_check()

        # Start updating the audio position
        self.update_audio_pos()
    elif self.is_paused:
        self.resume_audio()
    elif self.is_playing:
        self.pause_audio()
    else:
        print("No temp audio file available")


def play_audio(self):
    if self.temp_audio_file_name:
        if self.is_playing:
            pause_audio(self)
        elif self.is_paused:
            resume_audio(self)
        else:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = samplerate

            data, samplerate = sf.read(self.temp_audio_file_name)
            self.audio_data = data.T.copy(order='C')
            self.audio_data_played = 0
            self.samplerate = samplerate

            sd.play(data, samplerate)
            self.status.set("Playing")
            self.boolean_switch("play")
            self.play_button_check()
            self.update_audio_pos()

            try:
                x = threading.Thread(target=self.update_audio_pos, daemon=True)
                x.start()
            except Exception as e:
                print("\n[DEBUG]", e)

            def monitor_playback():
                while not self.audio_playback_finished:
                    time.sleep(0.1)
                self.stop_and_unload_audio()

            self.audio_playback_finished = False
            playback_monitor_thread = threading.Thread(
                target=monitor_playback, daemon=True)
            playback_monitor_thread.start()
    else:
        print("No audio file loaded")


def update_play_status(self):
    if self.stream and self.stream.active:
        self.is_playing = True
    else:
        self.is_playing = False


def pause_audio(self):
    if self.stream:
        self.stream.stop()
        self.status.set("Paused")
        self.boolean_switch("pause")
        self.play_button_check()


def resume_audio(self):
    if self.is_paused:
        # Resume the audio stream
        self.stream.start()

        self.status.set("Playing")
        self.boolean_switch("play")
        self.play_button_check()


def stop_audio(self):
    self.stream.stop()
    self.stream.close()
    self.stream = None
    self.current_audio.set("")  # Updates "actual_audio_lbl"
    self.audio_curr_pos.configure(text="0:00")
    # self.audio_end_pos.configure(text="0:00")  # Resetting the GUI
    self.audio_pos_slider.set(0)  # Resetting the GUI
    self.new_audio_position = 0
    self.boolean_switch("stop")
    self.play_button_check()
    update_play_status(self)

def stop_and_unload_audio(self):
    if hasattr(sd, '_stream') and sd.get_stream().active:
        sd.stop()
        time.sleep(1)  # Give it a second to fully stop
        sd.close()
    # Remove the temporary audio file if it exists
    if self.temp_audio_file_name:
        try:
            os.remove(self.temp_audio_file_name)
            self.temp_audio_file_name = None
        except PermissionError:
            print(f"Unable to delete file: {self.temp_audio_file_name}. It might still be in use.")
    self.audio_curr_pos.configure(text="0:00")
    self.audio_end_pos.configure(text=convert(self.audio_length))  # Resetting the GUI
    self.audio_pos_slider.set(0)  # Resetting the GUI
    self.new_audio_position = 0
    self.status.set("Stopped")
    self.boolean_switch("stop")
    self.play_button_check()
