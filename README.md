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
    <a href="https://github.com/adamelsaeed-afk/Engaz"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/adamelsaeed-afk/Engaz/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/adamelsaeed-afk/Engaz/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>

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
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

<!-- ABOUT THE PROJECT -->
## About The Project

**Engaz (إنجاز)** is a modern desktop legal management system built to streamline workflows for law firms, solo practitioners, and clients. Featuring a rich dark/light UI powered by PySide6 (Qt for Python), Engaz unifies case tracking, client-lawyer communication, conflict-free appointment scheduling, invoice generation, and stakeholder analytics in one desktop application.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

This project is built using Python and modern GUI libraries:

* [![Python][Python-shield]][Python-url]
* [![Qt][Qt-shield]][Qt-url]
* [![Matplotlib][Matplotlib-shield]][Matplotlib-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Key Features

* 🧑‍⚖️ **Multi-Role Dashboards**: Custom viewports tailored for Admins, Lawyers, and Clients.
* 📁 **Case & File Management**: Comprehensive case lifecycle tracking, status tags, document metadata, and file references.
* 📅 **Calendar & Appointment Scheduler**: Intelligent meeting scheduling, court date tracking, and automated conflict detection.
* 💳 **Billing & Invoicing System**: Automatic billing calculations, hourly rate caps, invoice generation, and payment status tracking.
* 💬 **Client-Lawyer Messaging**: Integrated secure direct messaging channel between clients and their assigned attorneys.
* 📚 **Legal Reference Library**: Searchable law books, legal statutes, and case law reference repository.
* 📊 **Analytics & Performance Reports**: Graphical charts for revenue, case distribution, and lawyer performance metrics.

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
5. Launch the application:
   ```sh
   python engaz.py
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE EXAMPLES -->
## Usage

After launching the app with `python engaz.py`, you will be greeted by the Engaz login screen. You can log in using any of the built-in demo accounts below:

### Demo Accounts

| Role | Username | Password | Key Features Accessible |
| :--- | :--- | :--- | :--- |
| 🧑‍⚖️ **Lawyer** | `sarah.jenkins` | `lawyer123` | Case tracking, billing, calendar scheduling, messaging |
| 👤 **Client** | `john.doe` | `client123` | Personal cases, appointment booking, invoice payments |
| 📊 **Stakeholder / Admin** | `ahmad.al-rashid` | `stakeholder123` | Firm analytics, revenue reports, metric preferences |

> [!NOTE]
> All application state is stored locally in `engaz_data.json` and automatically saved when actions are performed.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ROADMAP -->
## Roadmap

- [ ] Migration to full SQLite database backend
- [ ] AI-assisted legal document parsing and summarization
- [ ] Real-time WebSocket notifications for client-lawyer chat
- [ ] Multi-language support (Arabic & English UI toggle)
- [ ] Export invoices directly to native PDF documents

See the [open issues](https://github.com/adamelsaeed-afk/Engaz/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

Contributions make the open-source community an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

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

<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [Best-README-Template by othneildrew](https://github.com/othneildrew/Best-README-Template)
* [PySide6 (Qt for Python)](https://doc.qt.io/qtforpython-6/)
* [Matplotlib Data Visualization](https://matplotlib.org/)
* [Seaborn Visualization Library](https://seaborn.pydata.org/)
* [ReportLab PDF Toolkit](https://www.reportlab.com/)

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
