
# RFP Bot

An intelligent Request for Proposal (RFP) bot built with Python.

---

## Table of Contents
- [Features](#features)
- [Getting Started](#getting-started)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

---

## Features
- Automated RFP processing
- Easy setup and configuration
- Cross-platform support (Windows, macOS)

---

## Getting Started

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd rfp
```

### 2. Create a Virtual Environment

#### Windows (Command Prompt)
```cmd
python -m venv .env
.env\Scripts\activate
```

#### Windows (Git Bash)
```bash
python -m venv .env
source .env/Scripts/activate
```

#### macOS/Linux
```bash
python3 -m venv .env
source .env/bin/activate
```

---

## Installation

Install the required Python packages:

```bash
pip install -r requirements.txt
```

---

## Configuration

1. Create a `.env.development` file in the project root.
2. Add your API keys and bot token:

	```env
	API_KEY=your_api_key_here
	BOT_TOKEN=your_bot_token_here
	```

---

## Usage

To start the bot:

#### Windows
```cmd
python bot.py
```

#### macOS/Linux
```bash
python3 bot.py
```

---

## Contributing
Contributions are welcome! Please open issues or submit pull requests for improvements.

---

## License
This project is licensed under the MIT License.