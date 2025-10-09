# UniBot

**UniBot** is a Telegram bot designed to automate and simplify the course registration (unit selection) process for students at the University of Tabriz. The bot interacts with the university's official education portal on behalf of the student, submitting registration or removal requests for courses and providing real-time feedback through Telegram.

---

## Features

- **Student Information Management:** Register and update your student number and term.
- **Automated Course Selection:** Add or remove courses by entering course and group codes.
- **Session Management:** Authenticate using your browser cookie for secure operations.
- **Queue-based Messaging:** All bot responses are queued and delivered instantly.
- **Admin Panel:** Admins can broadcast messages to all users and manage the bot.
- **Feedback System:** Users can submit feedback or complaints directly to admins.
- **Database Integration:** Student and payment information is stored in a PostgreSQL database.
- **Operation Cancellation:** Users can cancel ongoing operations at any time.
- **Subscription & Payment:** Handles subscription payments and discount codes.

---

## How It Works

1. **User Registration:**  
   The user enters their student number and selects the current term.
2. **Course Selection:**  
   The user provides the course code and group number for each course to add or remove.
3. **Authentication:**  
   The user copies their browser cookie from the university portal and submits it to the bot.
4. **Automated Requests:**  
   The bot sends registration/removal requests to the university system, handling retries and errors.
5. **Feedback:**  
   The bot analyzes server responses and notifies the user of the result for each course.
6. **Database Logging:**  
   Student info and payment status are stored for future reference and admin management.

---

## Project Structure

```
UniBot/
│
├── bot.py                  # Main entry point for the Telegram bot
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (database credentials)
├── LICENSE                 # MIT License
├── README.md               # This file
│
├── tel_bot/                # Telegram bot logic and handlers
│   ├── handlers.py
│   ├── keyboard.py
│   ├── message_queue.py
│   └── config.py
│
├── main/                   # Core logic for unit selection and HTTP requests
│   ├── main.py
│   ├── network_module.py
│   ├── response_checker.py
│   ├── extract_data.py
│   └── logic_module.py
│
├── db/                     # Database models and utilities
│   ├── db.py
│   ├── models.py
│   └── save_to_db.py
│
└── .github/
    └── workflows/
        └── deploy.yml      # GitHub Actions deployment workflow
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **PostgreSQL** (for database)
- **git** (optional, for cloning)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/UniBot.git
   cd UniBot
   ```

2. **Create and activate a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   - Copy `.env` and set your PostgreSQL credentials:
     ```
     DB_HOST=localhost
     DB_PORT=5432
     DB_NAME=unibot_db
     DB_USER=unibot_user
     DB_PASS=***
     ```

5. **Set up the PostgreSQL database:**
   ```sql
   CREATE DATABASE unibot_db;
   CREATE USER unibot_user WITH PASSWORD '***';
   GRANT ALL PRIVILEGES ON DATABASE unibot_db TO unibot_user;
   ```

6. **Run the bot:**
   ```bash
   python bot.py
   ```

---

## Usage

- **Start the bot:**  
  Send `/start` in Telegram to the bot.
- **Register student info:**  
  Use the menu to enter your student number and select the term.
- **Select or remove courses:**  
  Enter course and group codes as prompted.
- **Submit your browser cookie:**  
  Copy the cookie from your browser (while logged in to the university portal) and paste it into the bot.
- **Monitor progress:**  
  The bot will notify you of each operation's result and any errors.
- **Cancel operations:**  
  Use the "Cancel" button at any time to stop ongoing processes.
- **Admin features:**  
  Admins can broadcast messages and manage users via the admin menu.

---

## Deployment (CI/CD)

The bot is configured for automatic deployment using GitHub Actions.  
On every push to the `main` branch, the workflow in `.github/workflows/deploy.yml` will:

- SSH into your server
- Pull the latest code
- Install dependencies
- Restart the bot service

---

## Security Notes

- **Never share your Telegram bot token or database credentials publicly.**
- **User cookies are used only for the current operation and are not stored.**
- **All sensitive information should be kept in the `.env` file and not committed to version control.**

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## 🧑‍💻 Contribution

If you have suggestions or encounter an issue, please open a new Issue or submit a Pull Request.

---

## 📞 Contact

For questions or support, you can reach out via [GitHub Issues](https://github.com/ahamxdev/backup-telebot/issues) or directly contact the maintainer.

---

## 👤 Author

**Name:** AmirHossein AliMohammadi
**GitHub:** [github.com/ahamxdev](https://github.com/ahamxdev)

Good luck! 🚀
