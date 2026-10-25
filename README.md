# MyCSU Project

## Project Overview

MyCSU is a student-facing website prototype intended to bring together student information, class schedules, orientation tasks, notifications, and a digital student ID interface.

The project aims to demonstrate how these features could be integrated into a unified student experience. It is a prototype, so features that require access to Cleveland State University's internal systems, authentication services, or ID hardware may be simulated rather than fully integrated.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Main programming language for application logic and server-side operations |
| Flask | Python web framework that handles website routes, requests, and page rendering |
| HTML | Defines the structure and content of each website page |
| CSS | Controls the website's visual appearance and layout |
| SQLite | Lightweight relational database for storing and retrieving application data |
| SQL | Language used to create database tables and retrieve, add, update, or delete records |
| Git | Tracks changes to the project's files |
| GitHub | Hosts the shared repository so team members can collaborate |
| VS Code | Code editor used to develop and test the application |

## Project Structure

The following describes the intended project structure. Files may be added or modified as development progresses.

```text
mycsu-project/
│
├── app.py
│
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── checklist.html
│   ├── schedule.html
│   ├── digital_id.html
│   └── admin.html
│
├── static/
│   └── style.css
│
├── database/
│   ├── schema.sql
│   ├── db.py
│   └── mycsu.db
│
├── requirements.txt
├── .gitignore
└── README.md
```

### Main Application

**`app.py`**

The main Flask application. It defines the website's routes and connects browser requests to the appropriate Python functions and HTML templates. It also handles form submissions and coordinates with the database when necessary.

### HTML Templates

The `templates/` folder contains the HTML files used to render the website's pages.

- **`base.html`** — Shared layout containing elements such as navigation and common page structure. Other pages can extend this template to maintain a consistent design.
- **`login.html`** — Sign-in interface. Authentication may use a demonstration login unless approved integration with CSU authentication becomes available.
- **`dashboard.html`** — Main landing page with navigation to the website's features.
- **`checklist.html`** — Displays orientation tasks and allows users to view or update completion status.
- **`schedule.html`** — Displays sample or stored class schedule information.
- **`digital_id.html`** — Displays a mock digital student ID. Real campus credential and NFC integration are outside the prototype unless separately approved and implemented.
- **`admin.html`** — Administrative interface for managing orientation tasks, if included in the final scope.

### Static Files

**`static/style.css`**

Contains the CSS used to style the website, including colors, fonts, navigation, buttons, spacing, and page layouts. A shared stylesheet helps maintain a consistent appearance across all pages.

### Database

The `database/` folder contains the files used to define and interact with the SQLite database.

- **`schema.sql`** — Contains SQL statements defining the database tables and their structure.
- **`db.py`** — Contains Python functions for connecting to SQLite and performing database operations.
- **`mycsu.db`** — The SQLite database file containing tables and stored records. It may be created during database initialization rather than manually.

The database may store information such as orientation tasks and their completion status. Sample data should be used unless access to real CSU data has been authorized.

### Project Configuration

- **`requirements.txt`** — Lists the Python packages required to run the application.
- **`.gitignore`** — Identifies files and folders Git should ignore, such as virtual environments, generated cache files, and local secrets.
- **`README.md`** — Documents the project, setup instructions, file structure, and development workflow.

## How the Components Work Together

The application follows a simple client-server architecture.

1. A user opens the website in a browser.
2. The browser sends a request to the Flask application.
3. Flask, running through `app.py`, identifies the requested route and executes the relevant Python function.
4. If information must be retrieved or saved, the Python code uses the database helpers in `db.py` to interact with SQLite. SQL statements define the operations performed on the database.
5. Flask passes the required information to an HTML template in `templates/`.
6. The browser displays the rendered page, styled using `static/style.css`.

Not every page requires a database. Some pages may initially use sample or hardcoded data while the database-dependent features are being developed.

## Installation and Setup

### Prerequisites

Install the following software:

- Python 3
- Git
- Visual Studio Code
- A web browser

A separate SQLite installation is not required for the application because Python includes the `sqlite3` module. A database viewer is optional.

### 1. Clone the Repository

Open a terminal and run:

```bash
git clone <repository-url>
cd mycsu-project
```

Replace `<repository-url>` with the repository's actual GitHub URL.

### 2. Create a Virtual Environment

A virtual environment isolates the Python packages used by this project from other Python projects.

On Windows using PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On Windows using Command Prompt:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
```

### 3. Install Dependencies

With the virtual environment activated, run:

```bash
python -m pip install -r requirements.txt
```

### 4. Initialize the Database

Once the database implementation is complete, follow the project's database initialization instructions. The schema must be applied to create the required tables, and any required demonstration data must be loaded.

Do not assume the database already exists or contains initialized tables after cloning the repository.

### 5. Run the Application

From the project root, run:

```bash
python app.py
```

Open the local address printed by Flask in your browser. During development, this is typically:

`http://127.0.0.1:5000`

The development server is intended for local testing, not public production deployment.

## Development and Collaboration

- Pull the latest changes before beginning work.
- Create a branch when developing a substantial feature.
- Keep changes focused on the assigned feature.
- Test changes locally before submitting them.
- Commit and push completed work to GitHub.
- Review and integrate changes before merging them into the main branch.
- Coordinate changes to shared files, particularly `app.py`, `base.html`, and `style.css`.
- Update this README when setup instructions, dependencies, or the project structure change.

## Project Limitations

This project is a prototype. Real CSU single sign-on, live student schedules, official student records, production notifications, and physical NFC credentials require appropriate data access, authorization, and technical integration.

Any feature that is simulated should be clearly identified as such during the demonstration.

## Current Development Status

The application structure and functionality will be completed incrementally. Refer to the team's task assignments and project documentation for the current implementation status and outstanding work.

