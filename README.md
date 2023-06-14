# ElevenGUI

ElevenGUI is a graphical user interface for the ElevenLabs API. It can also utilize OpenAI's Whisper for speech-to-text transcription, if installed.
## Features

With ElevenGUI, you can:

- Interact with the ElevenLabs API in real-time
- Record or upload audio files for transcription via OpenAI's Whisper (optional)
- Convert text to audio using ElevenLabs
- View and play back your ElevenLabs sample history

## Installation


https://github.com/winedarkmoon/ElevenGUI/assets/127571479/266635fd-6b31-4dc7-a3c6-b829d540c4d1


Ensure you have Python 3.9 or higher installed. Creating a Python virtual environment before the installation is recommended.

To install the application, first clone the repository:

```bash
git clone https://github.com/winedarkmoon/ElevenGUI.git
```

Then navigate into the directory and install the package using pip:

```bash
cd ElevenGUI
pip install .

```
To use OpenAI's Whisper API or a local Whisper implementation for transcription, you can install the extras like this:

```bash
pip install .[whisper_api]
```
Or:

```bash
pip install .[whisper_local]
```
Or if you want both:

```bash
pip install .[whisper_api,whisper_local]
```
### For zsh users (default in macOS Catalina and later)

For zsh users, use quotation marks due to the way zsh handles square brackets:
```bash
pip install ".[whisper_api]"
```
```bash
pip install ".[whisper_local]"
```
Or if you want both:
```bash
pip install ".[whisper_api,whisper_local]"
```
### :construction: Important notes for Linux and macOS users :construction:
#### Tkinter Installation
**For Linux:** Make sure tkinter is installed for your Python environment. You can do this by installing the python3-tk package using your package manager. For example, if you're using Ubuntu, you can install it with:
```bash
sudo apt-get install python3-tk
```
**For macOS:** Install tkinter via Homebrew:
```bash
brew install python-tk@3.9
```
#### OpenSSL Issue (macOS only)
**If you encounter an error with urllib3:** You may need to install or update OpenSSL. Use Homebrew to install OpenSSL:
```bash
brew install openssl
```
If you've already installed OpenSSL but you're still encountering the error, reinstall Python linked with the Homebrew version of OpenSSL:

```bash
brew reinstall python
```
If the error persists, try installing an older version of `urllib3`:

```bash
pip3 install 'urllib3<2.0'
```

## Optional: Installing OpenAI's Whisper

If you plan on using a local installation of OpenAI's Whisper for transcribing audio to text, you'll need to set it up separately. Detailed installation instructions for Whisper can be found in the [official Whisper repository](https://github.com/openai/whisper). 

If you prefer to use OpenAI's Whisper API for transcriptions, you do not need a local installation. You can obtain an API key for this purpose from [OpenAI's API key page](https://platform.openai.com/account/api-keys).

## Configuration

This application uses environment variables for configuration. An example environment file is included in the repository as `env.example`.

1. Create a copy of the `env.example` file and rename this copy to `.env`.

2. Open the newly created `.env` file in a text editor.

3. The `env.example` file includes all the environmental variables the application needs, with placeholder values. Replace these placeholders with your actual values.

4. Save and close the `.env` file.

Ensure that the `.env` file is in the same directory as the main application file (`main.py`). When you run the application, it will automatically read the configuration from this file.

## Usage

Run the main.py script to start the application:

```bash
python main.py
```
## License

This project is licensed under the terms of the MIT license.


​
