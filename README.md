<!-- Improved compatibility header image formatting -->
<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <h1 align="center">⚖️ Engaz (إنجاز)</h1>

  <p align="center">
    An all-in-one, role-based desktop legal management & workflow platform for law firms and legal professionals.
    <br />
    <a href="PROJECT_SPECIFICATION.md"><strong>Explore Full Project Specification »</strong></a>
    <br />
    <br />
    <a href="https://github.com/adamelsaeed-afk/Engaz/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/adamelsaeed-afk/Engaz/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>

> [!WARNING]
> ### ⚠️ Demonstration System Notice & Important Disclaimers
> **Engaz is strictly a DEMO application created for proof-of-concept testing.**
> - 🔒 **Security was NOT taken into mind**: Passwords are stored in plain text in `engaz_data.json`, authentication and multi-factor OTP checks are client-side mocks, and file system attachments are accessed directly without access controls or sandboxing.
> - ⚡ **Atomicity was NOT taken into mind**: Database updates perform whole-file JSON rewrites (`json.dump`) without ACID transactions, database locks, or atomic rollback mechanisms. Concurrent writes or abrupt process crashes can lead to data loss or corruption.

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
        <li><a href="#key-features">Key Features</a></li>
      </ul>
    </li>
    <li><a href="#application-architecture--modules">Application Architecture & Modules</a></li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
        <li><a href="#running-the-application">Running The Application</a></li>
      </ul>
    </li>
    <li><a href="#demo-accounts">Demo Accounts</a></li>
    <li><a href="#data-persistence--schema">Data Persistence & Schema</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

**Engaz (إنجاز)** is a desktop legal management system engineered using Python and PySide6 (Qt for Python). It unifies case lifecycle tracking, client-attorney messaging, conflict-free appointment scheduling, invoice generation with hourly billing caps, searchable legal reference libraries, lawyer performance reporting, and executive firm analytics into a single role-based desktop application.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

This project is built using standard Python and modern desktop GUI libraries:

* [![Python][Python-shield]][Python-url]
* [![Qt][Qt-shield]][Qt-url]
* [![Matplotlib][Matplotlib-shield]][Matplotlib-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Key Features

* 🧑‍⚖️ **Multi-Role Dashboards**: Role-tailored dashboards for Lawyers, Clients, and Firm Stakeholders.
* 📁 **Case & File Management**: Full case tracking, status tags (`Open`, `In Progress`, `Closed`), document metadata, file sharing toggles (`shared_with_client`), and native desktop file launching.
* 📅 **Calendar & Appointment Scheduler**: Interactive monthly schedule calendar, intelligent conflict detection preventing overlapping attorney slots, and lawyer approval/decline workflows.
* 💳 **Billing & Invoicing System**: Automatic billing calculations, hourly rate caps (`max_billable_hours`), tax/discount support, PDF export, and simulated client payment processing.
* 💬 **Client-Lawyer Messaging**: Direct messaging interface with optional case linking, unread badges, and overdue reply warning indicators (`⚠️`).
* 📚 **Legal Reference Library**: Searchable law books repository with attached discussion threads, inline page-specific comments, and PDF deep-linking fragment jumps (`#page=X`).
* 📊 **Lawyer Analytics & Reports**: Seaborn and Matplotlib visual analytics covering case trends, status breakdowns, and appointment stats with ReportLab PDF compilation.
* 📈 **Executive Stakeholder Dashboard**: Firm-wide dashboard with reorderable metric cards, customizable visibility controls, lawyer ranking charts, revenue metrics, and saved user preferences.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- APPLICATION ARCHITECTURE & MODULES -->
## Application Architecture & Modules

The Engaz codebase consists of 7 primary core modules:

| Module File | Primary Function & Responsibilities |
| :--- | :--- |
| 📄 [`engaz_constants.py`](file:///app/engaz_constants.py) | Shared design system color tokens, page routing index definitions, notification routing maps, status badges (`_status_badge`), and formatting utilities. |
| 📄 [`invoicesystem.py`](file:///app/invoicesystem.py) | Application entrypoint (`EngazApp`), `DataRepository` (JSON database manager), login screens, mock OTP dialog, application shell/navigation, case management, calendar scheduler, and invoicing engine. |
| 📄 [`case_files.py`](file:///app/case_files.py) | Case file attachment dialogs, document table views, lawyer file sharing controls (`shared_with_client`), notification triggers, and OS desktop file launch integration. |
| 📄 [`messaging.py`](file:///app/messaging.py) | Client-lawyer direct messaging dialogs, conversation list with unread counters, overdue reply thread alerts, message bubbles, and case contextual linking. |
| 📄 [`references.py`](file:///app/references.py) | Legal reference library view, PDF law book importer, book chat threads, page-indexed comment widgets, and PDF page fragment navigation. |
| 📄 [`lawyer_reports.py`](file:///app/lawyer_reports.py) | Individual lawyer performance reporting, Matplotlib/Seaborn charting panels, period filters (30/90/365 days, custom ranges), and single/multi-page PDF report generation. |
| 📄 [`stakeholder_dashboard.py`](file:///app/stakeholder_dashboard.py) | Executive firm-wide dashboard, firm closing rates, revenue trends, top lawyer rankings, active workload stats, drag-and-drop metric ordering, and metric toggle preferences. |

For exhaustive module breakdowns and data schema specifications, refer to [**`PROJECT_SPECIFICATION.md`**](file:///app/PROJECT_SPECIFICATION.md).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

Follow these instructions to get a local copy of Engaz up and running.

### Prerequisites

* **Python 3.9+** installed on your system. Verify installation with:
  ```sh
  python --version
  ```

### Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/adamelsaeed-afk/Engaz.git
   ```
2. Navigate to the project directory:
   ```sh
   cd Engaz
   ```
3. Create a virtual environment (optional but recommended):
   ```sh
   python -m venv venv
   ```
   * On Linux/macOS:
     ```sh
     source venv/bin/activate
     ```
   * On Windows:
     ```sh
     venv\Scripts\activate
     ```
4. Install the required Python packages:
   ```sh
   pip install PySide6 matplotlib seaborn reportlab
   ```

### Running The Application

Launch the desktop application using python with the main system file:
```sh
python invoicesystem.py
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- DEMO ACCOUNTS -->
## Demo Accounts

When starting the application, you can log in using any of the built-in demo credentials below:

| Role | Username | Password | Accessible Features & Dashboards |
| :--- | :--- | :--- | :--- |
| 🧑‍⚖️ **Lawyer** | `sarah.jenkins` | `lawyer123` | Case management, lawyer reports, client messaging, invoice creation, file sharing controls |
| 👤 **Client** | `john.doe` | `client123` | Personal cases view, appointment booking, invoice payments, shared case files, attorney chat |
| 📊 **Stakeholder / Admin** | `ahmad.al-rashid` | `stakeholder123` | Executive firm analytics, revenue charts, lawyer ranking metrics, dashboard preference customization |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- DATA PERSISTENCE & SCHEMA -->
## Data Persistence & Schema

All application state is stored locally in `engaz_data.json` and automatically saved when operations are performed. The database structure contains 10 primary entity collections:
- `users`: Account profiles, plain-text passwords, role designations, and dashboard preferences.
- `cases`: Legal case records, case numbers, client/lawyer mappings, types, and statuses.
- `appointments`: Booking requests, dates, time slots, statuses, and conflict validation records.
- `invoices`: Financial records, hourly rates, logged hours, billing caps, tax/discount rates, and payment statuses.
- `messages`: Direct chat messages exchanged between users with read states and case links.
- `notifications`: Application notifications mapped to target navigation pages.
- `case_files`: File attachment metadata, local OS file paths, and client sharing flags.
- `law_books`: Uploaded law book reference records saved in `law_books/`.
- `book_comments`: Page-indexed comments and research notes tied to specific law books.
- `book_chats`: Group discussion messages associated with reference books.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ROADMAP -->
## Roadmap

- [ ] Security hardening (password hashing with bcrypt/argon2, session tokens)
- [ ] Database migration to SQLite / PostgreSQL with ACID transaction guarantees
- [ ] AI-assisted legal document parsing and summarization
- [ ] Real-time WebSocket notifications for client-lawyer chat
- [ ] Multi-language support (Arabic & English UI toggle)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

Contributions are welcome! If you have suggestions or improvements:
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->
## Contact

Adam El-Saeed - [@adamelsaeed-afk](https://github.com/adamelsaeed-afk)

Project Link: [https://github.com/adamelsaeed-afk/Engaz](https://github.com/adamelsaeed-afk/Engaz)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/adamelsaeed-afk/Engaz.svg?style=for-the-badge
[contributors-url]: https://github.com/adamelsaeed-afk/Engaz/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/adamelsaeed-afk/Engaz.svg?style=for-the-badge
[forks-url]: https://github.com/adamelsaeed-afk/Engaz/network/members
[stars-shield]: https://img.shields.io/github/stars/adamelsaeed-afk/Engaz.svg?style=for-the-badge
[stars-url]: https://github.com/adamelsaeed-afk/Engaz/stargazers
[issues-shield]: https://img.shields.io/github/issues/adamelsaeed-afk/Engaz.svg?style=for-the-badge
[issues-url]: https://github.com/adamelsaeed-afk/Engaz/issues
[license-shield]: https://img.shields.io/github/license/adamelsaeed-afk/Engaz.svg?style=for-the-badge
[license-url]: https://github.com/adamelsaeed-afk/Engaz/blob/main/LICENSE
[Python-shield]: https://img.shields.io/badge/Python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54
[Python-url]: https://www.python.org/
[Qt-shield]: https://img.shields.io/badge/Qt-41CD52?style=for-the-badge&logo=qt&logoColor=white
[Qt-url]: https://doc.qt.io/qtforpython-6/
[Matplotlib-shield]: https://img.shields.io/badge/Matplotlib-11557c?style=for-the-badge&logo=python&logoColor=white
[Matplotlib-url]: https://matplotlib.org/
