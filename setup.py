from setuptools import setup

setup(
    name='ElevenGUI',
    version='1.0.0',
    description='A GUI application for interacting with ElevenLabs API with added speech-to-text functionality using OpenAI\'s Whisper.',
    url='https://github.com/winedarkmoon/ElevenGUI',
    author='winedarkmoon',
    license='MIT',
    install_requires=[
        'certifi==2023.5.7',
        'cffi==1.15.1',
        'charset-normalizer==3.1.0',
        'customtkinter==5.1.3',
        'darkdetect==0.8.0',
        'idna==3.4',
        'numpy==1.24.3',
        'Pillow==9.5.0',
        'pycparser==2.21',
        'python-dotenv==1.0.0',
        'requests==2.31.0',
        'sounddevice==0.4.6',
        'soundfile==0.12.1',
        'urllib3==2.0.2',
    ],
    extras_require={
        'whisper_api':  ['openai'],
        'whisper_local': ['whisper'],
    },
)
