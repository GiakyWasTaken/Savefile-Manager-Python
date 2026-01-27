# 🎮 Savefile Manager Python

This repository contains a collection of Python scripts designed to automate the management of local savefiles by interacting with a remote API. It supports full CRUD operations on both savefiles and consoles.

Originally developed in Bash, the system was completely rewritten in Python to enhance flexibility, maintainability, and scalability. These scripts were built from scratch during an internship in Maribor, Slovenia, with no prior Laravel experience, and were fully developed, tested, and deployed in under a month.

## 🚀 Features

- **Savefile Management**: Upload, download, update, and delete local or remote savefiles.
- **Console Management**: Register and manage console configurations.
- **Crawling Modes**: Flexible crawling/downloading logic: `AUTO`, `FORCE`, `UPDATE`, and others.
- **Authentication**: Full login/logout/session management.
- **Logging**: Detailed logs for monitoring and debugging.

## 📦 Requirements

- Python 3.8 or higher
- Install dependencies with:

  ```bash
  pip install -r requirements.txt
  ```

### Dependencies

- `requests`
- `python-dotenv`
- `colorama`

## ⚙️ Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/GiakyWasTaken/Savefile-Manager-Python.git
   cd Savefile-Manager-Python
   ```

2. Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure the environment variables:
   - Copy `.env.example` to `.env`:

     ```bash
     cp .env.example .env
     ```

   - Edit `.env` with your values:
     - `API_URL`: Base URL of the backend API
     - `EMAIL`: Your login email
     - `PASSWORD`: Your password
     - `CONSOLE_NAMES`: List of console names to manage
     - `SAVES_PATHS`: Corresponding savefile paths

## ▶️ Usage

Run the main script:

```bash
python main.py
```

### Command-line Options

```bash
python main.py -c auto -d update
```

- `-c`, `--crawl`: Crawling mode
- `-d`, `--download`: Download mode

### Modes Reference

| Code | Mode    | Description                                                  |
|------|---------|--------------------------------------------------------------|
| `u`  | update  | Syncs files only if remote is newer                          |
| `f`  | force   | Forces overwrite of all files regardless of timestamps       |
| `n`  | new     | Downloads/uploads only files that are not present locally    |
| `a`  | auto    | Automatically chooses the appropriate action per file        |
| `l`  | all     | Processes everything without any filtering                   |

## 🔐 Environment Variables

These are configured in the `.env` file:

| Variable        | Description                   |
|-----------------|-------------------------------|
| `API_URL`       | Base URL of the API server    |
| `EMAIL`         | Email used for login          |
| `PASSWORD`      | Password used for login       |
| `CONSOLE_NAMES` | List of consoles to manage    |
| `SAVES_PATHS`   | Local paths to your savefiles |

## 📝 Logs

Logs are stored in the `log/` directory and automatically cleaned up after 7 days.

## 🌐 Backend

Looking for scripts to interact with these scripts? Check out the companion repo:

👉 [GiakyWasTaken/Savefile-Manager](https://github.com/GiakyWasTaken/Savefile-Manager)

---
